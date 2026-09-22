"""Native macOS mouse automation using Quartz CGEvent."""

import time
from typing import Optional, Tuple
import Quartz
from zoe.config import get_config
from zoe.macos.cursor import get_cursor_position, move_cursor_smooth, calculate_smooth_trajectory, _set_raw_cursor_position
from zoe.macos.display import display_manager
from zoe.macos.emergency import emergency_controller
from zoe.macos.logger import zoe_logger

# State tracking for emergency button release
_mouse_buttons_held = {
    "left": False,
    "right": False,
}


def _emergency_release_mouse() -> None:
    """Safety callback to release any pressed mouse buttons when emergency stop fires."""
    curr_x, curr_y = get_cursor_position()
    pt = Quartz.CGPoint(curr_x, curr_y)
    if _mouse_buttons_held["left"]:
        evt = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft)
        if evt:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        _mouse_buttons_held["left"] = False
    if _mouse_buttons_held["right"]:
        evt = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventRightMouseUp, pt, Quartz.kCGMouseButtonRight)
        if evt:
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        _mouse_buttons_held["right"] = False


emergency_controller.register_cleanup_callback(_emergency_release_mouse)


def mouse_click(
    x: Optional[float] = None,
    y: Optional[float] = None,
    button: str = "left",
) -> Tuple[float, float]:
    """
    Perform a visible click at (x, y) or current cursor location.
    If x, y are provided, smoothly moves cursor there first.
    """
    emergency_controller.check_and_raise()
    cfg = get_config()

    if x is not None and y is not None:
        curr_x, curr_y = move_cursor_smooth(x, y)
        time.sleep(0.04)  # Small natural pause on target
    else:
        curr_x, curr_y = get_cursor_position()

    pt = Quartz.CGPoint(curr_x, curr_y)
    btn_type = button.lower()

    if btn_type == "right":
        down_type = Quartz.kCGEventRightMouseDown
        up_type = Quartz.kCGEventRightMouseUp
        cg_btn = Quartz.kCGMouseButtonRight
    else:
        down_type = Quartz.kCGEventLeftMouseDown
        up_type = Quartz.kCGEventLeftMouseUp
        cg_btn = Quartz.kCGMouseButtonLeft

    down_event = Quartz.CGEventCreateMouseEvent(None, down_type, pt, cg_btn)
    up_event = Quartz.CGEventCreateMouseEvent(None, up_type, pt, cg_btn)

    _mouse_buttons_held[btn_type] = True
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_event)
    time.sleep(cfg.mouse.click_delay)

    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_event)
    _mouse_buttons_held[btn_type] = False

    zoe_logger.log_action("CLICK", button=btn_type, x=round(curr_x, 1), y=round(curr_y, 1))
    return (curr_x, curr_y)


def mouse_right_click(x: Optional[float] = None, y: Optional[float] = None) -> Tuple[float, float]:
    return mouse_click(x, y, button="right")


def mouse_double_click(x: Optional[float] = None, y: Optional[float] = None) -> Tuple[float, float]:
    """Perform a double click with proper macOS kCGMouseEventClickState values."""
    emergency_controller.check_and_raise()
    cfg = get_config()

    if x is not None and y is not None:
        curr_x, curr_y = move_cursor_smooth(x, y)
        time.sleep(0.04)
    else:
        curr_x, curr_y = get_cursor_position()

    pt = Quartz.CGPoint(curr_x, curr_y)

    # Click 1
    d1 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft)
    u1 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventSetIntegerValueField(d1, Quartz.kCGMouseEventClickState, 1)
    Quartz.CGEventSetIntegerValueField(u1, Quartz.kCGMouseEventClickState, 1)

    # Click 2
    d2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, pt, Quartz.kCGMouseButtonLeft)
    u2 = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, pt, Quartz.kCGMouseButtonLeft)
    Quartz.CGEventSetIntegerValueField(d2, Quartz.kCGMouseEventClickState, 2)
    Quartz.CGEventSetIntegerValueField(u2, Quartz.kCGMouseEventClickState, 2)

    Quartz.CGEventPost(Quartz.kCGHIDEventTap, d1)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, u1)
    time.sleep(cfg.mouse.double_click_interval)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, d2)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, u2)

    zoe_logger.log_action("DOUBLE_CLICK", x=round(curr_x, 1), y=round(curr_y, 1))
    return (curr_x, curr_y)


def mouse_drag(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    duration: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Smoothly and visibly drag the mouse from start to end coordinates.
    Presses left mouse button, drags cursor visibly across intermediate points,
    and releases left mouse button at target.
    """
    emergency_controller.check_and_raise()
    cfg = get_config()
    if duration is None:
        duration = cfg.mouse.drag_duration

    # Smoothly position to start point
    start_x, start_y = move_cursor_smooth(start_x, start_y)
    time.sleep(0.05)

    # Mouse down
    start_pt = Quartz.CGPoint(start_x, start_y)
    down_evt = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, start_pt, Quartz.kCGMouseButtonLeft)
    _mouse_buttons_held["left"] = True
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_evt)
    time.sleep(0.04)

    # Trajectory points
    trajectory = calculate_smooth_trajectory((start_x, start_y), (end_x, end_y), steps=35, jitter=0.5)
    interval = duration / float(len(trajectory))

    try:
        for px, py in trajectory:
            emergency_controller.check_and_raise()
            _set_raw_cursor_position(px, py)
            drag_evt = Quartz.CGEventCreateMouseEvent(
                None,
                Quartz.kCGEventLeftMouseDragged,
                Quartz.CGPoint(px, py),
                Quartz.kCGMouseButtonLeft
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, drag_evt)
            time.sleep(interval)
    finally:
        # Guarantee mouse button release even on exception or emergency abort
        final_x, final_y = get_cursor_position()
        up_evt = Quartz.CGEventCreateMouseEvent(
            None,
            Quartz.kCGEventLeftMouseUp,
            Quartz.CGPoint(final_x, final_y),
            Quartz.kCGMouseButtonLeft
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_evt)
        _mouse_buttons_held["left"] = False

    zoe_logger.log_action("DRAG", start_x=round(start_x, 1), start_y=round(start_y, 1), end_x=round(end_x, 1), end_y=round(end_y, 1))
    return (end_x, end_y)


def mouse_scroll(vertical: int = 0, horizontal: int = 0) -> None:
    """
    Emit mouse scroll events in line units.
    Positive vertical scrolls UP, negative scrolls DOWN.
    Positive horizontal scrolls RIGHT, negative scrolls LEFT.
    """
    emergency_controller.check_and_raise()
    scroll_event = Quartz.CGEventCreateScrollWheelEvent(
        None,
        Quartz.kCGScrollEventUnitLine,
        2,
        int(vertical),
        int(horizontal)
    )
    if scroll_event is not None:
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, scroll_event)
    zoe_logger.log_action("SCROLL", vertical=vertical, horizontal=horizontal)
