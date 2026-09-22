"""Tests for Phase 7 Unified Runtime, Reliability, and Diagnostics."""

import pytest
from zoe.runtime import ZoeRuntime, get_runtime


def test_runtime_singleton_and_init():
    rt = get_runtime()
    assert rt is not None
    assert isinstance(rt, ZoeRuntime)


def test_runtime_preflight_check():
    rt = get_runtime()
    diag = rt.preflight_check()

    assert "accessibility" in diag
    assert "screen_recording" in diag
    assert "microphone" in diag
    assert "llm_ready" in diag
    assert "vision_ready" in diag
    assert isinstance(diag["all_systems_ready"], bool)


def test_runtime_friendly_diagnostics(capsys):
    rt = get_runtime()
    fake_diag = {
        "accessibility": False,
        "screen_recording": True,
        "microphone": False,
        "llm_ready": False,
        "vision_ready": False,
        "all_systems_ready": False,
    }
    rt.print_friendly_diagnostics(fake_diag)
    captured = capsys.readouterr().out

    assert "Accessibility permission is disabled" in captured
    assert "Microphone permission is not granted" in captured
    assert "Local reasoning model (qwen3:14b) is not reachable" in captured
    assert "Traceback" not in captured  # Friendly user guidance without unhandled tracebacks
