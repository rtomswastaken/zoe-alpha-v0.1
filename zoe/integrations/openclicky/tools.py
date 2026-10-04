"""Zoe BaseTool implementations exposing OpenClicky capabilities to the agent planner."""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from zoe.config import get_config
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.coordinates import (
    appkit_to_quartz,
    quartz_to_appkit,
    vision_to_openclicky,
    vision_to_quartz,
)
from zoe.integrations.openclicky.health import check_openclicky_health, get_openclicky_client
from zoe.integrations.openclicky.models import OpenClickyError
from zoe.macos.accessibility import find_element_by_title, get_app_accessibility_tree
from zoe.macos.logger import zoe_logger
from zoe.macos.screenshots import capture_for_vision
from zoe.models.vision_factory import get_vision_model
from zoe.tools.base import BaseTool
from zoe.visual.cursor import visual_cursor

if TYPE_CHECKING:
    from zoe.tools.registry import ToolRegistry




class OpenClickyHealthTool(BaseTool):
    name = "openclicky_health"
    description = "Check the connectivity, latency, and status of the local OpenClicky visual overlay bridge."
    parameters_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()
        status = check_openclicky_health(cl)
        return {
            "success": status.connected,
            "action": self.name,
            "connected": status.connected,
            "bridge": status.bridge,
            "latency_ms": status.latency_ms,
            "tools_count": status.tools_count,
            "tools": status.tools,
            "error": status.error,
            "message": status.format_diagnostic(),
        }


class OpenClickyScreenshotTool(BaseTool):
    name = "openclicky_screenshot"
    description = (
        "Capture macOS screens via OpenClicky's screenshot API with display frame metadata."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "focused": {
                "type": "boolean",
                "description": "Capture only the active focused window if True, or all displays if False",
            },
        },
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(self, focused: bool = False, **kwargs: Any) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()
        try:
            resp = cl.screenshot(focused=focused)
            screens_data = [
                {
                    "label": s.label,
                    "path": s.path,
                    "is_cursor_screen": s.is_cursor_screen,
                    "display_frame": {
                        "x": s.display_frame.x,
                        "y": s.display_frame.y,
                        "width": s.display_frame.width,
                        "height": s.display_frame.height,
                    },
                    "width_points": s.display_width_points,
                    "height_points": s.display_height_points,
                    "width_pixels": s.screenshot_width_pixels,
                    "height_pixels": s.screenshot_height_pixels,
                }
                for s in resp.screens
            ]
            return {
                "success": True,
                "action": self.name,
                "count": resp.count,
                "focused": resp.focused,
                "screens": screens_data,
                "message": f"Captured {resp.count} screen(s) via OpenClicky.",
            }
        except OpenClickyError as e:
            return {
                "success": False,
                "action": self.name,
                "error": str(e),
            }


