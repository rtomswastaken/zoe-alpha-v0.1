"""Unit tests for Phase 2 CLI commands."""

from zoe.cli import cmd_model_status


def test_cmd_model_status():
    ret = cmd_model_status()
    assert ret == 0
