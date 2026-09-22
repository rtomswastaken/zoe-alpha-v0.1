"""Unit tests for coordinate transformations between vision space and macOS display space."""

from zoe.macos.coordinates import (
    ImageTransformMetadata,
    vision_to_screen_points,
    screen_points_to_vision,
)


def test_retina_coordinate_roundtrip():
    # Retina display: 2056 x 1329 points -> 4112 x 2658 pixels (scale 2.0x)
    # Resized to vision input: 1024 x 662 pixels
    meta = ImageTransformMetadata.create(
        point_width=2056.0,
        point_height=1329.0,
        pixel_width=4112,
        pixel_height=2658,
        vision_width=1024,
        vision_height=662,
        scale_factor=2.0,
        origin_x=0.0,
        origin_y=0.0,
    )

    # Let's say vision model detects target at center of vision input (512, 331)
    screen_x, screen_y = vision_to_screen_points(512.0, 331.0, meta)
    # Should correspond to roughly (1028.0, 664.5) points
    assert abs(screen_x - 1028.0) < 2.0
    assert abs(screen_y - 664.5) < 2.0

    # Inverse mapping should return back to (512.0, 331.0)
    vx, vy = screen_points_to_vision(screen_x, screen_y, meta)
    assert abs(vx - 512.0) < 1.0
    assert abs(vy - 331.0) < 1.0


def test_normalized_coordinate_mapping():
    # Vision models outputting 0-1000 normalized coordinates
    meta = ImageTransformMetadata.create(
        point_width=1920.0,
        point_height=1080.0,
        pixel_width=1920,
        pixel_height=1080,
        vision_width=960,
        vision_height=540,
        scale_factor=1.0,
        origin_x=0.0,
        origin_y=0.0,
    )

    # Normalized 500, 500 (center of screen)
    screen_x, screen_y = vision_to_screen_points(500.0, 500.0, meta, normalized=True)
    assert abs(screen_x - 960.0) < 1.0
    assert abs(screen_y - 540.0) < 1.0


def test_multi_monitor_offset():
    # Secondary monitor with origin_x = 2056.0
    meta = ImageTransformMetadata.create(
        point_width=1920.0,
        point_height=1080.0,
        pixel_width=1920,
        pixel_height=1080,
        vision_width=1024,
        vision_height=576,
        scale_factor=1.0,
        origin_x=2056.0,
        origin_y=0.0,
    )

    # Point at (0, 0) in second monitor's vision input
    screen_x, screen_y = vision_to_screen_points(0.0, 0.0, meta)
    assert screen_x == 2056.0
    assert screen_y == 0.0
