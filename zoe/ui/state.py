"""Bridge linking voice state and audio metrics to the MacBook Notch UI."""

from typing import Optional
from zoe.ui.animation import get_animation_controller, NotchAnimationController
from zoe.voice.state import VoiceState, voice_state_manager


def set_ui_state(state: VoiceState) -> None:
    """Manually update the active UI visual state."""
    voice_state_manager.set_state(state)


def set_ui_audio_level(amplitude: float, pitch: float = 220.0) -> None:
    """Pass live amplitude and pitch to the active notch animation controller."""
    anim = get_animation_controller()
    anim.set_audio_metrics(amplitude=amplitude, pitch=pitch)
