"""Computer control tools: mouse, cursor, keyboard, screenshots."""

from typing import Any, Dict, List, Optional
from zoe.macos.cursor import move_cursor_smooth, get_cursor_position
from zoe.macos.mouse import (
    mouse_click,
    mouse_double_click,
    mouse_right_click,
    mouse_drag,
    mouse_scroll,
)
from zoe.macos.keyboard import press_key, hotkey, type_text
from zoe.macos.screenshots import capture_screen
from zoe.macos.display import display_manager
from zoe.macos.emergency import emergency_controller, EmergencyStopTriggeredException
from zoe.tools.base import BaseTool, ToolResult


class MoveCursorTool(BaseTool):
    name = "move_cursor"
    description = "Visibly and smoothly move the mouse cursor to target (x, y) coordinates."
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "Target X coordinate in points"},
            "y": {"type": "number", "description": "Target Y coordinate in points"},
            "duration": {"type": "number", "description": "Duration of movement in seconds (default 0.35s)"},
        },
        "required": ["x", "y"],
    }

    def execute(self, x: float, y: float, duration: Optional[float] = None) -> Dict[str, Any]:
        try:
            tx, ty = move_cursor_smooth(float(x), float(y), duration=duration)
            return ToolResult(
                success=True,
                action="move_cursor",
                message=f"Cursor moved to ({tx:.1f}, {ty:.1f})",
                data={"coordinates": [round(tx, 1), round(ty, 1)]},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="move_cursor", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="move_cursor", error=str(e)).to_dict()


class ClickTool(BaseTool):
    name = "click"
    description = "Click mouse at coordinates (x, y) or current location."
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "Optional target X coordinate"},
            "y": {"type": "number", "description": "Optional target Y coordinate"},
            "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
        },
    }

    def execute(self, x: Optional[float] = None, y: Optional[float] = None, button: str = "left") -> Dict[str, Any]:
        try:
            fx = float(x) if x is not None else None
            fy = float(y) if y is not None else None
            cx, cy = mouse_click(x=fx, y=fy, button=button)
            return ToolResult(
                success=True,
                action="click",
                message=f"{button.capitalize()} click completed at ({cx:.1f}, {cy:.1f})",
                data={"coordinates": [round(cx, 1), round(cy, 1)], "button": button},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="click", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="click", error=str(e)).to_dict()


class DoubleClickTool(BaseTool):
    name = "double_click"
    description = "Double-click mouse at coordinates (x, y) or current location."
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "Optional target X coordinate"},
            "y": {"type": "number", "description": "Optional target Y coordinate"},
        },
    }

    def execute(self, x: Optional[float] = None, y: Optional[float] = None) -> Dict[str, Any]:
        try:
            fx = float(x) if x is not None else None
            fy = float(y) if y is not None else None
            cx, cy = mouse_double_click(x=fx, y=fy)
            return ToolResult(
                success=True,
                action="double_click",
                message=f"Double click completed at ({cx:.1f}, {cy:.1f})",
                data={"coordinates": [round(cx, 1), round(cy, 1)]},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="double_click", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="double_click", error=str(e)).to_dict()


class RightClickTool(BaseTool):
    name = "right_click"
    description = "Right-click mouse at coordinates (x, y) or current location."
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "Optional target X coordinate"},
            "y": {"type": "number", "description": "Optional target Y coordinate"},
        },
    }

    def execute(self, x: Optional[float] = None, y: Optional[float] = None) -> Dict[str, Any]:
        try:
            fx = float(x) if x is not None else None
            fy = float(y) if y is not None else None
            cx, cy = mouse_right_click(x=fx, y=fy)
            return ToolResult(
                success=True,
                action="right_click",
                message=f"Right click completed at ({cx:.1f}, {cy:.1f})",
                data={"coordinates": [round(cx, 1), round(cy, 1)]},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="right_click", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="right_click", error=str(e)).to_dict()


