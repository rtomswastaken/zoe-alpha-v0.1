"""Data models for Zoe's local SQLite memory system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class MemoryType(str, Enum):
    SESSION = "session"         # Current session context
    TASK = "task"               # Information learned from prior tasks
    PREFERENCE = "preference"   # Explicit user preferences (e.g. browser, editor)
    PROJECT = "project"         # System / architectural facts about Zoe


@dataclass
class MemoryItem:
    """A single persistent memory record stored locally in SQLite."""
    id: Optional[int]
    key: str
    value: str
    category: MemoryType
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "category": self.category.value if isinstance(self.category, MemoryType) else str(self.category),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
