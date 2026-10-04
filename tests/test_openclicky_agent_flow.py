"""End-to-end simulated agent flow test: LLM -> screenshot -> vision -> coordinate transform -> OpenClicky cursor."""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch
from zoe.agent.agent import ZoeAgent
from zoe.integrations.openclicky.client import OpenClickyClient
from zoe.macos.coordinates import ImageTransformMetadata
from zoe.macos.emergency import emergency_controller
from zoe.models.base import LocalModel, ModelResponse, ToolCall
from zoe.models.vision import VisionTargetResult



class MockAgentLLM(LocalModel):
    """Deterministic mock LLM yielding a tool call to guide to Wi-Fi settings, then final response."""

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
        return ModelResponse(text="Task completed.")

    def is_available(self) -> bool:
        return True

    def model_info(self) -> Dict[str, Any]:
        return {"provider": "MockLLM", "status": "AVAILABLE"}


def test_agent_simulated_wifi_guidance_flow() -> None:
    """
    Test user request: 'Show me where the Wi-Fi settings are.'
    Flow:
      LLM Planner
           ↓
      openclicky_guide tool call
           ↓
      Screenshot capture (capture_for_vision)
           ↓
      Vision model locate (MiniCPM-V)
           ↓
      Coordinate transform (vision -> Retina pixels -> Quartz -> AppKit)
           ↓
      OpenClicky show_cursor HTTP call
           ↓
      Final natural response to user
    """
    emergency_controller.reset()

    # Model planned turns:
    # Turn 1: Invokes openclicky_guide tool
    # Turn 2: Summarizes the guidance to the user
    turns = [
        ModelResponse(
            text="",
            tool_calls=[
                ToolCall(
                    id="call_wifi_1",
                    name="openclicky_guide",
                    arguments={"target": "Wi-Fi settings", "caption": "Wi-Fi Settings"},
                )
            ],
        ),
        ModelResponse(text="I've highlighted the Wi-Fi settings on your screen."),
    ]

    llm = MockAgentLLM(turns)
    agent = ZoeAgent(model=llm)

    mock_openclicky_client = MagicMock(spec=OpenClickyClient)
    mock_openclicky_client.show_cursor.return_value = {"ok": True, "displayed": "primary_cursor"}

    # Mock screen resolution: 2x Retina MacBook Pro (1728x1117 points, 3456x2234 pixels)
    meta = ImageTransformMetadata.create(
        point_width=1728.0,
        point_height=1117.0,
        pixel_width=3456,
        pixel_height=2234,
        vision_width=1024,
        vision_height=662,
        scale_factor=2.0,
        origin_x=0.0,
        origin_y=0.0,
    )

    # Mock accessibility returning no match, triggering local vision fallback
    with patch("zoe.integrations.openclicky.tools.get_app_accessibility_tree", return_value={"success": False}):
        with patch("zoe.integrations.openclicky.tools.get_openclicky_client", return_value=mock_openclicky_client):
            with patch("zoe.integrations.openclicky.tools.capture_for_vision") as mock_capture:
                mock_capture.return_value = {
                    "success": True,
                    "base64_image": "fake_jpeg_base64",
                    "metadata": meta,
                }
                with patch("zoe.integrations.openclicky.tools.get_vision_model") as mock_vmodel_factory:
                    mock_vision = MagicMock()
                    mock_vision.is_available.return_value = True
                    mock_vision.locate.return_value = VisionTargetResult(
                        found=True,
                        target="Wi-Fi settings",
                        x=920.0,
                        y=24.0,
                        confidence=0.94,
                        normalized=False,
                    )

                    mock_vmodel_factory.return_value = mock_vision

                    state = agent.run_task("Show me where the Wi-Fi settings are.")

                    assert state.is_complete is True
                    assert state.cancelled is False
                    assert state.final_response is not None
                    assert "Wi-Fi settings" in state.final_response or "highlighted" in state.final_response

                    # Verify openclicky client was invoked with converted coordinates
                    mock_openclicky_client.show_cursor.assert_called_once()
                    call_kwargs = mock_openclicky_client.show_cursor.call_args[1]
                    assert call_kwargs["caption"] == "Wi-Fi Settings"

                    # Check that coordinates are in valid AppKit space
                    assert 1400.0 < call_kwargs["x"] < 1800.0
                    assert call_kwargs["y"] > 1000.0