class OpenClickyPointTool(BaseTool):
    name = "openclicky_point"
    description = (
        "Point OpenClicky's native cursor at a macOS screen coordinate with an optional caption. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "X coordinate in screen points",
            },
            "y": {
                "type": "number",
                "description": "Y coordinate in screen points",
            },
            "caption": {
                "type": "string",
                "description": "Optional text label to display near the pointer",
            },
            "duration_ms": {
                "type": "number",
                "description": "Duration in milliseconds to display the pointer (default ~4000ms)",
            },
            "mode": {
                "type": "string",
                "enum": ["primary", "secondary"],
                "description": "Primary runs smooth pointing choreography; secondary shows a temporary marker",
            },
            "accent_hex": {
                "type": "string",
                "description": "Optional hex color for the pointer indicator (e.g. '#60A5FA')",
            },
            "travel_ms": {
                "type": "number",
                "description": "Travel animation time in milliseconds",
            },
            "coordinate_space": {
                "type": "string",
                "enum": ["quartz", "appkit"],
                "description": "Coordinate space of x, y. Default 'quartz' (macOS top-left origin).",
            },
        },
        "required": ["x", "y"],
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(
        self,
        x: float,
        y: float,
        caption: Optional[str] = None,
        duration_ms: Optional[float] = None,
        mode: str = "primary",
        accent_hex: Optional[str] = None,
        travel_ms: Optional[float] = None,
        coordinate_space: str = "quartz",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()

        # Convert coordinates
        if coordinate_space.lower() == "quartz":
            qx, qy = float(x), float(y)
            ax, ay = quartz_to_appkit(x, y)
        else:
            ax, ay = float(x), float(y)
            qx, qy = appkit_to_quartz(ax, ay)

        # Drive Zoe's native visual cursor overlay (zero real mouse movement)
        try:
            visual_cursor.move_smoothly_to(x=qx, y=qy, caption=caption, accent_hex=accent_hex or "#00F0FF")
        except Exception:
            pass

        try:
            res = cl.show_cursor(
                x=ax,
                y=ay,
                caption=caption,
                duration_ms=duration_ms,
                mode=mode,
                accent_hex=accent_hex,
                travel_ms=travel_ms,
            )
            return {
                "success": True,
                "action": self.name,
                "input_coordinates": [x, y],
                "openclicky_coordinates": [ax, ay],
                "caption": caption,
                "mode": mode,
                "response": res,
                "message": f"Pointed visual cursor at ({x}, {y})" + (f" with caption '{caption}'" if caption else ""),
            }
        except OpenClickyError as e:
            if self.client is not None:
                return {
                    "success": False,
                    "action": self.name,
                    "error": str(e),
                }
            return {
                "success": True,
                "action": self.name,
                "input_coordinates": [x, y],
                "openclicky_coordinates": [ax, ay],
                "caption": caption,
                "mode": mode,
                "fallback": "native_visual_overlay",
                "message": f"Pointed Zoe native visual cursor at ({x}, {y}) [OpenClicky offline: {e}].",
            }


class OpenClickyMultiPointTool(BaseTool):
    name = "openclicky_multi_point"
    description = (
        "Point at multiple visible screen targets simultaneously with secondary OpenClicky markers. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "cursors": {
                "type": "array",
                "description": "List of cursor targets, each with 'x', 'y', and optional 'caption', 'accentHex'",
                "items": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "caption": {"type": "string"},
                        "accentHex": {"type": "string"},
                        "durationMs": {"type": "number"},
                    },
                    "required": ["x", "y"],
                },
            },
            "duration_ms": {
                "type": "number",
                "description": "Global duration for all markers in milliseconds",
            },
            "coordinate_space": {
                "type": "string",
                "enum": ["quartz", "appkit"],
                "description": "Default 'quartz' (converts to AppKit)",
            },
        },
        "required": ["cursors"],
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(
        self,
        cursors: List[Dict[str, Any]],
        duration_ms: Optional[float] = None,
        coordinate_space: str = "quartz",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()

        converted_cursors: List[Dict[str, Any]] = []
        is_quartz = coordinate_space.lower() == "quartz"
        for c in cursors:
            cx = float(c["x"])
            cy = float(c["y"])
            if is_quartz:
                qx, qy = cx, cy
                ax, ay = quartz_to_appkit(cx, cy)
            else:
                ax, ay = cx, cy
                qx, qy = appkit_to_quartz(ax, ay)

            entry: Dict[str, Any] = {"x": ax, "y": ay}
            if "caption" in c:
                entry["caption"] = c["caption"]
            if "accentHex" in c:
                entry["accentHex"] = c["accentHex"]
            if "durationMs" in c:
                entry["durationMs"] = c["durationMs"]
            converted_cursors.append(entry)

            # Drive Zoe native visual cursor markers
            try:
                visual_cursor.add_marker(
                    x=qx,
                    y=qy,
                    caption=c.get("caption"),
                    duration=(float(c.get("durationMs") or duration_ms or 5000.0) / 1000.0),
                    accent_hex=c.get("accentHex") or "#3B82F6",
                )
            except Exception:
                pass

        try:
            res = cl.show_cursors(converted_cursors, duration_ms=duration_ms)
            return {
                "success": True,
                "action": self.name,
                "count": len(converted_cursors),
                "response": res,
                "message": f"Displayed {len(converted_cursors)} visual markers.",
            }
        except OpenClickyError as e:
            if self.client is not None:
                return {
                    "success": False,
                    "action": self.name,
                    "error": str(e),
                }
            return {
                "success": True,
                "action": self.name,
                "count": len(converted_cursors),
                "fallback": "native_visual_overlay",
                "message": f"Displayed {len(converted_cursors)} Zoe native visual markers [OpenClicky offline: {e}].",
            }


class OpenClickyCaptionTool(BaseTool):
    name = "openclicky_caption"
    description = (
        "Display a visual caption bubble on the screen using OpenClicky. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text content to display in the caption bubble",
            },
            "x": {
                "type": "number",
                "description": "Optional X coordinate in screen points",
            },
            "y": {
                "type": "number",
                "description": "Optional Y coordinate in screen points",
            },
            "duration_ms": {
                "type": "number",
                "description": "Display duration in milliseconds",
            },
            "accent_hex": {
                "type": "string",
                "description": "Optional accent color hex",
            },
            "coordinate_space": {
                "type": "string",
                "enum": ["quartz", "appkit"],
                "description": "Default 'quartz'",
            },
        },
        "required": ["text"],
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(
        self,
        text: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        duration_ms: Optional[float] = None,
        accent_hex: Optional[str] = None,
        coordinate_space: str = "quartz",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()

        ax = None
        ay = None
        qx = None
        qy = None
        if x is not None and y is not None:
            if coordinate_space.lower() == "quartz":
                qx, qy = float(x), float(y)
                ax, ay = quartz_to_appkit(x, y)
            else:
                ax, ay = float(x), float(y)
                qx, qy = appkit_to_quartz(ax, ay)
            try:
                visual_cursor.target(qx, qy, caption=text, accent_hex=accent_hex or "#00F0FF")
            except Exception:
                pass
        else:
            try:
                visual_cursor.set_label(f"Zoe: {text}")
            except Exception:
                pass

        try:
            res = cl.show_caption(
                text=text,
                x=ax,
                y=ay,
                duration_ms=duration_ms,
                accent_hex=accent_hex,
            )
            return {
                "success": True,
                "action": self.name,
                "text": text,
                "response": res,
                "message": f"Displayed caption: '{text}'",
            }
        except OpenClickyError as e:
            if self.client is not None:
                return {
                    "success": False,
                    "action": self.name,
                    "error": str(e),
                }
            return {
                "success": True,
                "action": self.name,
                "text": text,
                "fallback": "native_visual_overlay",
                "message": f"Displayed visual caption '{text}' [OpenClicky offline: {e}].",
            }


class OpenClickySpeakTool(BaseTool):
    name = "openclicky_speak"
    description = "Speak a short instructional phrase through OpenClicky TTS without entering voice mode."
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Instruction text to speak aloud",
            },
            "interrupt": {
                "type": "boolean",
                "description": "Interrupt any ongoing speech if True",
            },
        },
        "required": ["text"],
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(self, text: str, interrupt: bool = False, **kwargs: Any) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()
        try:
            res = cl.speak(text=text, interrupt=interrupt)
            return {
                "success": True,
                "action": self.name,
                "spoken": text,
                "response": res,
                "message": f"Spoke via OpenClicky: '{text}'",
            }
        except OpenClickyError as e:
            return {
                "success": False,
                "action": self.name,
                "error": str(e),
            }


