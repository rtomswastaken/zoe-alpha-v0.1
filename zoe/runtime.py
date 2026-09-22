"""Unified Zoe Runtime orchestrating Voice, Agent, Vision, Notch UI, and Memory."""

import sys
import time
from typing import Any, Dict, Optional
from zoe.config import get_config
from zoe.agent.agent import ZoeAgent
from zoe.memory import get_memory_manager
from zoe.models.factory import get_model
from zoe.models.vision_factory import get_vision_model
from zoe.macos.emergency import emergency_controller
from zoe.macos.permissions import get_permission_status
from zoe.macos.logger import zoe_logger
from zoe.ui.notch import NotchGeometry
from zoe.voice.pipeline import get_voice_pipeline
from zoe.voice.state import VoiceState, voice_state_manager


class ZoeRuntime:
    """
    Unified high-level lifecycle orchestrator for the Zoe Personal AI Assistant.
    Coordinates local Voice, Reasoning Agent, Computer Vision, MacBook Notch Glow, and SQLite Memory.
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.voice_pipeline = get_voice_pipeline()
        self.memory = get_memory_manager()
        self.agent = ZoeAgent()
        self._running = False

    def preflight_check(self) -> Dict[str, Any]:
        """Check all local dependencies and return a structured diagnostic status."""
        perms = get_permission_status()
        model_ready = self.agent.is_ready()
        vision_model = get_vision_model()
        vision_ready = vision_model.is_available()

        diagnostics = {
            "accessibility": perms.get("accessibility_granted", False),
            "screen_recording": perms.get("screen_recording_granted", False),
            "microphone": perms.get("microphone_granted", False),
            "llm_ready": model_ready,
            "vision_ready": vision_ready,
            "all_systems_ready": bool(
                perms.get("accessibility_granted")
                and perms.get("screen_recording_granted")
                and perms.get("microphone_granted")
                and model_ready
            ),
        }
        return diagnostics

    def print_friendly_diagnostics(self, diag: Dict[str, Any]) -> None:
        """Print clear, non-technical diagnostics without tracebacks."""
        if not diag["accessibility"]:
            print("⚠️  Accessibility permission is disabled.")
            print("   Please enable it in System Settings -> Privacy & Security -> Accessibility.")
        if not diag["screen_recording"]:
            print("⚠️  Screen Recording permission is disabled.")
            print("   Please enable it in System Settings -> Privacy & Security -> Screen Recording.")
        if not diag["microphone"]:
            print("⚠️  Microphone permission is not granted.")
            print("   Please grant microphone access in System Settings.")
        if not diag["llm_ready"]:
            print("⚠️  Local reasoning model (qwen3:14b) is not reachable.")
            print("   Please verify Ollama is running locally via `ollama serve`.")
        if not diag["vision_ready"]:
            print("ℹ️  Local vision model (minicpm-v) is offline. Visual fallback will be limited.")

    def start(self, interactive_cli: bool = False) -> None:
        """Launch the unified assistant runtime with ambient Notch UI and voice listening."""
        diag = self.preflight_check()
        self.print_friendly_diagnostics(diag)

        if not diag["accessibility"] or not diag["screen_recording"]:
            print("\nCannot start Zoe: Required macOS permissions are missing.\n")
            return

        if not diag["llm_ready"]:
            print("\nCannot start Zoe: Local LLM is offline.\n")
            return

        print("\n" + "=" * 60)
        print("  ZOE — Unified Local AI Assistant for macOS (100% Offline)")
        print("=" * 60)
        print(f"• Wake Word:   '{self.config.voice.wake_word.phrase}'")
        print(f"• Reasoning:   {self.config.model.name} via Ollama")
        print(f"• Vision:      {self.config.vision.model} via Ollama")
        print(f"• Voice STT:   {self.config.voice.stt.provider} ({self.config.voice.stt.model})")
        print(f"• Voice TTS:   {self.config.voice.tts.provider} ({self.config.voice.tts.voice})")
        print(f"• Memory:      SQLite Local Database ({self.memory.db.db_path})")
        print("• Notch UI:    ACTIVE (Ambient interactive glow)")
        print("• Safety:      Press 'ESC' at any moment for Emergency Stop.")
        print("=" * 60 + "\n")
        print("Zoe is listening. Say 'Zoe' or a command to begin...\n")

        emergency_controller.start_listener()
        self.voice_pipeline.start()
        self._running = True
        zoe_logger.log_action("RUNTIME_STARTED")

        try:
            while self._running:
                time.sleep(0.5)
                if emergency_controller.is_stopped():
                    print("\n[Emergency Stop] ESC pressed. Resetting Zoe to IDLE.")
                    self.voice_pipeline.tts.stop()
                    voice_state_manager.set_state(VoiceState.IDLE)
                    emergency_controller.reset()
        except KeyboardInterrupt:
            print("\nShutdown signal received...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Cleanly shut down the runtime."""
        self._running = False
        self.voice_pipeline.stop()
        emergency_controller.stop_listener()
        zoe_logger.log_action("RUNTIME_STOPPED")
        print("Zoe assistant shut down safely.")


_runtime_instance: Optional[ZoeRuntime] = None


def get_runtime() -> ZoeRuntime:
    global _runtime_instance
    if _runtime_instance is None:
        _runtime_instance = ZoeRuntime()
    return _runtime_instance
