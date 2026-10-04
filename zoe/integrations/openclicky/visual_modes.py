"""Visual interaction modes: Explain, Guide, and Act."""

from typing import Any, Dict, Optional
from zoe.config import get_config
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.coordinates import (
    quartz_to_appkit,
    vision_to_openclicky,
    vision_to_quartz,
)
from zoe.integrations.openclicky.health import get_openclicky_client
from zoe.macos.accessibility import find_element_by_title, get_app_accessibility_tree, ax_click_at
from zoe.macos.logger import zoe_logger
from zoe.macos.screenshots import capture_for_vision
from zoe.models.vision_factory import get_vision_model


class VisualInteractionController:
    """
    Coordinates between Zoe's reasoning/vision engine, native macOS control,
    and OpenClicky's visual interaction layer.
    """

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def _get_client(self) -> OpenClickyClient:
        return self.client or get_openclicky_client()

    def explain(self, target: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """
        MODE 1 — Explain:
        'Where is the Wi-Fi button?'
        Locates UI element via vision/accessibility and directs OpenClicky cursor to point at it.
        Strictly zero real mouse movement.
        """
        cl = self._get_client()
        cfg = get_config()
        label = caption or f"Found: {target}"
        zoe_logger.log_action("VISUAL_MODE_EXPLAIN", target=target)

        # 1. Check Accessibility
        try:
            ax_res = get_app_accessibility_tree(max_depth=3)
            if ax_res.get("success") and "tree" in ax_res:
                elem = find_element_by_title(ax_res["tree"], target)
                if elem and elem.get("center"):
                    qx = elem["center"]["x"]
                    qy = elem["center"]["y"]
                    ax, ay = quartz_to_appkit(qx, qy)
                    cl.show_cursor(x=ax, y=ay, caption=label, mode="primary")
                    return {
                        "success": True,
                        "mode": "explain",
                        "target": target,
                        "source": "accessibility",
                        "coordinates": [qx, qy],
                        "message": f"Located '{target}' via Accessibility. Pointed with OpenClicky cursor.",
                    }
        except Exception:
            pass

        # 2. Vision Model
        vmodel = get_vision_model()
        if not vmodel.is_available():
            return {
                "success": False,
                "mode": "explain",
                "target": target,
                "error": "Vision model unavailable for explain mode.",
            }

        shot = capture_for_vision(max_dim=1024)
        if not shot.get("success"):
            return {
                "success": False,
                "mode": "explain",
                "target": target,
                "error": f"Failed to capture screen: {shot.get('error')}",
            }

        meta = shot["metadata"]
        threshold = cfg.vision.confidence_threshold
        v_res = vmodel.locate(shot["base64_image"], target, confidence_threshold=threshold)

        if v_res.found and v_res.x is not None and v_res.y is not None:
            ax, ay = vision_to_openclicky(v_res.x, v_res.y, meta, normalized=v_res.normalized)
            cl.show_cursor(x=ax, y=ay, caption=label, mode="primary")
            return {
                "success": True,
                "mode": "explain",
                "target": target,
                "source": "vision",
                "confidence": round(v_res.confidence, 2),
                "openclicky_coordinates": [ax, ay],
                "message": f"Located '{target}' visually ({v_res.confidence:.2f}). Pointed with OpenClicky cursor.",
            }

        return {
            "success": False,
            "mode": "explain",
            "target": target,
            "error": f"Could not locate '{target}'.",
        }

    def guide(
        self,
        target: str,
        caption: Optional[str] = None,
        accent_hex: Optional[str] = "#3B82F6",
    ) -> Dict[str, Any]:
        """
        MODE 2 — Guide:
        'Show me where I should click.'
        Locates UI element and displays OpenClicky cursor + guidance caption.
        Does NOT move the actual physical system pointer.
        """
        label = caption or f"Click here for {target}"
        zoe_logger.log_action("VISUAL_MODE_GUIDE", target=target)
        res = self.explain(target, caption=label)
        if res.get("success"):
            res["mode"] = "guide"
        return res

    def act(
        self,
        target: str,
        app_name: Optional[str] = None,
        button: str = "left",
    ) -> Dict[str, Any]:
        """
        MODE 3 — Act:
        'Click the Wi-Fi settings.'
        Preferred routing:
          1. Accessibility API -> AXUIElement -> Direct UI action
          2. Fallback: Vision -> Coordinate -> CGEvent mouse_click
        OpenClicky provides optional visual feedback, never taking over as sole actor.
        """
        cl = self._get_client()
        cfg = get_config()
        zoe_logger.log_action("VISUAL_MODE_ACT", target=target)

        # 1. Preferred route: Accessibility API
        try:
            ax_res = get_app_accessibility_tree(app_name_or_pid=app_name, max_depth=3)
            if ax_res.get("success") and "tree" in ax_res:
                elem = find_element_by_title(ax_res["tree"], target)
                if elem and elem.get("center"):
                    qx = elem["center"]["x"]
                    qy = elem["center"]["y"]
                    # Provide visual feedback via OpenClicky
                    try:
                        ax, ay = quartz_to_appkit(qx, qy)
                        cl.show_cursor(x=ax, y=ay, caption=f"Clicking: {target}", duration_ms=1500)
                    except Exception:
                        pass
                    # Perform real click via Accessibility-first cursorless action (Physical cursor stationary)
                    ax_success, ax_err = ax_click_at(qx, qy)
                    if not ax_success:
                        return {
                            "success": False,
                            "mode": "act",
                            "target": target,
                            "error": f"CURSORLESS_ACTION_UNAVAILABLE: Element '{target}' at ({qx}, {qy}) cannot be activated without moving physical mouse.",
                            "data": {"reason": ax_err},
                        }
                    return {
                        "success": True,
                        "mode": "act",
                        "target": target,
                        "source": "accessibility",
                        "clicked_at": [qx, qy],
                        "message": f"Activated '{target}' at ({qx}, {qy}) via Accessibility [Physical cursor stationary].",
                    }
        except Exception as e:
            zoe_logger.log_action("ACCESSIBILITY_FALLBACK", reason=str(e))

        # 2. Fallback route: Vision Model
        vmodel = get_vision_model()
        if not vmodel.is_available():
            return {
                "success": False,
                "mode": "act",
                "target": target,
                "error": "Target not found in Accessibility and vision model unavailable.",
            }

        shot = capture_for_vision(max_dim=1024)
        if not shot.get("success"):
            return {
                "success": False,
                "mode": "act",
                "target": target,
                "error": f"Failed to capture screen: {shot.get('error')}",
            }

        meta = shot["metadata"]
        threshold = cfg.vision.confidence_threshold
        v_res = vmodel.locate(shot["base64_image"], target, confidence_threshold=threshold)

        if v_res.found and v_res.x is not None and v_res.y is not None:
            qx, qy = vision_to_quartz(v_res.x, v_res.y, meta, normalized=v_res.normalized)
            try:
                ax, ay = quartz_to_appkit(qx, qy)
                cl.show_cursor(x=ax, y=ay, caption=f"Clicking: {target}", duration_ms=1500)
            except Exception:
                pass
            ax_success, ax_err = ax_click_at(qx, qy)
            if not ax_success:
                return {
                    "success": False,
                    "mode": "act",
                    "target": target,
                    "error": f"CURSORLESS_ACTION_UNAVAILABLE: Visual target '{target}' at ({qx}, {qy}) cannot be activated without moving physical mouse.",
                    "data": {"reason": ax_err},
                }
            return {
                "success": True,
                "mode": "act",
                "target": target,
                "source": "vision",
                "confidence": round(v_res.confidence, 2),
                "clicked_at": [qx, qy],
                "message": f"Visually located '{target}' ({v_res.confidence:.2f}) and activated at ({qx}, {qy}) via Accessibility [Physical cursor stationary].",
            }

        return {
            "success": False,
            "mode": "act",
            "target": target,
            "error": f"Could not locate '{target}' to perform click action.",
        }
