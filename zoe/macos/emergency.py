"""Emergency stop controller and cancellation mechanism for Zoe."""

import threading
import time
from typing import Callable, List
from zoe.macos.logger import zoe_logger


class EmergencyStopTriggeredException(Exception):
    """Raised when an action is aborted due to emergency stop."""
    pass


class EmergencyStopController:
    """
    Thread-safe emergency stop mechanism.
    Allows immediately aborting running cursor movements, drag operations,
    key typing, and drops any pending action in queue.
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[], None]] = []
        self._reason: str = ""
        self._listener_thread: threading.Thread | None = None
        self._listening: bool = False

    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def get_reason(self) -> str:
        with self._lock:
            return self._reason

    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to run immediately upon emergency stop (e.g. release mouse buttons)."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def trigger(self, reason: str = "Emergency stop triggered (ESC pressed)") -> None:
        """Trigger emergency stop immediately."""
        with self._lock:
            if self._stop_event.is_set():
                return
            self._reason = reason
            self._stop_event.set()

        zoe_logger.log_action("EMERGENCY_STOP", reason=reason)

        # Run cleanup callbacks safely
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                zoe_logger.log_action("EMERGENCY_CLEANUP_ERROR", error=str(e))

    def reset(self) -> None:
        """Reset emergency stop to allow resuming actions."""
        with self._lock:
            self._stop_event.clear()
            self._reason = ""
        zoe_logger.log_action("EMERGENCY_RESET")

    def check_and_raise(self) -> None:
        """Helper to check stop flag inside movement loops and raise exception."""
        if self._stop_event.is_set():
            raise EmergencyStopTriggeredException(self._reason or "Emergency stop active")

    def start_listener(self) -> None:
        """Start a background listener to detect emergency stop hotkey (ESC)."""
        if self._listening:
            return
        self._listening = True
        self._listener_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._listener_thread.start()

    def stop_listener(self) -> None:
        self._listening = False

    def _monitor_loop(self) -> None:
        """
        Background listener for ESC key using native Quartz CGEventTap / CGEventSourceKeyState.
        KeyCode for ESC on macOS keyboard is 53 (0x35).
        """
        try:
            from Quartz import CGEventSourceKeyState, kCGEventSourceStateCombinedSessionState
            esc_key_code = 53

            while self._listening:
                try:
                    # Check if Escape key (keycode 53) is physically pressed
                    is_pressed = CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, esc_key_code)
                    if is_pressed:
                        if not self.is_stopped():
                            self.trigger("ESC key pressed")
                except Exception:
                    pass
                time.sleep(0.015)  # ~66Hz poll
        except ImportError:
            pass


emergency_controller = EmergencyStopController()
