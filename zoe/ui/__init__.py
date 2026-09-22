"""Zoe MacBook Notch UI package."""

from .notch import NotchGeometry, ZoeNotchOverlayWindow, ZoeNotchGlowView, get_notch_overlay
from .animation import NotchAnimationController, get_animation_controller
from .state import set_ui_state, set_ui_audio_level

__all__ = [
    "NotchGeometry",
    "ZoeNotchOverlayWindow",
    "ZoeNotchGlowView",
    "get_notch_overlay",
    "NotchAnimationController",
    "get_animation_controller",
    "set_ui_state",
    "set_ui_audio_level",
]
