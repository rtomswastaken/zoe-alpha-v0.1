"""End-to-end integration tests verifying cursorless computer control and physical cursor immobility."""

from unittest.mock import MagicMock, patch
import pytest
from zoe.macos.cursor import get_cursor_position
from zoe.tools.registry import tool_registry
from zoe.tools.computer import MoveCursorTool, ClickTool, DoubleClickTool, RightClickTool, DragTool
from zoe.tools.applications import OpenAppTool, FocusAppTool
from zoe.visual.cursor import visual_cursor
from zoe.visual.state import VisualCursorState


def test_physical_cursor_immobility_during_full_agent_workflow() -> None:
    """
    Requirement 10: Real End-to-End Cursor Test
    Before Zoe starts: physical cursor = A.
    Zoe performs multiple actions:
      1. open application / focus
      2. move visual cursor
      3. type text
      4. activate element via accessibility
      5. visual guidance
    During and after the entire process:
      physical cursor must remain A.
    """
    initial_x, initial_y = get_cursor_position()
    visual_cursor.clear()

    with patch("zoe.macos.apps.launch_app", return_value={"success": True, "action": "launch_app", "name": "Safari"}) as mock_launch, \
         patch("zoe.macos.keyboard.Quartz.CGEventPost"), \
         patch("zoe.tools.computer.ax_click_at", return_value=(True, "Activated via AXPress")):

        # 1. Open / Focus Application
        open_tool = tool_registry.get("open_app")
        assert open_tool is not None
        open_res = open_tool.execute(app_name="Safari")
        assert open_res["success"] is True
        assert get_cursor_position() == (initial_x, initial_y)

        # 2. Visual cursor movement (moves visual cursor only, physical stationary)
        move_tool = tool_registry.get("move_cursor")
        assert move_tool is not None
        move_res = move_tool.execute(x=950.0, y=420.0, duration=0.01)
        assert move_res["success"] is True
        assert visual_cursor.position == (950.0, 420.0)
        assert get_cursor_position() == (initial_x, initial_y)

        # 3. Type text
        type_tool = tool_registry.get("type_text")
        assert type_tool is not None
        type_res = type_tool.execute(text="https://apple.com")
        assert type_res["success"] is True
        assert get_cursor_position() == (initial_x, initial_y)

        # 4. Activate button / element via Accessibility
        click_tool = tool_registry.get("click")
        assert click_tool is not None
        click_res = click_tool.execute(x=950.0, y=420.0)
        assert click_res["success"] is True
        assert click_res["method"] == "accessibility"
        assert get_cursor_position() == (initial_x, initial_y)

        # 5. Another action: visual target and caption
        visual_cursor.target(200.0, 300.0, caption="Inspecting element")
        assert visual_cursor.position == (200.0, 300.0)
        assert get_cursor_position() == (initial_x, initial_y)

    # Final assertion: physical cursor remains exactly at A
    final_x, final_y = get_cursor_position()
    assert (final_x, final_y) == (initial_x, initial_y)
    visual_cursor.clear()


def test_visual_cursor_independence_a_to_e() -> None:
    """
    Requirement 11: Visual Cursor Independence
    physical cursor = A
    visual cursor: A -> B -> C -> D -> E
    Expected:
      physical cursor == A
      visual cursor == E
      The two positions must be stored independently.
    """
    initial_pos = get_cursor_position()
    visual_cursor.clear()

    waypoints = [
        (100.0, 150.0),
        (300.0, 250.0),
        (550.0, 400.0),
        (750.0, 200.0),
        (900.0, 600.0),  # Point E
    ]

    for pt in waypoints:
        visual_cursor.move_to(pt[0], pt[1], caption="Gliding")
        # Physical cursor never moves
        assert get_cursor_position() == initial_pos
        # Visual cursor accurately reflects waypoint
        assert visual_cursor.position == pt

    # After journey A -> B -> C -> D -> E:
    assert get_cursor_position() == initial_pos
    assert visual_cursor.position == (900.0, 600.0)
    visual_cursor.clear()


def test_cursorless_fallback_unavailable() -> None:
    """
    Requirement 9: Cursorless Fallback
    If macOS cannot perform an action without moving the physical pointer,
    it must return CURSORLESS_ACTION_UNAVAILABLE and NEVER silently fall back
    to physical cursor movement.
    """
    initial_pos = get_cursor_position()
    visual_cursor.clear()

    # When Accessibility is unavailable for given coordinates:
    with patch("zoe.macos.accessibility.ax_click_at", return_value=(False, "No AX element at position")):
        click_tool = tool_registry.get("click")
        res = click_tool.execute(x=888.0, y=777.0)
        assert res["success"] is False
        assert "CURSORLESS_ACTION_UNAVAILABLE" in res["error"]
        # Physical cursor MUST remain unchanged
        assert get_cursor_position() == initial_pos

    # Drag tool: cannot drag without moving physical mouse, must return CURSORLESS_ACTION_UNAVAILABLE
    drag_tool = tool_registry.get("drag")
    drag_res = drag_tool.execute(start_x=100.0, start_y=100.0, end_x=500.0, end_y=500.0)
    assert drag_res["success"] is False
    assert "CURSORLESS_ACTION_UNAVAILABLE" in drag_res["error"]
    assert get_cursor_position() == initial_pos


def test_accessibility_first_ax_press() -> None:
    """
    Requirement 8: Accessibility-First
    Target -> AXUIElement -> AXPress.
    """
    with patch("zoe.macos.accessibility.ApplicationServices.AXUIElementCreateSystemWide"), \
         patch("zoe.macos.accessibility.ApplicationServices.AXUIElementCopyElementAtPosition") as mock_copy, \
         patch("zoe.macos.accessibility.ax_perform_action") as mock_action:

        fake_elem = MagicMock()
        mock_copy.return_value = (0, fake_elem)
        mock_action.return_value = (True, "Action performed: AXPress")

        click_tool = tool_registry.get("click")
        res = click_tool.execute(x=600.0, y=400.0)

        assert res["success"] is True
        assert res["method"] == "accessibility"
        mock_action.assert_called_once_with(fake_elem)
