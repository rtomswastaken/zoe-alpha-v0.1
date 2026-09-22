"""Safety validation and destructive action interception for Zoe."""

import re
from typing import Any, Dict, List, Tuple


# Regex patterns matching destructive intentions in tasks or tool arguments
DESTRUCTIVE_PATTERNS = [
    r"\b(?:delete|remove|erase|format|wipe|destroy)\s+(?:all|everything|my|files|disk|volume|directory|folder)\b",
    r"\brm\s+-rf\b",
    r"\bempty\s+(?:the\s+)?trash\b",
    r"\bshred\b",
    r"\bkill\s+-9\s+-1\b",
]

# Sensitive operations that require explicit user confirmation
SENSITIVE_TOOLS = {
    "close_app": ["Finder", "System Settings", "Terminal"],
}


class SafetyGuard:
    """Evaluates tasks and tool executions to prevent destructive operations."""

    @staticmethod
    def is_destructive_task(task_text: str) -> Tuple[bool, str]:
        """
        Check if natural language request asks for irreversible destructive actions.
        Returns (is_destructive, reason).
        """
        lower = task_text.lower().strip()
        for pat in DESTRUCTIVE_PATTERNS:
            if re.search(pat, lower):
                return True, f"Potentially destructive operation detected matching rule: {pat}"
        return False, ""

    @staticmethod
    def validate_tool_execution(tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate whether a specific tool execution is safe to perform without confirmation.
        Returns (is_safe, error_or_warning).
        """
        if tool_name == "close_app":
            target_app = str(arguments.get("app_name", "")).strip()
            if target_app in SENSITIVE_TOOLS["close_app"]:
                return False, f"Closing system critical application '{target_app}' requires confirmation."

        if tool_name == "type_text":
            text = str(arguments.get("text", "")).lower()
            for pat in DESTRUCTIVE_PATTERNS:
                if re.search(pat, text):
                    return False, f"Typing destructive command requires explicit confirmation: '{text[:30]}...'"

        return True, ""
