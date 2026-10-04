"""Unit tests for OpenClicky BaseTool wrappers and ToolRegistry integration."""

from unittest.mock import MagicMock, patch
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.models import ScreenshotResponse, ScreenshotScreen, DisplayFrame
from zoe.integrations.openclicky.tools import (
    OpenClickyCaptionTool,
    OpenClickyClearTool,
    OpenClickyGuideTool,
    OpenClickyHealthTool,
    OpenClickyMultiPointTool,
    OpenClickyPointTool,
    OpenClickyScreenshotTool,
    OpenClickySpeakTool,
)
from zoe.tools.registry import tool_registry


def test_openclicky_tools_registered_in_central_registry() -> None:
    """Verify all OpenClicky tools are properly registered in tool_registry."""
    names = tool_registry.get_tool_names()
    assert "openclicky_health" in names
    assert "openclicky_screenshot" in names
    assert "openclicky_point" in names
    assert "openclicky_multi_point" in names
    assert "openclicky_caption" in names
    assert "openclicky_speak" in names
    assert "openclicky_clear" in names
    assert "openclicky_guide" in names


def test_tool_schema_export() -> None:
    """Ensure OpenClicky tool schemas conform to OpenAI/Ollama function calling standard."""
    point_tool = OpenClickyPointTool()
    schema = point_tool.to_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "openclicky_point"
    assert "x" in schema["function"]["parameters"]["properties"]
    assert "y" in schema["function"]["parameters"]["properties"]


def test_point_tool_execution() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_cursor.return_value = {"ok": True}

    with patch("zoe.integrations.openclicky.tools.quartz_to_appkit", return_value=(500.0, 780.0)):
        tool = OpenClickyPointTool(client=mock_client)
        res = tool.execute(x=500.0, y=300.0, caption="Downloads", coordinate_space="quartz")

        assert res["success"] is True
        assert res["action"] == "openclicky_point"
        assert res["input_coordinates"] == [500.0, 300.0]
        assert res["openclicky_coordinates"] == [500.0, 780.0]
        mock_client.show_cursor.assert_called_once_with(
            x=500.0,
            y=780.0,
            caption="Downloads",
            duration_ms=None,
            mode="primary",
            accent_hex=None,
            travel_ms=None,
        )


def test_multi_point_tool_execution() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_cursors.return_value = {"ok": True, "count": 2}

    with patch("zoe.integrations.openclicky.tools.quartz_to_appkit", side_effect=lambda x, y: (x, 1080.0 - y)):
        tool = OpenClickyMultiPointTool(client=mock_client)
        cursors = [
            {"x": 100.0, "y": 200.0, "caption": "Left"},
            {"x": 400.0, "y": 500.0, "caption": "Right"},
        ]
        res = tool.execute(cursors=cursors, duration_ms=3000)

        assert res["success"] is True
        assert res["count"] == 2
        mock_client.show_cursors.assert_called_once()
        args, kwargs = mock_client.show_cursors.call_args
        converted = args[0]
        assert converted[0]["x"] == 100.0
        assert converted[0]["y"] == 880.0
        assert converted[1]["x"] == 400.0
        assert converted[1]["y"] == 580.0


def test_caption_tool_execution() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_caption.return_value = {"ok": True}

    with patch("zoe.integrations.openclicky.tools.quartz_to_appkit", return_value=(200.0, 600.0)):
        tool = OpenClickyCaptionTool(client=mock_client)
        res = tool.execute(text="Here is your file", x=200.0, y=480.0)
        assert res["success"] is True
        mock_client.show_caption.assert_called_once_with(
            text="Here is your file",
            x=200.0,
            y=600.0,
            duration_ms=None,
            accent_hex=None,
        )


def test_screenshot_tool_execution() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.screenshot.return_value = ScreenshotResponse(
        ok=True,
        count=1,
        focused=False,
        screens=[
            ScreenshotScreen(
                label="Screen 1",
                path="/tmp/test.jpg",
                is_cursor_screen=True,
                display_frame=DisplayFrame(x=0.0, y=0.0, width=1920.0, height=1080.0),
                display_width_points=1920.0,
                display_height_points=1080.0,
                screenshot_width_pixels=1920,
                screenshot_height_pixels=1080,
            )
        ],
    )

    tool = OpenClickyScreenshotTool(client=mock_client)
    res = tool.execute(focused=False)
    assert res["success"] is True
    assert res["count"] == 1
    assert len(res["screens"]) == 1
    assert res["screens"][0]["path"] == "/tmp/test.jpg"


def test_speak_and_clear_tools() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.speak.return_value = {"ok": True}
    mock_client.clear.return_value = {"ok": True}

    speak_tool = OpenClickySpeakTool(client=mock_client)
    res_spk = speak_tool.execute(text="Done!")
    assert res_spk["success"] is True
    assert res_spk["spoken"] == "Done!"

    clear_tool = OpenClickyClearTool(client=mock_client)
    res_clr = clear_tool.execute()
    assert res_clr["success"] is True


def test_guide_tool_accessibility_success() -> None:
    """When element is found in accessibility tree, guide tool uses accessibility center."""
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_cursor.return_value = {"ok": True}

    with patch("zoe.integrations.openclicky.tools.get_app_accessibility_tree") as mock_ax:
        mock_ax.return_value = {
            "success": True,
            "tree": {
                "title": "Wi-Fi Settings",
                "center": {"x": 500.0, "y": 300.0},
            },
        }
        with patch("zoe.integrations.openclicky.tools.find_element_by_title") as mock_find:
            mock_find.return_value = {"center": {"x": 500.0, "y": 300.0}}
            with patch("zoe.integrations.openclicky.tools.quartz_to_appkit", return_value=(500.0, 780.0)):
                tool = OpenClickyGuideTool(client=mock_client)
                res = tool.execute(target="Wi-Fi Settings")

                assert res["success"] is True
                assert res["source"] == "accessibility"
                assert res["openclicky_coordinates"] == [500.0, 780.0]
                mock_client.show_cursor.assert_called_once_with(
                    x=500.0, y=780.0, caption="Wi-Fi Settings", duration_ms=None
                )
