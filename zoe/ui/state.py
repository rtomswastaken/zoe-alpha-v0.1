"""Bridge linking runtime state and audio metrics to the MacBook Notch UI."""

from zoe.ui.animation import get_animation_controller, NotchAnimator, NotchAnimationController
from zoe.state import ZoeState, zoe_state
from zoe.voice.state import VoiceState, voice_state_manager


def set_ui_state(state: ZoeState) -> None:
    """Manually update the active UI visual state."""
    zoe_state.set_state(state)


def set_ui_audio_level(amplitude: float, pitch: float = 220.0) -> None:
    """Pass live amplitude and pitch to the active notch animation controller."""
    anim = get_animation_controller()
    anim.set_audio_level(amplitude=amplitude, pitch=pitch)
