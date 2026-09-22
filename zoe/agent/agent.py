"""Top-level Zoe agent coordinator."""

from typing import Optional
from zoe.config import get_config, Config
from zoe.models.base import LocalModel
from zoe.models.factory import get_model
from zoe.agent.state import AgentState
from zoe.agent.loop import AgentLoop


class ZoeAgent:
    """
    Personal local AI computer assistant agent.
    Runs 100% on-device with zero cloud telemetry.
    """

    def __init__(
        self,
        model: Optional[LocalModel] = None,
        config: Optional[Config] = None,
    ) -> None:
        self.config = config or get_config()
        self.model = model or get_model(self.config)
        self.loop = AgentLoop(self.model)

    def run_task(self, task: str) -> AgentState:
        """Execute a natural language task on the local Mac."""
        return self.loop.run(task)

    def is_ready(self) -> bool:
        """Check if local model backend is available and responsive."""
        return self.model.is_available()
