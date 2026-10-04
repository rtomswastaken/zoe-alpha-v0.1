"""Health check and diagnostics for OpenClicky bridge."""

from typing import Optional
from zoe.config import get_config
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.models import (
    OpenClickyAuthError,
    OpenClickyConnectionError,
    OpenClickyError,
    OpenClickyStatus,
    OpenClickyTimeoutError,
)

_cached_client: Optional[OpenClickyClient] = None


def get_openclicky_client(force_new: bool = False) -> OpenClickyClient:
    """Retrieve or instantiate the shared OpenClicky client configured from settings."""
    global _cached_client
    if _cached_client is None or force_new:
        cfg = get_config()
        oc_cfg = getattr(cfg, "openclicky", None)
        host = oc_cfg.host if oc_cfg else "127.0.0.1"
        port = oc_cfg.port if oc_cfg else 32123
        timeout = oc_cfg.timeout if oc_cfg else 2.0
        token = oc_cfg.token if oc_cfg else ""
        _cached_client = OpenClickyClient(
            host=host,
            port=port,
            timeout=timeout,
            token=token,
        )
    return _cached_client


def check_openclicky_health(client: Optional[OpenClickyClient] = None) -> OpenClickyStatus:
    """
    Perform a safe health check of the OpenClicky bridge.
    Guaranteed never to crash Zoe or hang indefinitely.
    """
    cfg = get_config()
    oc_cfg = getattr(cfg, "openclicky", None)
    if oc_cfg and not oc_cfg.enabled:
        return OpenClickyStatus(
            connected=False,
            bridge=f"http://{oc_cfg.host}:{oc_cfg.port}",
            error="Integration is disabled in configuration.",
        )

    cl = client or get_openclicky_client()
    bridge_url = cl.base_url

    try:
        h = cl.health()
        return OpenClickyStatus(
            connected=True,
            bridge=bridge_url,
            latency_ms=h.latency_ms,
            tools_count=len(h.tools),
            tools=h.tools,
            error=None,
        )
    except OpenClickyConnectionError:
        return OpenClickyStatus(
            connected=False,
            bridge=bridge_url,
            error="Bridge is offline (Connection refused).",
        )
    except OpenClickyTimeoutError:
        return OpenClickyStatus(
            connected=False,
            bridge=bridge_url,
            error=f"Bridge timed out after {cl.timeout}s.",
        )
    except OpenClickyAuthError:
        return OpenClickyStatus(
            connected=False,
            bridge=bridge_url,
            error="Bridge authentication failed (Check token).",
        )
    except OpenClickyError as e:
        return OpenClickyStatus(
            connected=False,
            bridge=bridge_url,
            error=str(e),
        )
    except Exception as e:
        return OpenClickyStatus(
            connected=False,
            bridge=bridge_url,
            error=f"Unexpected health check error: {e}",
        )
