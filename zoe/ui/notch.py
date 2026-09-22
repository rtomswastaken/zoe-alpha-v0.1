"""Native macOS AppKit MacBook Notch Glow Overlay Window and Gradient View."""

import math
from typing import Optional, Tuple
from AppKit import (
    NSWindow,
    NSView,
    NSColor,
    NSScreen,
    NSBezierPath,
    NSGradient,
    NSPoint,
    NSRect,
    NSSize,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSGraphicsContext,
)
import objc
import Quartz
from zoe.config import get_config
from zoe.macos.logger import zoe_logger


class NotchGeometry:
    """Calculates exact physical notch bounds using native NSScreen auxiliary areas."""

    @staticmethod
    def get_notch_rect(screen: Optional[NSScreen] = None) -> NSRect:
        """
        Returns NSRect of the physical MacBook notch in Cocoa screen coordinates.
        If no notch is detected (external monitor or notchless Mac), falls back to top-center.
        """
        target_screen = screen or NSScreen.mainScreen()
        frame = target_screen.frame()

        # Check for notch via auxiliaryTopLeftArea / auxiliaryTopRightArea (macOS 12+)
        if hasattr(target_screen, "auxiliaryTopLeftArea") and hasattr(target_screen, "auxiliaryTopRightArea"):
            top_left = target_screen.auxiliaryTopLeftArea()
            top_right = target_screen.auxiliaryTopRightArea()

            # If both exist and leave a gap in between, that gap is the physical notch!
            if top_left.size.width > 0 and top_right.origin.x > top_left.size.width:
                notch_x = top_left.size.width
                notch_w = top_right.origin.x - top_left.size.width
                notch_h = max(top_left.size.height, top_right.size.height)
                notch_y = frame.size.height - notch_h
                return NSRect(NSPoint(notch_x, notch_y), NSSize(notch_w, notch_h))

        # Check safeAreaInsets
        if hasattr(target_screen, "safeAreaInsets"):
            insets = target_screen.safeAreaInsets()
            if insets.top > 0:
                notch_w = 220.0
                notch_h = insets.top
                notch_x = (frame.size.width - notch_w) / 2.0
                notch_y = frame.size.height - notch_h
                return NSRect(NSPoint(notch_x, notch_y), NSSize(notch_w, notch_h))

        # Fallback top-center
        notch_w = 200.0
        notch_h = 32.0
        notch_x = (frame.size.width - notch_w) / 2.0
        notch_y = frame.size.height - notch_h
        return NSRect(NSPoint(notch_x, notch_y), NSSize(notch_w, notch_h))


class ZoeNotchGlowView(NSView):
    """Custom Cocoa NSView that draws subtle animated gradients around the MacBook notch."""

    def initWithFrame_(self, frame: NSRect):
        self = objc.super(ZoeNotchGlowView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.notch_rect = NSRect(NSPoint(0, 0), NSSize(220, 38))
        self.state_name: str = "IDLE"
        self.alpha_level: float = 0.0
        self.pulse_phase: float = 0.0
        self.audio_amplitude: float = 0.0
        self.pitch_hz: float = 220.0
        return self

    def isOpaque(self) -> bool:
        return False

    def drawRect_(self, dirtyRect: NSRect) -> None:
        if self.alpha_level <= 0.001:
            return

        ctx = NSGraphicsContext.currentContext()
        if ctx is None:
            return

        cg_ctx = ctx.CGContext()
        Quartz.CGContextSaveGState(cg_ctx)

        # Calculate reactive glow parameters
        amp_boost = 1.0 + (self.audio_amplitude * 0.8)
        pulse = 0.5 + 0.5 * math.sin(self.pulse_phase)

        # Color definition based on state:
        # Default palette: Deep blue -> Cyan -> Violet -> Soft Purple
        if self.state_name == "LISTENING":
            # Calming Cyan / Blue breathing
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.85, 1.0, 0.75 * self.alpha_level * amp_boost)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.4, 0.95, 0.45 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.48, 0.12, 0.85, 0.0)
        elif self.state_name == "THINKING":
            # Shifting Violet / Indigo
            shift = math.sin(self.pulse_phase * 1.5)
            r = 0.4 + 0.2 * shift
            g = 0.2 + 0.2 * (1.0 - shift)
            c1 = NSColor.colorWithRed_green_blue_alpha_(r, g, 1.0, 0.8 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.5, 0.1, 0.8, 0.45 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.6, 0.0)
        elif self.state_name == "ACTING":
            # Active Cyan / Purple flowing wave
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.95, 0.8, 0.85 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.3, 0.2, 0.9, 0.5 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.5, 0.9, 0.0)
        elif self.state_name == "SPEAKING":
            # Dynamic voice-reactive Soft Purple / Magenta / Cyan
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.7, 0.35, 1.0, min(1.0, 0.85 * self.alpha_level * amp_boost))
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.85, 1.0, 0.55 * self.alpha_level * amp_boost)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.4, 0.1, 0.8, 0.0)
        else:
            # Default subtle glow
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.8, 1.0, 0.4 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.4, 0.1, 0.8, 0.2 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.5, 0.0)

        gradient = NSGradient.alloc().initWithColors_([c1, c2, c3])

        # Draw soft curved ribbon directly beneath the notch
        notch_bottom_y = self.notch_rect.origin.y
        center_x = self.notch_rect.origin.x + (self.notch_rect.size.width / 2.0)

        # Draw axial gradient downward from the notch bottom
        path = NSBezierPath.bezierPath()
        rx = self.notch_rect.origin.x - 14.0
        rw = self.notch_rect.size.width + 28.0
        ry = notch_bottom_y - (20.0 * amp_boost)
        rh = (self.notch_rect.size.height + (22.0 * amp_boost))

        pill_rect = NSRect(NSPoint(rx, ry), NSSize(rw, rh))
        path.appendBezierPathWithRoundedRect_xRadius_yRadius_(pill_rect, 14.0, 14.0)

        start_pt = NSPoint(center_x, notch_bottom_y + 10.0)
        end_pt = NSPoint(center_x, ry)
        gradient.drawInBezierPath_angle_(path, -90.0)

        Quartz.CGContextRestoreGState(cg_ctx)


