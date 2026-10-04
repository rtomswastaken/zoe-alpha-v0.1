"""Tests for canonical Retina coordinate transformation between Vision, Quartz, and OpenClicky AppKit spaces."""

from zoe.macos.coordinates import ImageTransformMetadata
from zoe.integrations.openclicky.coordinates import (
    appkit_to_quartz,
    openclicky_screenshot_pixel_to_appkit,
    quartz_to_appkit,
    vision_to_openclicky,
    vision_to_quartz,
)


def test_quartz_appkit_roundtrip() -> None:
    """Verify bidirectional inversion between Quartz and AppKit coordinate spaces."""
    primary_h = 1080.0
    qx, qy = 500.0, 300.0

    ax, ay = quartz_to_appkit(qx, qy, primary_height=primary_h)
    assert ax == 500.0
    assert ay == 780.0  # 1080 - 300

    back_qx, back_qy = appkit_to_quartz(ax, ay, primary_height=primary_h)
    assert back_qx == qx
    assert back_qy == qy


def test_retina_2x_coordinate_pipeline() -> None:
    """
    Simulate a 2x Retina screen (e.g. 1728x1117 points, 3456x2234 pixels),
    downscaled to 1024x662 for vision model input.
    """
    point_w, point_h = 1728.0, 1117.0
    pixel_w, pixel_h = 3456, 2234
    vision_w, vision_h = 1024, 662
    scale_factor = 2.0

    meta = ImageTransformMetadata.create(
        point_width=point_w,
        point_height=point_h,
        pixel_width=pixel_w,
        pixel_height=pixel_h,
        vision_width=vision_w,
        vision_height=vision_h,
        scale_factor=scale_factor,
        origin_x=0.0,
        origin_y=0.0,
    )

    # Suppose vision model detects an element at center of vision input (512, 331)
    qx, qy = vision_to_quartz(512, 331, meta)
    # 512 / (1024/3456) = 1728 pixels -> 1728 / 2 = 864 points
    assert abs(qx - 864.0) < 1.0
    # 331 / (662/2234) = 1117 pixels -> 1117 / 2 = 558.5 points
    assert abs(qy - 558.5) < 1.0

    # Convert to OpenClicky AppKit points
    ax, ay = vision_to_openclicky(512, 331, meta, primary_height=point_h)
    assert abs(ax - 864.0) < 1.0
    assert abs(ay - (point_h - 558.5)) < 1.0


def test_retina_1x_scaling() -> None:
    """Simulate a standard 1x external monitor (1920x1080 points, 1920x1080 pixels)."""
    meta = ImageTransformMetadata.create(
        point_width=1920.0,
        point_height=1080.0,
        pixel_width=1920,
        pixel_height=1080,
        vision_width=1024,
        vision_height=576,
        scale_factor=1.0,
    )

    qx, qy = vision_to_quartz(512, 288, meta)
    assert abs(qx - 960.0) < 1.0
    assert abs(qy - 540.0) < 1.0

    ax, ay = vision_to_openclicky(512, 288, meta, primary_height=1080.0)
    assert abs(ax - 960.0) < 1.0
    assert abs(ay - 540.0) < 1.0


def test_normalized_vision_coordinates() -> None:
    """Test 0-1000 normalized vision coordinates (used by some models like Qwen-VL)."""
    meta = ImageTransformMetadata.create(
        point_width=1440.0,
        point_height=900.0,
        pixel_width=2880,
        pixel_height=1800,
        vision_width=1000,
        vision_height=625,
        scale_factor=2.0,
    )

    # 500, 500 normalized (middle of screen)
    ax, ay = vision_to_openclicky(500, 500, meta, normalized=True, primary_height=900.0)
    assert abs(ax - 720.0) < 1.0
    assert abs(ay - 450.0) < 1.0


def test_multi_display_negative_coordinates() -> None:
    """
    Test multi-monitor layouts:
    Display 1 (Main): 0, 0, 1920, 1080
    Display 2 (Left): -1920, 0, 1920, 1080
    Display 3 (Above): 0, -1080, 1920, 1080
    """
    primary_h = 1080.0

    # Point on Left Display (Quartz X negative, Y positive)
    left_qx, left_qy = -500.0, 400.0
    left_ax, left_ay = quartz_to_appkit(left_qx, left_qy, primary_height=primary_h)
    assert left_ax == -500.0
    assert left_ay == 680.0

    # Roundtrip back
    back_qx, back_qy = appkit_to_quartz(left_ax, left_ay, primary_height=primary_h)
    assert back_qx == left_qx
    assert back_qy == left_qy

    # Point on Top Display (Quartz Y negative -> AppKit Y > primary_h)
    top_qx, top_qy = 500.0, -300.0
    top_ax, top_ay = quartz_to_appkit(top_qx, top_qy, primary_height=primary_h)
    assert top_ax == 500.0
    assert top_ay == 1380.0  # 1080 - (-300) = 1380

    back_top_qx, back_top_qy = appkit_to_quartz(top_ax, top_ay, primary_height=primary_h)
    assert back_top_qx == top_qx
    assert back_top_qy == top_qy


def test_openclicky_screenshot_pixel_to_appkit() -> None:
    """Verify converting OpenClicky screenshot pixels into AppKit screen points."""
    # A Retina screen: 1728x1117 points, 3456x2234 pixels, displayFrame origin at (0, 0)
    ax, ay = openclicky_screenshot_pixel_to_appkit(
        px=1728,  # middle horizontally
        py=1117,  # middle vertically in image (image Y=0 is top)
        display_frame_x=0.0,
        display_frame_y=0.0,
        display_frame_width=1728.0,
        display_frame_height=1117.0,
        screenshot_pixel_width=3456,
        screenshot_pixel_height=2234,
    )
    assert abs(ax - 864.0) < 0.5
    assert abs(ay - 558.5) < 0.5
