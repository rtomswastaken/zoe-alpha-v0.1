"""Local in-memory audio capture, streaming buffers, and amplitude/pitch analysis."""

import math
import threading
import time
from typing import Callable, Optional, Tuple
import numpy as np
import sounddevice as sd
from zoe.macos.logger import zoe_logger


class AudioAnalyzer:
    """Calculates RMS amplitude and pitch with attack/release smoothing for voice-reactive UI."""

    def __init__(
        self,
        sample_rate: int = 16000,
        attack: float = 0.45,
        release: float = 0.15,
    ) -> None:
        self.sample_rate = sample_rate
        self.attack = attack
        self.release = release
        self.smoothed_rms = 0.0
        self.smoothed_pitch = 220.0  # default Hz

    def process_chunk(self, audio_chunk: np.ndarray) -> Tuple[float, float]:
        """
        Process a mono float32 audio chunk.
        Returns (smoothed_rms [0.0 - 1.0], smoothed_pitch [Hz]).
        """
        if len(audio_chunk) == 0:
            return 0.0, self.smoothed_pitch

        # 1. Compute raw RMS volume
        square_mean = np.mean(np.square(audio_chunk))
        raw_rms = float(np.sqrt(max(1e-9, square_mean)))

        # Normalize typical conversational mic volume (0.01 - 0.3) to 0.0 - 1.0
        norm_rms = min(1.0, max(0.0, raw_rms * 4.0))

        # 2. Attack / Release smoothing
        if norm_rms > self.smoothed_rms:
            self.smoothed_rms += self.attack * (norm_rms - self.smoothed_rms)
        else:
            self.smoothed_rms += self.release * (norm_rms - self.smoothed_rms)

        # 3. Approximate pitch via zero-crossing rate or autocorrelation
        raw_pitch = self._estimate_pitch(audio_chunk)
        if 80.0 <= raw_pitch <= 600.0:
            self.smoothed_pitch += 0.2 * (raw_pitch - self.smoothed_pitch)

        return round(self.smoothed_rms, 3), round(self.smoothed_pitch, 1)

    def _estimate_pitch(self, audio_chunk: np.ndarray) -> float:
        """Estimate fundamental frequency via normalized autocorrelation."""
        if len(audio_chunk) < 256:
            return self.smoothed_pitch

        # Downsample or take segment for fast autocorrelation
        segment = audio_chunk[:1024]
        corr = np.correlate(segment, segment, mode="full")
        corr = corr[len(corr) // 2 :]

        # Look for first peak between min_lag (600 Hz) and max_lag (80 Hz)
        min_lag = int(self.sample_rate / 600)
        max_lag = int(self.sample_rate / 80)

        if max_lag >= len(corr):
            max_lag = len(corr) - 1

        if min_lag >= max_lag:
            return self.smoothed_pitch

        peak_idx = min_lag + int(np.argmax(corr[min_lag:max_lag]))
        if corr[peak_idx] > 0.1 * corr[0]:
            freq = float(self.sample_rate / peak_idx)
            return freq
        return self.smoothed_pitch


class AudioRecorder:
    """Manages continuous in-memory microphone capture and voice activity buffering."""

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 512,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.analyzer = AudioAnalyzer(sample_rate=sample_rate)
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._lock = threading.Lock()
        self._buffer: list[np.ndarray] = []
        self._max_buffer_chunks = int((sample_rate * 10) / chunk_size)  # 10s max rolling
        self._audio_callbacks: list[Callable[[np.ndarray, float, float], None]] = []

    def add_callback(self, cb: Callable[[np.ndarray, float, float], None]) -> None:
        """Register callback: cb(chunk, smoothed_rms, pitch)."""
        if cb not in self._audio_callbacks:
            self._audio_callbacks.append(cb)

    def remove_callback(self, cb: Callable[[np.ndarray, float, float], None]) -> None:
        if cb in self._audio_callbacks:
            self._audio_callbacks.remove(cb)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._buffer.clear()

            def _audio_in(indata, frames, time_info, status):
                if not self._running:
                    return
                # Convert to mono float32
                chunk = indata[:, 0].copy().astype(np.float32)
                rms, pitch = self.analyzer.process_chunk(chunk)

                with self._lock:
                    self._buffer.append(chunk)
                    if len(self._buffer) > self._max_buffer_chunks:
                        self._buffer.pop(0)

                for cb in self._audio_callbacks:
                    try:
                        cb(chunk, rms, pitch)
                    except Exception:
                        pass

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.chunk_size,
                callback=_audio_in,
            )
            self._stream.start()
            zoe_logger.log_action("AUDIO_RECORDING_STARTED", sample_rate=self.sample_rate)

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            zoe_logger.log_action("AUDIO_RECORDING_STOPPED")

    def is_running(self) -> bool:
        return self._running

    def get_recent_audio(self, duration_seconds: float) -> np.ndarray:
        """Retrieve recent audio from ring buffer as single continuous 1D float32 array."""
        with self._lock:
            if not self._buffer:
                return np.zeros(0, dtype=np.float32)
            chunks_needed = int((duration_seconds * self.sample_rate) / self.chunk_size)
            selected = self._buffer[-chunks_needed:] if chunks_needed > 0 else self._buffer
            if not selected:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(selected)

    def record_until_silence(
        self,
        silence_timeout: float = 1.2,
        max_duration: float = 12.0,
        energy_threshold: float = 0.02,
        is_interrupted: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """
        Record speech until silence is detected or max_duration is reached.
        Keeps entire recording in memory.
        """
        if not self._running:
            self.start()

        recorded_chunks: list[np.ndarray] = []
        speech_started = False
        last_speech_time = time.time()
        start_time = time.time()

        while True:
            if is_interrupted and is_interrupted():
                break

            now = time.time()
            if now - start_time > max_duration:
                break

            time.sleep(0.04)
            with self._lock:
                if self._buffer:
                    latest = self._buffer[-1]
                else:
                    latest = None

            if latest is not None:
                recorded_chunks.append(latest)
                chunk_energy = float(np.sqrt(np.mean(np.square(latest))))
                if chunk_energy > energy_threshold:
                    speech_started = True
                    last_speech_time = now
                elif speech_started and (now - last_speech_time > silence_timeout):
                    # End of speech phrase detected
                    break

        if not recorded_chunks:
            return np.zeros(0, dtype=np.float32)

        return np.concatenate(recorded_chunks)
