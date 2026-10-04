"""Settings and configuration loader for Zoe."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict
import yaml


@dataclass
class ModelConfig:
    provider: str = "ollama"
    name: str = "qwen3:14b"
    endpoint: str = "http://127.0.0.1:11434"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: float = 60.0


@dataclass
class VisionConfig:
    provider: str = "ollama"
    model: str = "minicpm-v"
    endpoint: str = "http://127.0.0.1:11434"
    max_tokens: int = 1024
    enabled: bool = True
    confidence_threshold: float = 0.75
    debug_overlay: bool = False


@dataclass
class AgentConfig:
    max_tool_calls: int = 30
    timeout_seconds: float = 300.0
    system_prompt_extra: str = ""


@dataclass
class CursorConfig:
    default_duration: float = 0.35
    default_steps: int = 40
    easing: str = "cubic_bezier"
    jitter: float = 1.5
    bounds_check: bool = True


@dataclass
class MouseConfig:
    click_delay: float = 0.05
    double_click_interval: float = 0.12
    drag_duration: float = 0.5


@dataclass
class KeyboardConfig:
    typing_delay: float = 0.02
    key_press_duration: float = 0.03


@dataclass
class EmergencyConfig:
    enabled: bool = True
    hotkey: str = "escape"
    poll_interval: float = 0.01


@dataclass
class LoggingConfig:
    enabled: bool = True
    file_path: str = "logs/zoe.log"
    console_output: bool = True
    mask_sensitive: bool = True


@dataclass
class ScreenshotConfig:
    storage_dir: str = "cache/screenshots"
    format: str = "png"
    local_only: bool = True


@dataclass
class WakeWordConfig:
    enabled: bool = True
    phrase: str = "zoe"
    threshold: float = 0.6


@dataclass
class STTConfig:
    provider: str = "faster_whisper"
    model: str = "base.en"
    compute_type: str = "int8"
    language: str = "en"


@dataclass
class TTSConfig:
    provider: str = "nsspeech"
    voice: str = "Samantha"
    rate: int = 190
    volume: float = 1.0


@dataclass
class InterruptionConfig:
    voice_stop: bool = True
    keyboard_stop: bool = True


@dataclass
class VoiceConfig:
    enabled: bool = True
    sample_rate: int = 16000
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    interruption: InterruptionConfig = field(default_factory=InterruptionConfig)


@dataclass
class NotchUIConfig:
    enabled: bool = True
    animation: bool = True
    voice_reactive: bool = True
    show_on_idle: bool = True
    glow_spread: float = 24.0


@dataclass
class UIConfig:
    notch: NotchUIConfig = field(default_factory=NotchUIConfig)


@dataclass
class OpenClickyConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 32123
    timeout: float = 2.0
    token: str = ""


@dataclass
class Config:
    version: str = "1.0"
    model: ModelConfig = field(default_factory=ModelConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    keyboard: KeyboardConfig = field(default_factory=KeyboardConfig)
    emergency: EmergencyConfig = field(default_factory=EmergencyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    screenshots: ScreenshotConfig = field(default_factory=ScreenshotConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    openclicky: OpenClickyConfig = field(default_factory=OpenClickyConfig)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Config":
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = yaml.safe_load(f) or {}

            voice_raw = data.get("voice", {})
            wake_word_raw = voice_raw.get("wake_word", {})
            stt_raw = voice_raw.get("stt", {})
            tts_raw = voice_raw.get("tts", {})
            interruption_raw = voice_raw.get("interruption", {})

            voice_cfg = VoiceConfig(
                enabled=voice_raw.get("enabled", True),
                sample_rate=voice_raw.get("sample_rate", 16000),
                wake_word=WakeWordConfig(**wake_word_raw),
                stt=STTConfig(**stt_raw),
                tts=TTSConfig(**tts_raw),
                interruption=InterruptionConfig(**interruption_raw),
            )

            ui_raw = data.get("ui", {})
            notch_raw = ui_raw.get("notch", {})
            ui_cfg = UIConfig(
                notch=NotchUIConfig(**notch_raw)
            )

            openclicky_raw = data.get("openclicky", {})
            # Environment variable overrides
            oc_enabled = openclicky_raw.get("enabled", False)
            if "ZOE_OPENCLICKY_ENABLED" in os.environ:
                env_val = os.environ["ZOE_OPENCLICKY_ENABLED"].lower()
                oc_enabled = env_val in ("1", "true", "yes", "on")

            oc_host = os.environ.get("ZOE_OPENCLICKY_HOST", openclicky_raw.get("host", "127.0.0.1"))
            oc_port = int(os.environ.get("ZOE_OPENCLICKY_PORT", openclicky_raw.get("port", 32123)))
            oc_timeout = float(os.environ.get("ZOE_OPENCLICKY_TIMEOUT", openclicky_raw.get("timeout", 2.0)))
            oc_token = os.environ.get("ZOE_OPENCLICKY_TOKEN", openclicky_raw.get("token", ""))

            openclicky_cfg = OpenClickyConfig(
                enabled=oc_enabled,
                host=oc_host,
                port=oc_port,
                timeout=oc_timeout,
                token=oc_token,
            )

            return cls(
                version=data.get("version", "1.0"),
                model=ModelConfig(**data.get("model", {})),
                vision=VisionConfig(**data.get("vision", {})),
                agent=AgentConfig(**data.get("agent", {})),
                cursor=CursorConfig(**data.get("cursor", {})),
                mouse=MouseConfig(**data.get("mouse", {})),
                keyboard=KeyboardConfig(**data.get("keyboard", {})),
                emergency=EmergencyConfig(**data.get("emergency", {})),
                logging=LoggingConfig(**data.get("logging", {})),
                screenshots=ScreenshotConfig(**data.get("screenshots", {})),
                voice=voice_cfg,
                ui=ui_cfg,
                openclicky=openclicky_cfg,
            )
        except Exception:
            return cls()


_global_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    global _global_config
    if _global_config is None or reload:
        _global_config = Config.load()
    return _global_config
