"""Unit tests for tool registry and tool contracts."""

from zoe.tools.registry import tool_registry


def test_registered_tools():
    names = tool_registry.get_tool_names()
    expected = [
        "move_cursor", "click", "double_click", "right_click",
        "drag", "scroll", "type_text", "press_key", "hotkey",
        "take_screenshot", "open_app", "focus_app", "close_app",
        "get_active_app", "get_running_apps", "get_windows",
        "get_accessibility_tree",
    ]
    for exp in expected:
        assert exp in names, f"Missing tool: {exp}"


def test_schema_export():
    schemas = tool_registry.get_schema_definitions()
    assert len(schemas) >= 15
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]
        assert "parameters" in s["function"]


def test_tool_execution_structured():
    res = tool_registry.execute("get_active_app")
    assert isinstance(res, dict)
    assert "success" in res
    assert res["action"] == "get_active_app"

    res_unknown = tool_registry.execute("non_existent_tool")
    assert res_unknown["success"] is False
    assert "error" in res_unknown
