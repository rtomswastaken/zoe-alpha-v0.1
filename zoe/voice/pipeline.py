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
        from zoe.ui.terminal import get_terminal_indicator

        self.agent = agent or ZoeAgent()
        self.stt = stt or get_stt()
        self.tts = tts or get_tts()
        self.wake_word = wake_word or get_wake_word_detector()
        self.recorder = AudioRecorder(sample_rate=16000)
        self.anim_controller = get_animation_controller()
        self.terminal_indicator = get_terminal_indicator()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Link live microphone audio metrics directly to the notch UI
        self.recorder.add_callback(self._on_audio_chunk)

    def _on_audio_chunk(self, chunk, rms: float, pitch: float) -> None:
        if voice_state_manager.current_state in (VoiceState.LISTENING, VoiceState.SPEAKING, VoiceState.RESPONDING):
            self.anim_controller.set_audio_metrics(rms, pitch)

    def start(self) -> None:
        """Start the background voice listening pipeline."""
        with self._lock:
            if self._running:
                return
            self._running = True

            # Start audio recorder, animation controller, and terminal indicator
            self.recorder.start()
            self.anim_controller.start()
            self.terminal_indicator.start()

            # Pre-warm STT model in background so first wake-word check is instant
            if hasattr(self.stt, "_ensure_model"):
                threading.Thread(target=self.stt._ensure_model, daemon=True).start()

            # Trigger welcome bloom on program start, then settle into ambient IDLE
            voice_state_manager.set_temporary_state(VoiceState.STARTUP, duration=1.4, return_state=VoiceState.IDLE)

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
        self.terminal_indicator.stop()
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

            time.sleep(0.1)
            # Check recent 2.0s audio buffer for 'Zoe'
            recent_audio = self.recorder.get_recent_audio(2.0)
            if len(recent_audio) == 0:
                continue

            if self.wake_word.check_audio(recent_audio, sample_rate=16000):
                self._handle_wake_cycle()

    def _handle_wake_cycle(self) -> None:
        """
        Handle full voice cycle triggered by wake word:
        IDLE -> WAKE_WORD_DETECTED -> LISTENING -> COMMAND_CAPTURE -> FINAL_TRANSCRIPT
        -> THINKING -> ACTING -> RESPONDING -> SUCCESS -> IDLE.
        """
        # 1. Check if user already spoke their command in the same breath (e.g. "Zoe open Safari")
        extracted = getattr(self.wake_word, "extracted_command", "").strip()

        if extracted and len(extracted.split()) >= 1 and extracted.lower() not in ("zoe", "hey"):
            clean_text = extracted
            print(f"[COMMAND_CAPTURE_FINISHED command=\"{clean_text}\"]")
            zoe_logger.log_action("COMMAND_CAPTURE_FINISHED", length=len(clean_text))
            # Brief visual pulse in LISTENING acknowledging wake word before acting
            voice_state_manager.set_state(VoiceState.LISTENING)
            time.sleep(0.25)
            voice_state_manager.set_state(VoiceState.THINKING)
            time.sleep(0.15)
        else:
            # 2. User spoke only 'Zoe': enter LISTENING and capture the subsequent command
            voice_state_manager.set_state(VoiceState.LISTENING)
            print("[COMMAND_CAPTURE_STARTED mode=\"listening_for_utterance\"]")
            zoe_logger.log_action("COMMAND_CAPTURE_STARTED")

            speech = self.recorder.record_until_silence(
                silence_timeout=1.1,
                initial_timeout=4.5,
                max_duration=12.0,
                energy_threshold=0.070,
                on_amplitude=lambda amp: self.anim_controller.set_audio_metrics(amp),
                is_interrupted=lambda: emergency_controller.is_stopped() or not self._running,
            )

            print("[COMMAND_CAPTURE_FINISHED]")
            zoe_logger.log_action("COMMAND_CAPTURE_FINISHED")

            if emergency_controller.is_stopped() or not self._running:
                voice_state_manager.set_state(VoiceState.IDLE)
                return

            if len(speech) == 0:
                # User did not speak a command after saying 'Zoe'
                voice_state_manager.set_state(VoiceState.IDLE)
                return

            # 3. Transition State: THINKING (Full utterance STT)
            voice_state_manager.set_state(VoiceState.THINKING)
            try:
                transcription = self.stt.transcribe(speech, sample_rate=16000, vad_filter=True, partial=False)
            except TypeError:
                transcription = self.stt.transcribe(speech, sample_rate=16000)

            clean_text = transcription.strip()
            print(f"[FINAL_TRANSCRIPT text=\"{clean_text}\"]")

        # Filter out accidental triggers / empty input
        if not clean_text or clean_text.lower() in ("zoe", "zoe.", "hey zoe"):
            voice_state_manager.set_state(VoiceState.IDLE)
            return

        # Handle explicit voice interruption command
        if clean_text.lower() in ("stop", "zoe stop", "stop.", "cancel", "abort", "halt"):
            print("\n[Voice Stop Triggered]")
            emergency_controller.trigger_stop("Voice stop command")
            self.tts.stop()
            voice_state_manager.set_state(VoiceState.STOPPING)
            time.sleep(0.3)
            voice_state_manager.set_state(VoiceState.IDLE)
            return

        print(f"\n[Voice Command: \"{clean_text}\"]")
        print(f"[COMMAND_DISPATCH_CALLED command=\"{clean_text}\"]")

        # 4. Transition State: ACTING (Run Agent / Tools / Vision)
        voice_state_manager.set_state(VoiceState.ACTING)
        print(f"[AGENT_INVOCATION command=\"{clean_text}\"]")
        zoe_logger.log_action("VOICE_DISPATCH_AGENT", length=len(clean_text))

        agent_state = self.agent.run_task(clean_text)

        if emergency_controller.is_stopped() or not self._running:
            voice_state_manager.set_state(VoiceState.STOPPING)
            time.sleep(0.15)
            voice_state_manager.set_state(VoiceState.IDLE)
            return

        response_text = agent_state.final_response
        if not response_text:
            response_text = "Task completed."

        # 5. Transition State: RESPONDING (Local TTS with voice-reactive notch)
        print(f"[TTS_INVOCATION text=\"{response_text}\"]")
        voice_state_manager.set_state(VoiceState.RESPONDING)
        zoe_logger.log_action("VOICE_SPEAKING_RESPONSE", length=len(response_text))

        print(f"Zoe: {response_text}\n")
        self.tts.speak(
            response_text,
            wait=True,
            on_amplitude=lambda amp: self.anim_controller.set_audio_metrics(amp),
        )

        # 6. Brief confirmation pulse in SUCCESS, then return to IDLE
        voice_state_manager.set_state(VoiceState.SUCCESS)
        time.sleep(0.6)
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