class OpenClickyClearTool(BaseTool):
    name = "openclicky_clear"
    description = (
        "Clear all active OpenClicky visual overlay pointers, captions, and highlights. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()
        try:
            visual_cursor.clear()
        except Exception:
            pass

        try:
            res = cl.clear()
            return {
                "success": True,
                "action": self.name,
                "response": res,
                "message": "Cleared OpenClicky visual overlay.",
            }
        except OpenClickyError as e:
            if self.client is not None:
                return {
                    "success": False,
                    "action": self.name,
                    "error": str(e),
                }
            return {
                "success": True,
                "action": self.name,
                "fallback": "native_visual_overlay",
                "message": "Cleared visual overlay [OpenClicky offline].",
            }


class OpenClickyGuideTool(BaseTool):
    name = "openclicky_guide"
    description = (
        "Visually locate and point out a target UI element on screen using OpenClicky's pointer. "
        "Combines accessibility + local vision with OpenClicky's smooth visual cursor. "
        "VISUAL ONLY — DOES NOT MOVE THE REAL MACOS CURSOR."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Name or description of the UI element to highlight (e.g. 'Wi-Fi settings', 'Downloads folder')",
            },
            "caption": {
                "type": "string",
                "description": "Optional custom caption to display with the pointer (defaults to target)",
            },
            "app_name": {
                "type": "string",
                "description": "Optional specific application to inspect first via Accessibility",
            },
            "duration_ms": {
                "type": "number",
                "description": "Pointer display duration in milliseconds (default 4500)",
            },
        },
        "required": ["target"],
    }

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def execute(
        self,
        target: str,
        caption: Optional[str] = None,
        app_name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()
        cfg = get_config()
        label = caption or target

        # 1. Check Accessibility API first
        try:
            ax_res = get_app_accessibility_tree(app_name_or_pid=app_name, max_depth=3)
            if ax_res.get("success") and "tree" in ax_res:
                elem = find_element_by_title(ax_res["tree"], target)
                if elem and elem.get("center"):
                    qx = elem["center"]["x"]
                    qy = elem["center"]["y"]
                    ax, ay = quartz_to_appkit(qx, qy)
                    try:
                        visual_cursor.target(x=qx, y=qy, caption=label)
                    except Exception:
                        pass
                    try:
                        cl.show_cursor(x=ax, y=ay, caption=label, duration_ms=duration_ms)
                    except Exception:
                        pass
                    return {
                        "success": True,
                        "action": self.name,
                        "target": target,
                        "source": "accessibility",
                        "quartz_coordinates": [qx, qy],
                        "openclicky_coordinates": [ax, ay],
                        "confidence": 1.0,
                        "message": f"Located '{target}' via Accessibility and highlighted visually.",
                    }
        except Exception as e:
            zoe_logger.log_action("ACCESSIBILITY_FALLBACK", reason=str(e))

        # 2. Fall back to Vision Model
        vmodel = get_vision_model()
        if not vmodel.is_available():
            return {
                "success": False,
                "action": self.name,
                "error": f"Target '{target}' not found in Accessibility and vision model is unavailable.",
            }

        shot = capture_for_vision(max_dim=1024)
        if not shot.get("success"):
            return {
                "success": False,
                "action": self.name,
                "error": f"Failed to capture screen for vision: {shot.get('error')}",
            }

        meta = shot["metadata"]
        threshold = cfg.vision.confidence_threshold
        v_res = vmodel.locate(shot["base64_image"], target, confidence_threshold=threshold)

        if v_res.found and v_res.x is not None and v_res.y is not None:
            # Canonical coordinate conversion: Vision -> Quartz -> OpenClicky (AppKit)
            qx, qy = vision_to_quartz(v_res.x, v_res.y, meta, normalized=v_res.normalized)
            ax, ay = quartz_to_appkit(qx, qy)
            try:
                visual_cursor.target(x=qx, y=qy, caption=label)
            except Exception:
                pass
            try:
                cl.show_cursor(x=ax, y=ay, caption=label, duration_ms=duration_ms)
            except Exception:
                pass
            return {
                "success": True,
                "action": self.name,
                "target": target,
                "source": "vision",
                "openclicky_coordinates": [ax, ay],
                "confidence": round(v_res.confidence, 2),
                "message": f"Visually located '{target}' (confidence {v_res.confidence:.2f}) and highlighted visually.",
            }

        return {
            "success": False,
            "action": self.name,
            "target": target,
            "error": f"Could not locate '{target}' with sufficient confidence.",
        }


def register_openclicky_tools(registry: Any, client: Optional[OpenClickyClient] = None) -> None:
    """Register all OpenClicky tools with Zoe's central ToolRegistry."""
    registry.register(OpenClickyHealthTool(client))
    registry.register(OpenClickyScreenshotTool(client))
    registry.register(OpenClickyPointTool(client))
    registry.register(OpenClickyMultiPointTool(client))
    registry.register(OpenClickyCaptionTool(client))
    registry.register(OpenClickySpeakTool(client))
    registry.register(OpenClickyClearTool(client))
    registry.register(OpenClickyGuideTool(client))
