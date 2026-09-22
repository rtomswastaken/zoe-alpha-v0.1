"""Unit tests for Phase 2 configuration."""

from zoe.config import get_config


def test_phase2_config():
    config = get_config(reload=True)
    assert config.model.provider == "ollama"
    assert config.model.name == "qwen3:14b"
    assert "11434" in config.model.endpoint
    assert config.model.max_tokens >= 1024

    assert config.agent.max_tool_calls == 30
    assert config.agent.timeout_seconds > 0
