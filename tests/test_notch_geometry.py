"""Unit tests for NotchGeometry and ZoeNotchOverlayWindow."""

import pytest
from AppKit import NSScreen, NSRect, NSPoint, NSSize
from zoe.ui.notch import NotchGeometry, get_notch_overlay


def test_notch_geometry_detection():
    screen = NSScreen.mainScreen()
    notch = NotchGeometry.get_notch_rect(screen)

    assert notch.size.width > 0
    assert notch.size.height > 0
    assert notch.origin.x >= 0
    assert notch.origin.y >= 0

    # On this MacBook Pro, width is approximately 220pt and height is 38pt
    assert 150.0 <= notch.size.width <= 300.0
    assert 20.0 <= notch.size.height <= 50.0


def test_notch_overlay_initialization():
    overlay = get_notch_overlay()
    assert overlay is not None
    assert overlay.window is not None

    # Check window flags: borderless, click-through, non-focusing
    assert overlay.window.ignoresMouseEvents() is True
    assert overlay.window.isOpaque() is False

    # Check glow view
    assert overlay.glow_view is not None
    assert overlay.glow_view.isOpaque() is False
