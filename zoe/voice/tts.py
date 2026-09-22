"""Local Text-to-Speech engine implementations (Native NSSpeechSynthesizer and extensible BaseTTS)."""

from abc import ABC, abstractmethod
import threading
import time
from typing import Callable, List, Optional
from AppKit import NSSpeechSynthesizer, NSObject, NSRunLoop, NSDate
from zoe.config import get_config
from zoe.macos.logger import zoe_logger


class BaseTTS(ABC):
    """Abstract interface for local text-to-speech engines."""

    @abstractmethod
    def speak(
        self,
        text: str,
        wait: bool = True,
        on_amplitude: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """Synthesize and speak text. Returns True if completed, False if interrupted."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Immediately halt active speech output."""
        pass

    @abstractmethod
    def is_speaking(self) -> bool:
        """Return True if currently speaking audio."""
        pass

    @abstractmethod
    def get_voices(self) -> List[str]:
        """List available local voice names."""
        pass


class _SpeechDelegate(NSObject):
    """Cocoa delegate tracking speech completion."""

    def speechSynthesizer_didFinishSpeaking_(self, synth, success):
        if hasattr(self, "_on_finish"):
            self._on_finish(bool(success))


class NSSpeechTTS(BaseTTS):
    """
    100% local, zero-install TTS using native macOS NSSpeechSynthesizer.
    Instant latency, zero network access, and fully interruptible.
    """

    def __init__(
        self,
        voice_name: Optional[str] = None,
        rate: int = 190,
        volume: float = 1.0,
    ) -> None:
        self.rate = rate
        self.volume = volume
        self._synth = NSSpeechSynthesizer.alloc().init()
        self._lock = threading.Lock()
        self._is_speaking = False
        self._interrupted = False
        self._delegate = _SpeechDelegate.alloc().init()
        self._delegate._on_finish = self._handle_finished
        self._synth.setDelegate_(self._delegate)

        # Set voice
        cfg = get_config()
        chosen_voice = voice_name or cfg.voice.tts.voice
        self._set_voice_by_name(chosen_voice)

        if self.rate:
            self._synth.setRate_(float(self.rate))
        if self.volume:
            self._synth.setVolume_(float(self.volume))

    def _set_voice_by_name(self, name: str) -> None:
        """Set voice matching substring (e.g. 'Samantha' or 'Ava')."""
        target = name.lower()
        for v in NSSpeechSynthesizer.availableVoices():
            v_str = str(v)
            if target in v_str.lower():
                self._synth.setVoice_(v)
                return

    def _handle_finished(self, success: bool) -> None:
        with self._lock:
            self._is_speaking = False

    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking or bool(self._synth.isSpeaking())

    def stop(self) -> None:
        with self._lock:
            self._interrupted = True
            self._is_speaking = False
            try:
                self._synth.stopSpeaking()
            except Exception:
                pass
        zoe_logger.log_action("TTS_STOPPED_INTERRUPTION")

    def get_voices(self) -> List[str]:
        voices = []
        for v in NSSpeechSynthesizer.availableVoices():
            v_name = str(v).split(".")[-1]
            voices.append(v_name)
        return voices

    def speak(
        self,
        text: str,
        wait: bool = True,
        on_amplitude: Optional[Callable[[float], None]] = None,
    ) -> bool:
        if not text or not text.strip():
            return True

        clean_text = text.strip()
        zoe_logger.log_action("TTS_SPEAK_START", length=len(clean_text))

        with self._lock:
            self._interrupted = False
            self._is_speaking = True
            started = bool(self._synth.startSpeakingString_(clean_text))

        if not started:
            with self._lock:
                self._is_speaking = False
            return False

        if not wait:
            return True

        # Polling loop during playback with simulated amplitude modulation for notch glow
        start_time = time.time()
        while self.is_speaking():
            if self._interrupted:
                return False

            if on_amplitude:
                # Modulate amplitude with speech cadence envelope
                elapsed = time.time() - start_time
                sim_amp = 0.5 + 0.35 * (0.5 * (1.0 + (elapsed * 9.0) % 2.0 - 1.0))
                on_amplitude(sim_amp)

            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.03)
            )

        if on_amplitude:
            on_amplitude(0.0)

        zoe_logger.log_action("TTS_SPEAK_COMPLETE")
        return not self._interrupted


_tts_instance: Optional[BaseTTS] = None


def get_tts() -> BaseTTS:
    """Singleton getter for local TTS engine."""
    global _tts_instance
    if _tts_instance is None:
        cfg = get_config()
        _tts_instance = NSSpeechTTS(
            voice_name=cfg.voice.tts.voice,
            rate=cfg.voice.tts.rate,
            volume=cfg.voice.tts.volume,
        )
    return _tts_instance
