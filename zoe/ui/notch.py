"""Native macOS AppKit MacBook Notch Glow Overlay Window and Gradient View."""

import math
import time
from typing import Any, Optional, Tuple
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSDate,
    NSDefaultRunLoopMode,
    NSEventMaskAny,
    NSFloatingWindowLevel,
    NSGradient,
    NSGraphicsContext,
    NSObject,
    NSPoint,
    NSRect,
    NSScreen,
    NSSize,
    NSStatusWindowLevel,
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
from zoe.config import get_config
from zoe.macos.logger import zoe_logger


def pump_cocoa_events(duration: float = 0.02) -> None:
    """Pump AppKit event loop and flush display changes to the physical screen."""
    app = NSApplication.sharedApplication()
    limit = time.time() + duration
    while time.time() < limit:
        event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            NSEventMaskAny,
            NSDate.dateWithTimeIntervalSinceNow_(0.005),
            NSDefaultRunLoopMode,
            True,
        )
        if event:
            app.sendEvent_(event)
    app.updateWindows()


class NotchGeometry:
    """Calculates exact physical notch bounds using native NSScreen auxiliary areas."""

    @staticmethod
    def get_notch_screen() -> NSScreen:
        """Find the screen that physically has the MacBook notch, or fallback to mainScreen."""
        for s in NSScreen.screens():
            if hasattr(s, "safeAreaInsets") and s.safeAreaInsets().top > 0:
                return s
            if hasattr(s, "auxiliaryTopLeftArea") and hasattr(s, "auxiliaryTopRightArea"):
                tl = s.auxiliaryTopLeftArea()
                tr = s.auxiliaryTopRightArea()
                if tl.size.width > 0 and tr.origin.x > tl.size.width:
                    return s
            if "built-in" in s.localizedName().lower():
                return s
        return NSScreen.mainScreen()

    @staticmethod
    def get_notch_rect(screen: Optional[NSScreen] = None) -> NSRect:
        """
        Returns NSRect of the physical MacBook notch in Cocoa screen coordinates.
        If no notch is detected (external monitor or notchless Mac), falls back to top-center.
        """
        target_screen = screen or NotchGeometry.get_notch_screen()
        frame = target_screen.frame()

        # Check for notch via auxiliaryTopLeftArea / auxiliaryTopRightArea (macOS 12+)
        if hasattr(target_screen, "auxiliaryTopLeftArea") and hasattr(target_screen, "auxiliaryTopRightArea"):
            top_left = target_screen.auxiliaryTopLeftArea()
            top_right = target_screen.auxiliaryTopRightArea()

            if top_left.size.width > 0 and top_right.origin.x > top_left.size.width:
                notch_x = frame.origin.x + top_left.size.width
                notch_w = top_right.origin.x - top_left.size.width
                notch_h = max(top_left.size.height, top_right.size.height)
                notch_y = frame.origin.y + frame.size.height - notch_h
                return NSRect(NSPoint(notch_x, notch_y), NSSize(notch_w, notch_h))

        # Check safeAreaInsets
        if hasattr(target_screen, "safeAreaInsets"):
            insets = target_screen.safeAreaInsets()
            if insets.top > 0:
                notch_w = 220.0
                notch_h = insets.top
                notch_x = frame.origin.x + (frame.size.width - notch_w) / 2.0
                notch_y = frame.origin.y + frame.size.height - notch_h
                return NSRect(NSPoint(notch_x, notch_y), NSSize(notch_w, notch_h))

        # Fallback top-center
        notch_w = 200.0
        notch_h = 32.0
        notch_x = frame.origin.x + (frame.size.width - notch_w) / 2.0
        notch_y = frame.origin.y + frame.size.height - notch_h
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

        state = self.state_name.upper()

        # Debug mode: unmistakable bright outline + semi-transparent fill for physical QA
        if state == "DEBUG":
            fill_rect = NSRect(
                NSPoint(self.notch_rect.origin.x - 30.0, max(0.0, self.notch_rect.origin.y - 35.0)),
                NSSize(self.notch_rect.size.width + 60.0, 50.0),
            )
            NSColor.colorWithRed_green_blue_alpha_(1.0, 0.05, 0.55, 0.80).setFill()
            fill_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(fill_rect, 12.0, 12.0)
            fill_path.fill()
            NSColor.colorWithRed_green_blue_alpha_(0.0, 1.0, 1.0, 1.0).setStroke()
            fill_path.setLineWidth_(4.0)
            fill_path.stroke()
            Quartz.CGContextRestoreGState(cg_ctx)
            return

        # Calculate reactive glow parameters
        amp_boost = 1.0 + (self.audio_amplitude * 0.95)
        pulse = 0.5 + 0.5 * math.sin(self.pulse_phase)

        # Color definition based on state:
        if state == "STARTUP":
            # Welcome bloom: radiant Electric Cyan to Royal Violet expanding flare
            shift = 0.5 + 0.5 * math.sin(self.pulse_phase)
            c1 = NSColor.colorWithRed_green_blue_alpha_(
                0.0, 0.95, 1.0, min(1.0, 0.98 * self.alpha_level * (0.8 + 0.2 * shift))
            )
            c2 = NSColor.colorWithRed_green_blue_alpha_(
                0.60, 0.15, 1.0, min(1.0, 0.85 * self.alpha_level)
            )
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.15, 0.05, 0.8, 0.0)

        elif state == "LISTENING":
            # Radiant Electric Cyan / Cobalt Blue breathing with audio reactivity
            pulse_mod = 0.8 + 0.2 * pulse
            c1 = NSColor.colorWithRed_green_blue_alpha_(
                0.0, 0.95, 1.0, min(1.0, 0.95 * self.alpha_level * amp_boost * pulse_mod)
            )
            c2 = NSColor.colorWithRed_green_blue_alpha_(
                0.0, 0.45, 1.0, 0.65 * self.alpha_level * pulse_mod
            )
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.0, 0.8, 0.0)

        elif state == "THINKING":
            # Shifting Electric Violet / Royal Indigo flowing wave
            shift = 0.5 + 0.5 * math.sin(self.pulse_phase * 2.2)
            r = 0.55 + 0.35 * shift
            g = 0.05 + 0.15 * (1.0 - shift)
            c1 = NSColor.colorWithRed_green_blue_alpha_(r, g, 1.0, 0.95 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.38, 0.08, 0.88, 0.60 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.15, 0.0, 0.5, 0.0)

        elif state == "ACTING":
            # Energetic Turquoise / Vibrant Emerald / Violet pulse wave
            shift = 0.5 + 0.5 * math.sin(self.pulse_phase * 3.0)
            g = 0.80 + 0.20 * shift
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.0, g, 0.85, 0.98 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.3, 0.15, 0.95, 0.65 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.3, 0.8, 0.0)

        elif state in ("SPEAKING", "RESPONDING"):
            # Dynamic voice-reactive Hot Magenta / Electric Cyan
            pulse_mod = 0.85 + 0.15 * pulse
            c1 = NSColor.colorWithRed_green_blue_alpha_(
                1.0, 0.0, 0.55, min(1.0, 0.98 * self.alpha_level * amp_boost * pulse_mod)
            )
            c2 = NSColor.colorWithRed_green_blue_alpha_(
                0.0, 0.9, 1.0, min(1.0, 0.70 * self.alpha_level * amp_boost)
            )
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.4, 0.0, 0.8, 0.0)

        elif state == "SUCCESS":
            # Radiant Mint Emerald confirmation glow
            pulse_mod = 0.85 + 0.15 * pulse
            c1 = NSColor.colorWithRed_green_blue_alpha_(
                0.06, 0.78, 0.51, min(1.0, 0.98 * self.alpha_level * pulse_mod)
            )
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.20, 0.85, 0.60, 0.60 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.02, 0.40, 0.25, 0.0)

        elif state == "ERROR":
            # Warm Amber / Soft Coral Red warning pulse
            rapid_pulse = 0.5 + 0.5 * math.sin(self.pulse_phase * 4.0)
            c1 = NSColor.colorWithRed_green_blue_alpha_(
                0.94, 0.27, 0.27, min(1.0, 0.98 * self.alpha_level * (0.7 + 0.3 * rapid_pulse))
            )
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.96, 0.62, 0.04, 0.65 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.50, 0.0, 0.0, 0.0)

        elif state == "STOPPING":
            # Immediate stopping collapse
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.4, 0.4, 0.5, 0.4 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.2, 0.1 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.0, 0.0, 0.0)

        else:
            # Default IDLE / ambient ready: subtle, communicates "Zoe is awake"
            c1 = NSColor.colorWithRed_green_blue_alpha_(0.0, 0.90, 1.0, 0.65 * self.alpha_level)
            c2 = NSColor.colorWithRed_green_blue_alpha_(0.15, 0.35, 0.9, 0.35 * self.alpha_level)
            c3 = NSColor.colorWithRed_green_blue_alpha_(0.05, 0.0, 0.4, 0.0)

        gradient = NSGradient.alloc().initWithColors_([c1, c2, c3])

        # Draw radiant glowing aura below the notch into visible screen
        notch_bottom_y = self.notch_rect.origin.y
        center_x = self.notch_rect.origin.x + (self.notch_rect.size.width / 2.0)

        if state == "STARTUP":
            shift = 0.5 + 0.5 * math.sin(self.pulse_phase)
            glow_spread_h = 44.0 + (16.0 * shift)
            padding_x = 42.0
        elif state == "IDLE":
            glow_spread_h = 22.0
            padding_x = 24.0
        else:
            glow_spread_h = 38.0 + (24.0 * (amp_boost - 1.0))
            padding_x = 30.0

        # Bottom rim glow ribbon wrapping around notch edges
        rx = max(0.0, self.notch_rect.origin.x - padding_x)
        rw = self.notch_rect.size.width + (padding_x * 2.0)
        ry = max(0.0, notch_bottom_y - glow_spread_h)
        rh = glow_spread_h + 12.0

        pill_rect = NSRect(NSPoint(rx, ry), NSSize(rw, rh))
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(pill_rect, 20.0, 20.0)
        gradient.drawInBezierPath_angle_(path, -90.0)

        # Crisp glowing neon border contour directly hugging the bottom notch curve
        rim_path = NSBezierPath.bezierPath()
        notch_l = self.notch_rect.origin.x
        notch_r = notch_l + self.notch_rect.size.width
        notch_b = self.notch_rect.origin.y
        rim_path.moveToPoint_(NSPoint(notch_l, notch_b + 14.0))
        rim_path.appendBezierPathWithArcFromPoint_toPoint_radius_(
            NSPoint(notch_l, notch_b),
            NSPoint(notch_l + 14.0, notch_b),
            12.0,
        )
        rim_path.lineToPoint_(NSPoint(notch_r - 14.0, notch_b))
        rim_path.appendBezierPathWithArcFromPoint_toPoint_radius_(
            NSPoint(notch_r, notch_b),
            NSPoint(notch_r, notch_b + 14.0),
            12.0,
        )
        rim_width = 1.2 if state == "IDLE" else (2.6 if state == "STARTUP" else 2.2)
        rim_path.setLineWidth_(rim_width)
        c1.setStroke()
        rim_path.stroke()

        # If ACTING: Draw energetic flowing pulse segment traveling across the bottom edge
        if state == "ACTING":
            flow_t = (self.pulse_phase * 2.5) % (math.pi * 2)
            norm_x = (math.sin(flow_t) + 1.0) / 2.0
            pulse_x = notch_l + 20.0 + (norm_x * (self.notch_rect.size.width - 40.0))
            dot = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(pulse_x - 3.0, notch_b - 3.0), NSSize(6.0, 6.0))
            )
            NSColor.whiteColor().setFill()
            dot.fill()
        elif state == "STARTUP":
            # Central radiant accent point during welcome bloom
            dot = NSBezierPath.bezierPathWithOvalInRect_(
                NSRect(NSPoint(center_x - 3.5, notch_b - 3.5), NSSize(7.0, 7.0))
            )
            NSColor.whiteColor().setFill()
            dot.fill()

        Quartz.CGContextRestoreGState(cg_ctx)


