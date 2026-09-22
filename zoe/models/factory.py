"""Model factory for Zoe."""

from typing import Optional
from zoe.config import get_config, Config
from zoe.models.base import LocalModel
from zoe.models.ollama import OllamaModel


def get_model(config: Optional[Config] = None) -> LocalModel:
    """Instantiate and return the configured local model engine."""
    if config is None:
        config = get_config()

    provider = config.model.provider.lower().strip()

    if provider == "ollama":
        return OllamaModel(
            endpoint=config.model.endpoint,
            model_name=config.model.name,
            timeout=config.model.timeout,
            default_temperature=config.model.temperature,
            default_max_tokens=config.model.max_tokens,
        )
    else:
        # Default fallback to Ollama
        return OllamaModel(
            endpoint=config.model.endpoint,
            model_name=config.model.name,
            timeout=config.model.timeout,
            default_temperature=config.model.temperature,
            default_max_tokens=config.model.max_tokens,
        )
