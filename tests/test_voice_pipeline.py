"""Unit and integration tests for VoicePipeline."""

import numpy as np
import pytest
from zoe.agent.agent import ZoeAgent
from zoe.agent.state import AgentState
from zoe.macos.emergency import emergency_controller
from zoe.voice.pipeline import VoicePipeline
from zoe.voice.state import VoiceState, voice_state_manager
from zoe.voice.stt import BaseSTT
from zoe.voice.tts import BaseTTS
from zoe.voice.wake_word import BaseWakeWord


class MockSTT(BaseSTT):
    def __init__(self, transcription: str = "open Calculator"):
        self.transcription = transcription

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000, **kwargs) -> str:
        return self.transcription

    def is_available(self) -> bool:
        return True


class MockTTS(BaseTTS):
    def __init__(self):
        self.spoken = []
        self.stopped = False

    def speak(self, text: str, wait: bool = True, on_amplitude=None) -> bool:
        self.spoken.append(text)
        return True

    def stop(self) -> None:
        self.stopped = True

    def is_speaking(self) -> bool:
        return False

    def get_voices(self):
        return ["MockVoice"]


class MockWakeWord(BaseWakeWord):
    def __init__(self, trigger: bool = False):
        self.trigger = trigger

    def check_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> bool:
        return self.trigger

    @property
    def phrase(self) -> str:
        return "zoe"


class MockAgent:
    def __init__(self):
        self.tasks = []

    def run_task(self, command: str) -> AgentState:
        self.tasks.append(command)
        state = AgentState(task=command)
        state.final_response = f"Simulated execution of: {command}"
        state.is_complete = True
        return state


def test_voice_pipeline_wake_cycle():
    mock_stt = MockSTT("open Calculator")
    mock_tts = MockTTS()
    mock_ww = MockWakeWord(trigger=True)
    mock_agent = MockAgent()

    pipeline = VoicePipeline(
        agent=mock_agent,
        stt=mock_stt,
        tts=mock_tts,
        wake_word=mock_ww,
    )

    # Simulate handle_wake_cycle
    # Mock recorder to return simulated speech audio
    pipeline.recorder.record_until_silence = lambda **kwargs: np.ones(16000, dtype=np.float32)

    pipeline._running = True
    pipeline._handle_wake_cycle()

    assert len(mock_agent.tasks) == 1
    assert mock_agent.tasks[0] == "open Calculator"
    assert len(mock_tts.spoken) == 1
    assert "Simulated execution" in mock_tts.spoken[0]
    assert voice_state_manager.current_state == VoiceState.IDLE


def test_voice_pipeline_voice_stop():
    mock_stt = MockSTT("stop")
    mock_tts = MockTTS()
    mock_ww = MockWakeWord(trigger=True)
    mock_agent = MockAgent()

    pipeline = VoicePipeline(
        agent=mock_agent,
        stt=mock_stt,
        tts=mock_tts,
        wake_word=mock_ww,
    )
    pipeline.recorder.record_until_silence = lambda **kwargs: np.ones(16000, dtype=np.float32)

    emergency_controller.reset()
    pipeline._running = True
    pipeline._handle_wake_cycle()

    # Should have triggered emergency stop and skipped agent task
    assert len(mock_agent.tasks) == 0
    assert emergency_controller.is_stopped() is True
    assert mock_tts.stopped is True
    assert voice_state_manager.current_state == VoiceState.IDLE

    # Clean up emergency stop
    emergency_controller.reset()
