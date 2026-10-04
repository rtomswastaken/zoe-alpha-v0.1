"""Explicit state machine and event emitter for Zoe Voice and Notch UI.

Aliased to zoe.state for unified runtime architecture.
"""

from zoe.state import (
    ZoeState as VoiceState,
    ZoeStateManager as VoiceStateManager,
    zoe_state as voice_state_manager,
    STATE_PRIORITY,
    get_state_priority,
)

__all__ = [
    "VoiceState",
    "VoiceStateManager",
    "voice_state_manager",
    "STATE_PRIORITY",
    "get_state_priority",
]
