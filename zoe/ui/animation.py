"""Animation controller coordinating state transitions, pulsing, and audio reactivity for the Notch UI."""

import math
import threading
import time
from typing import Optional
from AppKit import NSRunLoop, NSDate
from zoe.config import get_config
from zoe.macos.logger import zoe_logger
from zoe.ui.notch import get_notch_overlay, ZoeNotchOverlayWindow
from zoe.voice.state import VoiceState, voice_state_manager


class NotchAnimationController:
    """Manages the 30fps animation ticker, alpha fades, pulse cycles, and audio reactivity."""

    def __init__(self, overlay: Optional[ZoeNotchOverlayWindow] = None) -> None:
        self.overlay = overlay or get_notch_overlay()
        self._current_state = VoiceState.IDLE
        self._target_alpha = 0.0
        self._current_alpha = 0.0
        self._pulse_phase = 0.0
        self._audio_amplitude = 0.0
        self._pitch_hz = 220.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Subscribe to voice state manager
        voice_state_manager.add_listener(self._on_voice_state_changed)

    def _on_voice_state_changed(self, old_state: VoiceState, new_state: VoiceState) -> None:
        with self._lock:
            self._current_state = new_state
            cfg = get_config()
            if new_state == VoiceState.IDLE:
                self._target_alpha = 1.0 if cfg.ui.notch.show_on_idle else 0.0
            else:
                self._target_alpha = 1.0

    def set_audio_metrics(self, amplitude: float, pitch: float = 220.0) -> None:
        """Update live audio amplitude [0.0 - 1.0] and pitch [Hz] from audio subsystem."""
        with self._lock:
            self._audio_amplitude = amplitude
            self._pitch_hz = pitch

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._animation_loop, daemon=True)
            self._thread.start()
            zoe_logger.log_action("NOTCH_ANIMATION_STARTED")

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.overlay.hide()
        zoe_logger.log_action("NOTCH_ANIMATION_STOPPED")

    def _animation_loop(self) -> None:
        frame_interval = 1.0 / 30.0  # 30 fps
        while self._running:
            start_t = time.time()

            with self._lock:
                state = self._current_state
                target_alpha = self._target_alpha
                amp = self._audio_amplitude
                pitch = self._pitch_hz

                # Smooth alpha transition
                alpha_diff = target_alpha - self._current_alpha
                self._current_alpha += alpha_diff * 0.25
                if abs(self._current_alpha - target_alpha) < 0.01:
                    self._current_alpha = target_alpha

                # Update pulse phase according to state and pitch
                speed_multiplier = 1.0
                if state == VoiceState.THINKING:
                    speed_multiplier = 1.6
                elif state == VoiceState.ACTING:
                    speed_multiplier = 1.2
                elif state == VoiceState.SPEAKING:
                    speed_multiplier = 1.8

                pitch_factor = max(0.8, min(1.4, pitch / 220.0))
                self._pulse_phase = (self._pulse_phase + 0.12 * speed_multiplier * pitch_factor) % (2.0 * math.pi)

                curr_alpha = self._current_alpha
                phase = self._pulse_phase

            # Update overlay visuals
            self.overlay.update_visuals(
                state=state,
                alpha=curr_alpha,
                pulse_phase=phase,
                amplitude=amp,
                pitch=pitch,
            )

            # Pump Cocoa run loop briefly on background threads to ensure AppKit rendering commits
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.005)
            )

            elapsed = time.time() - start_t
            sleep_t = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_t)


_animation_controller_instance: Optional[NotchAnimationController] = None


def get_animation_controller() -> NotchAnimationController:
    """Singleton getter for the Notch Animation Controller."""
    global _animation_controller_instance
    if _animation_controller_instance is None:
        _animation_controller_instance = NotchAnimationController()
    return _animation_controller_instance
