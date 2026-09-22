"""macOS Accessibility API (AXUIElement) traversal and UI hierarchy inspection."""

from typing import Any, Dict, List, Optional, Tuple
import ApplicationServices
from zoe.macos.apps import find_running_app, get_active_app
from zoe.macos.permissions import check_accessibility_permission
from zoe.macos.logger import zoe_logger

# AXError definitions
AX_ERRORS: Dict[int, str] = {
    0: "Success",
    -25200: "kAXErrorFailure: Generic failure",
    -25201: "kAXErrorIllegalArgument: Invalid argument",
    -25202: "kAXErrorInvalidUIElement: Invalid UI element",
    -25203: "kAXErrorInvalidUIElementObserver: Invalid observer",
    -25204: "kAXErrorCannotComplete: Operation could not complete",
    -25205: "kAXErrorAttributeUnsupported: Attribute unsupported",
    -25206: "kAXErrorActionUnsupported: Action unsupported",
    -25207: "kAXErrorNotificationUnsupported: Notification unsupported",
    -25208: "kAXErrorNotImplemented: Not implemented",
    -25209: "kAXErrorNotificationAlreadyRegistered: Notification already registered",
    -25210: "kAXErrorNotificationNotRegistered: Notification not registered",
    -25211: "kAXErrorAPIDisabled: Accessibility permission not granted in System Settings",
    -25212: "kAXErrorNoValue: Attribute has no value",
    -25213: "kAXErrorParameterizedAttributeUnsupported: Parameterized attribute unsupported",
    -25214: "kAXErrorNotEnoughPrecision: Not enough precision",
}


def _get_ax_attribute(element: Any, attribute: str) -> Tuple[int, Any]:
    """Query an attribute on an AXUIElement safely."""
    try:
        err, val = ApplicationServices.AXUIElementCopyAttributeValue(element, attribute, None)
        return (err, val)
    except Exception as e:
        return (-25200, None)


def _unpack_ax_value(val: Any) -> Optional[Dict[str, float]]:
    """Unpack AXValue CGPoint or CGSize into python dictionary."""
    if val is None:
        return None
    try:
        val_type = ApplicationServices.AXValueGetType(val)
        if val_type == ApplicationServices.kAXValueCGPointType:
            success, pt = ApplicationServices.AXValueGetValue(val, val_type, None)
            if success:
                return {"x": float(pt.x), "y": float(pt.y)}
        elif val_type == ApplicationServices.kAXValueCGSizeType:
            success, sz = ApplicationServices.AXValueGetValue(val, val_type, None)
            if success:
                return {"width": float(sz.width), "height": float(sz.height)}
        elif val_type == ApplicationServices.kAXValueCGRectType:
            success, rect = ApplicationServices.AXValueGetValue(val, val_type, None)
            if success:
                return {
                    "x": float(rect.origin.x),
                    "y": float(rect.origin.y),
                    "width": float(rect.size.width),
                    "height": float(rect.size.height),
                }
    except Exception:
        pass
    return None


