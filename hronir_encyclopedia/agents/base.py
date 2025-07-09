"""
Base Agent Class for Hronir Encyclopedia AI Agents

Provides common functionality for all AI agents in the system.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .. import gemini_util, storage
from ..models import SystemConfig


@dataclass
class AgentConfig:
    """Configuration for Hronir AI agents."""
    name: str
    role: str
    goal: str
    backstory: str
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    temperature: float = 0.7
    max_tokens: int = 2000
    verbose: bool = False

    # Hronir-specific settings
    competitive_mode: bool = True
    narrative_consistency_threshold: float = 0.8
    quality_threshold: float = 0.7


class BaseHronirAgent(ABC):
    """Base class for all Hronir Encyclopedia AI agents."""

    def __init__(self, config: AgentConfig, system_config: SystemConfig | None = None):
        self.config = config
        self.system_config = system_config or SystemConfig()
        self.data_manager = storage.DataManager()
        self.gemini_util = gemini_util

        # Initialize Gemini API
        self._ensure_gemini_api()

    def _ensure_gemini_api(self):
        """Ensure Gemini API is properly configured."""
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY environment variable not set")

    def get_canonical_path(self) -> dict[str, Any]:
        """Get the current canonical path state."""
        # This would integrate with the existing canonical path logic
        # For now, return a placeholder
        return {"path": {}, "last_updated": None}

    def get_narrative_context(self, position: int, predecessor_uuid: str | None = None) -> str:
        """Get narrative context for a given position."""
        if predecessor_uuid:
            # Get the hrönir content for context
            hrönir_data = self.data_manager.get_hrönir_by_uuid(predecessor_uuid)
            if hrönir_data:
                return hrönir_data.text_content[:500]  # First 500 chars for context
        return ""

    def generate_with_gemini(self, prompt: str) -> str:
        """Generate content using Gemini API."""
        return self.gemini_util._gemini_request(prompt)

    def evaluate_narrative_consistency(self, content: str, context: str) -> float:
        """Evaluate how well content fits with existing narrative."""
        # This would implement semantic similarity or other consistency metrics
        # For now, return a placeholder score
        return 0.8

    def log_action(self, action: str, details: dict[str, Any]):
        """Log agent actions for monitoring and debugging."""
        print(f"[{self.config.name}] {action}: {details}")

    @abstractmethod
    def execute_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a specific task - to be implemented by subclasses."""
        pass

    @abstractmethod
    def get_agent_prompt(self, task_data: dict[str, Any]) -> str:
        """Generate the prompt for this agent's task."""
        pass
