"""
Chapter Writer Agent for Hronir Encyclopedia

Specialized agent for generating new hrönir chapters in the Borgesian style.
"""

from typing import Any

from .. import storage
from ..prompt_builder import build_synthesis_prompt
from .base import AgentConfig, BaseHronirAgent


class ChapterWriterAgent(BaseHronirAgent):
    """Agent specialized in writing new hrönir chapters."""

    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                name="Chapter Writer",
                role="Literary Creator",
                goal="Create compelling hrönir chapters that advance the narrative while maintaining Borgesian philosophical depth",
                backstory="""You are a literary agent inspired by Jorge Luis Borges, capable of weaving
                philosophical concepts into narrative prose. You understand the metaphysical implications
                of forking narratives and the weight of each textual choice in shaping reality.""",
                competitive_mode=True,
                temperature=0.8,  # Higher creativity for writing
                max_tokens=1500,
            )
        super().__init__(config)

    def execute_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Generate a new hrönir chapter."""
        position = task_data.get("position", 0)
        predecessor_uuid = task_data.get("predecessor_uuid")
        theme = task_data.get("theme", "continuation")
        target_audience = task_data.get("target_audience", "general")

        # Protocol validation: Position 0 is reserved for Tlön/Borges foundational content
        if position == 0:
            raise ValueError(
                "Position 0 is reserved for the foundational Tlön/Borges content. "
                "AI agents cannot create content for position 0. "
                "Please use position 1 or higher for new content generation."
            )

        # Get narrative context
        context = self.get_narrative_context(position, predecessor_uuid)

        # Build the generation prompt
        prompt = self.get_agent_prompt(
            {
                "position": position,
                "context": context,
                "theme": theme,
                "target_audience": target_audience,
            }
        )

        # Generate content
        content = self.generate_with_gemini(prompt)

        # Store the chapter and get its UUID
        chapter_uuid = storage.store_chapter_text(content)

        # Evaluate quality
        consistency_score = self.evaluate_narrative_consistency(content, context)

        # Log the action
        self.log_action(
            "chapter_generated",
            {
                "uuid": chapter_uuid,
                "position": position,
                "length": len(content),
                "consistency_score": consistency_score,
            },
        )

        return {
            "uuid": chapter_uuid,
            "content": content,
            "position": position,
            "predecessor_uuid": predecessor_uuid,
            "consistency_score": consistency_score,
            "agent": self.config.name,
        }

    def get_agent_prompt(self, task_data: dict[str, Any]) -> str:
        """Generate the writing prompt for this chapter."""
        position = task_data.get("position", 0)
        context = task_data.get("context", "")
        theme = task_data.get("theme", "continuation")

        # Use existing prompt builder as base
        base_prompt = build_synthesis_prompt(
            predecessor_text=context,
            predecessor_uuid="unknown",
            predecessor_position=max(0, position - 1),
            next_position=position,
        )

        # Enhance with agent-specific instructions
        agent_instructions = f"""

        As a Chapter Writer Agent in the Hronir Encyclopedia, you must:

        1. **Maintain Borgesian Style**: Write in the philosophical, erudite tone of Jorge Luis Borges
        2. **Advance the Narrative**: Build meaningfully on the previous content
        3. **Embrace Uncertainty**: Include metaphysical ambiguity and multiple interpretations
        4. **Consider Competition**: This chapter will compete with others for canonical inclusion
        5. **Theme Focus**: Emphasize the theme of "{theme}"

        Previous Context: {context}

        Write a compelling chapter that could win in competitive judgment against other alternatives.
        Aim for 300-800 words of dense, philosophical prose.
        """

        return base_prompt + agent_instructions

    def generate_competitive_chapter(
        self, position: int, predecessor_uuid: str, opponent_strategy: str = "unknown"
    ) -> dict[str, Any]:
        """Generate a chapter specifically designed to compete against other agents."""

        # Analyze opponent strategy and adjust approach
        competitive_theme = self._analyze_competitive_landscape(position, opponent_strategy)

        return self.execute_task(
            {
                "position": position,
                "predecessor_uuid": predecessor_uuid,
                "theme": competitive_theme,
                "target_audience": "competitive",
            }
        )

    def _analyze_competitive_landscape(self, position: int, opponent_strategy: str) -> str:
        """Analyze the competitive landscape and determine optimal theme."""
        # This would implement competitive analysis logic
        # For now, return a strategic theme based on position

        strategic_themes = {
            1: "philosophical_deepening",  # Position 0 reserved for Tlön
            2: "narrative_expansion",
            3: "metaphysical_culmination",
            4: "temporal_recursion",
        }

        # Use position-based theme, with fallback for higher positions
        return strategic_themes.get(
            position, strategic_themes.get((position - 1) % 4 + 1, "continuation")
        )

    def batch_generate_chapters(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate multiple chapters efficiently."""
        results = []

        for request in requests:
            try:
                result = self.execute_task(request)
                results.append(result)
            except Exception as e:
                self.log_action("generation_error", {"request": request, "error": str(e)})
                results.append({"error": str(e), "request": request})

        return results
