"""Tests for Phase 5 Advanced Computer Use, planning, safety, and failure recovery."""

import pytest
from zoe.agent.history import ActionHistory, ActionRecord
from zoe.agent.plan import TaskPlan, StepStatus
from zoe.agent.safety import SafetyGuard
from zoe.agent.state import AgentState
from zoe.agent.loop import AgentLoop
from zoe.models.base import LocalModel, ModelResponse, ToolCall


class MockPlanningModel(LocalModel):
    """Mock model that returns multi-step tool calls for testing."""
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def is_available(self) -> bool:
        return True

    def model_info(self):
        return {"status": "AVAILABLE"}

    def chat(self, messages, tools=None, temperature=None, max_tokens=None):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return ModelResponse(text="All planned steps executed successfully.")


def test_task_plan_lifecycle():
    plan = TaskPlan(goal="Open Safari and search for Python")
    assert not plan.is_complete

    s1 = plan.add_step("Open Safari", tool_name="open_app", arguments={"app_name": "Safari"})
    s2 = plan.add_step("Find search bar", tool_name="find_on_screen", arguments={"target": "search"})

    assert plan.current_step == s1
    s1.mark_completed({"success": True})
    assert plan.current_step == s2

    s2.mark_completed({"success": True})
    assert plan.is_complete
    assert not plan.has_failure


def test_action_history_and_repetition_loop_detection():
    history = ActionHistory(max_records=10)

    # 1. Normal successful actions
    history.record("open_app", {"app_name": "Safari"}, {"success": True})
    assert not history.check_repetition_loop(threshold=3)

    # 2. Add repeated failures
    history.record("click", {"x": 100, "y": 100}, {"success": False, "error": "Not clickable"})
    history.record("click", {"x": 100, "y": 100}, {"success": False, "error": "Not clickable"})
    assert not history.check_repetition_loop(threshold=3)

    history.record("click", {"x": 100, "y": 100}, {"success": False, "error": "Not clickable"})
    assert history.check_repetition_loop(threshold=3)

    compact = history.get_compact_history()
    assert "FAILED" in compact
    assert "open_app" in compact


def test_safety_guard_destructive_tasks():
    is_dest, reason = SafetyGuard.is_destructive_task("delete all my files from disk")
    assert is_dest
    assert "destructive" in reason.lower()

    is_dest, reason = SafetyGuard.is_destructive_task("empty the trash right now")
    assert is_dest

    is_dest, _ = SafetyGuard.is_destructive_task("open Safari and go to wikipedia.org")
    assert not is_dest


def test_safety_guard_destructive_tool_calls():
    is_safe, warn = SafetyGuard.validate_tool_execution("type_text", {"text": "rm -rf /"})
    assert not is_safe
    assert "destructive" in warn.lower()

    is_safe, warn = SafetyGuard.validate_tool_execution("close_app", {"app_name": "Finder"})
    assert not is_safe
    assert "system critical" in warn.lower()

    is_safe, _ = SafetyGuard.validate_tool_execution("open_app", {"app_name": "Calculator"})
    assert is_safe


def test_agent_loop_blocks_destructive_task():
    model = MockPlanningModel([])
    loop = AgentLoop(model)

    state = loop.run("delete all my files immediately")
    assert state.cancelled
    assert "destructive" in state.final_response.lower()


def test_agent_loop_context_compaction_and_verification():
    # Mock model that emits a tool call, then finishes
    mock_resp1 = ModelResponse(
        text="",
        tool_calls=[
            ToolCall(id="tc1", name="get_active_app", arguments={})
        ]
    )
    mock_resp2 = ModelResponse(text="Active app verified.")
    model = MockPlanningModel([mock_resp1, mock_resp2])

    loop = AgentLoop(model)
    state = loop.run("check what app is active")

    assert state.is_complete
    assert not state.cancelled
    assert len(state.history.records) == 1
    rec = state.history.records[0]
    assert rec.verified is True
    assert rec.success is True
