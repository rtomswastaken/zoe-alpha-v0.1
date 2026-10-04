"""Canonical coordinate pipeline between Vision model space, Retina screenshots, macOS Quartz, and OpenClicky AppKit points.

Coordinate Spaces in the Pipeline:
1. Vision Model Space:
   - Output from local vision models (e.g., MiniCPM-V, Qwen-VL).
   - Can be normalized (0-1000) or pixel-scaled relative to model input size.
2. Screenshot Coordinate Space:
   - Physical pixels of the captured screen (e.g., 3456 x 2234 on Retina 2x).
   - Origin is top-left of the display image, Y downwards.
3. macOS Display Point Space (Quartz / CGEvent):
   - Logical points used by macOS CGEvent, CGWarpMouseCursorPosition, and Zoe's mouse/cursor controllers.
   - Origin is top-left of the primary display (0, 0), Y downwards.
4. OpenClicky Screen Point Space (AppKit / NSScreen / NSEvent):
   - Global AppKit points used by OpenClicky's external control bridge (/cursor, /cursors, /caption).
   - Origin is bottom-left of the primary display (0, 0), Y upwards.

Mathematical Invariant:
For primary screen height H_primary:
  appkit_x = quartz_x
  appkit_y = H_primary - quartz_y

This invariant holds globally across all multi-monitor arrangements (including negative display bounds
where secondary displays are positioned above or to the left of the primary monitor).
"""

from typing import Optional, Tuple
from zoe.macos.coordinates import ImageTransformMetadata, vision_to_screen_points
from zoe.macos.display import display_manager


def get_primary_display_height() -> float:
    """Retrieve the logical height of the primary macOS display in points."""
    try:
        main_disp = display_manager.get_main_display()
        return float(main_disp.height)
    except Exception:
        return 1080.0


def quartz_to_appkit(
    qx: float,
    qy: float,
    primary_height: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Convert native macOS Quartz coordinates (origin top-left, Y downwards)
    to AppKit / OpenClicky coordinates (origin bottom-left, Y upwards).
    """
    h = primary_height if primary_height is not None else get_primary_display_height()
    ax = float(qx)
    ay = float(h - qy)
    return (round(ax, 2), round(ay, 2))


def appkit_to_quartz(
    ax: float,
    ay: float,
    primary_height: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Convert AppKit / OpenClicky coordinates (origin bottom-left, Y upwards)
    to native macOS Quartz coordinates (origin top-left, Y downwards).
    """
    h = primary_height if primary_height is not None else get_primary_display_height()
    qx = float(ax)
    qy = float(h - ay)
    return (round(qx, 2), round(qy, 2))


def vision_to_quartz(
    vx: float,
    vy: float,
    meta: ImageTransformMetadata,
    normalized: bool = False,
) -> Tuple[float, float]:
    """
    Convert local vision model coordinates into native macOS Quartz screen points.
    Directly reuses Zoe's canonical Retina/display transformation.
    """
    return vision_to_screen_points(vx, vy, meta, normalized=normalized)


def vision_to_openclicky(
    vx: float,
    vy: float,
    meta: ImageTransformMetadata,
    normalized: bool = False,
    primary_height: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Full canonical pipeline:
      Vision coordinates
             ↓
      Screenshot coordinate space
             ↓
      Display coordinate space (Retina scaling)
             ↓
      Logical macOS points (Quartz)
             ↓
      OpenClicky coordinate space (AppKit)
    """
    qx, qy = vision_to_quartz(vx, vy, meta, normalized=normalized)
    return quartz_to_appkit(qx, qy, primary_height=primary_height)


def openclicky_screenshot_pixel_to_appkit(
    px: float,
    py: float,
    display_frame_x: float,
    display_frame_y: float,
    display_frame_width: float,
    display_frame_height: float,
    screenshot_pixel_width: int,
    screenshot_pixel_height: int,
) -> Tuple[float, float]:
    """
    Convert pixel coordinates within an OpenClicky-captured JPEG into
    global AppKit screen points.
    
    Since JPEG images are stored top-down (pixel Y=0 at image top),
    while displayFrame in AppKit has Y=0 at bottom:
      point_x = display_frame_x + (px / scale_x)
      point_y = display_frame_y + display_frame_height - (py / scale_y)
    """
    scale_x = float(screenshot_pixel_width) / float(display_frame_width) if display_frame_width > 0 else 1.0
    scale_y = float(screenshot_pixel_height) / float(display_frame_height) if display_frame_height > 0 else 1.0

    ax = display_frame_x + (px / scale_x)
    ay = display_frame_y + display_frame_height - (py / scale_y)
    return (round(ax, 2), round(ay, 2))
