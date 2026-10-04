"""OpenClicky local bridge client with strict security, timeouts, and error handling."""

import ipaddress
import time
from typing import Any, Dict, List, Optional
import httpx
from zoe.integrations.openclicky.models import (
    CursorPoint,
    HealthResponse,
    OpenClickyAPIError,
    OpenClickyAuthError,
    OpenClickyConnectionError,
    OpenClickyError,
    OpenClickySecurityError,
    OpenClickyTimeoutError,
    ScreenshotResponse,
)
from zoe.macos.logger import zoe_logger


class OpenClickyClient:
    """
    Lightweight, robust HTTP client connecting Zoe to the local OpenClicky bridge.
    Defaults to http://127.0.0.1:32123.
    """

    ALLOWED_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 32123,
        timeout: float = 2.0,
        token: Optional[str] = None,
    ) -> None:
        self._validate_local_host(host)
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.token = token.strip() if token else ""
        self.base_url = f"http://{self.host}:{self.port}"
        self._client: Optional[httpx.Client] = None

    def _validate_local_host(self, host: str) -> None:
        """Enforce strict local-only security. Rejects 0.0.0.0 or non-local addresses."""
        cleaned = host.strip().lower()
        if cleaned in self.ALLOWED_LOCAL_HOSTS:
            return

        # Attempt to parse IP
        try:
            ip = ipaddress.ip_address(cleaned)
            if not ip.is_loopback:
                raise OpenClickySecurityError(
                    f"Security violation: OpenClicky bridge host must be a loopback address (127.0.0.1). Got '{host}'."
                )
        except ValueError:
            raise OpenClickySecurityError(
                f"Security violation: Non-local host '{host}' rejected for OpenClicky integration."
            )

    def _get_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["x-openclicky-token"] = self.token
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        if self._client is not None and not self._client.is_closed:
            self._client.close()
            self._client = None
            zoe_logger.log_action("OPENCLICKY_DISCONNECT", host=self.host, port=self.port)

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None,
        silent: bool = False,
    ) -> Dict[str, Any]:
        client = self._get_client()
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        req_timeout = timeout_override or self.timeout

        try:
            resp = client.request(
                method=method,
                url=url,
                json=json_data,
                headers=headers,
                timeout=req_timeout,
            )
        except httpx.ConnectError as e:
            if not silent:
                zoe_logger.log_action("OPENCLICKY_ERROR", error="connect_error", path=path)
            raise OpenClickyConnectionError(
                f"Could not connect to OpenClicky bridge at {self.base_url}. Is OpenClicky running?"
            ) from e
        except httpx.TimeoutException as e:
            if not silent:
                zoe_logger.log_action("OPENCLICKY_ERROR", error="timeout", path=path, timeout=req_timeout)
            raise OpenClickyTimeoutError(
                f"OpenClicky bridge request to {path} timed out after {req_timeout}s."
            ) from e
        except Exception as e:
            if not silent:
                zoe_logger.log_action("OPENCLICKY_ERROR", error=str(e), path=path)
            raise OpenClickyError(f"Unexpected error communicating with OpenClicky: {e}") from e

        if resp.status_code == 401:
            if not silent:
                zoe_logger.log_action("OPENCLICKY_ERROR", error="unauthorized", path=path)
            raise OpenClickyAuthError(
                "OpenClicky bridge authentication failed. Check OPENCLICKY_BRIDGE_TOKEN."
            )

        try:
            data = resp.json()
        except Exception as e:
            raise OpenClickyAPIError(
                f"OpenClicky returned invalid non-JSON response ({resp.status_code}): {resp.text[:100]}",
                status_code=resp.status_code,
            ) from e

        if resp.status_code >= 400 or (isinstance(data, dict) and data.get("ok") is False):
            err_msg = data.get("error", f"HTTP {resp.status_code}") if isinstance(data, dict) else f"HTTP {resp.status_code}"
            if not silent:
                zoe_logger.log_action("OPENCLICKY_ERROR", status=resp.status_code, error=err_msg, path=path)
            raise OpenClickyAPIError(err_msg, status_code=resp.status_code, response_data=data if isinstance(data, dict) else {})

        return data if isinstance(data, dict) else {"data": data}

    def health(self) -> HealthResponse:
        """
        Check health and status of the local OpenClicky bridge.
        Does not require bridge authentication.
        """
        start_t = time.perf_counter()
        data = self._request("GET", "/health", silent=True)
        latency = (time.perf_counter() - start_t) * 1000.0

        tools = data.get("tools", [])
        if not isinstance(tools, list):
            tools = []

        res = HealthResponse(
            ok=bool(data.get("ok", True)),
            name=str(data.get("name", "OpenClicky Bridge")),
            port=int(data.get("port", self.port)),
            transport=str(data.get("transport", "local-http")),
            bridge_token_required=bool(data.get("bridgeTokenRequired", False)),
            bridge_token_configured=bool(data.get("bridgeTokenConfigured", False)),
            tools=[str(t) for t in tools],
            latency_ms=round(latency, 2),
            raw=data,
        )
        zoe_logger.log_action("OPENCLICKY_CONNECT", port=self.port, latency_ms=res.latency_ms)
        return res

    def get_tools(self) -> List[Dict[str, Any]]:
        """List advertised MCP tool descriptors from GET /mcp/tools."""
        data = self._request("GET", "/mcp/tools")
        return data.get("tools", [])

    def show_cursor(
        self,
        x: float,
        y: float,
        caption: Optional[str] = None,
        duration_ms: Optional[float] = None,
        mode: str = "primary",
        accent_hex: Optional[str] = None,
        travel_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Point at macOS screen coordinates (AppKit space).
        Mode 'primary' executes OpenClicky's smooth pointing choreography without warping mouse pointer.
        Mode 'secondary' shows a temporary secondary pointer indicator.
        """
        spec = CursorPoint(
            x=x,
            y=y,
            caption=caption,
            duration_ms=duration_ms,
            accent_hex=accent_hex,
            mode=mode,
            travel_ms=travel_ms,
        )
        payload = spec.to_dict()
        zoe_logger.log_action("OPENCLICKY_CURSOR", x=x, y=y, mode=mode, caption=caption or "")
        return self._request("POST", "/cursor", json_data=payload)

    def show_cursors(
        self,
        cursors: List[Dict[str, Any]],
        duration_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Show multiple simultaneous temporary secondary pointers with captions."""
        payload: Dict[str, Any] = {"cursors": cursors}
        if duration_ms is not None:
            payload["durationMs"] = duration_ms
        zoe_logger.log_action("OPENCLICKY_CURSOR", multi=True, count=len(cursors))
        return self._request("POST", "/cursors", json_data=payload)

    def show_caption(
        self,
        text: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        duration_ms: Optional[float] = None,
        accent_hex: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Show a standalone contextual caption near a coordinate or current cursor."""
        payload: Dict[str, Any] = {"text": text}
        if x is not None and y is not None:
            payload["x"] = x
            payload["y"] = y
        if duration_ms is not None:
            payload["durationMs"] = duration_ms
        if accent_hex is not None:
            payload["accentHex"] = accent_hex
        zoe_logger.log_action("OPENCLICKY_TOOL_CALL", tool="show_caption", length=len(text))
        return self._request("POST", "/caption", json_data=payload)

    def screenshot(self, focused: bool = False) -> ScreenshotResponse:
        """
        Request OpenClicky capture screenshots of connected displays or focused window.
        Returns display frames and file paths.
        """
        # Screenshots may take slightly longer than 2s
        data = self._request("POST", "/screenshot", json_data={"focused": focused}, timeout_override=max(self.timeout, 5.0))
        res = ScreenshotResponse.from_dict(data)
        zoe_logger.log_action("OPENCLICKY_SCREENSHOT", count=res.count, focused=focused)
        return res

    def click(self, x: float, y: float, caption: Optional[str] = None) -> Dict[str, Any]:
        """Left-click a screen coordinate through OpenClicky's native computer-use path."""
        payload: Dict[str, Any] = {"x": x, "y": y}
        if caption:
            payload["caption"] = caption
        zoe_logger.log_action("OPENCLICKY_TOOL_CALL", tool="click", x=x, y=y)
        return self._request("POST", "/click", json_data=payload)

    def speak(self, text: str, interrupt: bool = False) -> Dict[str, Any]:
        """Speak a short instruction through OpenClicky TTS without entering voice mode."""
        payload = {"text": text, "interrupt": interrupt}
        zoe_logger.log_action("OPENCLICKY_TOOL_CALL", tool="speak", length=len(text))
        return self._request("POST", "/speak", json_data=payload)

    def clear(self) -> Dict[str, Any]:
        """Clear all active OpenClicky proxy overlay cursors and captions."""
        zoe_logger.log_action("OPENCLICKY_TOOL_CALL", tool="clear")
        return self._request("POST", "/clear", json_data={})

    def notify(
        self,
        title: str,
        body: str,
        thread_id: Optional[str] = None,
        sound: bool = True,
    ) -> Dict[str, Any]:
        """Post a native macOS notification through OpenClicky."""
        payload: Dict[str, Any] = {"title": title, "body": body, "sound": sound}
        if thread_id:
            payload["threadID"] = thread_id
        return self._request("POST", "/notify", json_data=payload)

    def call_mcp_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke an MCP tool by name via POST /mcp/call."""
        payload = {"tool": name, "arguments": arguments}
        zoe_logger.log_action("OPENCLICKY_TOOL_CALL", tool=name)
        return self._request("POST", "/mcp/call", json_data=payload)

    def jsonrpc_mcp(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        req_id: Any = 1,
    ) -> Dict[str, Any]:
        """Send a standard JSON-RPC 2.0 MCP request to POST /mcp."""
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        return self._request("POST", "/mcp", json_data=payload)
