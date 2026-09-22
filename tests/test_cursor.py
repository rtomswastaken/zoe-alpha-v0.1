"""Unit tests for cursor trajectory and movement."""

import pytest
from zoe.macos.cursor import (
    get_cursor_position,
    calculate_smooth_trajectory,
    move_cursor_smooth,
)
from zoe.macos.emergency import emergency_controller, EmergencyStopTriggeredException


def test_calculate_trajectory():
    start = (100.0, 100.0)
    end = (500.0, 500.0)
    points = calculate_smooth_trajectory(start, end, steps=20, jitter=0.0)
    assert len(points) == 20
    assert points[-1] == end
    # First point should be close to start
    assert points[0][0] > start[0]
    assert points[0][1] > start[1]


def test_cursor_emergency_stop():
    emergency_controller.reset()
    emergency_controller.trigger("Simulated abort")
    with pytest.raises(EmergencyStopTriggeredException):
        move_cursor_smooth(200.0, 200.0, duration=0.2)
    emergency_controller.reset()


def test_cursor_read_and_move():
    emergency_controller.reset()
    curr_x, curr_y = get_cursor_position()
    assert isinstance(curr_x, float)
    assert isinstance(curr_y, float)

    # Test small smooth move near current position
    tx, ty = move_cursor_smooth(curr_x + 10.0, curr_y + 10.0, duration=0.05, steps=10)
    assert isinstance(tx, float)
    assert isinstance(ty, float)
