"""Unit tests for in-memory screenshot capture and resizing for vision."""

from zoe.macos.screenshots import capture_for_vision


def test_capture_for_vision():
    res = capture_for_vision(max_dim=512)
    assert isinstance(res, dict)
    if res.get("success"):
        assert "base64_image" in res
        assert len(res["base64_image"]) > 100
        assert "metadata" in res
        meta = res["metadata"]
        assert meta.vision_input_width <= 512
        assert meta.vision_input_height <= 512
        assert meta.scale_x > 0
        assert meta.scale_y > 0
        assert meta.backing_scale_factor in (1.0, 2.0, 3.0)
    else:
        assert "error" in res
