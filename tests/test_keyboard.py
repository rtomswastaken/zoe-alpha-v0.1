"""Unit tests for keyboard automation."""

import pytest
from zoe.macos.keyboard import (
    press_key,
    hotkey,
    type_text,
    KEY_CODES,
)
from zoe.macos.emergency import emergency_controller, EmergencyStopTriggeredException


def test_key_codes_defined():
    assert "return" in KEY_CODES
    assert "space" in KEY_CODES
    assert "command" in KEY_CODES
    assert "a" in KEY_CODES


def test_press_key():
    emergency_controller.reset()
    # Press shift (modifier key has no destructive side-effect)
    press_key("shift", duration=0.01)


def test_hotkey():
    emergency_controller.reset()
    # Hotkey with shift
    hotkey("shift")


def test_type_text():
    emergency_controller.reset()
    # Type string without throwing exception
    type_text("Zoe", delay=0.01)


def test_keyboard_emergency_stop():
    emergency_controller.reset()
    emergency_controller.trigger("Keyboard stop")
    with pytest.raises(EmergencyStopTriggeredException):
        type_text("Hello World", delay=0.05)
    emergency_controller.reset()
