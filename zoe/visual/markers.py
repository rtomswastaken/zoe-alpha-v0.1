"""Visual markers, highlights, and click ripple effects."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VisualMarker:
    """A stationary visual point marker (e.g. multi-step guide point, alternative choice)."""
    x: float
    y: float
    caption: Optional[str] = None
    accent_hex: str = "#3B82F6"  # Blue
    radius: float = 8.0
    duration: Optional[float] = 5.0  # Seconds before auto-fade
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = field(default_factory=time.time)

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.duration is None:
            return False
        current = now if now is not None else time.time()
        return (current - self.created_at) >= self.duration


@dataclass
class HighlightRegion:
    """A rectangular region highlight (e.g. enclosing a button, card, or window)."""
    x: float
    y: float
    width: float
    height: float
    caption: Optional[str] = None
    accent_hex: str = "#00F0FF"  # Cyan
    line_width: float = 2.5
    fill_alpha: float = 0.12
    duration: Optional[float] = 5.0
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = field(default_factory=time.time)

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.duration is None:
            return False
        current = now if now is not None else time.time()
        return (current - self.created_at) >= self.duration


@dataclass
class ClickRipple:
    """An expanding circular click ripple effect rendered at the pointer tip."""
    x: float
    y: float
    accent_hex: str = "#00F0FF"
    start_time: float = field(default_factory=time.time)
    duration: float = 0.5  # seconds
    max_radius: float = 38.0

    @property
    def progress(self) -> float:
        elapsed = time.time() - self.start_time
        return min(1.0, max(0.0, elapsed / self.duration))

    @property
    def current_radius(self) -> float:
        # Smooth ease-out expansion
        p = self.progress
        ease_out = 1.0 - (1.0 - p) ** 3
        return 4.0 + (self.max_radius - 4.0) * ease_out

    @property
    def current_alpha(self) -> float:
        # Fades out as it expands
        return max(0.0, 1.0 - self.progress)

    def is_expired(self) -> bool:
        return self.progress >= 1.0
