"""High-level Memory Manager for Zoe with explicit command handling."""

import re
from typing import Optional, Tuple
from zoe.memory.database import MemoryDatabase
from zoe.memory.models import MemoryItem, MemoryType
from zoe.memory.retrieval import MemoryRetriever
from zoe.memory.store import MemoryStore


class MemoryManager:
    """Coordinates local persistent memory storage, directive parsing, and retrieval."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db = MemoryDatabase(db_path)
        self.store = MemoryStore(self.db)
        self.retriever = MemoryRetriever(self.store)

    def process_directive(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user input is an explicit memory directive.
        Returns (is_directive, response_message).
        Supported patterns:
          - "remember that <key> is <value>"
          - "remember <key> = <value>"
          - "remember I prefer <value> for <key>"
          - "forget <key>"
        """
        lower = text.strip()

        # 1. "forget <key>"
        forget_match = re.match(r"^(?:zoe,?\s*)?forget\s+(?:that\s+)?(?:my\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+preference)?\.?$", lower, re.IGNORECASE)
        if forget_match:
            raw_key = forget_match.group(1).strip().replace(" ", "_")
            deleted = self.store.delete(raw_key)
            if not deleted:
                # Try finding closest match
                items = self.store.search(raw_key)
                if items:
                    self.store.delete(items[0].key)
                    return True, f"I have forgotten your preference for '{items[0].key}'."
                return True, f"I didn't find any memory for '{raw_key}'."
            return True, f"I have forgotten your preference for '{raw_key}'."

        # 2. "remember that I prefer <value> for/as <key>" or "remember that my <key> is <value>"
        pref_match = re.match(r"^(?:zoe,?\s*)?remember\s+that\s+i\s+prefer\s+([a-zA-Z0-9_\-\s]+)\s+(?:for|as)\s+([a-zA-Z0-9_\-\s]+)\.?$", lower, re.IGNORECASE)
        if pref_match:
            val = pref_match.group(1).strip()
            raw_key = pref_match.group(2).strip().replace(" ", "_")
            self.store.set(raw_key, val, category=MemoryType.PREFERENCE)
            return True, f"Remembered: your preferred {raw_key.replace('_', ' ')} is {val}."

        # 3. "remember that my preferred <key> is <value>"
        pref_match2 = re.match(r"^(?:zoe,?\s*)?remember\s+that\s+(?:my\s+)?([a-zA-Z0-9_\-\s]+)\s+is\s+([a-zA-Z0-9_\-\s]+)\.?$", lower, re.IGNORECASE)
        if pref_match2:
            raw_key = pref_match2.group(1).strip().replace(" ", "_")
            val = pref_match2.group(2).strip()
            self.store.set(raw_key, val, category=MemoryType.PREFERENCE)
            return True, f"Remembered: {raw_key.replace('_', ' ')} is {val}."

        return False, None


_memory_manager_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance
