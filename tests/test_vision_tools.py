"""Unit tests for hybrid Accessibility+Vision tools."""

from unittest.mock import patch, MagicMock
from zoe.tools.registry import tool_registry
from zoe.models.vision import VisionTargetResult, VisionAnalysisResult
from zoe.macos.coordinates import ImageTransformMetadata


def test_vision_tools_registered():
    names = tool_registry.get_tool_names()
    assert "find_on_screen" in names
    assert "inspect_screen" in names


def test_find_on_screen_accessibility_priority():
    """Test that Accessibility is checked first; if element found, vision is NOT called."""
    mock_tree_res = {
        "success": True,
        "tree": {
            "role": "AXApplication",
            "title": "Safari",
            "children": [
                {
                    "role": "AXButton",
                    "title": "Full Screen",
                    "center": {"x": 800.0, "y": 450.0},
                }
            ],
        },
    }

    with patch("zoe.tools.vision.get_app_accessibility_tree", return_value=mock_tree_res):
        with patch("zoe.tools.vision.get_vision_model") as mock_get_vmodel:
            res = tool_registry.execute("find_on_screen", target="Full Screen")
            assert res["success"] is True
            assert res["found"] is True
            assert res["source"] == "accessibility"
            assert res["coordinates"] == [800.0, 450.0]
            assert res["confidence"] == 1.0
            # Vision model should NOT have been called
            mock_get_vmodel.assert_not_called()


def test_find_on_screen_vision_fallback():
    """Test that if Accessibility fails to find element, local vision is used as fallback."""
    mock_tree_res = {"success": True, "tree": {"role": "AXApplication", "children": []}}

    mock_meta = ImageTransformMetadata.create(
        point_width=2000.0,
        point_height=1000.0,
        pixel_width=4000,
        pixel_height=2000,
        vision_width=1000,
        vision_height=500,
        scale_factor=2.0,
        origin_x=0.0,
        origin_y=0.0,
    )
    mock_shot = {
        "success": True,
        "base64_image": "fake_img",
        "metadata": mock_meta,
    }

    mock_vmodel = MagicMock()
    mock_vmodel.is_available.return_value = True
    # Vision model finds target at vision input (500, 250) with 0.92 confidence
    mock_vmodel.locate.return_value = VisionTargetResult(
        found=True,
        target="custom_canvas_btn",
        x=500.0,
        y=250.0,
        confidence=0.92,
    )

    with patch("zoe.tools.vision.get_app_accessibility_tree", return_value=mock_tree_res):
        with patch("zoe.tools.vision.get_vision_model", return_value=mock_vmodel):
            with patch("zoe.tools.vision.capture_for_vision", return_value=mock_shot):
                res = tool_registry.execute("find_on_screen", target="custom_canvas_btn")
                assert res["success"] is True
                assert res["found"] is True
                assert res["source"] == "vision"
                assert res["confidence"] == 0.92
                # (500, 250) in vision input should map to (1000.0, 500.0) screen points
                assert res["coordinates"] == [1000.0, 500.0]
