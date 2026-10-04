"""Zoe native visual cursor and marker tools. Strictly visual — real mouse is untouched."""

from typing import Any, Dict, Optional
from zoe.tools.base import BaseTool
from zoe.visual.cursor import visual_cursor


class VisualCursorMoveTool(BaseTool):
    name = "visual_cursor_move"
    description = (
        "Smoothly glide Zoe's visual cursor to screen coordinates (x, y) with an optional caption. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X coordinate in screen points"},
            "y": {"type": "number", "description": "Y coordinate in screen points"},
            "caption": {"type": "string", "description": "Optional label next to the visual cursor"},
            "duration": {"type": "number", "description": "Glide duration in seconds (default 0.35)"},
        },
        "required": ["x", "y"],
    }

    def execute(self, x: float, y: float, caption: Optional[str] = None, duration: float = 0.35, **kwargs: Any) -> Dict[str, Any]:
        visual_cursor.move_smoothly_to(x=x, y=y, duration=duration, caption=caption, blocking=True)
        return {
            "success": True,
            "action": self.name,
            "visual_position": [x, y],
            "caption": caption,
            "message": f"Moved visual cursor to ({x}, {y}) [Real mouse was not moved].",
        }


class VisualCursorTargetTool(BaseTool):
    name = "visual_cursor_target"
    description = (
        "Target and highlight a screen coordinate with Zoe's glowing pointer and reticle. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X coordinate in screen points"},
            "y": {"type": "number", "description": "Y coordinate in screen points"},
            "caption": {"type": "string", "description": "Target element label or instruction"},
            "accent_hex": {"type": "string", "description": "Optional color hex (default '#00F0FF')"},
        },
        "required": ["x", "y"],
    }

    def execute(self, x: float, y: float, caption: Optional[str] = None, accent_hex: str = "#00F0FF", **kwargs: Any) -> Dict[str, Any]:
        visual_cursor.target(x=x, y=y, caption=caption, accent_hex=accent_hex)
        return {
            "success": True,
            "action": self.name,
            "target": [x, y],
            "caption": caption,
            "message": f"Targeted visual cursor at ({x}, {y}) [Real mouse was not moved].",
        }


class VisualCursorMarkerTool(BaseTool):
    name = "visual_cursor_marker"
    description = (
        "Place a temporary visual pin/marker on screen. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "X coordinate in screen points"},
            "y": {"type": "number", "description": "Y coordinate in screen points"},
            "caption": {"type": "string", "description": "Optional marker text label"},
            "duration": {"type": "number", "description": "Display duration in seconds (default 5.0)"},
            "accent_hex": {"type": "string", "description": "Optional marker color hex"},
        },
        "required": ["x", "y"],
    }

    def execute(self, x: float, y: float, caption: Optional[str] = None, duration: float = 5.0, accent_hex: str = "#3B82F6", **kwargs: Any) -> Dict[str, Any]:
        marker_id = visual_cursor.add_marker(x=x, y=y, caption=caption, duration=duration, accent_hex=accent_hex)
        return {
            "success": True,
            "action": self.name,
            "marker_id": marker_id,
            "coordinates": [x, y],
            "caption": caption,
            "message": f"Placed visual marker at ({x}, {y}) [Real mouse was not moved].",
        }


class VisualCursorCaptionTool(BaseTool):
    name = "visual_cursor_caption"
    description = (
        "Show a visual text label or guidance instruction near coordinates. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text caption to display"},
            "x": {"type": "number", "description": "Optional X coordinate"},
            "y": {"type": "number", "description": "Optional Y coordinate"},
        },
        "required": ["text"],
    }

    def execute(self, text: str, x: Optional[float] = None, y: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
        if x is not None and y is not None:
            visual_cursor.move_to(x, y, caption=text)
        else:
            visual_cursor.set_label(f"Zoe: {text}")
        return {
            "success": True,
            "action": self.name,
            "caption": text,
            "message": f"Displayed visual caption: '{text}'.",
        }


class VisualCursorClearTool(BaseTool):
    name = "visual_cursor_clear"
    description = "Clear all active visual cursor pointers, markers, and highlights."
    parameters_schema = {"type": "object", "properties": {}}

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        visual_cursor.clear()
        return {
            "success": True,
            "action": self.name,
            "message": "Cleared all visual cursor elements.",
        }
