"""Audio-reactive input processor with noise floor gating, attack/release smoothing, and peak tracking."""

import math
from typing import Optional
import numpy as np


class AudioReactiveLevel:
    """
    Reusable processor converting raw audio RMS or PCM chunks into smooth,
    normalized visual amplitude [0.0 - 1.0] without visual jitter.
    
    Pipeline:
      raw RMS
         ↓
      noise floor gate
         ↓
      clamped normalization
         ↓
      peak tracking
         ↓
      attack / release smoothing
         ↓
      visual amplitude [0.0 - 1.0]
    """

    def __init__(
        self,
        noise_floor: float = 0.002,
        ceiling: float = 0.08,
        attack: float = 0.45,    # Fast rise for punchy vocal response
        release: float = 0.18,   # Gentle decay to prevent flickering
    ) -> None:
        self.noise_floor = max(0.0, float(noise_floor))
        self.ceiling = max(self.noise_floor + 0.001, float(ceiling))
        self.attack = max(0.01, min(1.0, float(attack)))
        self.release = max(0.01, min(1.0, float(release)))

        self._current_level: float = 0.0
        self._peak: float = 0.0

    @property
    def current_level(self) -> float:
        return self._current_level

    @property
    def peak(self) -> float:
        return self._peak

    def process(self, raw_rms: float) -> float:
        """
        Process a single raw RMS sample into a smoothed visual amplitude.
        
        Returns:
            Smoothed visual level between 0.0 and 1.0.
        """
        rms = max(0.0, float(raw_rms))

        # 1. Gate below noise floor
        if rms <= self.noise_floor:
            target = 0.0
        else:
            # 2. Normalize between noise floor and ceiling with non-linear perceptual curve
            norm = (rms - self.noise_floor) / (self.ceiling - self.noise_floor)
            norm = max(0.0, min(1.0, norm))
            # Square-root expansion gives better low-level responsiveness
            target = math.sqrt(norm)

        # 3. Peak tracking with gradual decay
        if target > self._peak:
            self._peak = target
        else:
            self._peak *= 0.94

        # 4. Attack / Release smoothing
        if target > self._current_level:
            # Rising edge (attack): respond rapidly to voice onset
            self._current_level += (target - self._current_level) * self.attack
        else:
            # Falling edge (release): smooth decay between syllables
            self._current_level += (target - self._current_level) * self.release

        # 5. Strict clamp
        self._current_level = max(0.0, min(1.0, self._current_level))
        return self._current_level

    def process_buffer(self, audio_buffer: np.ndarray) -> float:
        """Calculate RMS of raw float32 or int16 PCM buffer and process it."""
        if audio_buffer is None or len(audio_buffer) == 0:
            return self.process(0.0)

        data = audio_buffer.astype(np.float32)
        if np.max(np.abs(data)) > 1.0:
            data = data / 32768.0

        rms = float(np.sqrt(np.mean(data ** 2)))
        return self.process(rms)

    def reset(self) -> None:
        """Clear active smoothing state."""
        self._current_level = 0.0
        self._peak = 0.0
