"""Zoe MacBook Notch UI package."""

from .audio_reactive import AudioReactiveLevel
from .animation import NotchAnimator, NotchAnimationController, get_animation_controller
from .notch import NotchGeometry, ZoeNotchGlowView, ZoeNotchOverlayWindow, get_notch_overlay
from .state import set_ui_audio_level, set_ui_state
from .terminal import TerminalStatusIndicator, get_terminal_indicator

__all__ = [
    "AudioReactiveLevel",
    "NotchGeometry",
    "ZoeNotchOverlayWindow",
    "ZoeNotchGlowView",
    "get_notch_overlay",
    "NotchAnimator",
    "NotchAnimationController",
    "get_animation_controller",
    "set_ui_state",
    "set_ui_audio_level",
    "TerminalStatusIndicator",
    "get_terminal_indicator",
]
