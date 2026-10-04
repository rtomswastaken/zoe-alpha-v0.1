"""Zoe Native Visual Cursor Subsystem.

Provides an independent, transparent, click-through visual cursor and marker overlay.
Strictly decoupled from real macOS mouse control.
"""

from zoe.visual.animation import generate_visual_trajectory
from zoe.visual.cursor import ZoeVisualCursor, visual_cursor
from zoe.visual.markers import ClickRipple, HighlightRegion, VisualMarker
from zoe.visual.overlay import VisualCursorOverlayWindow
from zoe.visual.state import VisualCursorSnapshot, VisualCursorState

__all__ = [
    "visual_cursor",
    "ZoeVisualCursor",
    "VisualCursorState",
    "VisualCursorSnapshot",
    "VisualMarker",
    "HighlightRegion",
    "ClickRipple",
    "VisualCursorOverlayWindow",
    "generate_visual_trajectory",
]
