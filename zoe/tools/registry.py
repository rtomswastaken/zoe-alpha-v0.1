"""Central tool registry for computer control and future LLM integration."""

from typing import Any, Dict, List, Optional
from zoe.tools.base import BaseTool
from zoe.tools.computer import (
    MoveCursorTool,
    ClickTool,
    DoubleClickTool,
    RightClickTool,
    DragTool,
    ScrollTool,
    TypeTextTool,
    PressKeyTool,
    HotkeyTool,
    TakeScreenshotTool,
)
from zoe.tools.applications import (
    OpenAppTool,
    FocusAppTool,
    CloseAppTool,
    GetActiveAppTool,
    GetRunningAppsTool,
    GetWindowsTool,
    GetAccessibilityTreeTool,
)


class ToolRegistry:
    """Registry holding all available macOS tools for Zoe."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def execute(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch tool execution by name with kwargs."""
        tool = self._tools.get(name)
        if not tool:
            return {
                "success": False,
                "action": name,
                "error": f"Tool '{name}' is not recognized. Available tools: {list(self._tools.keys())}",
            }
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            return {
                "success": False,
                "action": name,
                "error": f"Tool execution failed with exception: {str(e)}",
            }

    def get_tool_names(self) -> List[str]:
        return list(self._tools.keys())

    def get_schema_definitions(self) -> List[Dict[str, Any]]:
        """
        Export all registered tools in standard function calling JSON-schema format.
        Directly consumable by Ollama, llama.cpp, and MLX-LM in Phase 2.
        """
        return [tool.to_schema() for tool in self._tools.values()]

    def _register_default_tools(self) -> None:
        # Computer controls
        self.register(MoveCursorTool())
        self.register(ClickTool())
        self.register(DoubleClickTool())
        self.register(RightClickTool())
        self.register(DragTool())
        self.register(ScrollTool())
        self.register(TypeTextTool())
        self.register(PressKeyTool())
        self.register(HotkeyTool())
        self.register(TakeScreenshotTool())

        # Applications and Accessibility
        self.register(OpenAppTool())
        self.register(FocusAppTool())
        self.register(CloseAppTool())
        self.register(GetActiveAppTool())
        self.register(GetRunningAppsTool())
        self.register(GetWindowsTool())
        self.register(GetAccessibilityTreeTool())


tool_registry = ToolRegistry()
