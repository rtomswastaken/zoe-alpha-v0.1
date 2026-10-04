"""Zoe Visual Cursor controller: independent, click-through visual pointer and marker system."""

import threading
import time
from typing import Dict, List, Optional, Tuple
from zoe.macos.emergency import emergency_controller
from zoe.macos.logger import zoe_logger
from zoe.state import ZoeState, zoe_state
from zoe.visual.animation import generate_visual_trajectory
from zoe.visual.markers import ClickRipple, HighlightRegion, VisualMarker
from zoe.visual.overlay import VisualCursorOverlayWindow
from zoe.visual.state import VisualCursorSnapshot, VisualCursorState


class ZoeVisualCursor:
    """
    Independent visual cursor and UI overlay for Zoe.
    
    STRICT INVARIANTS:
    - Never modifies the real macOS cursor (never calls CGWarpMouseCursorPosition or NSCursor).
    - Mouse transparent and click-through: never intercepts user clicks, typing, or gestures.
    - Operates as a separate visual guide, collaborator cursor, and visual feedback layer.
    """

    def __init__(self) -> None:
        self._x: float = 500.0
        self._y: float = 300.0
        self._state: VisualCursorState = VisualCursorState.HIDDEN
        self._label: str = "Zoe"
        self._caption: Optional[str] = None
        self._accent_hex: str = "#00F0FF"
        self._alpha: float = 0.0
        self._markers: List[VisualMarker] = []
        self._regions: List[HighlightRegion] = []
        self._ripples: List[ClickRipple] = []

        self._lock = threading.RLock()
        self._animation_cancel_event = threading.Event()
        self._active_anim_thread: Optional[threading.Thread] = None

        # Instantiate native overlay window
        self._overlay = VisualCursorOverlayWindow()

        # Register safety callback with Zoe emergency controller
        emergency_controller.register_cleanup_callback(self.emergency_stop)

        # Subscribe to authoritative Zoe runtime state
        zoe_state.add_listener(self._on_zoe_state_changed)

    def _on_zoe_state_changed(self, old_state: ZoeState, new_state: ZoeState) -> None:
        """Observe authoritative Zoe runtime state changes."""
        if new_state == ZoeState.STOPPING:
            self.emergency_stop()
        elif new_state == ZoeState.IDLE:
            if self._state == VisualCursorState.ACTING:
                self.idle()
        elif new_state == ZoeState.ACTING:
            if self.is_visible:
                self.acting_effect()

    # -------------------------------------------------------------------------
    # Properties & Status
    # -------------------------------------------------------------------------

    @property
    def position(self) -> Tuple[float, float]:
        """Current logical Quartz coordinates (x, y) of the visual cursor."""
        with self._lock:
            return (self._x, self._y)

    @property
    def state(self) -> VisualCursorState:
        with self._lock:
            return self._state

    @property
    def overlay(self) -> VisualCursorOverlayWindow:
        return self._overlay

    @property
    def markers(self) -> List[VisualMarker]:
        with self._lock:
            return list(self._markers)

    @property
    def regions(self) -> List[HighlightRegion]:
        with self._lock:
            return list(self._regions)

    @property
    def is_visible(self) -> bool:
        with self._lock:
            return self._state != VisualCursorState.HIDDEN and self._alpha > 0.01

    def snapshot(self) -> VisualCursorSnapshot:
        with self._lock:
            return VisualCursorSnapshot(
                x=self._x,
                y=self._y,
                state=self._state,
                label=self._label,
                caption=self._caption,
                alpha=self._alpha,
                accent_hex=self._accent_hex,
                is_visible=self.is_visible,
            )

    # -------------------------------------------------------------------------
    # Positioning & Movement (Visual Only — Real mouse is NEVER touched)
    # -------------------------------------------------------------------------

    def move_to(
        self,
        x: float,
        y: float,
        caption: Optional[str] = None,
        state: VisualCursorState = VisualCursorState.GUIDING,
    ) -> None:
        """Instantly update visual cursor position without animating."""
        with self._lock:
            self._x = float(x)
            self._y = float(y)
            if caption is not None:
                self._caption = caption
            self._state = state
            self._alpha = 1.0
            self._sync_overlay()

    def idle(self) -> None:
        """Set visual cursor to resting idle presence."""
        with self._lock:
            self._state = VisualCursorState.IDLE
            self._alpha = 0.7
            self._sync_overlay()

    def move_smoothly_to(
        self,
        x: float,
        y: float,
        duration: float = 0.35,
        steps: int = 30,
        caption: Optional[str] = None,
        accent_hex: str = "#00F0FF",
        blocking: bool = True,
    ) -> None:
        """
        Smoothly glide the visual cursor from current position to (x, y).
        Strictly visual: real mouse pointer remains completely stationary.
        """
        emergency_controller.check_and_raise()
        self._animation_cancel_event.clear()

        start_pt = self.position
        end_pt = (float(x), float(y))

        # Generate human-like curved trajectory
        points = generate_visual_trajectory(start_pt, end_pt, steps=steps)

        def _glide():
            with self._lock:
                self._state = VisualCursorState.GUIDING
                self._alpha = 1.0
                self._accent_hex = accent_hex
                if caption is not None:
                    self._caption = caption
                self._overlay.show()

            step_delay = duration / max(1, len(points))
            for pt in points:
                if self._animation_cancel_event.is_set() or emergency_controller.is_stopped():
                    break
                with self._lock:
                    self._x = pt[0]
                    self._y = pt[1]
                    self._sync_overlay()
                time.sleep(step_delay)

            with self._lock:
                if not self._animation_cancel_event.is_set():
                    self._x = end_pt[0]
                    self._y = end_pt[1]
                    self._state = VisualCursorState.IDLE
                    self._sync_overlay()

        if blocking:
            _glide()
        else:
            th = threading.Thread(target=_glide, daemon=True)
            self._active_anim_thread = th
            th.start()

    # -------------------------------------------------------------------------
    # Visual Highlights, Targets & Click Ripples
    # -------------------------------------------------------------------------

    def target(self, x: float, y: float, caption: Optional[str] = None, accent_hex: str = "#00F0FF") -> None:
        """Move to (x, y) and display pulsating target reticle."""
        with self._lock:
            self._x = float(x)
            self._y = float(y)
            self._state = VisualCursorState.TARGETED
            self._caption = caption
            self._accent_hex = accent_hex
            self._alpha = 1.0
            self._overlay.show()
            self._sync_overlay()

    def click_effect(self, x: Optional[float] = None, y: Optional[float] = None, accent_hex: str = "#00F0FF") -> None:
        """Trigger an expanding click ripple effect at cursor tip or specified coordinates."""
        with self._lock:
            cx = float(x) if x is not None else self._x
            cy = float(y) if y is not None else self._y
            self._x = cx
            self._y = cy
            self._state = VisualCursorState.CLICKING
            self._alpha = 1.0
            ripple = ClickRipple(x=cx, y=cy, accent_hex=accent_hex)
            self._ripples.append(ripple)
            self._overlay.show()
            self._sync_overlay()

    def acting_effect(self, x: Optional[float] = None, y: Optional[float] = None, caption: Optional[str] = None) -> None:
        """Set visual state to ACTING while Zoe executes a real computer control action."""
        with self._lock:
            if x is not None:
                self._x = float(x)
            if y is not None:
                self._y = float(y)
            self._state = VisualCursorState.ACTING
            if caption is not None:
                self._caption = caption
            self._accent_hex = "#A855F7"  # Purple/Violet
            self._alpha = 1.0
            self._overlay.show()
            self._sync_overlay()

    def done_effect(self, caption: str = "Done", fade_after: float = 0.8) -> None:
        """Display green confirmation badge and fade out."""
        with self._lock:
            self._state = VisualCursorState.DONE
            self._caption = caption
            self._accent_hex = "#10B981"  # Emerald Green
            self._alpha = 1.0
            self._sync_overlay()

        def _delayed_fade():
            time.sleep(fade_after)
            with self._lock:
                if self._state == VisualCursorState.DONE:
                    self.hide()

        threading.Thread(target=_delayed_fade, daemon=True).start()

    # -------------------------------------------------------------------------
    # Markers & Regions
    # -------------------------------------------------------------------------

    def add_marker(
        self,
        x: float,
        y: float,
        caption: Optional[str] = None,
        accent_hex: str = "#3B82F6",
        duration: Optional[float] = 5.0,
    ) -> str:
        """Add a temporary stationary visual point marker."""
        marker = VisualMarker(x=float(x), y=float(y), caption=caption, accent_hex=accent_hex, duration=duration)
        with self._lock:
            self._markers.append(marker)
            self._overlay.show()
            self._sync_overlay()
        return marker.id

    def highlight_region(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        caption: Optional[str] = None,
        accent_hex: str = "#00F0FF",
        duration: Optional[float] = 5.0,
    ) -> str:
        """Highlight a rectangular region on screen."""
        region = HighlightRegion(
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            caption=caption,
            accent_hex=accent_hex,
            duration=duration,
        )
        with self._lock:
            self._regions.append(region)
            self._overlay.show()
            self._sync_overlay()
        return region.id

    def remove_marker(self, marker_id: str) -> None:
        with self._lock:
            self._markers = [m for m in self._markers if m.id != marker_id]
            self._regions = [r for r in self._regions if r.id != marker_id]
            self._sync_overlay()

    def clear_markers(self) -> None:
        with self._lock:
            self._markers.clear()
            self._regions.clear()
            self._ripples.clear()
            self._sync_overlay()

    # -------------------------------------------------------------------------
    # Visibility, Labels & Emergency Stop
    # -------------------------------------------------------------------------

    def show(self) -> None:
        with self._lock:
            self._state = VisualCursorState.IDLE
            self._alpha = 1.0
            self._overlay.show()
            self._sync_overlay()

    def hide(self) -> None:
        with self._lock:
            self._state = VisualCursorState.HIDDEN
            self._alpha = 0.0
            self._caption = None
            self._sync_overlay()
            self._overlay.hide()

    def set_label(self, label: str = "Zoe") -> None:
        with self._lock:
            self._label = label
            self._sync_overlay()

    def clear(self) -> None:
        """Clear all active visual indicators and hide overlay."""
        self._animation_cancel_event.set()
        with self._lock:
            self.clear_markers()
            self.hide()

    def emergency_stop(self) -> None:
        """Safety callback invoked when ESC is pressed. Immediately halts all visual animation."""
        self._animation_cancel_event.set()
        with self._lock:
            self._state = VisualCursorState.HIDDEN
            self._alpha = 0.0
            self._caption = None
            self._markers.clear()
            self._regions.clear()
            self._ripples.clear()
            self._overlay.hide()
            zoe_logger.log_action("VISUAL_CURSOR_EMERGENCY_STOP")

    # -------------------------------------------------------------------------
    # Private Overlay Sync
    # -------------------------------------------------------------------------

    def _sync_overlay(self) -> None:
        if self._overlay.view is not None:
            self._overlay.view.update_cursor(
                x=self._x,
                y=self._y,
                state=self._state,
                label=self._label,
                caption=self._caption,
                accent_hex=self._accent_hex,
                alpha=self._alpha,
            )
            # Filter expired
            now = time.time()
            self._markers = [m for m in self._markers if not m.is_expired(now)]
            self._regions = [r for r in self._regions if not r.is_expired(now)]
            self._ripples = [rip for rip in self._ripples if not rip.is_expired()]
            self._overlay.view.set_markers(self._markers, self._regions, self._ripples)
            self._overlay.redraw()


# Global singleton instance
visual_cursor = ZoeVisualCursor()
