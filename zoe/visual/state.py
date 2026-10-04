"""Visual cursor state definitions and snapshots."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VisualCursorState(str, Enum):
    """
    Visual cursor states defining appearance, animation, and behavior.
    Purely visual — never impacts real mouse cursor or event routing.
    """
    HIDDEN = "HIDDEN"        # Completely invisible
    IDLE = "IDLE"            # Resting visual presence with subtle breathing
    GUIDING = "GUIDING"      # Actively gliding along smooth trajectory
    TARGETED = "TARGETED"    # Pulsing highlight ring on target element
    CLICKING = "CLICKING"    # Expanding ripple pulse at pointer tip
    ACTING = "ACTING"        # Visual cue while Zoe executes a real computer action
    DONE = "DONE"            # Confirmation green flash, then fades to hidden


@dataclass
class VisualCursorSnapshot:
    """Read-only snapshot of current visual cursor presentation."""
    x: float
    y: float
    state: VisualCursorState
    label: str = "Zoe"
    caption: Optional[str] = None
    alpha: float = 1.0
    accent_hex: str = "#00F0FF"  # Radiant Electric Cyan
    is_visible: bool = True
