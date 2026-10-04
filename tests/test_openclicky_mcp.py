"""Unit tests for OpenClicky dynamic MCP adapter and tool wrappers."""

from unittest.mock import MagicMock
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.integrations.openclicky.mcp_adapter import OpenClickyMCPAdapter, OpenClickyMCPToolWrapper
from zoe.tools.registry import ToolRegistry


def test_mcp_tool_wrapper_execution() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.call_mcp_tool.return_value = {"ok": True, "result": "pointed"}

    wrapper = OpenClickyMCPToolWrapper(
        name="openclicky_point",
        description="Point at coordinate",
        parameters_schema={"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}},
        client=mock_client,
    )

    schema = wrapper.to_schema()
    assert schema["function"]["name"] == "openclicky_point"
    assert "x" in schema["function"]["parameters"]["properties"]

    res = wrapper.execute(x=100, y=200)
    assert res["success"] is True
    mock_client.call_mcp_tool.assert_called_once_with("openclicky_point", {"x": 100, "y": 200})


def test_mcp_adapter_discovery_and_registration() -> None:
    mock_client = MagicMock(spec=OpenClickyClient)
    mock_client.get_tools.return_value = [
        {
            "name": "openclicky_point",
            "description": "Point tool",
            "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}}},
        },
        {
            "name": "show_caption",
            "description": "Caption tool",
            "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
        },
    ]

    adapter = OpenClickyMCPAdapter(client=mock_client)
    tools = adapter.discover_tools()
    assert len(tools) == 2
    assert tools[0].name == "mcp_openclicky_point"
    assert tools[1].name == "mcp_show_caption"

    custom_registry = ToolRegistry()
    count = adapter.register_dynamic_tools(custom_registry)
    assert count == 2
    assert custom_registry.get("mcp_openclicky_point") is not None
    assert custom_registry.get("mcp_show_caption") is not None
