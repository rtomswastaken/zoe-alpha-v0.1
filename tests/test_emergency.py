"""Unit tests for emergency stop controller."""

import pytest
from zoe.macos.emergency import emergency_controller, EmergencyStopTriggeredException


def test_emergency_stop_lifecycle():
    emergency_controller.reset()
    assert not emergency_controller.is_stopped()

    # check_and_raise should not raise when not stopped
    emergency_controller.check_and_raise()

    cleanup_called = False

    def on_cleanup():
        nonlocal cleanup_called
        cleanup_called = True

    emergency_controller.register_cleanup_callback(on_cleanup)
    emergency_controller.trigger(reason="Test stop")

    assert emergency_controller.is_stopped()
    assert cleanup_called is True
    assert emergency_controller.get_reason() == "Test stop"

    with pytest.raises(EmergencyStopTriggeredException):
        emergency_controller.check_and_raise()

    # Reset
    emergency_controller.reset()
    assert not emergency_controller.is_stopped()
    emergency_controller.check_and_raise()
