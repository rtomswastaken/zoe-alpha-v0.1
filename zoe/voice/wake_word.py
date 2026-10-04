"""Local wake-word detection for 'Zoe' without external cloud services."""

from abc import ABC, abstractmethod
import re
import threading
import time
from typing import Optional
import numpy as np
from zoe.config import get_config
from zoe.macos.logger import zoe_logger
from zoe.voice.stt import get_stt, BaseSTT


class BaseWakeWord(ABC):
    """Abstract interface for local wake-word detector."""

    @abstractmethod
    def check_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        """Analyze audio chunk/buffer and return True if wake word is detected."""
        pass

    @property
    @abstractmethod
    def phrase(self) -> str:
        """The trigger wake phrase."""
        pass


class VADKeywordWakeWord(BaseWakeWord):
    """
    Local wake-word detector combining adaptive noise floor tracking,
    fast neural VAD, and deterministic keyword spotting for 'Zoe'.
    Matches variations: 'zoe', 'Zoe', 'ZOË', 'zoey', 'hey zoe'.
    """

    def __init__(
        self,
        phrase: str = "zoe",
        stt_engine: Optional[BaseSTT] = None,
        energy_threshold: float = 0.045,
        cooldown_seconds: float = 1.0,
    ) -> None:
        self._phrase = phrase.lower().strip()
        self._stt = stt_engine or get_stt()
        self.energy_threshold = energy_threshold
        self.cooldown_seconds = cooldown_seconds
        self._last_trigger = 0.0
        self._extracted_command: str = ""
        self._noise_floor: float = 0.04
        self._vad_options = None
        self._lock = threading.Lock()

    @property
    def phrase(self) -> str:
        return self._phrase

    @property
    def extracted_command(self) -> str:
        """Returns any command captured in the same breath as the wake word."""
        return self._extracted_command

    def check_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        now = time.time()
        with self._lock:
            if now - self._last_trigger < self.cooldown_seconds:
                return False

        if len(audio) < int(sample_rate * 0.4):  # At least 400ms
            return False

        # 1. Adaptive energy check: do not invoke VAD or STT on room noise / silence
        square_mean = np.mean(np.square(audio))
        rms = float(np.sqrt(max(1e-9, square_mean)))

        if rms < 0.12:
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * rms

        cutoff = max(self.energy_threshold, self._noise_floor * 1.35)
        if rms < cutoff:
            return False

        # 2. Fast Silero VAD check: verify vocal speech is present before running Whisper
        try:
            from faster_whisper.vad import get_speech_timestamps, VadOptions
            if self._vad_options is None:
                self._vad_options = VadOptions(
                    threshold=0.45,
                    min_speech_duration_ms=150,
                    min_silence_duration_ms=250,
                )
            speech_stamps = get_speech_timestamps(audio, self._vad_options, sampling_rate=sample_rate)
            if not speech_stamps:
                return False
        except Exception:
            pass

        # 3. Transcribe speech slice with local STT (marked as partial/diagnostic)
        try:
            transcription = self._stt.transcribe(
                audio,
                sample_rate=sample_rate,
                vad_filter=True,
                partial=True,
            )
        except TypeError:
            transcription = self._stt.transcribe(audio, sample_rate=sample_rate)

        if not transcription or not transcription.strip():
            return False

        raw_text = transcription.strip()

        # 4. Deterministic keyword matching: normalize and match 'zoe', 'zoey', 'zoë'
        clean = re.sub(r"[^\w\s]", " ", raw_text.lower()).strip()
        clean = clean.replace("ë", "e")
        clean = " ".join(clean.split())

        wake_patterns = [
            r"\b(?:hey\s+|hi\s+|ok\s+|okay\s+)?(zoe|zoey|zoie)\b",
        ]
        if self._phrase and self._phrase not in ("zoe", "zoey", "zoie"):
            wake_patterns.append(r"\b" + re.escape(self._phrase) + r"\b")

        for pat in wake_patterns:
            m = re.search(pat, clean)
            if m:
                match_text = m.group(0)
                # Extract subsequent command spoken in the same breath
                trailing = clean[m.end():].strip()
                trailing = re.sub(r"^(?:please|can you|could you|would you)\s+", "", trailing).strip()
                with self._lock:
                    self._last_trigger = now
                    self._extracted_command = trailing

                # Explicit diagnostic events (console + structured logger)
                print(f"\n[WAKE_WORD_DETECTED text=\"{match_text}\"]")
                zoe_logger.log_action("WAKE_WORD_DETECTED", phrase=match_text)
                return True

        return False


_wake_word_instance: Optional[BaseWakeWord] = None


def get_wake_word_detector() -> BaseWakeWord:
    """Singleton getter for wake word detector."""
    global _wake_word_instance
    if _wake_word_instance is None:
        cfg = get_config()
        _wake_word_instance = VADKeywordWakeWord(
            phrase=cfg.voice.wake_word.phrase,
        )
    return _wake_word_instance
