"""Tests for Phase 6 Local Persistent Memory Subsystem."""

import os
import pytest
from zoe.memory.database import MemoryDatabase
from zoe.memory.models import MemoryItem, MemoryType
from zoe.memory.store import MemoryStore
from zoe.memory.retrieval import MemoryRetriever
from zoe.memory.manager import MemoryManager
from zoe.agent.agent import ZoeAgent
from zoe.models.base import LocalModel, ModelResponse


class MockMemoryModel(LocalModel):
    def __init__(self, response_text: str = "Memory task completed."):
        self.response_text = response_text
        self.received_messages = []

    def is_available(self) -> bool:
        return True

    def model_info(self):
        return {"status": "AVAILABLE"}

    def chat(self, messages, tools=None, temperature=None, max_tokens=None):
        self.received_messages = list(messages)
        return ModelResponse(text=self.response_text)


def test_memory_store_crud():
    db = MemoryDatabase(db_path=":memory:")
    store = MemoryStore(db)

    # 1. Set memories across categories
    item1 = store.set("preferred_browser", "Safari", MemoryType.PREFERENCE)
    item2 = store.set("preferred_editor", "VS Code", MemoryType.PREFERENCE)
    item3 = store.set("last_opened_project", "zoe-ai", MemoryType.TASK)

    assert item1.key == "preferred_browser"
    assert item1.value == "Safari"

    # 2. Get memory
    fetched = store.get("preferred_browser")
    assert fetched is not None
    assert fetched.value == "Safari"
    assert fetched.category == MemoryType.PREFERENCE

    # 3. Search memories
    results = store.search("preferred")
    assert len(results) == 2
    assert {r.key for r in results} == {"preferred_browser", "preferred_editor"}

    # 4. List by category
    pref_list = store.list_all(category=MemoryType.PREFERENCE)
    assert len(pref_list) == 2
    task_list = store.list_all(category=MemoryType.TASK)
    assert len(task_list) == 1

    # 5. Delete and clear
    assert store.delete("preferred_editor") is True
    assert store.get("preferred_editor") is None
    cleared = store.clear()
    assert cleared == 2
    assert len(store.list_all()) == 0


def test_memory_retrieval_salience():
    db = MemoryDatabase(db_path=":memory:")
    store = MemoryStore(db)
    store.set("preferred_browser", "Safari", MemoryType.PREFERENCE)
    store.set("preferred_editor", "PyCharm", MemoryType.PREFERENCE)
    store.set("color_theme", "dark", MemoryType.PREFERENCE)

    retriever = MemoryRetriever(store)

    # Relevant task about browser
    block = retriever.format_context_block("Open my favorite browser and search for apple")
    assert block is not None
    assert "preferred_browser: Safari" in block
    assert "preferred_editor" not in block  # Salience filtering!

    # Irrelevant task with no matches
    empty_block = retriever.format_context_block("calculate 45 plus 12")
    assert empty_block is None


def test_memory_manager_explicit_directives():
    mgr = MemoryManager(db_path=":memory:")

    # 1. "remember that I prefer Safari as browser"
    is_dir, resp = mgr.process_directive("Zoe, remember that I prefer Safari for browser")
    assert is_dir is True
    assert "Safari" in resp

    mem = mgr.store.get("browser")
    assert mem is not None
    assert mem.value == "Safari"

    # 2. "forget browser"
    is_dir, resp = mgr.process_directive("Zoe, forget browser preference")
    assert is_dir is True
    assert "forgotten" in resp.lower()
    assert mgr.store.get("browser") is None


def test_agent_loop_memory_integration():
    mock_model = MockMemoryModel()
    agent = ZoeAgent(model=mock_model)

    # 1. Test explicit memory directive via agent
    state1 = agent.run_task("remember that I prefer Safari for browser")
    assert state1.is_complete is True
    assert not state1.cancelled
    assert "Safari" in state1.final_response

    # 2. Test context injection on subsequent task
    state2 = agent.run_task("open my browser")
    assert state2.is_complete is True
    # Verify that the system prompt in mock_model received the memory block
    sys_content = mock_model.received_messages[0]["content"]
    assert "Relevant memory:" in sys_content
    assert "Safari" in sys_content