class DragTool(BaseTool):
    name = "drag"
    description = "Visibly drag from (start_x, start_y) to (end_x, end_y)."
    parameters_schema = {
        "type": "object",
        "properties": {
            "start_x": {"type": "number"},
            "start_y": {"type": "number"},
            "end_x": {"type": "number"},
            "end_y": {"type": "number"},
            "duration": {"type": "number", "default": 0.5},
        },
        "required": ["start_x", "start_y", "end_x", "end_y"],
    }

    def execute(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        duration: Optional[float] = None,
    ) -> Dict[str, Any]:
        try:
            rx, ry = mouse_drag(float(start_x), float(start_y), float(end_x), float(end_y), duration=duration)
            return ToolResult(
                success=True,
                action="drag",
                message=f"Dragged from ({start_x}, {start_y}) to ({rx:.1f}, {ry:.1f})",
                data={"start": [start_x, start_y], "end": [rx, ry]},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="drag", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="drag", error=str(e)).to_dict()


class ScrollTool(BaseTool):
    name = "scroll"
    description = "Scroll the screen vertically and/or horizontally."
    parameters_schema = {
        "type": "object",
        "properties": {
            "vertical": {"type": "integer", "description": "Positive for UP, negative for DOWN"},
            "horizontal": {"type": "integer", "description": "Positive for RIGHT, negative for LEFT", "default": 0},
        },
        "required": ["vertical"],
    }

    def execute(self, vertical: int, horizontal: int = 0) -> Dict[str, Any]:
        try:
            mouse_scroll(int(vertical), int(horizontal))
            return ToolResult(
                success=True,
                action="scroll",
                message=f"Scrolled vertical={vertical}, horizontal={horizontal}",
                data={"vertical": vertical, "horizontal": horizontal},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="scroll", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="scroll", error=str(e)).to_dict()


class TypeTextTool(BaseTool):
    name = "type_text"
    description = "Type text visibly on the Mac keyboard."
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type"},
            "delay": {"type": "number", "description": "Inter-key delay in seconds (default 0.02s)"},
        },
        "required": ["text"],
    }

    def execute(self, text: str, delay: Optional[float] = None) -> Dict[str, Any]:
        try:
            type_text(str(text), delay=delay)
            return ToolResult(
                success=True,
                action="type_text",
                message=f"Typed {len(text)} characters",
                data={"length": len(text)},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="type_text", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="type_text", error=str(e)).to_dict()


class PressKeyTool(BaseTool):
    name = "press_key"
    description = "Press a single keyboard key (e.g. return, space, escape, tab, f1)."
    parameters_schema = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Name of key (e.g. return, space, escape)"},
        },
        "required": ["key"],
    }

    def execute(self, key: str) -> Dict[str, Any]:
        try:
            press_key(str(key))
            return ToolResult(
                success=True,
                action="press_key",
                message=f"Pressed key '{key}'",
                data={"key": key},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="press_key", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="press_key", error=str(e)).to_dict()


class HotkeyTool(BaseTool):
    name = "hotkey"
    description = "Execute a keyboard shortcut (e.g. ['command', 'space'] or ['command', 'c'])."
    parameters_schema = {
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of keys (e.g. ['command', 'space'])",
            }
        },
        "required": ["keys"],
    }

    def execute(self, keys: List[str]) -> Dict[str, Any]:
        try:
            hotkey(*keys)
            return ToolResult(
                success=True,
                action="hotkey",
                message=f"Executed hotkey: {'+'.join(keys)}",
                data={"keys": keys},
            ).to_dict()
        except EmergencyStopTriggeredException as e:
            return ToolResult(success=False, action="hotkey", error=str(e)).to_dict()
        except Exception as e:
            return ToolResult(success=False, action="hotkey", error=str(e)).to_dict()


class TakeScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = "Capture a local screenshot of the desktop or display."
    parameters_schema = {
        "type": "object",
        "properties": {
            "save_path": {"type": "string", "description": "Optional local path to save PNG file"},
            "display_id": {"type": "integer", "description": "Optional specific display ID to capture"},
        },
    }

    def execute(self, save_path: Optional[str] = None, display_id: Optional[int] = None) -> Dict[str, Any]:
        return capture_screen(display_id=display_id, save_path=save_path)
