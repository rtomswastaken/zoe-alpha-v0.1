"""Settings and configuration loader for Zoe."""

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
class Config:
    version: str = "1.0"
    model: ModelConfig = field(default_factory=ModelConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    keyboard: KeyboardConfig = field(default_factory=KeyboardConfig)
    emergency: EmergencyConfig = field(default_factory=EmergencyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    screenshots: ScreenshotConfig = field(default_factory=ScreenshotConfig)

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

            return cls(
                version=data.get("version", "1.0"),
                model=ModelConfig(**data.get("model", {})),
                agent=AgentConfig(**data.get("agent", {})),
                cursor=CursorConfig(**data.get("cursor", {})),
                mouse=MouseConfig(**data.get("mouse", {})),
                keyboard=KeyboardConfig(**data.get("keyboard", {})),
                emergency=EmergencyConfig(**data.get("emergency", {})),
                logging=LoggingConfig(**data.get("logging", {})),
                screenshots=ScreenshotConfig(**data.get("screenshots", {})),
            )
        except Exception:
            return cls()


_global_config: Config | None = None


def get_config(reload: bool = False) -> Config:
    global _global_config
    if _global_config is None or reload:
        _global_config = Config.load()
    return _global_config
