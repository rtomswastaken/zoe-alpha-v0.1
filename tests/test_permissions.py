"""Unit tests for permissions module."""

from zoe.macos.permissions import (
    check_accessibility_permission,
    check_screen_recording_permission,
    get_permission_status,
)


def test_permission_queries():
    # Calling the checkers without prompt must return booleans and not raise exceptions
    acc = check_accessibility_permission(prompt=False)
    assert isinstance(acc, bool)

    rec = check_screen_recording_permission(prompt=False)
    assert isinstance(rec, bool)

    status = get_permission_status()
    assert isinstance(status, dict)
    assert "accessibility_granted" in status
    assert "screen_recording_granted" in status
    assert "instructions" in status
