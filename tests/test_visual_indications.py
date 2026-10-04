"""Comprehensive verification of primary MacBook Notch visual indicator and terminal indicator across all states."""

import time
import pytest
from AppKit import NSRect, NSPoint, NSSize
from zoe.state import ZoeState, zoe_state, STATE_PRIORITY
from zoe.voice.state import VoiceState, voice_state_manager
from zoe.ui.notch import ZoeNotchGlowView, ZoeNotchOverlayWindow, get_notch_overlay
from zoe.ui.animation import NotchAnimator, get_animation_controller
from zoe.ui.audio_reactive import AudioReactiveLevel
from zoe.ui.terminal import TerminalStatusIndicator, get_terminal_indicator
from zoe.macos.cursor import get_cursor_position
from zoe.config import get_config


def test_all_authoritative_states_defined():
    """Verify all 9 runtime states are defined in the single authoritative ZoeState enum."""
    expected_states = [
        "STARTUP",
        "IDLE",
        "LISTENING",
        "THINKING",
        "ACTING",
        "RESPONDING",
        "SUCCESS",
        "ERROR",
        "STOPPING",
    ]
    for s in expected_states:
        state_enum = getattr(ZoeState, s, None)
        assert state_enum is not None, f"ZoeState.{s} is missing"
        assert state_enum.value == s
        assert state_enum in STATE_PRIORITY, f"STATE_PRIORITY[{s}] is missing"


def test_startup_bloom_and_revert():
    """Verify STARTUP state triggers welcome bloom and cleanly reverts to ambient IDLE."""
    history = []

    def on_change(old, new):
        history.append(new)

    zoe_state.add_listener(on_change)
    try:
        zoe_state.set_temporary_state(ZoeState.STARTUP, duration=0.15, return_state=ZoeState.IDLE)
        assert zoe_state.current_state == ZoeState.STARTUP
        time.sleep(0.25)
        assert zoe_state.current_state == ZoeState.IDLE
        assert ZoeState.STARTUP in history
        assert history[-1] == ZoeState.IDLE
    finally:
        zoe_state.remove_listener(on_change)
        zoe_state.set_state(ZoeState.IDLE)


def test_subtle_ambient_idle_state():
    """Verify ambient IDLE state has subtle target alpha (~0.28) when show_on_idle is True."""
    anim = NotchAnimator()
    cfg = get_config()
    orig_show = cfg.ui.notch.show_on_idle
    try:
        cfg.ui.notch.show_on_idle = True
        anim._on_state_changed(ZoeState.STARTUP, ZoeState.IDLE)
        assert anim._target_alpha == pytest.approx(0.28, abs=0.02)
        assert anim._target_alpha < 0.40  # Must be subtle, not bright

        cfg.ui.notch.show_on_idle = False
        anim._on_state_changed(ZoeState.STARTUP, ZoeState.IDLE)
        assert anim._target_alpha == 0.0
    finally:
        cfg.ui.notch.show_on_idle = orig_show
        anim.stop()


def test_emergency_stopping_immediate_collapse():
    """Verify STOPPING state causes immediate collapse (target_alpha=0, current_alpha=0)."""
    anim = NotchAnimator()
    anim._current_alpha = 0.95
    anim._on_state_changed(ZoeState.ACTING, ZoeState.STOPPING)
    assert anim._target_alpha == 0.0
    assert anim._current_alpha == 0.0
    anim.stop()


def test_all_states_draw_in_glow_view():
    """Verify ZoeNotchGlowView draws without crashing for all 9 states."""
    view = ZoeNotchGlowView.alloc().initWithFrame_(
        NSRect(NSPoint(0, 0), NSSize(340, 90))
    )
    view.notch_rect = NSRect(NSPoint(70, 50), NSSize(200, 38))
    view.alpha_level = 0.8
    view.pulse_phase = 1.2
    view.audio_amplitude = 0.5
    view.pitch_hz = 220.0

    all_states = [
        "STARTUP",
        "IDLE",
        "LISTENING",
        "THINKING",
        "ACTING",
        "RESPONDING",
        "SPEAKING",
        "SUCCESS",
        "ERROR",
        "STOPPING",
    ]

    for st in all_states:
        view.state_name = st
        # Trigger drawRect_ without exception
        view.drawRect_(view.bounds())


