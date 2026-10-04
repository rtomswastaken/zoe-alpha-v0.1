"""Structured data models and exceptions for the OpenClicky external control bridge."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class OpenClickyError(Exception):
    """Base exception for all OpenClicky integration errors."""
    pass


class OpenClickySecurityError(OpenClickyError):
    """Raised when security boundaries (e.g. non-local host) are violated."""
    pass


class OpenClickyConnectionError(OpenClickyError):
    """Raised when unable to establish a connection to the OpenClicky bridge."""
    pass


class OpenClickyTimeoutError(OpenClickyError):
    """Raised when an OpenClicky bridge request times out."""
    pass


class OpenClickyAuthError(OpenClickyError):
    """Raised when bridge token authentication fails."""
    pass


class OpenClickyAPIError(OpenClickyError):
    """Raised when the bridge returns an error status code or ok: false."""
    def __init__(self, message: str, status_code: int = 500, response_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


@dataclass
class CursorPoint:
    x: float
    y: float
    caption: Optional[str] = None
    duration_ms: Optional[float] = None
    accent_hex: Optional[str] = None
    mode: str = "primary"  # "primary" or "secondary"
    travel_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "x": self.x,
            "y": self.y,
            "mode": self.mode,
        }
        if self.caption is not None:
            payload["caption"] = self.caption
        if self.duration_ms is not None:
            payload["durationMs"] = self.duration_ms
        if self.accent_hex is not None:
            payload["accentHex"] = self.accent_hex
        if self.travel_ms is not None:
            payload["travelMs"] = self.travel_ms
        return payload


@dataclass
class MultiCursorSpec:
    x: float
    y: float
    caption: Optional[str] = None
    duration_ms: Optional[float] = None
    accent_hex: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "x": self.x,
            "y": self.y,
        }
        if self.caption is not None:
            payload["caption"] = self.caption
        if self.duration_ms is not None:
            payload["durationMs"] = self.duration_ms
        if self.accent_hex is not None:
            payload["accentHex"] = self.accent_hex
        return payload


@dataclass
class DisplayFrame:
    x: float
    y: float
    width: float
    height: float


@dataclass
class ScreenshotScreen:
    label: str
    path: str
    is_cursor_screen: bool
    display_frame: DisplayFrame
    display_width_points: float
    display_height_points: float
    screenshot_width_pixels: int
    screenshot_height_pixels: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScreenshotScreen":
        df_raw = data.get("displayFrame", {})
        df = DisplayFrame(
            x=float(df_raw.get("x", 0.0)),
            y=float(df_raw.get("y", 0.0)),
            width=float(df_raw.get("width", 0.0)),
            height=float(df_raw.get("height", 0.0)),
        )
        return cls(
            label=str(data.get("label", "Main Display")),
            path=str(data.get("path", "")),
            is_cursor_screen=bool(data.get("isCursorScreen", False)),
            display_frame=df,
            display_width_points=float(data.get("displayWidthInPoints", 0.0)),
            display_height_points=float(data.get("displayHeightInPoints", 0.0)),
            screenshot_width_pixels=int(data.get("screenshotWidthInPixels", 0)),
            screenshot_height_pixels=int(data.get("screenshotHeightInPixels", 0)),
        )


@dataclass
class ScreenshotResponse:
    ok: bool
    count: int
    focused: bool
    screens: List[ScreenshotScreen] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScreenshotResponse":
        screens = [ScreenshotScreen.from_dict(s) for s in data.get("screens", [])]
        return cls(
            ok=bool(data.get("ok", False)),
            count=int(data.get("count", len(screens))),
            focused=bool(data.get("focused", False)),
            screens=screens,
        )


@dataclass
class HealthResponse:
    ok: bool
    name: str
    port: int
    transport: str
    bridge_token_required: bool
    bridge_token_configured: bool
    tools: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OpenClickyStatus:
    connected: bool
    bridge: str
    latency_ms: Optional[float] = None
    tools_count: int = 0
    tools: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def format_diagnostic(self) -> str:
        """Format friendly diagnostic string for Zoe CLI / runtime."""
        lines = [
            f"OpenClicky: {'CONNECTED' if self.connected else 'DISCONNECTED'}",
            f"Bridge:     {self.bridge}",
        ]
        if self.connected:
            lat = f"{self.latency_ms:.1f}ms" if self.latency_ms is not None else "N/A"
            lines.append(f"Latency:    {lat}")
            lines.append(f"Tools:      {self.tools_count}")
        elif self.error:
            lines.append(f"Reason:     {self.error}")
        return "\n".join(lines)
