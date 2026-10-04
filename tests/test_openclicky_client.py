"""Unit tests for OpenClickyClient: health, cursor, screenshot, speech, security, and error handling."""

from unittest.mock import MagicMock, patch
import pytest
import httpx
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.models import (
    OpenClickyAPIError,
    OpenClickyAuthError,
    OpenClickyConnectionError,
    OpenClickySecurityError,
    OpenClickyTimeoutError,
)


def test_client_security_rejects_external_hosts() -> None:
    """Ensure non-local addresses and 0.0.0.0 are strictly rejected."""
    with pytest.raises(OpenClickySecurityError):
        OpenClickyClient(host="0.0.0.0")

    with pytest.raises(OpenClickySecurityError):
        OpenClickyClient(host="192.168.1.100")

    with pytest.raises(OpenClickySecurityError):
        OpenClickyClient(host="evil.com")

    # Valid loopback hosts
    c1 = OpenClickyClient(host="127.0.0.1")
    assert c1.host == "127.0.0.1"

    c2 = OpenClickyClient(host="localhost")
    assert c2.host == "localhost"


def test_health_success() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "name": "OpenClicky External Control Bridge",
        "port": 32123,
        "transport": "local-http+sse",
        "bridgeTokenRequired": True,
        "bridgeTokenConfigured": False,
        "tools": ["openclicky_point", "screenshot", "speak"],
    }

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.return_value = mock_resp
        mock_get_client.return_value = mock_http

        health = client.health()
        assert health.ok is True
        assert health.port == 32123
        assert len(health.tools) == 3
        assert "openclicky_point" in health.tools
        assert health.latency_ms >= 0.0


def test_health_connection_error() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.side_effect = httpx.ConnectError("Connection refused")
        mock_get_client.return_value = mock_http

        with pytest.raises(OpenClickyConnectionError):
            client.health()


def test_health_timeout_error() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123, timeout=1.0)

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.side_effect = httpx.TimeoutException("Read timeout")
        mock_get_client.return_value = mock_http

        with pytest.raises(OpenClickyTimeoutError):
            client.health()


def test_auth_failure_401() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"ok": False, "error": "Token required"}

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.return_value = mock_resp
        mock_get_client.return_value = mock_http

        with pytest.raises(OpenClickyAuthError):
            client.show_cursor(100, 200)


def test_show_cursor_primary() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "displayed": "primary_cursor"}

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.return_value = mock_resp
        mock_get_client.return_value = mock_http

        res = client.show_cursor(
            x=640.0,
            y=520.0,
            caption="Test Menu",
            duration_ms=4500,
            mode="primary",
            travel_ms=350,
        )
        assert res["ok"] is True
        mock_http.request.assert_called_once()
        args, kwargs = mock_http.request.call_args
        assert kwargs["json"] == {
            "x": 640.0,
            "y": 520.0,
            "mode": "primary",
            "caption": "Test Menu",
            "durationMs": 4500,
            "travelMs": 350,
        }


def test_show_cursors_multi() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "displayed": "secondary_cursors", "count": 2}

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.return_value = mock_resp
        mock_get_client.return_value = mock_http

        cursors = [
            {"x": 100, "y": 200, "caption": "Point 1"},
            {"x": 300, "y": 400, "caption": "Point 2"},
        ]
        res = client.show_cursors(cursors, duration_ms=3000)
        assert res["ok"] is True
        args, kwargs = mock_http.request.call_args
        assert kwargs["json"]["cursors"] == cursors
        assert kwargs["json"]["durationMs"] == 3000


def test_screenshot_parsing() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "count": 1,
        "focused": False,
        "screens": [
            {
                "label": "Built-in Retina Display",
                "path": "/tmp/screen-1.jpg",
                "isCursorScreen": True,
                "displayFrame": {"x": 0.0, "y": 0.0, "width": 1728.0, "height": 1117.0},
                "displayWidthInPoints": 1728.0,
                "displayHeightInPoints": 1117.0,
                "screenshotWidthInPixels": 3456,
                "screenshotHeightInPixels": 2234,
            }
        ],
    }

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.return_value = mock_resp
        mock_get_client.return_value = mock_http

        res = client.screenshot(focused=False)
        assert res.ok is True
        assert res.count == 1
        screen = res.screens[0]
        assert screen.label == "Built-in Retina Display"
        assert screen.display_frame.width == 1728.0
        assert screen.screenshot_width_pixels == 3456
        assert screen.path == "/tmp/screen-1.jpg"


def test_speak_and_clear() -> None:
    client = OpenClickyClient(host="127.0.0.1", port=32123)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}

    with patch.object(client, "_get_client") as mock_get_client:
        mock_http = MagicMock()
        mock_http.request.return_value = mock_resp
        mock_get_client.return_value = mock_http

        res_speak = client.speak("Hello from Zoe", interrupt=True)
        assert res_speak["ok"] is True

        res_clear = client.clear()
        assert res_clear["ok"] is True
