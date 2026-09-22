"""CRUD operations for persistent local memories."""

from datetime import datetime
from typing import List, Optional
from zoe.memory.database import MemoryDatabase
from zoe.memory.models import MemoryItem, MemoryType


class MemoryStore:
    """Provides structured storage, querying, and updating of memories in SQLite."""

    def __init__(self, db: MemoryDatabase) -> None:
        self.db = db

    def set(self, key: str, value: str, category: MemoryType = MemoryType.PREFERENCE) -> MemoryItem:
        """Insert or update a memory item by key."""
        now = datetime.now().isoformat()
        cat_str = category.value if isinstance(category, MemoryType) else str(category)

        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO memories (key, value, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = excluded.updated_at
            """, (key, value, cat_str, now, now))
            conn.commit()

        return self.get(key)  # type: ignore

    def get(self, key: str) -> Optional[MemoryItem]:
        """Retrieve a specific memory by key."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, key, value, category, created_at, updated_at FROM memories WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return MemoryItem(
                id=row["id"],
                key=row["key"],
                value=row["value"],
                category=MemoryType(row["category"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def delete(self, key: str) -> bool:
        """Remove a memory by key. Returns True if found and deleted."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self, category: Optional[MemoryType] = None) -> List[MemoryItem]:
        """List all stored memories, optionally filtered by category."""
        query = "SELECT id, key, value, category, created_at, updated_at FROM memories"
        params = ()
        if category:
            query += " WHERE category = ?"
            params = (category.value if isinstance(category, MemoryType) else str(category),)
        query += " ORDER BY key ASC"

        items: List[MemoryItem] = []
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, params)
            for row in cursor.fetchall():
                items.append(MemoryItem(
                    id=row["id"],
                    key=row["key"],
                    value=row["value"],
                    category=MemoryType(row["category"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))
        return items

    def search(self, query_str: str) -> List[MemoryItem]:
        """Search memories matching a keyword in key or value."""
        pattern = f"%{query_str}%"
        items: List[MemoryItem] = []
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, key, value, category, created_at, updated_at FROM memories WHERE key LIKE ? OR value LIKE ? ORDER BY key ASC",
                (pattern, pattern),
            )
            for row in cursor.fetchall():
                items.append(MemoryItem(
                    id=row["id"],
                    key=row["key"],
                    value=row["value"],
                    category=MemoryType(row["category"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))
        return items

    def clear(self) -> int:
        """Erase all memories. Returns count of deleted rows."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM memories")
            conn.commit()
            return cursor.rowcount