from AppKit import NSThread, NSObject, NSApplication

class _UIBridge(NSObject):
    def applyVisuals_(self, params):
        overlay, state, alpha, pulse, amp, pitch = params
        overlay._apply_visuals_main(state, alpha, pulse, amp, pitch)

    def showWindow_(self, overlay):
        overlay.window.orderFrontRegardless()

    def hideWindow_(self, overlay):
        overlay.window.orderOut_(None)

_ui_bridge = _UIBridge.alloc().init()


class ZoeNotchOverlayWindow:
    """Non-activating, click-through borderless overlay window anchored to the MacBook notch."""

    def __init__(self) -> None:
        self.app = NSApplication.sharedApplication()
        self.screen = NSScreen.mainScreen()
        self.notch_rect = NotchGeometry.get_notch_rect(self.screen)

        # Spread padding around the notch for the glow
        cfg = get_config()
        self.spread = float(cfg.ui.notch.glow_spread)

        # Frame window around notch
        win_x = max(0.0, self.notch_rect.origin.x - self.spread)
        win_y = max(0.0, self.notch_rect.origin.y - self.spread)
        win_w = self.notch_rect.size.width + (2.0 * self.spread)
        win_h = self.notch_rect.size.height + self.spread + 10.0
        self.window_frame = NSRect(NSPoint(win_x, win_y), NSSize(win_w, win_h))

        # Notch rect in local view coordinates
        local_notch_rect = NSRect(
            NSPoint(self.spread, self.spread),
            self.notch_rect.size,
        )

        # Initialize NSWindow
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            self.window_frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )

        # Configure window: floating, click-through, non-focusing, transparent
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setHasShadow_(False)
        if hasattr(self.window, "setCanBecomeVisibleWithoutLogin_"):
            self.window.setCanBecomeVisibleWithoutLogin_(True)

        self.glow_view = ZoeNotchGlowView.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(win_w, win_h))
        )
        self.glow_view.notch_rect = local_notch_rect
        self.window.setContentView_(self.glow_view)
        self.window.orderOut_(None)

    def show(self) -> None:
        if NSThread.isMainThread():
            self.window.orderFrontRegardless()
        else:
            _ui_bridge.performSelectorOnMainThread_withObject_waitUntilDone_("showWindow:", self, False)

    def hide(self) -> None:
        if NSThread.isMainThread():
            self.window.orderOut_(None)
        else:
            _ui_bridge.performSelectorOnMainThread_withObject_waitUntilDone_("hideWindow:", self, False)

    def update_visuals(
        self,
        state: Any,
        alpha: float,
        pulse_phase: float,
        amplitude: float = 0.0,
        pitch: float = 220.0,
    ) -> None:
        if NSThread.isMainThread():
            self._apply_visuals_main(state, alpha, pulse_phase, amplitude, pitch)
        else:
            _ui_bridge.performSelectorOnMainThread_withObject_waitUntilDone_(
                "applyVisuals:",
                [self, state, alpha, pulse_phase, amplitude, pitch],
                False,
            )

    def _apply_visuals_main(
        self,
        state: Any,
        alpha: float,
        pulse_phase: float,
        amplitude: float = 0.0,
        pitch: float = 220.0,
    ) -> None:
        self.glow_view.state_name = getattr(state, "value", str(state))
        self.glow_view.alpha_level = alpha
        self.glow_view.pulse_phase = pulse_phase
        self.glow_view.audio_amplitude = amplitude
        self.glow_view.pitch_hz = pitch

        if alpha > 0.001:
            if not self.window.isVisible():
                self.window.orderFrontRegardless()
            self.glow_view.setNeedsDisplay_(True)
        else:
            if self.window.isVisible():
                self.window.orderOut_(None)


_notch_overlay_instance: Optional[ZoeNotchOverlayWindow] = None


def get_notch_overlay() -> ZoeNotchOverlayWindow:
    """Singleton getter for the MacBook Notch Overlay."""
    global _notch_overlay_instance
    if _notch_overlay_instance is None:
        _notch_overlay_instance = ZoeNotchOverlayWindow()
    return _notch_overlay_instance
