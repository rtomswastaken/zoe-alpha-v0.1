"""Native macOS keyboard automation and shortcut execution using Quartz."""

import time
from typing import Dict, List, Optional
import Quartz
from zoe.config import get_config
from zoe.macos.emergency import emergency_controller
from zoe.macos.logger import zoe_logger

# Virtual key codes from HIToolbox/Events.h
KEY_CODES: Dict[str, int] = {
    # Special keys
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "backspace": 51,
    "delete": 51,
    "escape": 53,
    "esc": 53,
    "command": 55,
    "cmd": 55,
    "shift": 56,
    "capslock": 57,
    "option": 58,
    "alt": 58,
    "control": 59,
    "ctrl": 59,
    "rightshift": 60,
    "rightoption": 61,
    "rightcontrol": 62,
    # Navigation
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "pageup": 116,
    "pagedown": 121,
    "home": 115,
    "end": 119,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    # Letters
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19,
    "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28,
    "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38,
    "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
    "`": 50,
}

MODIFIER_MASKS: Dict[str, int] = {
    "command": Quartz.kCGEventFlagMaskCommand,
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "control": Quartz.kCGEventFlagMaskControl,
    "ctrl": Quartz.kCGEventFlagMaskControl,
}


def key_down(key: str, flags: int = 0) -> None:
    """Send key down event for specified key name."""
    emergency_controller.check_and_raise()
    code = KEY_CODES.get(key.lower())
    if code is None:
        raise ValueError(f"Unknown key: '{key}'")

    event = Quartz.CGEventCreateKeyboardEvent(None, code, True)
    if flags != 0:
        Quartz.CGEventSetFlags(event, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def key_up(key: str, flags: int = 0) -> None:
    """Send key up event for specified key name."""
    code = KEY_CODES.get(key.lower())
    if code is None:
        return
    event = Quartz.CGEventCreateKeyboardEvent(None, code, False)
    if flags != 0:
        Quartz.CGEventSetFlags(event, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def press_key(key: str, duration: Optional[float] = None) -> None:
    """Press and release a single key."""
    emergency_controller.check_and_raise()
    cfg = get_config()
    if duration is None:
        duration = cfg.keyboard.key_press_duration

    key_down(key)
    time.sleep(duration)
    key_up(key)

    zoe_logger.log_action("PRESS_KEY", key=key)


def hotkey(*keys: str) -> None:
    """
    Execute a keyboard shortcut with modifiers and a primary key.
    Example: hotkey("command", "space") or hotkey("command", "shift", "3")
    """
    emergency_controller.check_and_raise()
    if not keys:
        return

    modifier_flag = 0
    non_modifiers: List[str] = []

    for k in keys:
        norm = k.lower()
        if norm in MODIFIER_MASKS:
            modifier_flag |= MODIFIER_MASKS[norm]
        else:
            non_modifiers.append(norm)

    # Press down modifier keys
    for k in keys:
        norm = k.lower()
        if norm in KEY_CODES and norm in MODIFIER_MASKS:
            key_down(norm)

    time.sleep(0.02)

    # Press and release main keys with combined flags
    for k in non_modifiers:
        emergency_controller.check_and_raise()
        code = KEY_CODES.get(k)
        if code is not None:
            evt_down = Quartz.CGEventCreateKeyboardEvent(None, code, True)
            if modifier_flag:
                Quartz.CGEventSetFlags(evt_down, modifier_flag)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt_down)
            time.sleep(0.03)

            evt_up = Quartz.CGEventCreateKeyboardEvent(None, code, False)
            if modifier_flag:
                Quartz.CGEventSetFlags(evt_up, modifier_flag)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt_up)

    time.sleep(0.02)

    # Release modifier keys in reverse order
    for k in reversed(keys):
        norm = k.lower()
        if norm in KEY_CODES and norm in MODIFIER_MASKS:
            key_up(norm)

    zoe_logger.log_action("HOTKEY", keys="+".join(keys))


def type_text(text: str, delay: Optional[float] = None) -> None:
    """
    Type a string of text visibly with human-like inter-character delay.
    Uses Unicode event injection to accurately type special characters and emojis.
    """
    emergency_controller.check_and_raise()
    cfg = get_config()
    if delay is None:
        delay = cfg.keyboard.typing_delay

    for char in text:
        emergency_controller.check_and_raise()

        if char == "\n":
            press_key("return", duration=delay)
            continue
        elif char == "\t":
            press_key("tab", duration=delay)
            continue

        # Unicode keyboard event synthesis
        evt_down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(evt_down, len(char), char)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt_down)

        time.sleep(delay / 2.0)

        evt_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
        Quartz.CGEventKeyboardSetUnicodeString(evt_up, len(char), char)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt_up)

        time.sleep(delay / 2.0)

    zoe_logger.log_action("TYPE_TEXT", length=len(text), text=text)
