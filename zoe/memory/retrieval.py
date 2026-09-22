"""Task-relevant memory retrieval for context injection without bloat."""

import re
from typing import List, Optional
from zoe.memory.models import MemoryItem
from zoe.memory.store import MemoryStore


class MemoryRetriever:
    """Finds only task-relevant memories to keep prompt context slim and focused."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def retrieve_relevant(self, task_text: str, max_items: int = 5) -> List[MemoryItem]:
        """
        Extract salient keywords from task and return only matching memories.
        Never dumps the entire database into the prompt.
        """
        words = re.findall(r"\b\w{3,}\b", task_text.lower())
        all_memories = self.store.list_all()
        if not all_memories or not words:
            return []

        matched: List[MemoryItem] = []
        for mem in all_memories:
            key_lower = mem.key.lower()
            val_lower = mem.value.lower()
            # Match if any significant word appears in key or value
            for w in words:
                if w in key_lower or w in val_lower:
                    if mem not in matched:
                        matched.append(mem)
                    break
            if len(matched) >= max_items:
                break

        return matched

    def format_context_block(self, task_text: str) -> Optional[str]:
        """Format relevant memories into an LLM context block."""
        relevant = self.retrieve_relevant(task_text)
        if not relevant:
            return None

        lines = ["Relevant memory:"]
        for m in relevant:
            lines.append(f"- {m.key}: {m.value}")
        return "\n".join(lines)
