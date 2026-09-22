"""Unit and integration tests for local model abstraction and Ollama provider."""

from unittest.mock import patch, MagicMock
import io
import json
from zoe.models.base import ToolCall, ModelResponse
from zoe.models.ollama import OllamaModel
from zoe.models.factory import get_model


def test_model_response_helpers():
    resp_empty = ModelResponse(text="Hello")
    assert not resp_empty.has_tool_calls()

    resp_tools = ModelResponse(
        text="",
        tool_calls=[ToolCall(id="1", name="open_app", arguments={"app_name": "Calculator"})],
    )
    assert resp_tools.has_tool_calls()
    assert resp_tools.tool_calls[0].name == "open_app"
    assert resp_tools.tool_calls[0].arguments == {"app_name": "Calculator"}


def test_ollama_mocked_chat():
    model = OllamaModel(endpoint="http://127.0.0.1:11434", model_name="qwen3:14b")

    mock_ollama_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "open_app",
                        "arguments": {"app_name": "Safari"},
                    },
                }
            ],
        }
    }

    mock_http_response = MagicMock()
    mock_http_response.read.return_value = json.dumps(mock_ollama_response).encode("utf-8")
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("urllib.request.urlopen", return_value=mock_http_response):
        resp = model.chat(messages=[{"role": "user", "content": "Open Safari"}])

        assert resp.has_tool_calls()
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "open_app"
        assert resp.tool_calls[0].arguments == {"app_name": "Safari"}


def test_ollama_mocked_stringified_json_args():
    model = OllamaModel(endpoint="http://127.0.0.1:11434", model_name="qwen3:14b")

    mock_ollama_response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_456",
                    "function": {
                        "name": "move_cursor",
                        "arguments": '{"x": 500, "y": 300}',
                    },
                }
            ],
        }
    }

    mock_http_response = MagicMock()
    mock_http_response.read.return_value = json.dumps(mock_ollama_response).encode("utf-8")
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("urllib.request.urlopen", return_value=mock_http_response):
        resp = model.chat(messages=[{"role": "user", "content": "Move cursor"}])

        assert resp.has_tool_calls()
        assert resp.tool_calls[0].name == "move_cursor"
        assert resp.tool_calls[0].arguments == {"x": 500, "y": 300}


def test_ollama_live_availability():
    """Live test verifying communication with actual running Ollama daemon."""
    model = get_model()
    available = model.is_available()
    assert available is True, f"Configured model {model.model_name} should be available in running Ollama"

    info = model.model_info()
    assert info["provider"] == "Ollama"
    assert info["status"] == "AVAILABLE"
    assert info["inference"] == "LOCAL"
    assert info["network_ai"] == "DISABLED"
