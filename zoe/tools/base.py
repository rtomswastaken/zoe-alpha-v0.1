"""Base tool abstractions and structured result serialization."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ToolResult:
    success: bool
    action: str
    message: str = ""
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "success": self.success,
            "action": self.action,
        }
        if self.message:
            res["message"] = self.message
        if self.error:
            res["error"] = self.error
        if self.data:
            res.update(self.data)
        return res


class BaseTool:
    """Abstract base class for all computer control tools."""

    name: str
    description: str
    parameters_schema: Dict[str, Any]

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError

    def to_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
