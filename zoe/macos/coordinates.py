"""Bidirectional coordinate transformations between vision model space, Retina screenshots, and macOS display points."""

from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class ImageTransformMetadata:
    """
    Metadata recording exact resolution transformations applied to a screenshot
    so vision model coordinate outputs can be mapped back to physical cursor positions.
    """
    original_point_width: float
    original_point_height: float
    original_pixel_width: int
    original_pixel_height: int
    vision_input_width: int
    vision_input_height: int
    scale_x: float  # vision_input_width / original_pixel_width
    scale_y: float  # vision_input_height / original_pixel_height
    backing_scale_factor: float = 2.0  # Retina scaling (e.g. 2.0)
    display_origin_x: float = 0.0  # Multi-monitor point X offset
    display_origin_y: float = 0.0  # Multi-monitor point Y offset
    crop_offset_px_x: float = 0.0  # Crop offset in screenshot pixels
    crop_offset_px_y: float = 0.0  # Crop offset in screenshot pixels

    @classmethod
    def create(
        cls,
        point_width: float,
        point_height: float,
        pixel_width: int,
        pixel_height: int,
        vision_width: int,
        vision_height: int,
        scale_factor: float = 2.0,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        crop_x: float = 0.0,
        crop_y: float = 0.0,
    ) -> "ImageTransformMetadata":
        sx = float(vision_width) / float(pixel_width) if pixel_width > 0 else 1.0
        sy = float(vision_height) / float(pixel_height) if pixel_height > 0 else 1.0
        return cls(
            original_point_width=point_width,
            original_point_height=point_height,
            original_pixel_width=pixel_width,
            original_pixel_height=pixel_height,
            vision_input_width=vision_width,
            vision_input_height=vision_height,
            scale_x=sx,
            scale_y=sy,
            backing_scale_factor=scale_factor,
            display_origin_x=origin_x,
            display_origin_y=origin_y,
            crop_offset_px_x=crop_x,
            crop_offset_px_y=crop_y,
        )


def vision_to_screen_points(
    vx: float,
    vy: float,
    meta: ImageTransformMetadata,
    normalized: bool = False,
) -> Tuple[float, float]:
    """
    Convert coordinates returned by local vision model (e.g. 600, 500)
    back to native macOS logical point coordinates (used by move_cursor / click).
    
    Pipeline:
      Vision coordinates
             ↓
      Original screenshot pixel coordinates
             ↓
      Retina scaling (pixels -> points)
             ↓
      Multi-monitor origin offset
             ↓
      macOS display cursor coordinates
    """
    # 1. If normalized (0-1000 scale)
    if normalized:
        vx = (vx / 1000.0) * meta.vision_input_width
        vy = (vy / 1000.0) * meta.vision_input_height

    # 2. Map from vision input dimensions back to original screenshot pixel dimensions
    if meta.scale_x > 0:
        orig_px_x = (vx / meta.scale_x) + meta.crop_offset_px_x
    else:
        orig_px_x = vx + meta.crop_offset_px_x

    if meta.scale_y > 0:
        orig_px_y = (vy / meta.scale_y) + meta.crop_offset_px_y
    else:
        orig_px_y = vy + meta.crop_offset_px_y

    # 3. Convert physical pixels to macOS logical points using backing_scale_factor
    scale = meta.backing_scale_factor if meta.backing_scale_factor > 0 else 1.0
    pt_x = orig_px_x / scale
    pt_y = orig_px_y / scale

    # 4. Add display origin (for multi-monitor layouts)
    screen_x = meta.display_origin_x + pt_x
    screen_y = meta.display_origin_y + pt_y

    return (round(screen_x, 1), round(screen_y, 1))


def screen_points_to_vision(
    sx: float,
    sy: float,
    meta: ImageTransformMetadata,
) -> Tuple[float, float]:
    """Inverse transformation: maps macOS display cursor points to vision model coordinate space."""
    # 1. Subtract display origin
    pt_x = sx - meta.display_origin_x
    pt_y = sy - meta.display_origin_y

    # 2. Convert points to physical screenshot pixels
    scale = meta.backing_scale_factor if meta.backing_scale_factor > 0 else 1.0
    orig_px_x = pt_x * scale
    orig_px_y = pt_y * scale

    # 3. Adjust for crop
    uncropped_x = orig_px_x - meta.crop_offset_px_x
    uncropped_y = orig_px_y - meta.crop_offset_px_y

    # 4. Scale to vision input dimensions
    vx = uncropped_x * meta.scale_x
    vy = uncropped_y * meta.scale_y

    return (round(vx, 1), round(vy, 1))
