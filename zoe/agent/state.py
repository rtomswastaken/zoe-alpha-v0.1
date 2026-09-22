"""Episodic state tracking for Zoe's active task."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    """
    Episodic state tracked during the execution of a user command.
    Exists only as long as needed for the current task.
    """
    task: str
    active_app: str = ""
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    cancelled: bool = False
    is_complete: bool = False
    iteration_count: int = 0
    final_response: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def record_action(self, action_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Record an executed tool action and its structured outcome."""
        entry = {
            "action": action_name,
            "arguments": arguments,
            "result": result,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "iteration": self.iteration_count,
        }
        self.recent_actions.append(entry)
        self.tool_results.append(result)

    def mark_complete(self, response_text: str) -> None:
        self.is_complete = True
        self.final_response = response_text

    def mark_cancelled(self, reason: str = "Emergency stop triggered") -> None:
        self.cancelled = True
        self.is_complete = True
        self.final_response = f"Task cancelled: {reason}"
