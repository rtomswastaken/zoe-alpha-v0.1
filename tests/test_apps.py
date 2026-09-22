"""Unit tests for application lifecycle and window queries."""

import time
from zoe.macos.apps import (
    get_active_app,
    get_running_apps,
    get_windows,
    launch_app,
    activate_app,
    quit_app,
)


def test_get_active_and_running_apps():
    active = get_active_app()
    assert isinstance(active, dict)
    assert "name" in active
    assert "pid" in active

    running = get_running_apps()
    assert isinstance(running, list)
    assert len(running) > 0
    assert any(a["name"] != "" for a in running)


def test_get_windows():
    windows = get_windows()
    assert isinstance(windows, list)
    for w in windows[:5]:
        assert "window_id" in w
        assert "owner_name" in w
        assert "bounds" in w


def test_app_lifecycle_calculator():
    # Launch Calculator
    launch_res = launch_app("Calculator")
    assert launch_res["success"] is True
    time.sleep(0.5)

    # Activate Calculator
    act_res = activate_app("Calculator")
    assert act_res["success"] is True
    time.sleep(0.5)

    # Quit Calculator
    quit_res = quit_app("Calculator", force=True)
    assert quit_res["success"] is True
