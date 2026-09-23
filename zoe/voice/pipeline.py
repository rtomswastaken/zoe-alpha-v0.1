"""Complete local voice pipeline coordinating audio, wake-word, STT, agent reasoning, and TTS."""

import threading
import time
from typing import Optional
from zoe.agent.agent import ZoeAgent
from zoe.config import get_config
from zoe.macos.emergency import emergency_controller
from zoe.macos.logger import zoe_logger
from zoe.voice.audio import AudioRecorder
from zoe.voice.state import VoiceState, voice_state_manager
from zoe.voice.stt import get_stt, BaseSTT
from zoe.voice.tts import get_tts, BaseTTS
from zoe.voice.wake_word import get_wake_word_detector, BaseWakeWord


class VoicePipeline:
    """100% on-device continuous voice assistant pipeline for Zoe."""

    def __init__(
        self,
        agent: Optional[ZoeAgent] = None,
        stt: Optional[BaseSTT] = None,
        tts: Optional[BaseTTS] = None,
        wake_word: Optional[BaseWakeWord] = None,
    ) -> None:
        from zoe.ui.animation import get_animation_controller

        self.agent = agent or ZoeAgent()
        self.stt = stt or get_stt()
        self.tts = tts or get_tts()
        self.wake_word = wake_word or get_wake_word_detector()
        self.recorder = AudioRecorder(sample_rate=16000)
        self.anim_controller = get_animation_controller()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Link live microphone audio metrics directly to the notch UI
        self.recorder.add_callback(self._on_audio_chunk)

    def _on_audio_chunk(self, chunk, rms: float, pitch: float) -> None:
        if voice_state_manager.current_state in (VoiceState.LISTENING, VoiceState.SPEAKING):
            self.anim_controller.set_audio_metrics(rms, pitch)

    def start(self) -> None:
        """Start the background voice listening pipeline."""
        with self._lock:
            if self._running:
                return
            self._running = True

            # Start audio recorder and animation controller
            self.recorder.start()
            self.anim_controller.start()
            voice_state_manager.set_state(VoiceState.IDLE)

            self._thread = threading.Thread(target=self._pipeline_loop, daemon=True)
            self._thread.start()
            zoe_logger.log_action("VOICE_PIPELINE_STARTED")

    def stop(self) -> None:
        """Halt the voice pipeline."""
        with self._lock:
            self._running = False

        self.tts.stop()
        self.recorder.stop()
        self.anim_controller.stop()
        voice_state_manager.set_state(VoiceState.IDLE)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        zoe_logger.log_action("VOICE_PIPELINE_STOPPED")

    def _pipeline_loop(self) -> None:
        """Main listening loop cycling IDLE -> LISTENING -> THINKING -> ACTING -> SPEAKING -> IDLE."""
        while self._running:
            # 1. State: IDLE - Monitor for wake word or voice activation
            if emergency_controller.is_stopped():
                time.sleep(0.1)
                continue

            time.sleep(0.08)
            # Check recent 1.5s audio buffer for 'Zoe'
            recent_audio = self.recorder.get_recent_audio(1.5)
            if len(recent_audio) == 0:
                continue

            if self.wake_word.check_audio(recent_audio, sample_rate=16000):
                self._handle_wake_cycle()

    def _handle_wake_cycle(self) -> None:
        """Handle execution cycle triggered by wake word."""
        # 1. Check if user already spoke their command in the same breath (e.g. "Zoe open Safari")
        extracted = getattr(self.wake_word, "extracted_command", "").strip()

        if extracted and len(extracted.split()) >= 1 and extracted.lower() not in ("zoe", "hey"):
            clean_text = extracted
            zoe_logger.log_action("VOICE_COMMAND_IMMEDIATE", command=clean_text)
            # Brief visual pulse acknowledging wake word before acting
            voice_state_manager.set_state(VoiceState.LISTENING)
            time.sleep(0.3)
            voice_state_manager.set_state(VoiceState.THINKING)
            time.sleep(0.15)
        else:
            # 2. Transition State: LISTENING with voice-reactive amplitude on notch glow
            voice_state_manager.set_state(VoiceState.LISTENING)
            zoe_logger.log_action("VOICE_LISTENING_PHRASE")

            speech = self.recorder.record_until_silence(
                silence_timeout=1.2,
                max_duration=12.0,
                energy_threshold=0.0015,
                on_amplitude=lambda amp: self.anim_controller.set_audio_metrics(amp),
                is_interrupted=lambda: emergency_controller.is_stopped() or not self._running,
            )

            if emergency_controller.is_stopped() or not self._running:
                voice_state_manager.set_state(VoiceState.IDLE)
                return

            # 3. Transition State: THINKING (Local STT)
            voice_state_manager.set_state(VoiceState.THINKING)
            try:
                transcription = self.stt.transcribe(speech, sample_rate=16000, vad_filter=True)
            except TypeError:
                transcription = self.stt.transcribe(speech, sample_rate=16000)
            clean_text = transcription.strip()

        # Filter out accidental triggers / empty input
        if not clean_text or clean_text.lower() in ("zoe", "zoe.", "hey zoe"):
            voice_state_manager.set_state(VoiceState.IDLE)
            return

        # Handle explicit voice interruption command
        if clean_text.lower() in ("stop", "zoe stop", "stop.", "cancel"):
            emergency_controller.trigger_stop("Voice stop command")
            self.tts.stop()
            voice_state_manager.set_state(VoiceState.IDLE)
            print("\n[Voice Stop Triggered]")
            return

        print(f"\n[Voice Command: \"{clean_text}\"]")

        # 4. Transition State: ACTING (Run Agent / Tools / Vision)
        voice_state_manager.set_state(VoiceState.ACTING)
        zoe_logger.log_action("VOICE_DISPATCH_AGENT", command=clean_text)

        agent_state = self.agent.run_task(clean_text)

        if emergency_controller.is_stopped() or not self._running:
            voice_state_manager.set_state(VoiceState.IDLE)
            return

        response_text = agent_state.final_response
        if not response_text:
            response_text = "Task completed."

        # 5. Transition State: SPEAKING (Local TTS with voice-reactive notch)
        voice_state_manager.set_state(VoiceState.SPEAKING)
        zoe_logger.log_action("VOICE_SPEAKING_RESPONSE", text=response_text[:60])

        print(f"Zoe: {response_text}\n")
        self.tts.speak(
            response_text,
            wait=True,
            on_amplitude=lambda amp: self.anim_controller.set_audio_metrics(amp),
        )

        # 6. Return State: IDLE
        self.anim_controller.set_audio_metrics(0.0)
        voice_state_manager.set_state(VoiceState.IDLE)

    def process_command(self, command: str, speak: bool = True) -> str:
        """Process a text command through the voice state pipeline (useful for testing and CLI)."""
        clean_text = command.strip()
        if not clean_text:
            return ""

        if clean_text.lower() in ("stop", "zoe stop", "stop.", "cancel"):
            emergency_controller.trigger_stop("Voice stop command")
            self.tts.stop()
            voice_state_manager.set_state(VoiceState.IDLE)
            return "Stopped."

        # THINKING -> ACTING
        voice_state_manager.set_state(VoiceState.THINKING)
        time.sleep(0.1)
        voice_state_manager.set_state(VoiceState.ACTING)
        zoe_logger.log_action("VOICE_DISPATCH_AGENT", command=clean_text)

        agent_state = self.agent.run_task(clean_text)

        if emergency_controller.is_stopped():
            voice_state_manager.set_state(VoiceState.IDLE)
            return "Interrupted."

        response_text = agent_state.final_response or "Task completed."

        if speak:
            voice_state_manager.set_state(VoiceState.SPEAKING)
            zoe_logger.log_action("VOICE_SPEAKING_RESPONSE", text=response_text[:60])
            self.tts.speak(
                response_text,
                wait=True,
                on_amplitude=lambda amp: self.anim_controller.set_audio_metrics(amp),
            )

        voice_state_manager.set_state(VoiceState.IDLE)
        return response_text


_voice_pipeline_instance: Optional[VoicePipeline] = None


def get_voice_pipeline() -> VoicePipeline:
    """Singleton getter for the Zoe Voice Pipeline."""
    global _voice_pipeline_instance
    if _voice_pipeline_instance is None:
        _voice_pipeline_instance = VoicePipeline()
    return _voice_pipeline_instance
