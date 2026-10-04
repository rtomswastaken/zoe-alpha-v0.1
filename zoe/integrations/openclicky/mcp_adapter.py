"""Dynamic MCP adapter for discovering and routing OpenClicky MCP tools into Zoe."""

from typing import Any, Dict, List, Optional
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.health import get_openclicky_client
from zoe.integrations.openclicky.models import OpenClickyError
from zoe.macos.logger import zoe_logger
from zoe.tools.base import BaseTool



class OpenClickyMCPToolWrapper(BaseTool):
    """Dynamically wraps an MCP tool descriptor returned by OpenClicky."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        client: Optional[OpenClickyClient] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema or {"type": "object", "properties": {}}
        self.client = client

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        cl = self.client or get_openclicky_client()
        try:
            res = cl.call_mcp_tool(self.name, kwargs)
            return {
                "success": True,
                "action": self.name,
                "result": res,
            }
        except OpenClickyError as e:
            return {
                "success": False,
                "action": self.name,
                "error": str(e),
            }


class OpenClickyMCPAdapter:
    """
    Connects to OpenClicky's MCP endpoint (GET /mcp/tools or JSON-RPC POST /mcp),
    dynamically discovers available tools, and provides wrappers ready for Zoe's ToolRegistry.
    """

    def __init__(self, client: Optional[OpenClickyClient] = None) -> None:
        self.client = client

    def discover_tools(self) -> List[BaseTool]:
        """Query OpenClicky for MCP tool definitions and wrap them as Zoe BaseTools."""
        cl = self.client or get_openclicky_client()
        try:
            descriptors = cl.get_tools()
        except Exception as e:
            zoe_logger.log_action("OPENCLICKY_ERROR", mcp_discovery_failed=str(e))
            return []

        tools: List[BaseTool] = []
        for desc in descriptors:
            name = desc.get("name")
            if not name:
                continue
            desc_text = desc.get("description", f"OpenClicky MCP tool: {name}")
            schema = desc.get("inputSchema") or desc.get("parameters") or {"type": "object", "properties": {}}
            wrapped = OpenClickyMCPToolWrapper(
                name=f"mcp_{name}",
                description=desc_text,
                parameters_schema=schema,
                client=cl,
            )
            tools.append(wrapped)
        return tools

    def register_dynamic_tools(self, registry: ToolRegistry) -> int:
        """Discover tools and register them into Zoe's central ToolRegistry."""
        tools = self.discover_tools()
        for t in tools:
            registry.register(t)
        return len(tools)
