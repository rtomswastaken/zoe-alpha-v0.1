"""Unified animation engine coordinating state transitions, pulsing, and audio reactivity for the Notch UI."""

import math
import threading
import time
from typing import Optional
from AppKit import NSDate, NSRunLoop
from zoe.config import get_config
from zoe.macos.logger import zoe_logger
from zoe.state import ZoeState, zoe_state
from zoe.ui.audio_reactive import AudioReactiveLevel
from zoe.ui.notch import ZoeNotchOverlayWindow, get_notch_overlay


class NotchAnimator:
    """
    Reusable 30-60fps animation engine driving the MacBook Notch Glow visual indicator.
    
    Responsibilities:
    - Smooth alpha transitions between active and idle states.
    - Continuous autonomous state pulsing (LISTENING, THINKING, ACTING, RESPONDING).
    - Jitter-free audio reactivity via AudioReactiveLevel.
    - Power efficiency: sleeps dormant during IDLE, animates continuously when active.
    """

    def __init__(self, overlay: Optional[ZoeNotchOverlayWindow] = None) -> None:
        self.overlay = overlay or get_notch_overlay()
        self.audio_reactive = AudioReactiveLevel()
        self._current_state: ZoeState = ZoeState.IDLE
        self._target_alpha: float = 0.0
        self._current_alpha: float = 0.0
        self._pulse_phase: float = 0.0
        self._pitch_hz: float = 220.0
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._last_frame_time: float = time.time()

        # Subscribe to unified authoritative runtime state
        zoe_state.add_listener(self._on_state_changed)

    # -------------------------------------------------------------------------
    # Public Controller API
    # -------------------------------------------------------------------------

    def set_state(self, state: ZoeState) -> None:
        """Manually trigger state transition in animator."""
        self._on_state_changed(self._current_state, state)

    def set_audio_level(self, amplitude: float, pitch: float = 220.0) -> None:
        """Feed live raw audio RMS [0.0 - 1.0] and pitch [Hz] into audio reactive filter."""
        smoothed = self.audio_reactive.process(amplitude)
        with self._lock:
            self._pitch_hz = pitch

    def set_audio_metrics(self, amplitude: float, pitch: float = 220.0) -> None:
        """Alias for backward compatibility with existing voice pipeline."""
        self.set_audio_level(amplitude=amplitude, pitch=pitch)

    def start(self) -> None:
        """Start the animation ticker background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._last_frame_time = time.time()
            self._thread = threading.Thread(target=self._animation_loop, daemon=True)
            self._thread.start()
            zoe_logger.log_action("NOTCH_ANIMATION_STARTED")

    def stop(self) -> None:
        """Stop the animation ticker and hide the overlay immediately."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.overlay.hide()
        zoe_logger.log_action("NOTCH_ANIMATION_STOPPED")

    # -------------------------------------------------------------------------
    # State Observer Callback
    # -------------------------------------------------------------------------

    def _on_state_changed(self, old_state: ZoeState, new_state: ZoeState) -> None:
        with self._lock:
            self._current_state = new_state
            cfg = get_config()

            if new_state == ZoeState.IDLE:
                # Extremely subtle ambient glow when idle/ready (~0.28 alpha)
                self._target_alpha = 0.28 if cfg.ui.notch.show_on_idle else 0.0
                self.audio_reactive.reset()
            elif new_state == ZoeState.STARTUP:
                # Welcome bloom full radiant presence
                self._target_alpha = 1.0
                self.audio_reactive.reset()
            elif new_state == ZoeState.STOPPING:
                # Emergency stop: immediate collapse
                self._target_alpha = 0.0
                self._current_alpha = 0.0
                self.audio_reactive.reset()
            elif new_state in (ZoeState.ERROR, ZoeState.SUCCESS):
                self._target_alpha = 1.0
                self.audio_reactive.reset()
            else:
                self._target_alpha = 1.0

    # -------------------------------------------------------------------------
    # Frame Update and Render
    # -------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Update animation curves, smoothing, and phase for delta-time dt."""
        with self._lock:
            state = self._current_state
            target_alpha = self._target_alpha

            # Smooth alpha transition (attack/fade rate ~10x dt)
            alpha_rate = 8.0 if state != ZoeState.STOPPING else 28.0
            alpha_diff = target_alpha - self._current_alpha
            self._current_alpha += alpha_diff * min(1.0, alpha_rate * dt)
            if abs(self._current_alpha - target_alpha) < 0.005:
                self._current_alpha = target_alpha

            # Speed multiplier per state
            if state == ZoeState.STARTUP:
                speed = 2.0
            elif state == ZoeState.THINKING:
                speed = 2.2
            elif state == ZoeState.ACTING:
                speed = 2.8
            elif state in (ZoeState.SPEAKING, ZoeState.RESPONDING):
                speed = 2.0
            elif state == ZoeState.ERROR:
                speed = 4.0
            elif state == ZoeState.SUCCESS:
                speed = 1.5
            elif state == ZoeState.IDLE:
                speed = 0.4  # Tranquil, calm ambient breathing
            else:
                speed = 1.0

            pitch_factor = max(0.8, min(1.4, self._pitch_hz / 220.0))
            self._pulse_phase = (self._pulse_phase + (speed * pitch_factor * 3.5 * dt)) % (math.pi * 2.0)

    def render(self) -> None:
        """Push current animation state into the native Cocoa overlay view."""
        with self._lock:
            state = self._current_state
            curr_alpha = self._current_alpha
            phase = self._pulse_phase
            amp = self.audio_reactive.current_level
            pitch = self._pitch_hz

        self.overlay.update_visuals(
            state=state,
            alpha=curr_alpha,
            pulse_phase=phase,
            amplitude=amp,
            pitch=pitch,
        )

    # -------------------------------------------------------------------------
    # Internal Animation Loop
    # -------------------------------------------------------------------------

    def _animation_loop(self) -> None:
        target_fps = 45.0
        frame_interval = 1.0 / target_fps

        while self._running:
            now = time.time()
            dt = max(0.001, now - self._last_frame_time)
            self._last_frame_time = now

            with self._lock:
                state = self._current_state
                curr_alpha = self._current_alpha
                target_alpha = self._target_alpha

            is_hidden = (state == ZoeState.IDLE and curr_alpha <= 0.001)

            # Power saving: sleep longer if completely idle and hidden
            if is_hidden:
                time.sleep(0.08)
                continue

            # CPU optimization: if idle and alpha is stable, throttle to ~12 FPS
            if state == ZoeState.IDLE and abs(curr_alpha - target_alpha) < 0.01:
                self.update(dt)
                self.render()
                NSRunLoop.currentRunLoop().runUntilDate_(
                    NSDate.dateWithTimeIntervalSinceNow_(0.002)
                )
                time.sleep(0.08)
                continue

            self.update(dt)
            self.render()

            # Pump Cocoa RunLoop briefly on background threads to ensure drawing commits
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.004)
            )

            elapsed = time.time() - now
            sleep_t = max(0.002, frame_interval - elapsed)
            time.sleep(sleep_t)


# Alias for backward compatibility
NotchAnimationController = NotchAnimator

_animation_controller_instance: Optional[NotchAnimator] = None


def get_animation_controller() -> NotchAnimator:
    """Singleton getter for the unified Notch Animation Controller."""
    global _animation_controller_instance
    if _animation_controller_instance is None:
        _animation_controller_instance = NotchAnimator()
    return _animation_controller_instance
