"""Compact, clean terminal status presenter observing authoritative Zoe runtime state."""

import sys
import threading
from typing import Optional
from zoe.state import ZoeState, zoe_state


class TerminalStatusIndicator:
    """
    Secondary terminal status channel for Zoe.
    
    Responsibilities:
    - Clean, compact visual status line for CLI environments.
    - Zero spam: deduplicates and only logs upon actual state transition.
    - Gracefully handles non-interactive or piped terminals.
    - Thread-safe and non-blocking.
    """

    # ANSI color definitions
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    BLUE = "\033[94m"

    STATE_FORMATS = {
        ZoeState.STARTUP: ("✨", "[STARTUP]", "Zoe assistant initializing...", MAGENTA),
        ZoeState.IDLE: ("●", "[READY]", "Ambient listening active (say 'Zoe')", CYAN),
        ZoeState.LISTENING: ("🎤", "[LISTENING]", "Capturing microphone audio...", CYAN),
        ZoeState.THINKING: ("🧠", "[THINKING]", "Zoe is reasoning...", MAGENTA),
        ZoeState.ACTING: ("⚙️", "[WORKING]", "Executing computer action...", YELLOW),
        ZoeState.RESPONDING: ("💬", "[RESPONDING]", "Zoe speaking...", GREEN),
        ZoeState.SPEAKING: ("💬", "[RESPONDING]", "Zoe speaking...", GREEN),
        ZoeState.SUCCESS: ("✓", "[SUCCESS]", "Action completed.", GREEN),
        ZoeState.ERROR: ("⚠️", "[ERROR]", "Issue encountered.", RED),
        ZoeState.STOPPING: ("⏹", "[STOPPED]", "Emergency stop triggered.", RED),
    }

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._last_state: Optional[ZoeState] = None
        self._lock = threading.Lock()
        self._listening = False

    def start(self) -> None:
        """Register state listener and enable output."""
        with self._lock:
            if self._listening:
                return
            self._listening = True
            zoe_state.add_listener(self._on_state_changed)

    def stop(self) -> None:
        """Unregister state listener."""
        with self._lock:
            if not self._listening:
                return
            self._listening = False
            zoe_state.remove_listener(self._on_state_changed)

    def format_status(self, state: ZoeState, use_color: bool = True) -> str:
        """Format a single state message with or without ANSI colors."""
        icon, badge, desc, color = self.STATE_FORMATS.get(
            state, ("ℹ️", f"[{state.value}]", "", self.CYAN)
        )
        if use_color:
            return f"{icon} {self.BOLD}{color}{badge}{self.RESET} {desc}"
        return f"{icon} {badge} {desc}"

    def _on_state_changed(self, old_state: ZoeState, new_state: ZoeState) -> None:
        if not self.enabled:
            return

        with self._lock:
            if new_state == self._last_state:
                return
            self._last_state = new_state

        try:
            is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
            msg = self.format_status(new_state, use_color=is_tty)
            sys.stdout.write(f"\n{msg}\n")
            sys.stdout.flush()
        except Exception:
            # Piped / closed terminal safety: never crash runtime
            pass


_terminal_indicator_instance: Optional[TerminalStatusIndicator] = None


def get_terminal_indicator() -> TerminalStatusIndicator:
    """Singleton getter for the terminal status indicator."""
    global _terminal_indicator_instance
    if _terminal_indicator_instance is None:
        _terminal_indicator_instance = TerminalStatusIndicator()
    return _terminal_indicator_instance
