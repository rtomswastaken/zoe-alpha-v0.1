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
    Local wake-word detector combining voice energy detection and fast keyword spotting.
    Matches variations like 'Zoe', 'Hey Zoe', 'So Zoe'.
    """

    def __init__(
        self,
        phrase: str = "zoe",
        stt_engine: Optional[BaseSTT] = None,
        energy_threshold: float = 0.02,
        cooldown_seconds: float = 1.0,
    ) -> None:
        self._phrase = phrase.lower().strip()
        self._stt = stt_engine or get_stt()
        self.energy_threshold = energy_threshold
        self.cooldown_seconds = cooldown_seconds
        self._last_trigger = 0.0
        self._lock = threading.Lock()

    @property
    def phrase(self) -> str:
        return self._phrase

    def check_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        now = time.time()
        with self._lock:
            if now - self._last_trigger < self.cooldown_seconds:
                return False

        if len(audio) < int(sample_rate * 0.4):  # At least 400ms
            return False

        # 1. Energy check (don't run STT on complete background silence)
        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms < self.energy_threshold:
            return False

        # 2. Transcribe short slice with local STT
        transcription = self._stt.transcribe(audio, sample_rate=sample_rate).lower()
        if not transcription:
            return False

        # 3. Keyword matching: check if target phrase appears as standalone word or token
        pattern = r"\b" + re.escape(self._phrase) + r"\b"
        if re.search(pattern, transcription) or self._phrase in transcription:
            with self._lock:
                self._last_trigger = now
            zoe_logger.log_action("WAKE_WORD_TRIGGERED", phrase=self._phrase, heard=transcription)
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