class _UIBridge(NSObject):
    def applyVisuals_(self, params):
        overlay, state, alpha, pulse, amp, pitch = params
        overlay._apply_visuals_main(state, alpha, pulse, amp, pitch)

    def showWindow_(self, overlay):
        overlay.window.orderFrontRegardless()

    def hideWindow_(self, overlay):
        overlay.window.orderOut_(None)

    def initOverlay_(self, _):
        global _notch_overlay_instance
        if _notch_overlay_instance is None:
            _notch_overlay_instance = ZoeNotchOverlayWindow()


_ui_bridge = _UIBridge.alloc().init()


class ZoeNotchOverlayWindow:
    """Non-activating, click-through borderless overlay window anchored to the MacBook notch."""

    def __init__(self) -> None:
        self.app = NSApplication.sharedApplication()
        if hasattr(self.app, "setActivationPolicy_"):
            self.app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        if hasattr(self.app, "finishLaunching"):
            self.app.finishLaunching()

        self.screen = NotchGeometry.get_notch_screen()
        frame = self.screen.frame()
        self.notch_rect = NotchGeometry.get_notch_rect(self.screen)

        # Window dimensions: wide enough to frame notch wings + deep enough to glow below
        win_w = max(340.0, self.notch_rect.size.width + 120.0)
        win_h = self.notch_rect.size.height + 65.0
        win_x = frame.origin.x + (frame.size.width - win_w) / 2.0
        win_y = frame.origin.y + frame.size.height - win_h
        self.window_frame = NSRect(NSPoint(win_x, win_y), NSSize(win_w, win_h))

        # Notch rect in local view coordinates (bottom of notch is at win_h - notch_h)
        local_notch_x = (win_w - self.notch_rect.size.width) / 2.0
        local_notch_y = win_h - self.notch_rect.size.height
        local_notch_rect = NSRect(
            NSPoint(local_notch_x, local_notch_y),
            self.notch_rect.size,
        )

        # Initialize NSWindow
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            self.window_frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )

        # Configure window: Status level + 2 (above menu bar and full-screen apps), non-focusing, transparent
        self.window.setLevel_(NSStatusWindowLevel + 2)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setHasShadow_(False)
        self.window.setHidesOnDeactivate_(False)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorStationary |
            NSWindowCollectionBehaviorIgnoresCycle |
            NSWindowCollectionBehaviorFullScreenAuxiliary
        )
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
            self.window.orderFrontRegardless()
            self.glow_view.setNeedsDisplay_(True)
            self.glow_view.displayIfNeeded()
        else:
            if self.window.isVisible():
                self.window.orderOut_(None)


_notch_overlay_instance: Optional[ZoeNotchOverlayWindow] = None


def get_notch_overlay() -> ZoeNotchOverlayWindow:
    """Singleton getter for the MacBook Notch Overlay (thread-safe, main-thread guaranteed)."""
    global _notch_overlay_instance
    if _notch_overlay_instance is None:
        if NSThread.isMainThread():
            _notch_overlay_instance = ZoeNotchOverlayWindow()
        else:
            _ui_bridge.performSelectorOnMainThread_withObject_waitUntilDone_(
                "initOverlay:", None, True
            )
    return _notch_overlay_instance
