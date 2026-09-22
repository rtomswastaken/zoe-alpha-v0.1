"""Local macOS screenshot capture via Quartz CoreGraphics."""

import base64
from datetime import datetime
import io
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from Foundation import NSURL, NSMutableData
import Quartz
from PIL import Image
from zoe.config import get_config
from zoe.macos.coordinates import ImageTransformMetadata
from zoe.macos.display import display_manager
from zoe.macos.permissions import check_screen_recording_permission
from zoe.macos.logger import zoe_logger


def _save_cgimage_to_png(cg_image: Any, file_path: str | Path) -> bool:
    """Save a Quartz CGImageRef to a local PNG file using native ImageIO."""
    p = Path(file_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    url = NSURL.fileURLWithPath_(str(p))

    dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
    if dest is None:
        return False

    Quartz.CGImageDestinationAddImage(dest, cg_image, None)
    success = bool(Quartz.CGImageDestinationFinalize(dest))
    return success


def capture_screen(
    display_id: Optional[int] = None,
    rect: Optional[Tuple[float, float, float, float]] = None,
    save_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Capture a screenshot of a display or specific region in point coordinates.
    Saves image strictly locally and returns metadata.
    """
    if not check_screen_recording_permission():
        err_msg = (
            "Screen Recording permission not granted. "
            "Please enable Screen & System Audio Recording in macOS System Settings > Privacy & Security."
        )
        zoe_logger.log_action("SCREENSHOT_PERMISSION_DENIED")
        return {
            "success": False,
            "action": "take_screenshot",
            "error": err_msg,
        }

    cfg = get_config()

    if rect is not None:
        rx, ry, rw, rh = rect
        cg_rect = Quartz.CGRectMake(rx, ry, rw, rh)
    elif display_id is not None:
        cg_rect = Quartz.CGDisplayBounds(display_id)
    else:
        main_disp = display_manager.get_main_display()
        cg_rect = Quartz.CGRectMake(
            main_disp.origin_x,
            main_disp.origin_y,
            main_disp.width,
            main_disp.height,
        )

    # Capture image using Quartz
    cg_image = Quartz.CGWindowListCreateImage(
        cg_rect,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )

    if cg_image is None:
        zoe_logger.log_action("SCREENSHOT_FAILED")
        return {
            "success": False,
            "action": "take_screenshot",
            "error": "Quartz CGWindowListCreateImage returned null. Display may be asleep or locked.",
        }

    pixel_w = int(Quartz.CGImageGetWidth(cg_image))
    pixel_h = int(Quartz.CGImageGetHeight(cg_image))
    point_w = float(cg_rect.size.width)
    point_h = float(cg_rect.size.height)
    scale_factor = round(pixel_w / point_w, 2) if point_w > 0 else 1.0

    # Determine destination local file path
    if save_path is None:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        filename = f"screen_{now_str}.png"
        out_dir = Path(cfg.screenshots.storage_dir)
        dest_path = out_dir / filename
    else:
        dest_path = Path(save_path)

    saved = _save_cgimage_to_png(cg_image, dest_path)
    if not saved:
        return {
            "success": False,
            "action": "take_screenshot",
            "error": f"Failed to save screenshot to local destination: {dest_path}",
        }

    zoe_logger.log_action("SCREENSHOT", file=str(dest_path), width=pixel_w, height=pixel_h)

    return {
        "success": True,
        "action": "take_screenshot",
        "file_path": str(dest_path.resolve()),
        "width_points": point_w,
        "height_points": point_h,
        "width_pixels": pixel_w,
        "height_pixels": pixel_h,
        "scale_factor": scale_factor,
        "message": f"Screenshot captured locally ({pixel_w}x{pixel_h}px).",
    }


def capture_window(window_id: int, save_path: Optional[str] = None) -> Dict[str, Any]:
    """Capture a screenshot of a specific macOS window by window ID."""
    if not check_screen_recording_permission():
        return {
            "success": False,
            "action": "take_screenshot",
            "error": "Screen Recording permission not granted.",
        }

    cfg = get_config()
    cg_image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming,
    )

    if cg_image is None:
        return {
            "success": False,
            "action": "take_screenshot",
            "error": f"Failed to capture window ID {window_id}.",
        }

    pixel_w = int(Quartz.CGImageGetWidth(cg_image))
    pixel_h = int(Quartz.CGImageGetHeight(cg_image))

    if save_path is None:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        filename = f"window_{window_id}_{now_str}.png"
        dest_path = Path(cfg.screenshots.storage_dir) / filename
    else:
        dest_path = Path(save_path)

    saved = _save_cgimage_to_png(cg_image, dest_path)
    if not saved:
        return {
            "success": False,
            "action": "take_screenshot",
            "error": f"Failed to save window screenshot to {dest_path}",
        }

    zoe_logger.log_action("SCREENSHOT_WINDOW", window_id=window_id, file=str(dest_path))

    return {
        "success": True,
        "action": "take_screenshot",
        "window_id": window_id,
        "file_path": str(dest_path.resolve()),
        "width_pixels": pixel_w,
        "height_pixels": pixel_h,
        "message": f"Window {window_id} screenshot captured locally.",
    }


def capture_for_vision(
    max_dim: int = 1024,
    display_id: Optional[int] = None,
    rect: Optional[Tuple[float, float, float, float]] = None,
) -> Dict[str, Any]:
    """
    Capture screen in memory specifically for local vision model inference.
    Applies downscaling while preserving aspect ratio and records transformation metadata
    so vision model coordinate outputs can be mapped back accurately to screen coordinates.
    Zero disk writes required.
    """
    if not check_screen_recording_permission():
        return {
            "success": False,
            "error": "Screen Recording permission not granted.",
        }

    disp = display_manager.get_main_display()
    if display_id is not None:
        for d in display_manager.get_displays():
            if d.display_id == display_id:
                disp = d
                break

    if rect is not None:
        rx, ry, rw, rh = rect
        cg_rect = Quartz.CGRectMake(rx, ry, rw, rh)
        disp_origin_x = rx
        disp_origin_y = ry
        pt_w = rw
        pt_h = rh
    else:
        cg_rect = Quartz.CGRectMake(disp.origin_x, disp.origin_y, disp.width, disp.height)
        disp_origin_x = disp.origin_x
        disp_origin_y = disp.origin_y
        pt_w = disp.width
        pt_h = disp.height

    cg_image = Quartz.CGWindowListCreateImage(
        cg_rect,
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
        Quartz.kCGWindowImageDefault,
    )

    if cg_image is None:
        return {
            "success": False,
            "error": "Failed to capture display image via Quartz.",
        }

    orig_pixel_w = int(Quartz.CGImageGetWidth(cg_image))
    orig_pixel_h = int(Quartz.CGImageGetHeight(cg_image))

    # Convert to in-memory JPEG bytes
    raw_data = NSMutableData.data()
    dest = Quartz.CGImageDestinationCreateWithData(raw_data, "public.jpeg", 1, None)
    Quartz.CGImageDestinationAddImage(dest, cg_image, None)
    Quartz.CGImageDestinationFinalize(dest)

    # Open with Pillow in memory for aspect-ratio preserved resizing
    pil_img = Image.open(io.BytesIO(bytes(raw_data)))

    # Calculate resized dimensions
    scale_ratio = min(max_dim / float(orig_pixel_w), max_dim / float(orig_pixel_h), 1.0)
    vision_w = max(1, int(round(orig_pixel_w * scale_ratio)))
    vision_h = max(1, int(round(orig_pixel_h * scale_ratio)))

    if scale_ratio < 1.0:
        pil_resized = pil_img.resize((vision_w, vision_h), Image.Resampling.LANCZOS)
    else:
        pil_resized = pil_img

    # Encode resized image to base64
    out_buf = io.BytesIO()
    pil_resized.save(out_buf, format="JPEG", quality=85)
    b64_image = base64.b64encode(out_buf.getvalue()).decode("utf-8")

    # Build transformation metadata
    meta = ImageTransformMetadata.create(
        point_width=pt_w,
        point_height=pt_h,
        pixel_width=orig_pixel_w,
        pixel_height=orig_pixel_h,
        vision_width=vision_w,
        vision_height=vision_h,
        scale_factor=disp.scale_factor,
        origin_x=disp_origin_x,
        origin_y=disp_origin_y,
    )

    zoe_logger.log_action(
        "CAPTURE_FOR_VISION",
        orig_px=f"{orig_pixel_w}x{orig_pixel_h}",
        vision_px=f"{vision_w}x{vision_h}",
        scale=disp.scale_factor,
    )

    return {
        "success": True,
        "base64_image": b64_image,
        "metadata": meta,
        "vision_width": vision_w,
        "vision_height": vision_h,
        "original_points": [pt_w, pt_h],
        "original_pixels": [orig_pixel_w, orig_pixel_h],
    }
