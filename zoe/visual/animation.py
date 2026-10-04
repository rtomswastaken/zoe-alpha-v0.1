"""Smooth interpolation, Bezier trajectory calculations, and easing for the visual cursor."""

import math
from typing import List, Tuple


def ease_in_out_cubic(t: float) -> float:
    """Smooth cubic ease-in-out curve for natural visual movement."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        p = (2.0 * t) - 2.0
        return 0.5 * (p * p * p) + 1.0


def ease_out_quad(t: float) -> float:
    """Quadratic ease-out for quick decelerating arrivals."""
    t = max(0.0, min(1.0, t))
    return -1.0 * t * (t - 2.0)


def cubic_bezier_point(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    t: float,
) -> Tuple[float, float]:
    """Calculate 2D point along a cubic Bezier curve at parameter t in [0.0, 1.0]."""
    u = 1.0 - t
    tt = t * t
    uu = u * u
    u_cubed = uu * u
    t_cubed = tt * t

    x = (u_cubed * p0[0]) + (3.0 * uu * t * p1[0]) + (3.0 * u * tt * p2[0]) + (t_cubed * p3[0])
    y = (u_cubed * p0[1]) + (3.0 * uu * t * p1[1]) + (3.0 * u * tt * p2[1]) + (t_cubed * p3[1])
    return (x, y)


def generate_visual_trajectory(
    start: Tuple[float, float],
    end: Tuple[float, float],
    steps: int = 30,
    curvature: float = 0.15,
) -> List[Tuple[float, float]]:
    """
    Generate an aesthetic, human-like curved path for Zoe's visual cursor.
    Uses slight organic perpendicular bow so the cursor glides gracefully across UI.
    """
    if steps <= 1:
        return [end]

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    if dist < 2.0:
        return [end]

    # Perpendicular vector for subtle arching curve
    perp_x = -dy / dist
    perp_y = dx / dist
    arch_amount = min(dist * curvature, 40.0)

    # Control points
    p0 = start
    p1 = (start[0] + dx * 0.25 + perp_x * arch_amount, start[1] + dy * 0.25 + perp_y * arch_amount)
    p2 = (start[0] + dx * 0.75 + perp_x * (arch_amount * 0.5), start[1] + dy * 0.75 + perp_y * (arch_amount * 0.5))
    p3 = end

    trajectory: List[Tuple[float, float]] = []
    for i in range(1, steps + 1):
        t_raw = float(i) / float(steps)
        t_eased = ease_in_out_cubic(t_raw)
        pt = cubic_bezier_point(p0, p1, p2, p3, t_eased)
        trajectory.append((round(pt[0], 2), round(pt[1], 2)))

    return trajectory
