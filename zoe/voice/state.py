"""Explicit state machine and event emitter for Zoe Voice and Notch UI."""

from enum import Enum
import threading
from typing import Callable, List, Optional
from zoe.macos.logger import zoe_logger


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    ACTING = "ACTING"
    SPEAKING = "SPEAKING"
    STOPPING = "STOPPING"


class VoiceStateManager:
    """Thread-safe state manager for Zoe's voice and UI lifecycle."""

    def __init__(self, initial_state: VoiceState = VoiceState.IDLE) -> None:
        self._state = initial_state
        self._lock = threading.Lock()
        self._listeners: List[Callable[[VoiceState, VoiceState], None]] = []

    @property
    def current_state(self) -> VoiceState:
        with self._lock:
            return self._state

    def set_state(self, new_state: VoiceState) -> None:
        """Atomically transition to new_state and notify registered listeners."""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state

        zoe_logger.log_action("VOICE_STATE_CHANGE", old=old_state.value, new=new_state.value)

        # Notify outside lock to prevent deadlocks
        for listener in self._listeners:
            try:
                listener(old_state, new_state)
            except Exception as e:
                zoe_logger.log_action("VOICE_STATE_LISTENER_ERROR", error=str(e))

    def add_listener(self, listener: Callable[[VoiceState, VoiceState], None]) -> None:
        """Register a callback for state changes: func(old_state, new_state)."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[VoiceState, VoiceState], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)


# Global singleton voice state manager
voice_state_manager = VoiceStateManager()
