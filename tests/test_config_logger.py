"""Unit tests for config and logger."""

from pathlib import Path
from zoe.config import get_config
from zoe.macos.logger import zoe_logger


def test_config_loading():
    config = get_config(reload=True)
    assert config is not None
    assert config.cursor.default_duration > 0
    assert config.mouse.click_delay > 0
    assert config.emergency.hotkey == "escape"
    assert config.logging.enabled is True


def test_logger_action():
    zoe_logger.clear_history()
    line = zoe_logger.log_action("MOVE_CURSOR", x=842, y=611, duration=0.42)
    assert "MOVE_CURSOR" in line
    assert "x=842" in line
    assert "y=611" in line
    assert "duration=0.42" in line

    # Check sensitive masking
    line2 = zoe_logger.log_action("TYPE_TEXT", text="SuperSecretPassword123")
    assert "length=22" in line2
    assert "SuperSecretPassword123" not in line2

    history = zoe_logger.get_history()
    assert len(history) >= 2
