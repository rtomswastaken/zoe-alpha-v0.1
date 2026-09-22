"""Vision and hybrid Accessibility+Vision UI understanding tools."""

from typing import Any, Dict, Optional
from zoe.config import get_config
from zoe.macos.accessibility import get_app_accessibility_tree, find_element_by_title
from zoe.macos.screenshots import capture_for_vision
from zoe.macos.coordinates import vision_to_screen_points
from zoe.models.vision_factory import get_vision_model
from zoe.tools.base import BaseTool
from zoe.macos.logger import zoe_logger


class FindOnScreenTool(BaseTool):
    name = "find_on_screen"
    description = (
        "Locate a target UI control or element on screen using hybrid "
        "macOS Accessibility-first inspection with local computer vision fallback."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Name or description of the UI element to locate (e.g. 'fullscreen button', 'search box')",
            },
            "confidence_threshold": {
                "type": "number",
                "description": "Minimum confidence required (default 0.75)",
            },
            "app_name": {
                "type": "string",
                "description": "Optional specific application name to check Accessibility first",
            },
        },
        "required": ["target"],
    }

    def execute(
        self,
        target: str,
        confidence_threshold: Optional[float] = None,
        app_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        cfg = get_config()
        threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else cfg.vision.confidence_threshold
        )

        zoe_logger.log_action("FIND_ON_SCREEN", target=target)

        # -------------------------------------------------------------
        # 1. Primary Strategy: macOS Accessibility API (Fast & Precise)
        # -------------------------------------------------------------
        try:
            ax_res = get_app_accessibility_tree(app_name_or_pid=app_name, max_depth=3)
            if ax_res.get("success") and "tree" in ax_res:
                element = find_element_by_title(ax_res["tree"], target)
                if element and element.get("center"):
                    cx = element["center"]["x"]
                    cy = element["center"]["y"]
                    zoe_logger.log_action("UI_FOUND_ACCESSIBILITY", target=target, x=cx, y=cy)
                    return {
                        "success": True,
                        "found": True,
                        "source": "accessibility",
                        "target": target,
                        "coordinates": [cx, cy],
                        "confidence": 1.0,
                        "message": f"Found '{target}' via native Accessibility at ({cx}, {cy}).",
                    }
        except Exception as e:
            zoe_logger.log_action("ACCESSIBILITY_FALLBACK", reason=str(e))

        # -------------------------------------------------------------
        # 2. Fallback Strategy: Local Computer Vision Model
        # -------------------------------------------------------------
        vision_model = get_vision_model()
        if not vision_model.is_available():
            return {
                "success": False,
                "found": False,
                "target": target,
                "error": (
                    f"Target '{target}' was not found in Accessibility tree, and "
                    f"local vision model '{cfg.vision.model}' is currently unavailable."
                ),
            }

        # Capture screen in memory
        shot_res = capture_for_vision(max_dim=1024)
        if not shot_res.get("success"):
            return {
                "success": False,
                "found": False,
                "target": target,
                "error": f"Failed to capture screen for vision: {shot_res.get('error')}",
            }

        b64_img = shot_res["base64_image"]
        meta = shot_res["metadata"]

        # Run vision model locate
        v_res = vision_model.locate(b64_img, target, confidence_threshold=threshold)

        if v_res.found and v_res.x is not None and v_res.y is not None:
            # Map vision coordinates back to screen point space
            sx, sy = vision_to_screen_points(v_res.x, v_res.y, meta, normalized=v_res.normalized)
            zoe_logger.log_action(
                "UI_FOUND_VISION",
                target=target,
                x=sx,
                y=sy,
                confidence=round(v_res.confidence, 2),
            )
            return {
                "success": True,
                "found": True,
                "source": "vision",
                "target": target,
                "coordinates": [sx, sy],
                "confidence": round(v_res.confidence, 2),
                "message": f"Located '{target}' visually at ({sx}, {sy}) with confidence {v_res.confidence:.2f}.",
            }
        else:
            zoe_logger.log_action("UI_NOT_FOUND", target=target, confidence=round(v_res.confidence, 2))
            return {
                "success": True,
                "found": False,
                "target": target,
                "confidence": round(v_res.confidence, 2),
                "message": (
                    f"Could not locate '{target}' with sufficient confidence "
                    f"({v_res.confidence:.2f} < {threshold:.2f})."
                ),
            }


class InspectScreenTool(BaseTool):
    name = "inspect_screen"
    description = "Visually inspect the current macOS screen and describe visible windows, controls, or state."
    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Specific visual question or description request (e.g. 'Is the video playing in fullscreen?')",
            },
        },
    }

    def execute(self, prompt: Optional[str] = None) -> Dict[str, Any]:
        p = prompt or "Describe the visible application windows, controls, and screen state."
        vision_model = get_vision_model()

        if not vision_model.is_available():
            return {
                "success": False,
                "action": "inspect_screen",
                "error": "Local vision model is currently unavailable.",
            }

        shot_res = capture_for_vision(max_dim=1024)
        if not shot_res.get("success"):
            return {
                "success": False,
                "action": "inspect_screen",
                "error": f"Failed to capture screen: {shot_res.get('error')}",
            }

        analysis = vision_model.analyze(shot_res["base64_image"], p)
        zoe_logger.log_action("INSPECT_SCREEN", prompt=p[:40])

        return {
            "success": True,
            "action": "inspect_screen",
            "description": analysis.description,
        }
