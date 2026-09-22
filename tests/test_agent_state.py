"""Unit tests for AgentState and system prompts."""

from zoe.agent.state import AgentState
from zoe.agent.prompts import get_system_prompt, ZOE_SYSTEM_PROMPT


def test_system_prompt_generation():
    prompt = get_system_prompt()
    assert "You are Zoe" in prompt
    assert "Accessibility" in prompt

    custom_prompt = get_system_prompt(extra_instructions="Be extra careful with files.")
    assert "Be extra careful with files." in custom_prompt


def test_agent_state_lifecycle():
    state = AgentState(task="Open Safari and open new tab")
    assert state.task == "Open Safari and open new tab"
    assert not state.is_complete
    assert not state.cancelled
    assert state.iteration_count == 0

    state.record_action(
        action_name="open_app",
        arguments={"app_name": "Safari"},
        result={"success": True, "action": "open_app", "message": "App opened"},
    )
    assert len(state.recent_actions) == 1
    assert len(state.tool_results) == 1

    state.mark_complete("Done.")
    assert state.is_complete
    assert state.final_response == "Done."
