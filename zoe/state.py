"""Authoritative runtime state machine and event emitter for Zoe."""

from enum import Enum
import threading
import time
from typing import Callable, Dict, List, Optional
from zoe.macos.logger import zoe_logger


class ZoeState(str, Enum):
    """
    Unified authoritative runtime states for Zoe.
    Observed by the MacBook Notch UI, voice pipeline, and agent coordinator.
    """
    IDLE = "IDLE"              # Inactive / dormant / ambient ready
    STARTUP = "STARTUP"        # Program boot / welcome bloom sequence
    LISTENING = "LISTENING"    # Microphone active, capturing user speech
    THINKING = "THINKING"      # Processing intent, running STT or reasoning
    ACTING = "ACTING"          # Executing computer actions (tools, vision, mouse, apps)
    RESPONDING = "RESPONDING"  # Speaking response aloud through TTS
    SPEAKING = "SPEAKING"      # Synonym for RESPONDING for backwards compatibility
    SUCCESS = "SUCCESS"        # Task or action completed successfully
    ERROR = "ERROR"            # Task failure or system error
    STOPPING = "STOPPING"      # Emergency stop triggered, aborting and resetting


# Deterministic state priority: higher values take rendering precedence
STATE_PRIORITY: Dict[ZoeState, int] = {
    ZoeState.STOPPING: 70,
    ZoeState.ERROR: 60,
    ZoeState.SUCCESS: 55,
    ZoeState.STARTUP: 52,
    ZoeState.RESPONDING: 50,
    ZoeState.SPEAKING: 50,
    ZoeState.ACTING: 40,
    ZoeState.THINKING: 30,
    ZoeState.LISTENING: 20,
    ZoeState.IDLE: 10,
}


def get_state_priority(state: ZoeState) -> int:
    """Return numeric priority of a given runtime state."""
    return STATE_PRIORITY.get(state, 0)


class ZoeStateManager:
    """Thread-safe authoritative state manager for Zoe."""

    def __init__(self, initial_state: ZoeState = ZoeState.IDLE) -> None:
        self._state = initial_state
        self._lock = threading.RLock()
        self._listeners: List[Callable[[ZoeState, ZoeState], None]] = []
        self._temp_timer: Optional[threading.Timer] = None

    @property
    def current_state(self) -> ZoeState:
        with self._lock:
            return self._state

    def set_state(self, new_state: ZoeState) -> None:
        """Atomically transition to new_state and notify registered listeners."""
        with self._lock:
            if self._temp_timer:
                self._temp_timer.cancel()
                self._temp_timer = None

            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state

        zoe_logger.log_action("STATE_CHANGE", old=old_state.value, new=new_state.value)

        # Notify outside lock to prevent deadlocks
        for listener in list(self._listeners):
            try:
                listener(old_state, new_state)
            except Exception as e:
                zoe_logger.log_action("STATE_LISTENER_ERROR", error=str(e))

    def set_temporary_state(
        self,
        temp_state: ZoeState,
        duration: float = 1.0,
        return_state: ZoeState = ZoeState.IDLE,
    ) -> None:
        """
        Transition to a temporary state (like SUCCESS or ERROR) for `duration` seconds,
        then automatically revert to `return_state`.
        """
        with self._lock:
            self.set_state(temp_state)

            def _revert():
                with self._lock:
                    if self._state == temp_state:
                        self.set_state(return_state)

            self._temp_timer = threading.Timer(duration, _revert)
            self._temp_timer.daemon = True
            self._temp_timer.start()

    def add_listener(self, listener: Callable[[ZoeState, ZoeState], None]) -> None:
        """Register a callback for state changes: func(old_state, new_state)."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ZoeState, ZoeState], None]) -> None:
        """Unregister a state change listener."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)


# Global singleton runtime state manager
zoe_state = ZoeStateManager()
