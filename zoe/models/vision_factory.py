"""Vision model factory for Zoe."""

from typing import Optional
from zoe.config import get_config, Config
from zoe.models.vision import VisionModel, OllamaVisionModel


def get_vision_model(config: Optional[Config] = None) -> VisionModel:
    """Instantiate and return the configured local vision model engine."""
    if config is None:
        config = get_config()

    # Default to OllamaVisionModel
    return OllamaVisionModel(
        endpoint=config.vision.endpoint,
        model_name=config.vision.model,
        default_confidence_threshold=config.vision.confidence_threshold,
    )
