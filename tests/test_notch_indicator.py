"""Tests for the MacBook Notch Activity Indicator, AudioReactiveLevel filter, and Authoritative State Machine."""

import time
import pytest
from zoe.state import ZoeState, ZoeStateManager, zoe_state
from zoe.voice.state import VoiceState, voice_state_manager
from zoe.ui.audio_reactive import AudioReactiveLevel
from zoe.ui.animation import NotchAnimator, get_animation_controller
from zoe.visual.cursor import visual_cursor
from zoe.visual.state import VisualCursorState


def test_single_authoritative_state_system() -> None:
    """
    Requirement 1: There must be ONE authoritative Zoe runtime/activity state.
    VoiceState is ZoeState, voice_state_manager is zoe_state.
    UI and Visual Cursor observe the same authoritative state singleton.
    """
    # 1. Verify aliases are identical types and singletons
    assert VoiceState is ZoeState
    assert voice_state_manager is zoe_state

    recorded_transitions = []

    def state_listener(old_s: ZoeState, new_s: ZoeState) -> None:
        recorded_transitions.append((old_s, new_s))

    zoe_state.add_listener(state_listener)

    # 2. State change via voice_state_manager reflects in zoe_state
    voice_state_manager.set_state(VoiceState.LISTENING)
    assert zoe_state.current_state == ZoeState.LISTENING

    voice_state_manager.set_state(VoiceState.THINKING)
    assert zoe_state.current_state == ZoeState.THINKING

    voice_state_manager.set_state(VoiceState.IDLE)
    assert zoe_state.current_state == ZoeState.IDLE

    assert (ZoeState.IDLE, ZoeState.LISTENING) in recorded_transitions
    assert (ZoeState.LISTENING, ZoeState.THINKING) in recorded_transitions
    assert (ZoeState.THINKING, ZoeState.IDLE) in recorded_transitions

    zoe_state.remove_listener(state_listener)


def test_runtime_transitions_lifecycle() -> None:
    """
    Requirement 2: Full runtime transitions trace:
    Wake word -> LISTENING
    Command captured -> THINKING
    Agent/tool execution -> ACTING
    TTS begins -> RESPONDING
    TTS ends -> SUCCESS -> IDLE
    """
    history = []

    def tracker(old_s: ZoeState, new_s: ZoeState) -> None:
        history.append(new_s)

    zoe_state.add_listener(tracker)

    try:
        # Simulate wake word sequence
        zoe_state.set_state(ZoeState.LISTENING)
        zoe_state.set_state(ZoeState.THINKING)
        zoe_state.set_state(ZoeState.ACTING)
        zoe_state.set_state(ZoeState.RESPONDING)
        zoe_state.set_temporary_state(ZoeState.SUCCESS, duration=0.1, return_state=ZoeState.IDLE)

        assert history[-5:] == [
            ZoeState.LISTENING,
            ZoeState.THINKING,
            ZoeState.ACTING,
            ZoeState.RESPONDING,
            ZoeState.SUCCESS,
        ]

        # Wait for temporary state to revert to IDLE
        time.sleep(0.18)
        assert zoe_state.current_state == ZoeState.IDLE

        # Error sequence
        zoe_state.set_temporary_state(ZoeState.ERROR, duration=0.1, return_state=ZoeState.IDLE)
        assert zoe_state.current_state == ZoeState.ERROR
        time.sleep(0.18)
        assert zoe_state.current_state == ZoeState.IDLE

        # Stop sequence
        zoe_state.set_state(ZoeState.STOPPING)
        assert zoe_state.current_state == ZoeState.STOPPING
        zoe_state.set_state(ZoeState.IDLE)
        assert zoe_state.current_state == ZoeState.IDLE

    finally:
        zoe_state.remove_listener(tracker)
        zoe_state.set_state(ZoeState.IDLE)


def test_audio_reactive_pipeline() -> None:
    """
    Requirement 3:
    Microphone -> RMS -> noise-floor removal -> normalization -> smoothing -> Notch
    """
    processor = AudioReactiveLevel(noise_floor=0.002, ceiling=0.08, attack=0.5, release=0.2)

    # 1. Noise-floor removal: silence / ambient room noise (< 0.002) must output exactly 0.0
    ambient_noise = 0.0012
    assert processor.process(ambient_noise) == 0.0

    # 2. Active vocal onset (RMS = 0.04): must normalize and attack upward
    speech_rms = 0.04
    level1 = processor.process(speech_rms)
    assert level1 > 0.0
    assert level1 <= 1.0

    # Continued speech sustaining level
    level2 = processor.process(speech_rms)
    assert level2 >= level1  # attack smoothed upward

    # Peak is tracked
    assert processor.peak >= level2

    # 3. Speech drops to silence: release smoothing gradually decays towards 0
    decay1 = processor.process(0.0)
    assert decay1 < level2
    assert decay1 > 0.0  # smooth release decay, not instant cutoff

    decay2 = processor.process(0.0)
    assert decay2 < decay1


def test_visual_cursor_observes_authoritative_state() -> None:
    """
    Visual cursor observes authoritative ZoeState changes:
    STOPPING -> emergency_stop
    IDLE -> returns to resting presence
    """
    visual_cursor.show()
    visual_cursor.move_to(300.0, 300.0)
    assert visual_cursor.is_visible is True

    # When emergency stop occurs, visual cursor immediately halts
    zoe_state.set_state(ZoeState.STOPPING)
    assert visual_cursor.state == VisualCursorState.HIDDEN

    zoe_state.set_state(ZoeState.IDLE)
    visual_cursor.clear()
