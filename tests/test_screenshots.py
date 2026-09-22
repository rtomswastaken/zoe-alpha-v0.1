"""Unit tests for local screenshot capture."""

import os
from pathlib import Path
from zoe.macos.screenshots import capture_screen


def test_capture_screen_region(tmp_path: Path):
    out_file = tmp_path / "test_region.png"
    res = capture_screen(rect=(0.0, 0.0, 100.0, 100.0), save_path=str(out_file))

    assert isinstance(res, dict)
    assert res["action"] == "take_screenshot"

    if res["success"]:
        assert out_file.exists()
        assert out_file.stat().st_size > 0
        assert res["width_points"] == 100.0
        assert res["height_points"] == 100.0
        assert res["width_pixels"] >= 100
        assert res["height_pixels"] >= 100
    else:
        assert "error" in res
