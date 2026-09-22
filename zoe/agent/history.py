"""Structured execution history, loop detection, and context management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ActionRecord:
    """Detailed record of a single computer control or vision action."""
    action_id: int
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    target: Optional[str] = None
    confidence: Optional[float] = None
    success: bool = True
    verified: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.action_id,
            "action": self.tool_name,
            "tool": self.tool_name,
            "target": self.target,
            "arguments": self.arguments,
            "result": self.result,
            "success": self.success,
            "confidence": self.confidence,
            "verified": self.verified,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    def to_compact_summary(self) -> str:
        """Compact one-line summary for LLM context optimization."""
        status = "SUCCESS" if self.success else f"FAILED({self.error or 'unknown'})"
        conf_str = f" [conf={self.confidence:.2f}]" if self.confidence is not None else ""
        tgt_str = f" target='{self.target}'" if self.target else ""
        return f"{self.action_id}. {self.tool_name}{tgt_str} -> {status}{conf_str}"


class ActionHistory:
    """Manages the agent's action history and detects loops/failures."""

    def __init__(self, max_records: int = 50) -> None:
        self.records: List[ActionRecord] = []
        self.max_records = max_records

    def record(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        verified: bool = False,
    ) -> ActionRecord:
        action_id = len(self.records) + 1
        success = bool(result.get("success", False))
        error = result.get("error")
        target = arguments.get("target") or arguments.get("app_name")
        confidence = result.get("confidence")

        record = ActionRecord(
            action_id=action_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            target=target,
            confidence=confidence,
            success=success,
            verified=verified,
            error=error,
        )
        self.records.append(record)
        if len(self.records) > self.max_records:
            self.records.pop(0)
        return record

    def check_repetition_loop(self, threshold: int = 3) -> bool:
        """
        Detect if the agent is stuck repeating the exact same failed action.
        Returns True if the last `threshold` actions used the same tool, arguments, and failed.
        """
        if len(self.records) < threshold:
            return False

        last_records = self.records[-threshold:]
        first = last_records[0]
        for r in last_records[1:]:
            if r.tool_name != first.tool_name or r.arguments != first.arguments:
                return False
            if r.success:
                return False
        return True

    def get_compact_history(self, last_n: int = 10) -> str:
        """Get compact summary of recent actions to fit efficiently within context."""
        recent = self.records[-last_n:]
        if not recent:
            return "No previous actions taken."
        return "\n".join(r.to_compact_summary() for r in recent)

    def clear(self) -> None:
        self.records.clear()