def test_microphone_reactivity():
    """Verify microphone RMS values produce smoothed, jitter-free visual amplitude."""
    audio_filter = AudioReactiveLevel(noise_floor=0.002, ceiling=0.08, attack=0.45, release=0.18)

    # Ambient room noise below threshold -> 0.0
    assert audio_filter.process(0.001) == 0.0

    # Vocal onset -> punchy attack
    level1 = audio_filter.process(0.05)
    assert level1 > 0.0
    assert level1 <= 1.0

    level2 = audio_filter.process(0.05)
    assert level2 >= level1

    # Vocal pause -> smooth release decay
    level3 = audio_filter.process(0.0)
    assert level3 < level2
    assert level3 > 0.0


def test_tts_reactivity():
    """Verify TTS speech cadence envelope produces smooth dynamic levels with release decay."""
    audio_filter = AudioReactiveLevel()
    
    # Word spoken -> attack rises
    active_level = audio_filter.process(0.05)
    assert active_level > 0.0

    # Continued speaking attacks upward
    sustained_level = audio_filter.process(0.05)
    assert sustained_level >= active_level

    # Word pause / speech complete -> release smoothing decays smoothly toward 0
    decay1 = audio_filter.process(0.0)
    assert decay1 < sustained_level

    decay2 = audio_filter.process(0.0)
    assert decay2 < decay1


def test_terminal_indicator_formatting_and_deduplication():
    """Verify TerminalStatusIndicator formats clean badges and avoids repeated spam."""
    indicator = TerminalStatusIndicator(enabled=True)

    # Check formatting of core states
    startup_str = indicator.format_status(ZoeState.STARTUP, use_color=False)
    assert "[STARTUP]" in startup_str

    listen_str = indicator.format_status(ZoeState.LISTENING, use_color=False)
    assert "[LISTENING]" in listen_str

    think_str = indicator.format_status(ZoeState.THINKING, use_color=False)
    assert "[THINKING]" in think_str

    act_str = indicator.format_status(ZoeState.ACTING, use_color=False)
    assert "[WORKING]" in act_str

    resp_str = indicator.format_status(ZoeState.RESPONDING, use_color=False)
    assert "[RESPONDING]" in resp_str

    # Test deduplication
    indicator._last_state = None
    indicator._on_state_changed(ZoeState.IDLE, ZoeState.LISTENING)
    assert indicator._last_state == ZoeState.LISTENING

    # Same state change should be ignored (deduplicated)
    prev_last = indicator._last_state
    indicator._on_state_changed(ZoeState.LISTENING, ZoeState.LISTENING)
    assert indicator._last_state == prev_last


def test_physical_cursor_unchanged():
    """Verify that updating Notch visual states does not move or touch physical mouse cursor."""
    pos_before = get_cursor_position()

    anim = get_animation_controller()
    anim.set_state(ZoeState.STARTUP)
    anim.update(0.016)
    anim.set_state(ZoeState.LISTENING)
    anim.update(0.016)
    anim.set_state(ZoeState.THINKING)
    anim.update(0.016)
    anim.set_state(ZoeState.ACTING)
    anim.update(0.016)
    anim.set_state(ZoeState.IDLE)
    anim.update(0.016)

    pos_after = get_cursor_position()

    # The physical mouse position must remain exactly the same
    assert pos_before == pos_after


def test_notch_overlay_window_configuration_and_display():
    """Verify NSWindow configuration: main thread, correct level, screen, frame, and visibility."""
    from AppKit import NSThread, NSStatusWindowLevel
    from zoe.ui.notch import get_notch_overlay, pump_cocoa_events

    assert NSThread.isMainThread() is True

    overlay = get_notch_overlay()
    assert overlay.window is not None
    assert overlay.glow_view is not None

    # Check Window Level
    assert overlay.window.level() == NSStatusWindowLevel + 2

    # Check Window properties
    assert overlay.window.isOpaque() is False
    assert overlay.window.ignoresMouseEvents() is True
    assert overlay.window.hidesOnDeactivate() is False

    # Check Frame & Screen
    s_frame = overlay.screen.frame()
    w_frame = overlay.window.frame()
    assert w_frame.size.width >= 340.0
    assert w_frame.size.height >= 80.0
    assert w_frame.origin.y >= s_frame.origin.y

    # Test display and visibility
    overlay.update_visuals(state="DEBUG", alpha=1.0, pulse_phase=0.0)
    assert overlay.window.isVisible() is True
    assert overlay.window.alphaValue() == 1.0

    pump_cocoa_events(0.02)
    overlay.hide()
    assert overlay.window.isVisible() is False
