"""Episodic state tracking for Zoe's active task."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoe.agent.history import ActionHistory, ActionRecord
from zoe.agent.plan import TaskPlan


@dataclass
class AgentState:
    """
    Episodic state tracked during the execution of a user command.
    Exists only as long as needed for the current task.
    """
    task: str
    active_app: str = ""
    history: ActionHistory = field(default_factory=ActionHistory)
    plan: Optional[TaskPlan] = None
    cancelled: bool = False
    is_complete: bool = False
    iteration_count: int = 0
    final_response: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def recent_actions(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.history.records]

    @property
    def tool_results(self) -> List[Dict[str, Any]]:
        return [r.result for r in self.history.records]

    def record_action(
        self,
        action_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        verified: bool = False,
    ) -> ActionRecord:
        """Record an executed tool action and its structured outcome."""
        return self.history.record(
            tool_name=action_name,
            arguments=arguments,
            result=result,
            verified=verified,
        )

    def mark_complete(self, response_text: str) -> None:
        self.is_complete = True
        self.final_response = response_text

    def mark_cancelled(self, reason: str = "Emergency stop triggered") -> None:
        self.cancelled = True
        self.is_complete = True
        self.final_response = f"Task cancelled: {reason}"
