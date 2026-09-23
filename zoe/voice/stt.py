"""Local Speech-to-Text implementation using faster-whisper on Apple Silicon."""

from abc import ABC, abstractmethod
import threading
import time
from typing import Optional
import numpy as np
from zoe.config import get_config
from zoe.macos.logger import zoe_logger


class BaseSTT(ABC):
    """Abstract interface for local speech-to-text transcription."""

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000, vad_filter: bool = False) -> str:
        """Transcribe in-memory audio array (float32) to text string."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if STT model is loaded and ready."""
        pass


class FasterWhisperSTT(BaseSTT):
    """
    100% offline, local Speech-to-Text using faster-whisper and CTranslate2.
    Runs on Apple Silicon CPU/NEON with int8 quantization.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        compute_type: str = "int8",
        device: str = "cpu",
    ) -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self.device = device
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel

                    zoe_logger.log_action("STT_LOADING_MODEL", model=self.model_size, compute_type=self.compute_type)
                    start_t = time.time()
                    self._model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
                    elapsed = time.time() - start_t
                    zoe_logger.log_action("STT_MODEL_LOADED", elapsed=round(elapsed, 2))

    def is_available(self) -> bool:
        try:
            import faster_whisper
            return True
        except ImportError:
            return False

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000, vad_filter: bool = False) -> str:
        if len(audio) == 0:
            return ""

        # Normalize sample rate if necessary
        if sample_rate != 16000:
            # Simple linear resample if needed
            duration = len(audio) / sample_rate
            new_length = int(duration * 16000)
            if new_length > 0:
                audio = np.interp(
                    np.linspace(0, len(audio), new_length, endpoint=False),
                    np.arange(len(audio)),
                    audio,
                ).astype(np.float32)

        self._ensure_model()

        start_t = time.time()
        # faster-whisper accepts 1D float32 numpy array directly in memory
        transcribe_kwargs = {
            "beam_size": 3,
            "language": "en",
            "vad_filter": vad_filter,
        }
        if vad_filter:
            transcribe_kwargs["vad_parameters"] = dict(min_silence_duration_ms=400)

        segments, info = self._model.transcribe(
            audio,
            **transcribe_kwargs,
        )

        texts = []
        for segment in segments:
            texts.append(segment.text.strip())

        result = " ".join(texts).strip()
        elapsed = time.time() - start_t
        zoe_logger.log_action("STT_TRANSCRIBED", text=result, duration=round(elapsed, 2))
        return result


_stt_instance: Optional[BaseSTT] = None


def get_stt() -> BaseSTT:
    """Singleton getter for local STT engine."""
    global _stt_instance
    if _stt_instance is None:
        cfg = get_config()
        _stt_instance = FasterWhisperSTT(
            model_size=cfg.voice.stt.model,
            compute_type=cfg.voice.stt.compute_type,
        )
    return _stt_instance
