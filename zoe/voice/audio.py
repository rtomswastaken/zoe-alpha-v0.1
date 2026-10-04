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
        self._feeding_simulated = False
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
                if not self._running or self._feeding_simulated:
                    return
                # Convert to mono float32
                chunk = indata[:, 0].copy().astype(np.float32)
                rms, pitch = self.analyzer.process_chunk(chunk)

                with self._lock:
                    self._buffer.append(chunk)
                    if len(self._buffer) > self._max_buffer_chunks:
                        self._buffer.pop(0)

                for cb in list(self._audio_callbacks):
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

    def start_recording(self) -> None:
        """Alias for start()."""
        self.start()

    def stop_recording(self) -> None:
        """Alias for stop()."""
        self.stop()

    def is_running(self) -> bool:
        return self._running

    def feed_audio(self, audio: np.ndarray, realtime: bool = True) -> None:
        """Feed audio array into live recording buffer and callbacks (for testing and simulation)."""
        self._feeding_simulated = True
        try:
            chunk_size = self.chunk_size
            delay = (chunk_size / self.sample_rate) if realtime else 0.0
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i : i + chunk_size].astype(np.float32)
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                rms, pitch = self.analyzer.process_chunk(chunk)
                with self._lock:
                    self._buffer.append(chunk)
                    if len(self._buffer) > self._max_buffer_chunks:
                        self._buffer.pop(0)
                for cb in list(self._audio_callbacks):
                    try:
                        cb(chunk, rms, pitch)
                    except Exception:
                        pass
                if delay > 0:
                    time.sleep(delay)
        finally:
            self._feeding_simulated = False

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
        silence_timeout: float = 1.1,
        initial_timeout: float = 4.0,
        max_duration: float = 12.0,
        energy_threshold: float = 0.070,
        on_amplitude: Optional[Callable[[float], None]] = None,
        is_interrupted: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """
        Record continuous speech until silence is detected or max_duration is reached.
        Uses real-time callback queueing to ensure zero dropped audio chunks.
        """
        if not self._running:
            self.start()

        recorded_chunks: list[np.ndarray] = []
        incoming: list[Tuple[np.ndarray, float]] = []
        q_lock = threading.Lock()

        def _capture_cb(chunk: np.ndarray, rms: float, _pitch: float) -> None:
            with q_lock:
                incoming.append((chunk, rms))

        self.add_callback(_capture_cb)

        speech_started = False
        start_time = time.time()
        last_speech_time = start_time
        noise_floor = 0.04

        try:
            while True:
                if is_interrupted and is_interrupted():
                    break

                now = time.time()
                if now - start_time > max_duration:
                    break

                # Pop new incoming chunks from queue
                with q_lock:
                    batch = list(incoming)
                    incoming.clear()

                for chunk, chunk_rms in batch:
                    recorded_chunks.append(chunk)

                    # Update live amplitude for voice-reactive notch UI
                    if on_amplitude:
                        try:
                            on_amplitude(chunk_rms)
                        except Exception:
                            pass

                    # Adaptive noise floor tracking
                    if chunk_rms < 0.12:
                        noise_floor = 0.95 * noise_floor + 0.05 * chunk_rms

                    threshold = max(energy_threshold, noise_floor * 1.45)
                    if chunk_rms > threshold:
                        speech_started = True
                        last_speech_time = now

                # If speech hasn't started and initial wait expires, stop
                if not speech_started and (now - start_time > initial_timeout):
                    break

                # If speech started and user has stopped talking for silence_timeout, finish
                if speech_started and (now - last_speech_time > silence_timeout):
                    break

                time.sleep(0.02)
        finally:
            self.remove_callback(_capture_cb)

        if not recorded_chunks or not speech_started:
            return np.zeros(0, dtype=np.float32)

        return np.concatenate(recorded_chunks)
