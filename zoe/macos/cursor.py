"""Visible, smooth, human-like cursor movement and positioning using Quartz."""

import math
import random
import time
from typing import List, Tuple, Optional
import Quartz
from zoe.config import get_config
from zoe.macos.display import display_manager
from zoe.macos.emergency import emergency_controller
from zoe.macos.logger import zoe_logger


def get_cursor_position() -> Tuple[float, float]:
    """Get the current cursor location in logical point coordinates."""
    event = Quartz.CGEventCreate(None)
    if event is None:
        main_disp = display_manager.get_main_display()
        return (main_disp.origin_x + main_disp.width / 2.0, main_disp.origin_y + main_disp.height / 2.0)
    point = Quartz.CGEventGetLocation(event)
    return (float(point.x), float(point.y))


def _set_raw_cursor_position(x: float, y: float) -> None:
    """Instantly set physical macOS cursor position and post mouse moved event."""
    cg_point = Quartz.CGPoint(x, y)
    Quartz.CGWarpMouseCursorPosition(cg_point)
    move_event = Quartz.CGEventCreateMouseEvent(
        None,
        Quartz.kCGEventMouseMoved,
        cg_point,
        Quartz.kCGMouseButtonLeft
    )
    if move_event is not None:
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, move_event)


def _cubic_bezier(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """Calculate 1D point along cubic Bezier curve at parameter t in [0, 1]."""
    u = 1.0 - t
    tt = t * t
    uu = u * u
    return (uu * u * p0) + (3.0 * uu * t * p1) + (3.0 * u * tt * p2) + (tt * t * p3)


def _ease_in_out(t: float) -> float:
    """Smooth sine-based easing function."""
    return (1.0 - math.cos(t * math.pi)) / 2.0


def calculate_smooth_trajectory(
    start: Tuple[float, float],
    end: Tuple[float, float],
    steps: int = 40,
    jitter: float = 1.5,
) -> List[Tuple[float, float]]:
    """
    Generate a human-like smooth trajectory between start and end coordinates
    using a curved cubic Bezier path with slight organic deviation.
    """
    x0, y0 = start
    x3, y3 = end
    dist = math.hypot(x3 - x0, y3 - y0)

    if dist < 2.0 or steps <= 1:
        return [(x3, y3)]

    # Orthogonal unit vector for human-like arc curvature
    dx = x3 - x0
    dy = y3 - y0
    norm = math.hypot(dx, dy)
    perp_x = -dy / norm
    perp_y = dx / norm

    # Organic arc offset proportional to distance
    max_arc = min(dist * 0.25, 80.0)
    arc_magnitude = (random.random() - 0.5) * max_arc

    # Control points P1 and P2
    x1 = x0 + (dx * 0.33) + (perp_x * arc_magnitude)
    y1 = y0 + (dy * 0.33) + (perp_y * arc_magnitude)
    x2 = x0 + (dx * 0.66) + (perp_x * arc_magnitude * 0.8)
    y2 = y0 + (dy * 0.66) + (perp_y * arc_magnitude * 0.8)

    points: List[Tuple[float, float]] = []
    for i in range(1, steps + 1):
        raw_t = i / float(steps)
        t = _ease_in_out(raw_t)

        # Bezier interpolation
        bx = _cubic_bezier(x0, x1, x2, x3, t)
        by = _cubic_bezier(y0, y1, y2, y3, t)

        # Micro-jitter during flight (drops to 0 near the target)
        if jitter > 0 and i < steps:
            jitter_scale = (1.0 - raw_t) * jitter
            bx += (random.random() - 0.5) * jitter_scale
            by += (random.random() - 0.5) * jitter_scale

        points.append((bx, by))

    # Guarantee final point is exactly the target
    points[-1] = (x3, y3)
    return points


def move_cursor_smooth(
    target_x: float,
    target_y: float,
    duration: Optional[float] = None,
    steps: Optional[int] = None,
    smooth: bool = True,
) -> Tuple[float, float]:
    """
    Visibly move the macOS cursor from its current position to (target_x, target_y).
    Aborts immediately if emergency stop is triggered.
    """
    emergency_controller.check_and_raise()

    cfg = get_config()
    if duration is None:
        duration = cfg.cursor.default_duration
    if steps is None:
        steps = cfg.cursor.default_steps

    # Validate and clamp target to available displays
    if cfg.cursor.bounds_check:
        target_x, target_y = display_manager.clamp_to_screen(target_x, target_y)

    start_x, start_y = get_cursor_position()

    dist = math.hypot(target_x - start_x, target_y - start_y)
    if dist < 1.0:
        return (target_x, target_y)

    # Scale steps and duration for very short or very long moves
    if duration <= 0.0 or not smooth:
        _set_raw_cursor_position(target_x, target_y)
        zoe_logger.log_action("MOVE_CURSOR", x=round(target_x, 1), y=round(target_y, 1), duration=0.0)
        return (target_x, target_y)

    # Calculate points
    actual_steps = max(10, int(steps * (min(dist, 1000.0) / 500.0)))
    trajectory = calculate_smooth_trajectory(
        (start_x, start_y),
        (target_x, target_y),
        steps=actual_steps,
        jitter=cfg.cursor.jitter
    )

    interval = duration / float(len(trajectory))

    for px, py in trajectory:
        emergency_controller.check_and_raise()
        _set_raw_cursor_position(px, py)
        time.sleep(interval)

    # Ensure target position
    _set_raw_cursor_position(target_x, target_y)
    zoe_logger.log_action("MOVE_CURSOR", x=round(target_x, 1), y=round(target_y, 1), duration=round(duration, 2))
    return (target_x, target_y)
