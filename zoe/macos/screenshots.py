"""Local macOS screenshot capture via Quartz CoreGraphics."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from Foundation import NSURL
import Quartz
from zoe.config import get_config
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
