"""Abstract base class and data structures for local model providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """Represents a structured tool invocation requested by the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ModelResponse:
    """Standardized response from any local model provider."""
    text: str = ""
    thinking: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LocalModel(ABC):
    """
    Abstract interface for local inference engines.
    Allows seamlessly supporting Ollama, MLX-LM, or llama.cpp
    without altering any agent logic.
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ModelResponse:
        """Send chat messages and optional tool schemas to the local model."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the local inference backend and configured model are accessible."""
        pass

    @abstractmethod
    def model_info(self) -> Dict[str, Any]:
        """Return metadata about the loaded local model."""
        pass
