"""Unit tests for mouse automation."""

import pytest
from zoe.macos.cursor import get_cursor_position
from zoe.macos.mouse import (
    mouse_click,
    mouse_double_click,
    mouse_right_click,
    mouse_drag,
    mouse_scroll,
)
from zoe.macos.emergency import emergency_controller, EmergencyStopTriggeredException


def test_mouse_clicks():
    emergency_controller.reset()
    curr_x, curr_y = get_cursor_position()

    # Click in place
    res_x, res_y = mouse_click()
    assert abs(res_x - curr_x) < 20.0

    # Double click in place
    res_x, res_y = mouse_double_click()
    assert abs(res_x - curr_x) < 20.0

    # Right click in place
    res_x, res_y = mouse_right_click()
    assert abs(res_x - curr_x) < 20.0


def test_mouse_scroll():
    emergency_controller.reset()
    # Scroll should succeed without error
    mouse_scroll(vertical=5, horizontal=0)
    mouse_scroll(vertical=-5, horizontal=0)


def test_mouse_drag():
    emergency_controller.reset()
    curr_x, curr_y = get_cursor_position()
    # Small drag
    end_x, end_y = mouse_drag(curr_x, curr_y, curr_x + 5.0, curr_y + 5.0, duration=0.05)
    assert abs(end_x - (curr_x + 5.0)) < 2.0


def test_mouse_emergency_stop():
    emergency_controller.reset()
    emergency_controller.trigger("Mouse stop")
    with pytest.raises(EmergencyStopTriggeredException):
        mouse_click()
    emergency_controller.reset()
