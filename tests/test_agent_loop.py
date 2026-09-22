"""Unit tests for AgentLoop and ZoeAgent planning loop."""

from typing import Any, Dict, List, Optional
from zoe.agent.agent import ZoeAgent
from zoe.agent.loop import AgentLoop
from zoe.models.base import LocalModel, ModelResponse, ToolCall
from zoe.macos.emergency import emergency_controller


class MockStepModel(LocalModel):
    """Deterministic mock model that yields predefined responses per turn."""

    def __init__(self, turns: List[ModelResponse]) -> None:
        self.turns = turns
        self.current_turn = 0

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ModelResponse:
        if self.current_turn < len(self.turns):
            resp = self.turns[self.current_turn]
            self.current_turn += 1
            return resp
        return ModelResponse(text="Done.")

    def is_available(self) -> bool:
        return True

    def model_info(self) -> Dict[str, Any]:
        return {"provider": "Mock", "status": "AVAILABLE"}


def test_agent_multistep_execution():
    emergency_controller.reset()

    # Turn 1: open_app, Turn 2: close_app, Turn 3: Final completion text
    mock_turns = [
        ModelResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="open_app", arguments={"app_name": "Calculator"})],
        ),
        ModelResponse(
            text="",
            tool_calls=[ToolCall(id="c2", name="close_app", arguments={"app_name": "Calculator"})],
        ),
        ModelResponse(text="Opened Calculator and then closed it successfully."),
    ]

    model = MockStepModel(mock_turns)
    agent = ZoeAgent(model=model)

    state = agent.run_task("Open Calculator and then close it.")

    assert state.is_complete is True
    assert state.cancelled is False
    assert len(state.recent_actions) == 2
    assert state.recent_actions[0]["action"] == "open_app"
    assert state.recent_actions[1]["action"] == "close_app"
    assert "successfully" in str(state.final_response)


def test_agent_max_iterations_cap():
    emergency_controller.reset()

    # Infinite tool loop
    infinite_turn = ModelResponse(
        text="",
        tool_calls=[ToolCall(id="inf", name="get_active_app", arguments={})],
    )
    model = MockStepModel([infinite_turn] * 50)
    agent = ZoeAgent(model=model)
    # Set max_tool_calls to 3 for fast test
    agent.config.agent.max_tool_calls = 3

    state = agent.run_task("Infinite task")

    assert state.is_complete is True
    assert state.cancelled is True
    assert "maximum tool call limit" in str(state.final_response)
    assert state.iteration_count == 3


def test_agent_emergency_stop():
    emergency_controller.reset()

    # Emergency stop triggered before second tool call
    def on_tool_step(messages, **kwargs):
        emergency_controller.trigger("User hit ESC")
        return ModelResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="get_active_app", arguments={})],
        )

    mock_model = MockStepModel([])
    mock_model.chat = on_tool_step  # type: ignore

    agent = ZoeAgent(model=mock_model)
    state = agent.run_task("Run with emergency stop")

    assert state.cancelled is True
    assert "Emergency stop" in str(state.final_response)
    emergency_controller.reset()


def test_agent_unknown_tool_recovery():
    emergency_controller.reset()

    mock_turns = [
        # Turn 1: model requests invalid tool
        ModelResponse(
            text="",
            tool_calls=[ToolCall(id="c1", name="fake_unknown_tool", arguments={"foo": "bar"})],
        ),
        # Turn 2: model sees error in conversation and recovers
        ModelResponse(text="I corrected the error and finished."),
    ]
    model = MockStepModel(mock_turns)
    agent = ZoeAgent(model=model)

    state = agent.run_task("Run invalid tool recovery")

    assert state.is_complete is True
    assert state.cancelled is False
    assert len(state.recent_actions) == 1
    # Check that tool result captured the structured error without crashing
    assert state.recent_actions[0]["result"]["success"] is False
    assert "not recognized" in state.recent_actions[0]["result"]["error"]