def _parse_element(element: Any, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
    """Recursively parse an AXUIElement into a clean, serializable dictionary."""
    err_role, role = _get_ax_attribute(element, ApplicationServices.kAXRoleAttribute)
    err_subrole, subrole = _get_ax_attribute(element, ApplicationServices.kAXSubroleAttribute)
    err_title, title = _get_ax_attribute(element, ApplicationServices.kAXTitleAttribute)
    err_desc, desc = _get_ax_attribute(element, ApplicationServices.kAXDescriptionAttribute)
    err_val, value = _get_ax_attribute(element, ApplicationServices.kAXValueAttribute)
    err_pos, pos_val = _get_ax_attribute(element, ApplicationServices.kAXPositionAttribute)
    err_size, size_val = _get_ax_attribute(element, ApplicationServices.kAXSizeAttribute)

    position = _unpack_ax_value(pos_val) if err_pos == 0 else None
    size = _unpack_ax_value(size_val) if err_size == 0 else None

    # Calculate center point for convenient cursor targeting
    center_point = None
    if position and size and "x" in position and "width" in size:
        center_point = {
            "x": round(position["x"] + size["width"] / 2.0, 1),
            "y": round(position["y"] + size["height"] / 2.0, 1),
        }

    # Bounding box
    bounds = None
    if position and size:
        bounds = {
            "x": position.get("x", 0.0),
            "y": position.get("y", 0.0),
            "width": size.get("width", 0.0),
            "height": size.get("height", 0.0),
        }

    info: Dict[str, Any] = {
        "role": str(role) if err_role == 0 and role else "",
        "subrole": str(subrole) if err_subrole == 0 and subrole else "",
        "title": str(title) if err_title == 0 and title else "",
        "description": str(desc) if err_desc == 0 and desc else "",
        "value": str(value) if err_val == 0 and value is not None and not isinstance(value, (list, tuple)) else "",
        "bounds": bounds,
        "center": center_point,
    }

    # Recurse children if depth allows
    children_nodes: List[Dict[str, Any]] = []
    if current_depth < max_depth:
        err_children, children = _get_ax_attribute(element, ApplicationServices.kAXChildrenAttribute)
        if err_children == 0 and children:
            for child in children:
                child_parsed = _parse_element(child, max_depth, current_depth + 1)
                # Keep meaningful elements
                if child_parsed["role"] or child_parsed["title"] or child_parsed.get("children"):
                    children_nodes.append(child_parsed)

    if children_nodes:
        info["children"] = children_nodes

    return info


def get_app_accessibility_tree(
    app_name_or_pid: Optional[str | int] = None,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """
    Inspect the macOS Accessibility tree for an application.
    Returns structured hierarchy or structured error.
    """
    # 1. Preflight permission check
    if not check_accessibility_permission():
        err_msg = (
            "Accessibility permission not granted (kAXErrorAPIDisabled). "
            "Please enable Accessibility in macOS System Settings > Privacy & Security > Accessibility."
        )
        zoe_logger.log_action("ACCESSIBILITY_PERMISSION_DENIED")
        return {
            "success": False,
            "action": "get_accessibility_tree",
            "error": err_msg,
            "error_code": -25211,
        }

    # 2. Identify target PID
    pid: Optional[int] = None
    target_name: str = ""

    if isinstance(app_name_or_pid, int):
        pid = app_name_or_pid
        target_name = f"PID-{pid}"
    elif isinstance(app_name_or_pid, str) and app_name_or_pid.strip():
        app = find_running_app(app_name_or_pid)
        if not app:
            return {
                "success": False,
                "action": "get_accessibility_tree",
                "error": f"Application '{app_name_or_pid}' is not running.",
            }
        pid = int(app.processIdentifier())
        target_name = str(app.localizedName() or app_name_or_pid)
    else:
        active = get_active_app()
        pid = active.get("pid", -1)
        target_name = active.get("name", "ActiveApp")

    if pid is None or pid <= 0:
        return {
            "success": False,
            "action": "get_accessibility_tree",
            "error": "No valid running application found to inspect.",
        }

    # 3. Create AXUIElement
    try:
        ax_app = ApplicationServices.AXUIElementCreateApplication(pid)
        if ax_app is None:
            return {
                "success": False,
                "action": "get_accessibility_tree",
                "error": f"Failed to create AXUIElement for application PID {pid}.",
            }

        # Check access on app element
        err_title, title = _get_ax_attribute(ax_app, ApplicationServices.kAXTitleAttribute)
        if err_title in AX_ERRORS and err_title != 0:
            return {
                "success": False,
                "action": "get_accessibility_tree",
                "app": target_name,
                "pid": pid,
                "error": f"Accessibility query returned error: {AX_ERRORS.get(err_title, f'Unknown error {err_title}')}",
                "error_code": err_title,
            }

        tree = _parse_element(ax_app, max_depth=max_depth, current_depth=0)
        zoe_logger.log_action("GET_ACCESSIBILITY_TREE", app=target_name, pid=pid, depth=max_depth)

        return {
            "success": True,
            "action": "get_accessibility_tree",
            "app": target_name,
            "pid": pid,
            "tree": tree,
        }
    except Exception as e:
        return {
            "success": False,
            "action": "get_accessibility_tree",
            "error": f"Unexpected accessibility inspection error: {str(e)}",
        }


def find_elements_by_role(tree: Dict[str, Any], role: str) -> List[Dict[str, Any]]:
    """Traverse an accessibility tree dictionary to find all elements matching a role."""
    results: List[Dict[str, Any]] = []
    target_role = role.lower()

    def _traverse(node: Dict[str, Any]) -> None:
        if node.get("role", "").lower() == target_role:
            results.append(node)
        for child in node.get("children", []):
            _traverse(child)

    _traverse(tree)
    return results


def find_element_by_title(tree: Dict[str, Any], title: str) -> Optional[Dict[str, Any]]:
    """Traverse an accessibility tree dictionary to find the first element matching a title."""
    target_title = title.lower().strip()

    def _traverse(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        node_title = node.get("title", "").lower().strip()
        if target_title in node_title:
            return node
        for child in node.get("children", []):
            res = _traverse(child)
            if res:
                return res
        return None

    return _traverse(tree)
