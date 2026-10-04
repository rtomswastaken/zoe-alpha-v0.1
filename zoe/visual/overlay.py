"""Native macOS transparent, click-through overlay window for Zoe's visual cursor."""

import math
import threading
import time
from typing import Dict, List, Optional, Tuple
from AppKit import (
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSObject,
    NSPoint,
    NSRect,
    NSScreen,
    NSScreenSaverWindowLevel,
    NSSize,
    NSThread,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
)
import objc
import Quartz
from zoe.visual.markers import ClickRipple, HighlightRegion, VisualMarker
from zoe.visual.state import VisualCursorSnapshot, VisualCursorState


class _UIThreadBridge(NSObject):
    """Helper bridging background Python threads cleanly onto Cocoa's main RunLoop."""

    def invokeBlock_(self, block) -> None:
        if callable(block):
            block()

    def setNeedsDisplay_(self, view) -> None:
        if view is not None:
            view.setNeedsDisplay_(True)

    def orderFront_(self, win) -> None:
        if win is not None:
            win.orderFrontRegardless()

    def orderOut_(self, win) -> None:
        if win is not None:
            win.orderOut_(None)


_ui_bridge = _UIThreadBridge.alloc().init()


def run_on_main_thread(fn, wait: bool = False) -> None:
    """Execute a callable on Cocoa's main thread."""
    if NSThread.isMainThread():
        fn()
    else:
        _ui_bridge.performSelectorOnMainThread_withObject_waitUntilDone_("invokeBlock:", fn, wait)


