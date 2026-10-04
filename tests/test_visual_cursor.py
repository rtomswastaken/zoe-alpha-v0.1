"""Comprehensive automated tests for Zoe's independent visual cursor subsystem."""

import os
import re
import time
from unittest.mock import MagicMock, patch
import pytest

from zoe.macos.cursor import get_cursor_position
from zoe.macos.emergency import emergency_controller
from zoe.macos.mouse import mouse_click
from zoe.tools.registry import tool_registry
from zoe.visual.cursor import visual_cursor
from zoe.visual.state import VisualCursorState


def test_1_visual_movement_leaves_real_mouse_untouched() -> None:
    """
    Test 1 — Visual movement:
    Moving the Zoe visual cursor changes its visual position
    while leaving the real macOS mouse cursor completely stationary.
    """
    real_before = get_cursor_position()
    visual_cursor.clear()

    # Move visual cursor to a specific coordinate
    visual_cursor.move_to(450.0, 320.0, caption="Test Target")

    assert visual_cursor.position == (450.0, 320.0)
    assert visual_cursor.state == VisualCursorState.GUIDING

    real_after = get_cursor_position()
    assert real_before == real_after, f"Real mouse moved from {real_before} to {real_after}!"
    visual_cursor.clear()


def test_2_click_through_overlay_window() -> None:
    """
    Test 2 — Click-through:
    Overlay window must be mouse-transparent (ignoresMouseEvents == True),
    borderless, non-activating, and unable to steal focus.
    """
    win = visual_cursor.overlay.window
    if win is not None:
        assert win.ignoresMouseEvents() is True, "Overlay window must ignore all mouse events"
        assert win.canBecomeKeyWindow() is False, "Overlay window must never become key window"
        assert win.canBecomeMainWindow() is False, "Overlay window must never become main window"
        assert win.isOpaque() is False, "Overlay window must be transparent/non-opaque"


def test_3_no_cgwarp_in_visual_subsystem() -> None:
    """
    Test 3 — No CGWarp:
    Verify that the visual subsystem (zoe/visual/) contains ZERO executable code calls to
    CGWarpMouseCursorPosition, NSCursor.setPosition, or real pointer warping APIs.
    """
    visual_dir = os.path.join(os.path.dirname(__file__), "..", "zoe", "visual")
    # Code invocation regexes (not mere mentions in comments or docstrings)
    forbidden_code_patterns = [
        re.compile(r"^\s*[^#\n]*CGWarpMouseCursorPosition\s*\(", re.MULTILINE),
        re.compile(r"^\s*[^#\n]*NSCursor\.setPosition\s*\(", re.MULTILINE),
        re.compile(r"^\s*[^#\n]*CGEventCreateMouseEvent\s*\(", re.MULTILINE),
    ]

    for root, _, files in os.walk(visual_dir):
        for f in files:
            if f.endswith(".py"):
                file_path = os.path.join(root, f)
                with open(file_path, "r", encoding="utf-8") as py_file:
                    lines = py_file.readlines()
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line.startswith("#") or clean_line.startswith('"""') or clean_line.startswith("'''"):
                            continue
                        for pattern in forbidden_code_patterns:
                            matches = pattern.findall(clean_line)
                            assert not matches, (
                                f"Forbidden pointer manipulation '{clean_line}' found in {f}!"
                            )


def test_4_retina_coordinate_mapping() -> None:
    """
    Test 4 — Retina coordinates:
    Verify 2x Retina display mapping: Retina pixel space vs AppKit/Quartz point space.
    """
    from zoe.macos.coordinates import ImageTransformMetadata, vision_to_screen_points

    meta = ImageTransformMetadata.create(
        point_width=2056.0,
        point_height=1329.0,
        pixel_width=4112,
        pixel_height=2658,
        vision_width=1024,
        vision_height=662,
        scale_factor=2.0,
    )

    # Check scaling calculation
    assert meta.backing_scale_factor == 2.0
    assert meta.original_pixel_width == meta.original_point_width * 2.0
    assert meta.original_pixel_height == meta.original_point_height * 2.0

    # Test center point mapping from vision downscale to logical points
    pt_x, pt_y = vision_to_screen_points(512.0, 331.0, meta)
    assert abs(pt_x - 1028.0) <= 2.0
    assert abs(pt_y - 664.5) <= 2.0


def test_5_multi_monitor_and_negative_coordinates() -> None:
    """
    Test 5 — Multi-monitor:
    Verify handling of negative or secondary display coordinates.
    """
    visual_cursor.clear()

    # Move visual cursor to a secondary monitor positioned to the left (negative X)
    visual_cursor.move_to(-800.0, 450.0, caption="Left Monitor")
    assert visual_cursor.position == (-800.0, 450.0)

    # Move to a monitor above primary (negative Quartz Y or high offset)
    visual_cursor.move_to(500.0, -300.0, caption="Top Monitor")
    assert visual_cursor.position == (500.0, -300.0)

    visual_cursor.clear()


