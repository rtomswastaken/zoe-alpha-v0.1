"""Unit tests for VoiceState and VoiceStateManager."""

import pytest
from zoe.voice.state import VoiceState, VoiceStateManager


def test_voice_state_values():
    assert VoiceState.IDLE.value == "IDLE"
    assert VoiceState.LISTENING.value == "LISTENING"
    assert VoiceState.THINKING.value == "THINKING"
    assert VoiceState.ACTING.value == "ACTING"
    assert VoiceState.SPEAKING.value == "SPEAKING"
    assert VoiceState.STOPPING.value == "STOPPING"


def test_voice_state_transitions():
    mgr = VoiceStateManager(initial_state=VoiceState.IDLE)
    assert mgr.current_state == VoiceState.IDLE

    history = []

    def on_change(old, new):
        history.append((old, new))

    mgr.add_listener(on_change)

    mgr.set_state(VoiceState.LISTENING)
    assert mgr.current_state == VoiceState.LISTENING

    mgr.set_state(VoiceState.THINKING)
    assert mgr.current_state == VoiceState.THINKING

    mgr.set_state(VoiceState.ACTING)
    assert mgr.current_state == VoiceState.ACTING

    mgr.set_state(VoiceState.SPEAKING)
    assert mgr.current_state == VoiceState.SPEAKING

    mgr.set_state(VoiceState.IDLE)
    assert mgr.current_state == VoiceState.IDLE

    assert len(history) == 5
    assert history[0] == (VoiceState.IDLE, VoiceState.LISTENING)
    assert history[-1] == (VoiceState.SPEAKING, VoiceState.IDLE)

    mgr.remove_listener(on_change)
    mgr.set_state(VoiceState.LISTENING)
    # Listener was removed, history length should remain 5
    assert len(history) == 5