def hex_to_nscolor(hex_str: str, alpha: float = 1.0) -> NSColor:
    """Convert hex color string like '#00F0FF' to NSColor."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        r = int(clean[0:2], 16) / 255.0
        g = int(clean[2:4], 16) / 255.0
        b = int(clean[4:6], 16) / 255.0
        return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)
    return NSColor.colorWithRed_green_blue_alpha_(0.0, 0.94, 1.0, alpha)


class ZoeVisualOverlayView(NSView):
    """Custom transparent NSView drawing the visual cursor, markers, and ripples."""

    def initWithFrame_(self, frame: NSRect):
        self = objc.super(ZoeVisualOverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._cursor_x: float = 100.0
        self._cursor_y: float = 100.0
        self._state: VisualCursorState = VisualCursorState.HIDDEN
        self._label: str = "Zoe"
        self._caption: Optional[str] = None
        self._accent_hex: str = "#00F0FF"
        self._alpha: float = 1.0
        self._markers: List[VisualMarker] = []
        self._regions: List[HighlightRegion] = []
        self._ripples: List[ClickRipple] = []
        self._pulse_phase: float = 0.0
        return self

    def isOpaque(self) -> bool:
        return False

    def update_cursor(
        self,
        x: float,
        y: float,
        state: VisualCursorState,
        label: str,
        caption: Optional[str],
        accent_hex: str,
        alpha: float,
    ) -> None:
        self._cursor_x = x
        self._cursor_y = y
        self._state = state
        self._label = label
        self._caption = caption
        self._accent_hex = accent_hex
        self._alpha = alpha
        self._pulse_phase = (self._pulse_phase + 0.15) % (math.pi * 2.0)

    def set_markers(self, markers: List[VisualMarker], regions: List[HighlightRegion], ripples: List[ClickRipple]) -> None:
        self._markers = list(markers)
        self._regions = list(regions)
        self._ripples = list(ripples)

    def drawRect_(self, dirtyRect: NSRect) -> None:
        ctx = NSGraphicsContext.currentContext()
        if ctx is None:
            return

        cg = ctx.CGContext()
        Quartz.CGContextSaveGState(cg)

        bounds_h = self.bounds().size.height

        # 1. Draw Highlight Regions
        for r in self._regions:
            if r.is_expired():
                continue
            # Convert Quartz Y (top-down) to AppKit View Y (bottom-up)
            view_y = bounds_h - (r.y + r.height)
            rect = NSRect(NSPoint(r.x, view_y), NSSize(r.width, r.height))

            # Fill
            fill_color = hex_to_nscolor(r.accent_hex, r.fill_alpha)
            fill_color.setFill()
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 6.0, 6.0)
            path.fill()

            # Border
            stroke_color = hex_to_nscolor(r.accent_hex, 0.85)
            stroke_color.setStroke()
            path.setLineWidth_(r.line_width)
            path.stroke()

            # Region label
            if r.caption:
                self._draw_label_tag(r.x, view_y + r.height + 4.0, r.caption, r.accent_hex)

        # 2. Draw Visual Markers
        for m in self._markers:
            if m.is_expired():
                continue
            view_y = bounds_h - m.y
            center = NSPoint(m.x, view_y)

            # Outer glowing halo
            halo_color = hex_to_nscolor(m.accent_hex, 0.3)
            halo_color.setFill()
            halo_path = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(center.x - m.radius * 1.8, center.y - m.radius * 1.8), NSSize(m.radius * 3.6, m.radius * 3.6))
            )
            halo_path.fill()

            # Core marker dot
            core_color = hex_to_nscolor(m.accent_hex, 0.95)
            core_color.setFill()
            core_path = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(center.x - m.radius, center.y - m.radius), NSSize(m.radius * 2.0, m.radius * 2.0))
            )
            core_path.fill()

            # White center pip
            NSColor.whiteColor().setFill()
            pip_path = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(center.x - 2.5, center.y - 2.5), NSSize(5.0, 5.0))
            )
            pip_path.fill()

            if m.caption:
                self._draw_label_tag(m.x + m.radius + 6.0, view_y - 8.0, m.caption, m.accent_hex)

        # 3. Draw Click Ripples
        for rip in self._ripples:
            if rip.is_expired():
                continue
            rad = rip.current_radius
            alpha = rip.current_alpha
            view_y = bounds_h - rip.y
            rip_color = hex_to_nscolor(rip.accent_hex, alpha * 0.9)
            rip_color.setStroke()
            rip_path = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(rip.x - rad, view_y - rad), NSSize(rad * 2.0, rad * 2.0))
            )
            rip_path.setLineWidth_(2.2)
            rip_path.stroke()

        # 4. Draw Zoe Visual Cursor
        if self._state != VisualCursorState.HIDDEN and self._alpha > 0.01:
            self._draw_cursor(cg, bounds_h)

        Quartz.CGContextRestoreGState(cg)

    def _draw_cursor(self, cg, bounds_h: float) -> None:
        """Render the modern glowing AI assistant pointer and pill tag."""
        # Convert Quartz point coordinates to AppKit View coordinate space
        vx = self._cursor_x
        vy = bounds_h - self._cursor_y
        accent = self._accent_hex
        alpha = self._alpha

        # If TARGETED or CLICKING, add pulse aura
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
        if self._state == VisualCursorState.TARGETED:
            # Pulsing target reticle
            ring_rad = 18.0 + 4.0 * pulse
            ring_color = hex_to_nscolor(accent, 0.6 * alpha)
            ring_color.setStroke()
            r_path = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(vx - ring_rad, vy - ring_rad), NSSize(ring_rad * 2.0, ring_rad * 2.0))
            )
            r_path.setLineWidth_(2.0)
            r_path.stroke()

        # Pointer chevron geometry: Tip is at (vx, vy), extends down-right in View space
        pointer = NSBezierPath.bezierPath()
        tip = NSPoint(vx, vy)
        p_right = NSPoint(vx + 18.0, vy - 10.0)
        p_notch = NSPoint(vx + 12.0, vy - 12.0)
        p_bottom = NSPoint(vx + 7.0, vy - 21.0)

        pointer.moveToPoint_(tip)
        pointer.lineToPoint_(p_right)
        pointer.lineToPoint_(p_notch)
        pointer.lineToPoint_(p_bottom)
        pointer.closePath()

        # Outer glowing halo
        halo_color = hex_to_nscolor(accent, 0.45 * alpha)
        halo_color.setStroke()
        pointer.setLineWidth_(4.0)
        pointer.stroke()

        # Dark sleek body fill
        NSColor.colorWithRed_green_blue_alpha_(0.05, 0.07, 0.12, 0.95 * alpha).setFill()
        pointer.fill()

        # Neon accent stroke
        hex_to_nscolor(accent, 0.95 * alpha).setStroke()
        pointer.setLineWidth_(1.8)
        pointer.stroke()

        # Tip jewel
        hex_to_nscolor(accent, 1.0 * alpha).setFill()
        tip_dot = NSBezierPath.bezierPathWithOvalInRect_(
            NSRect(NSPoint(vx - 2.0, vy - 2.0), NSSize(4.0, 4.0))
        )
        tip_dot.fill()

        # Label tag (Pill next to cursor: "Zoe" + optional caption)
        label_text = self._label
        if self._caption:
            label_text = f"{self._label}: {self._caption}"
        self._draw_label_tag(vx + 16.0, vy - 28.0, label_text, accent, alpha)

    def _draw_label_tag(self, x: float, y: float, text: str, accent_hex: str, alpha: float = 1.0) -> None:
        """Render a clean glassmorphic pill badge with neon border."""
        font = NSFont.systemFontOfSize_weight_(11.0, 600)
        attrs = {
            NSFontAttributeName: font,
            NSForegroundColorAttributeName: NSColor.whiteColor(),
        }
        attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
        text_size = attr_str.size()

        pad_x = 8.0
        pad_y = 4.0
        badge_w = text_size.width + (pad_x * 2.0)
        badge_h = text_size.height + (pad_y * 2.0)
        badge_rect = NSRect(NSPoint(x, y), NSSize(badge_w, badge_h))

        # Backdrop
        bg = NSColor.colorWithRed_green_blue_alpha_(0.08, 0.10, 0.16, 0.88 * alpha)
        bg.setFill()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(badge_rect, 6.0, 6.0)
        path.fill()

        # Neon border
        hex_to_nscolor(accent_hex, 0.75 * alpha).setStroke()
        path.setLineWidth_(1.2)
        path.stroke()

        # Text draw
        text_point = NSPoint(x + pad_x, y + pad_y - 1.0)
        attr_str.drawAtPoint_(text_point)


class VisualCursorOverlayWindow:
    """Manages the lifecycle, positioning, and rendering of the native macOS overlay window."""

    def __init__(self) -> None:
        self.window: Optional[NSWindow] = None
        self.view: Optional[ZoeVisualOverlayView] = None
        self._is_ready: bool = False
        self._init_lock = threading.Lock()
        self._setup_window()

    def _setup_window(self) -> None:
        """Construct the transparent, non-activating, click-through NSWindow."""
        def _build():
            try:
                # Cover primary screen or desktop bounds
                main_screen = NSScreen.mainScreen()
                if main_screen is None:
                    return
                frame = main_screen.frame()

                win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                    frame,
                    NSWindowStyleMaskBorderless,
                    NSBackingStoreBuffered,
                    False,
                )

                win.setLevel_(NSScreenSaverWindowLevel)
                win.setIgnoresMouseEvents_(True)  # STRICT CLICK-THROUGH
                win.setOpaque_(False)
                win.setBackgroundColor_(NSColor.clearColor())
                win.setHasShadow_(False)
                win.setCollectionBehavior_(
                    NSWindowCollectionBehaviorCanJoinAllSpaces |
                    NSWindowCollectionBehaviorStationary |
                    NSWindowCollectionBehaviorIgnoresCycle |
                    NSWindowCollectionBehaviorFullScreenAuxiliary
                )

                view = ZoeVisualOverlayView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), frame.size))
                win.setContentView_(view)
                win.orderOut_(None)

                self.window = win
                self.view = view
                self._is_ready = True
            except Exception:
                self._is_ready = False

        run_on_main_thread(_build, wait=True)

    def show(self) -> None:
        if not self._is_ready or self.window is None:
            return
        def _show():
            self.window.orderFrontRegardless()
        run_on_main_thread(_show, wait=False)

    def hide(self) -> None:
        if not self._is_ready or self.window is None:
            return
        def _hide():
            self.window.orderOut_(None)
        run_on_main_thread(_hide, wait=False)

    def redraw(self) -> None:
        if not self._is_ready or self.view is None:
            return
        def _draw():
            self.view.setNeedsDisplay_(True)
        run_on_main_thread(_draw, wait=False)
