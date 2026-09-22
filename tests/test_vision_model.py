"""Unit tests for VisionModel abstractions and OllamaVisionModel."""

from unittest.mock import patch, MagicMock
import json
from zoe.models.vision import OllamaVisionModel, VisionTargetResult, VisionAnalysisResult
from zoe.models.vision_factory import get_vision_model


def test_ollama_vision_locate_mocked():
    vmodel = OllamaVisionModel(endpoint="http://127.0.0.1:11434", model_name="minicpm-v")

    # Mock response with high confidence detection
    mock_payload = {
        "message": {
            "role": "assistant",
            "content": '{"found": true, "target": "fullscreen button", "x": 512, "y": 331, "confidence": 0.94}',
        }
    }
    mock_http = MagicMock()
    mock_http.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_http.__enter__.return_value = mock_http

    with patch("urllib.request.urlopen", return_value=mock_http):
        res = vmodel.locate(image_b64="fake_b64", target="fullscreen button", confidence_threshold=0.75)
        assert res.found is True
        assert res.x == 512.0
        assert res.y == 331.0
        assert res.confidence == 0.94


def test_ollama_vision_low_confidence_rejection():
    vmodel = OllamaVisionModel(endpoint="http://127.0.0.1:11434", model_name="minicpm-v")

    # Low confidence detection (0.45 < 0.75 threshold)
    mock_payload = {
        "message": {
            "role": "assistant",
            "content": '{"found": true, "target": "hidden icon", "x": 100, "y": 200, "confidence": 0.45}',
        }
    }
    mock_http = MagicMock()
    mock_http.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_http.__enter__.return_value = mock_http

    with patch("urllib.request.urlopen", return_value=mock_http):
        res = vmodel.locate(image_b64="fake_b64", target="hidden icon", confidence_threshold=0.75)
        # Should be rejected because confidence < threshold
        assert res.found is False
        assert res.confidence == 0.45


def test_ollama_vision_analyze_mocked():
    vmodel = OllamaVisionModel(endpoint="http://127.0.0.1:11434", model_name="minicpm-v")

    mock_payload = {
        "message": {
            "role": "assistant",
            "content": "Safari browser window is visible with YouTube homepage loaded.",
        }
    }
    mock_http = MagicMock()
    mock_http.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_http.__enter__.return_value = mock_http

    with patch("urllib.request.urlopen", return_value=mock_http):
        res = vmodel.analyze(image_b64="fake_b64", prompt="Describe screen")
        assert "Safari" in res.description
        assert "YouTube" in res.description
