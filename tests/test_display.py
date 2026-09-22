"""Unit tests for display enumeration and coordinate conversion."""

from zoe.macos.display import display_manager, DisplayInfo


def test_display_enumeration():
    displays = display_manager.get_displays()
    assert len(displays) >= 1

    main_disp = display_manager.get_main_display()
    assert main_disp is not None
    assert main_disp.width > 0
    assert main_disp.height > 0
    assert main_disp.scale_factor in (1.0, 2.0, 3.0)


def test_coordinate_conversion():
    main_disp = display_manager.get_main_display()
    # Test point (100, 100)
    px, py = display_manager.point_to_pixel(100.0, 100.0)
    expected_px = int(round(100.0 * main_disp.scale_factor))
    expected_py = int(round(100.0 * main_disp.scale_factor))
    assert px == expected_px
    assert py == expected_py

    # Reverse convert
    pt_x, pt_y = display_manager.pixel_to_point(px, py, main_disp.display_id)
    assert abs(pt_x - 100.0) < 1e-4
    assert abs(pt_y - 100.0) < 1e-4


def test_clamp_coordinates():
    main_disp = display_manager.get_main_display()
    # Coordinates way off screen
    cx, cy = display_manager.clamp_to_screen(-500.0, -500.0)
    assert cx >= main_disp.origin_x
    assert cy >= main_disp.origin_y
