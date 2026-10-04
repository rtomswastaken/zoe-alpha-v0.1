"""Unit tests for Visual Interaction Modes: Explain, Guide, and Act."""

from unittest.mock import MagicMock, patch
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.visual_modes import VisualInteractionController
from zoe.macos.coordinates import ImageTransformMetadata
from zoe.models.vision import VisionTargetResult


def test_explain_mode_vision() -> None:
    """Mode 1: Explain points with OpenClicky cursor and does not move real mouse pointer."""
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_cursor.return_value = {"ok": True}

    controller = VisualInteractionController(client=mock_client)

    meta = ImageTransformMetadata.create(
        point_width=1728.0,
        point_height=1117.0,
        pixel_width=3456,
        pixel_height=2234,
        vision_width=1024,
        vision_height=662,
        scale_factor=2.0,
    )

    with patch("zoe.integrations.openclicky.visual_modes.get_app_accessibility_tree", return_value={"success": False}):
        with patch("zoe.integrations.openclicky.visual_modes.get_vision_model") as mock_vmodel_factory:
            mock_vmodel = MagicMock()
            mock_vmodel.is_available.return_value = True
            mock_vmodel.locate.return_value = VisionTargetResult(
                found=True,
                target="Wi-Fi Button",
                x=512.0,
                y=331.0,
                confidence=0.92,
            )
            mock_vmodel_factory.return_value = mock_vmodel


            with patch("zoe.integrations.openclicky.visual_modes.capture_for_vision") as mock_cap:
                mock_cap.return_value = {
                    "success": True,
                    "base64_image": "fake_b64",
                    "metadata": meta,
                }
                with patch("zoe.macos.mouse.mouse_click") as mock_mouse_click:
                    res = controller.explain("Wi-Fi Button")

                    assert res["success"] is True
                    assert res["mode"] == "explain"
                    assert res["source"] == "vision"
                    assert res["confidence"] == 0.92
                    mock_client.show_cursor.assert_called_once()
                    # Physical mouse must NEVER be clicked or moved
                    mock_mouse_click.assert_not_called()


def test_guide_mode() -> None:
    """Mode 2: Guide displays OpenClicky cursor + guidance caption without physical mouse movement."""
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_cursor.return_value = {"ok": True}

    controller = VisualInteractionController(client=mock_client)

    with patch.object(controller, "explain") as mock_explain:
        mock_explain.return_value = {
            "success": True,
            "mode": "explain",
            "target": "Downloads",
            "openclicky_coordinates": [200.0, 800.0],
        }

        res = controller.guide("Downloads")
        assert res["success"] is True
        assert res["mode"] == "guide"
        mock_explain.assert_called_once_with("Downloads", caption="Click here for Downloads")


def test_act_mode_accessibility_first() -> None:
    """Mode 3: Act prefers Accessibility API, gives OpenClicky visual feedback, and activates cursorlessly."""
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.show_cursor.return_value = {"ok": True}

    controller = VisualInteractionController(client=mock_client)

    with patch("zoe.integrations.openclicky.visual_modes.get_app_accessibility_tree") as mock_ax:
        mock_ax.return_value = {
            "success": True,
            "tree": {"title": "Wi-Fi Settings", "center": {"x": 640.0, "y": 480.0}},
        }
        with patch("zoe.integrations.openclicky.visual_modes.find_element_by_title") as mock_find:
            mock_find.return_value = {"center": {"x": 640.0, "y": 480.0}}
            with patch("zoe.integrations.openclicky.visual_modes.ax_click_at", return_value=(True, "OK")) as mock_ax_click:
                res = controller.act("Wi-Fi Settings")

                assert res["success"] is True
                assert res["mode"] == "act"
                assert res["source"] == "accessibility"
                assert res["clicked_at"] == [640.0, 480.0]
                mock_ax_click.assert_called_once_with(640.0, 480.0)
                # OpenClicky visual feedback was shown
                mock_client.show_cursor.assert_called_once()