def test_6_visual_state_transitions() -> None:
    """
    Test 6 — Visual states:
    Verify transitions across HIDDEN, IDLE, GUIDING, TARGETED, CLICKING, ACTING, DONE.
    """
    visual_cursor.clear()
    assert visual_cursor.state == VisualCursorState.HIDDEN

    # IDLE
    visual_cursor.idle()
    assert visual_cursor.state == VisualCursorState.IDLE

    # GUIDING
    visual_cursor.move_to(300.0, 300.0)
    assert visual_cursor.state == VisualCursorState.GUIDING

    # TARGETED
    visual_cursor.target(300.0, 300.0, caption="Target Element")
    assert visual_cursor.state == VisualCursorState.TARGETED

    # CLICKING
    visual_cursor.click_effect(300.0, 300.0)
    assert visual_cursor.state == VisualCursorState.CLICKING

    # ACTING
    visual_cursor.acting_effect(300.0, 300.0)
    assert visual_cursor.state == VisualCursorState.ACTING

    # DONE
    visual_cursor.done_effect()
    assert visual_cursor.state == VisualCursorState.DONE

    # HIDDEN
    visual_cursor.clear()
    assert visual_cursor.state == VisualCursorState.HIDDEN


def test_7_emergency_stop_aborts_visual_animation() -> None:
    """
    Test 7 — Emergency stop:
    Pressing ESC (or triggering emergency_controller) must immediately abort
    visual animation and reset the cursor overlay to hidden.
    """
    emergency_controller.reset()
    try:
        visual_cursor.move_to(200.0, 200.0)
        assert visual_cursor.state != VisualCursorState.HIDDEN

        # Start a smooth glide
        visual_cursor.move_smoothly_to(900.0, 900.0, duration=2.0, blocking=False)

        # Immediately trigger emergency stop
        emergency_controller.trigger("TEST_ESC")

        time.sleep(0.1)
        assert visual_cursor.state == VisualCursorState.HIDDEN
        assert len(visual_cursor.markers) == 0
    finally:
        emergency_controller.reset()


def test_8_openclicky_unavailable_graceful_degradation() -> None:
    """
    Test 8 — OpenClicky unavailable:
    When OpenClicky bridge is offline, Zoe continues functioning,
    visual tools degrade gracefully to Zoe's native overlay, and native control is unaffected.
    """
    emergency_controller.reset()
    from zoe.integrations.openclicky.tools import OpenClickyPointTool, OpenClickyClearTool

    # In production without an injected mock client, PointTool gracefully falls back to native overlay
    pt_tool = OpenClickyPointTool()
    res = pt_tool.execute(x=600.0, y=400.0, caption="Offline Test")

    assert res["success"] is True
    assert visual_cursor.position == (600.0, 400.0)

    clr_tool = OpenClickyClearTool()
    clr_res = clr_tool.execute()
    assert clr_res["success"] is True
    assert visual_cursor.state == VisualCursorState.HIDDEN


def test_9_actual_computer_action_independence() -> None:
    """
    Test 9 — Actual computer action:
    Verify that native click/action functionality still works independently
    from visual cursor movement.
    """
    emergency_controller.reset()
    visual_cursor.clear()
    visual_cursor.move_to(100.0, 100.0)

    # Actual click invokes Quartz CGEvent, independent of visual cursor
    with patch("zoe.macos.mouse.Quartz.CGEventCreateMouseEvent") as mock_event:
        with patch("zoe.macos.mouse.Quartz.CGEventPost"):
            clicked = mouse_click(800.0, 500.0)
            assert clicked == (800.0, 500.0)
            mock_event.assert_called()

    # Visual cursor was NOT forced to (800, 500) simply by mouse_click
    assert visual_cursor.position == (100.0, 100.0)
    visual_cursor.clear()


def test_10_cursor_independence_a_to_d() -> None:
    """
    Test 10 — Independence (The Crucial Acceptance Test):
    Place real cursor at A.
    Move Zoe visual cursor: A -> B -> C -> D.
    Assert:
    real cursor == A
    visual cursor == D
    """
    emergency_controller.reset()
    visual_cursor.clear()
    pos_a = get_cursor_position()

    pos_b = (pos_a[0] + 120.0, pos_a[1] + 80.0)
    pos_c = (pos_a[0] - 150.0, pos_a[1] + 140.0)
    pos_d = (pos_a[0] + 50.0, pos_a[1] - 110.0)

    # Move visual cursor through path
    visual_cursor.move_to(pos_a[0], pos_a[1], caption="Start at A")
    assert visual_cursor.position == (pos_a[0], pos_a[1])

    visual_cursor.move_to(pos_b[0], pos_b[1], caption="Way B")
    assert visual_cursor.position == pos_b

    visual_cursor.move_to(pos_c[0], pos_c[1], caption="Way C")
    assert visual_cursor.position == pos_c

    visual_cursor.move_to(pos_d[0], pos_d[1], caption="Final D")
    assert visual_cursor.position == pos_d

    # Critical Assertion: Real macOS cursor NEVER moved from position A!
    real_after = get_cursor_position()
    assert real_after == pos_a, f"Real cursor moved! Expected {pos_a}, but was {real_after}"
    assert visual_cursor.position == pos_d, f"Visual cursor should be at {pos_d}"

    visual_cursor.clear()
