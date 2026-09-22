"""Application lifecycle and accessibility tools."""

from typing import Any, Dict, Optional
from zoe.macos.apps import (
    launch_app,
    activate_app,
    quit_app,
    get_active_app,
    get_running_apps,
    get_windows,
)
from zoe.macos.accessibility import get_app_accessibility_tree
from zoe.tools.base import BaseTool


class OpenAppTool(BaseTool):
    name = "open_app"
    description = "Launch or focus a macOS application by name."
    parameters_schema = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the application (e.g. 'Safari', 'Finder')"},
        },
        "required": ["app_name"],
    }

    def execute(self, app_name: str) -> Dict[str, Any]:
        return launch_app(app_name)


class FocusAppTool(BaseTool):
    name = "focus_app"
    description = "Bring a running macOS application to the foreground."
    parameters_schema = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the application to activate"},
        },
        "required": ["app_name"],
    }

    def execute(self, app_name: str) -> Dict[str, Any]:
        return activate_app(app_name)


class CloseAppTool(BaseTool):
    name = "close_app"
    description = "Terminate / quit a running macOS application."
    parameters_schema = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the application to quit"},
            "force": {"type": "boolean", "description": "Force terminate if true", "default": False},
        },
        "required": ["app_name"],
    }

    def execute(self, app_name: str, force: bool = False) -> Dict[str, Any]:
        return quit_app(app_name, force=force)


class GetActiveAppTool(BaseTool):
    name = "get_active_app"
    description = "Retrieve details about the currently active frontmost application."
    parameters_schema = {"type": "object", "properties": {}}

    def execute(self) -> Dict[str, Any]:
        info = get_active_app()
        return {
            "success": True,
            "action": "get_active_app",
            "data": info,
            "message": f"Active application: {info.get('name')}",
        }


class GetRunningAppsTool(BaseTool):
    name = "get_running_apps"
    description = "List all regular running applications currently open on the Mac."
    parameters_schema = {"type": "object", "properties": {}}

    def execute(self) -> Dict[str, Any]:
        apps = get_running_apps()
        return {
            "success": True,
            "action": "get_running_apps",
            "count": len(apps),
            "apps": apps,
        }


class GetWindowsTool(BaseTool):
    name = "get_windows"
    description = "Retrieve list of visible on-screen windows with titles, owners, and coordinates."
    parameters_schema = {"type": "object", "properties": {}}

    def execute(self) -> Dict[str, Any]:
        windows = get_windows()
        return {
            "success": True,
            "action": "get_windows",
            "count": len(windows),
            "windows": windows,
        }


class GetAccessibilityTreeTool(BaseTool):
    name = "get_accessibility_tree"
    description = "Inspect the native macOS accessibility hierarchy for an application."
    parameters_schema = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Application name or empty for active app"},
            "max_depth": {"type": "integer", "description": "Maximum tree recursion depth (default 3)", "default": 3},
        },
    }

    def execute(self, app_name: Optional[str] = None, max_depth: int = 3) -> Dict[str, Any]:
        return get_app_accessibility_tree(app_name_or_pid=app_name, max_depth=max_depth)
