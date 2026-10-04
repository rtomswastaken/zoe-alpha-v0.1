"""OpenClicky visual interaction and cursor overlay integration for Zoe."""

from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.coordinates import (
    appkit_to_quartz,
    get_primary_display_height,
    openclicky_screenshot_pixel_to_appkit,
    quartz_to_appkit,
    vision_to_openclicky,
    vision_to_quartz,
)
from zoe.integrations.openclicky.health import check_openclicky_health, get_openclicky_client
from zoe.integrations.openclicky.mcp_adapter import OpenClickyMCPAdapter, OpenClickyMCPToolWrapper
from zoe.integrations.openclicky.models import (
    CursorPoint,
    DisplayFrame,
    HealthResponse,
    MultiCursorSpec,
    OpenClickyAPIError,
    OpenClickyAuthError,
    OpenClickyConnectionError,
    OpenClickyError,
    OpenClickySecurityError,
    OpenClickyStatus,
    OpenClickyTimeoutError,
    ScreenshotResponse,
    ScreenshotScreen,
)
from zoe.integrations.openclicky.tools import (
    OpenClickyCaptionTool,
    OpenClickyClearTool,
    OpenClickyGuideTool,
    OpenClickyHealthTool,
    OpenClickyMultiPointTool,
    OpenClickyPointTool,
    OpenClickyScreenshotTool,
    OpenClickySpeakTool,
    register_openclicky_tools,
)
from zoe.integrations.openclicky.visual_modes import VisualInteractionController

__all__ = [
    "OpenClickyClient",
    "OpenClickyError",
    "OpenClickySecurityError",
    "OpenClickyConnectionError",
    "OpenClickyTimeoutError",
    "OpenClickyAuthError",
    "OpenClickyAPIError",
    "CursorPoint",
    "MultiCursorSpec",
    "DisplayFrame",
    "ScreenshotScreen",
    "ScreenshotResponse",
    "HealthResponse",
    "OpenClickyStatus",
    "check_openclicky_health",
    "get_openclicky_client",
    "get_primary_display_height",
    "quartz_to_appkit",
    "appkit_to_quartz",
    "vision_to_quartz",
    "vision_to_openclicky",
    "openclicky_screenshot_pixel_to_appkit",
    "OpenClickyHealthTool",
    "OpenClickyScreenshotTool",
    "OpenClickyPointTool",
    "OpenClickyMultiPointTool",
    "OpenClickyCaptionTool",
    "OpenClickySpeakTool",
    "OpenClickyClearTool",
    "OpenClickyGuideTool",
    "register_openclicky_tools",
    "OpenClickyMCPAdapter",
    "OpenClickyMCPToolWrapper",
    "VisualInteractionController",
]
