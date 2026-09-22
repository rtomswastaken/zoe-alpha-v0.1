"""Structured plan representations for multi-step computer use tasks."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """An individual step in an agent's multi-step execution plan."""
    step_id: int
    description: str
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def mark_in_progress(self) -> None:
        self.status = StepStatus.IN_PROGRESS

    def mark_completed(self, result: Optional[Dict[str, Any]] = None) -> None:
        self.status = StepStatus.COMPLETED
        self.result = result

    def mark_failed(self, error: str) -> None:
        self.status = StepStatus.FAILED
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class TaskPlan:
    """A multi-step plan decomposed from a user's high-level goal."""
    goal: str
    steps: List[PlanStep] = field(default_factory=list)

    @property
    def current_step(self) -> Optional[PlanStep]:
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
                return step
        return None

    @property
    def is_complete(self) -> bool:
        if not self.steps:
            return False
        return all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self.steps)

    @property
    def has_failure(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def add_step(self, description: str, tool_name: Optional[str] = None, arguments: Optional[Dict[str, Any]] = None) -> PlanStep:
        step_id = len(self.steps) + 1
        step = PlanStep(
            step_id=step_id,
            description=description,
            tool_name=tool_name,
            arguments=arguments or {},
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "is_complete": self.is_complete,
        }
