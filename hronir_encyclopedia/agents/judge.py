"""
Judge Agent for Hronir Encyclopedia

Specialized agent for evaluating and voting on hrönir chapters during judgment sessions.
"""

from typing import Any

from .. import ratings
from ..models import SessionDuel
from .base import AgentConfig, BaseHronirAgent


class JudgeAgent(BaseHronirAgent):
    """Agent specialized in judging hrönir chapters and participating in sessions."""

    def __init__(self, config: AgentConfig | None = None):
        if config is None:
            config = AgentConfig(
                name="Judge",
                role="Literary Critic",
                goal="Evaluate hrönir chapters fairly and vote for the most compelling narratives",
                backstory="""You are a discerning literary critic with deep appreciation for Borgesian 
                philosophy. You evaluate texts not just for their prose quality, but for their 
                metaphysical depth, narrative coherence, and contribution to the greater literary labyrinth.""",
                competitive_mode=True,
                temperature=0.3,  # Lower temperature for more consistent judgments
                max_tokens=1000
            )
        super().__init__(config)

    def execute_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a judgment task."""
        session_id = task_data.get("session_id")
        position = task_data.get("position")

        if not session_id:
            raise ValueError("session_id required for judgment task")

        # Get session data
        session = self._get_session_data(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Get duel for this position
        duel = session.dossier.duels.get(str(position))
        if not duel:
            raise ValueError(f"No duel found for position {position}")

        # Evaluate both options
        judgment = self._evaluate_duel(duel, position)

        # Record the vote
        vote_uuid = self._record_vote(position, judgment)

        self.log_action("judgment_made", {
            "session_id": session_id,
            "position": position,
            "winner": judgment["winner"],
            "confidence": judgment["confidence"],
            "vote_uuid": vote_uuid
        })

        return {
            "session_id": session_id,
            "position": position,
            "judgment": judgment,
            "vote_uuid": vote_uuid,
            "agent": self.config.name
        }

    def get_agent_prompt(self, task_data: dict[str, Any]) -> str:
        """Generate the judgment prompt."""
        content_a = task_data.get("content_a", "")
        content_b = task_data.get("content_b", "")
        position = task_data.get("position", 0)
        context = task_data.get("context", "")

        prompt = f"""
        As a Judge Agent in the Hronir Encyclopedia, you must evaluate two competing hrönir chapters 
        and determine which better serves the greater narrative.

        Position: {position}
        Previous Context: {context}

        CHAPTER A:
        {content_a}

        CHAPTER B:
        {content_b}

        Evaluate based on:
        1. **Borgesian Style**: Philosophical depth, erudite tone, metaphysical themes
        2. **Narrative Coherence**: How well it builds on previous content
        3. **Literary Merit**: Prose quality, imagery, intellectual sophistication
        4. **Competitive Strength**: Ability to advance the canonical narrative
        5. **Thematic Resonance**: Connection to broader Borgesian concepts

        Provide your judgment in this format:
        WINNER: [A or B]
        CONFIDENCE: [0.0-1.0]
        REASONING: [Detailed explanation of your choice]
        """

        return prompt

    def _evaluate_duel(self, duel: SessionDuel, position: int) -> dict[str, Any]:
        """Evaluate a duel between two hrönir chapters."""

        # Get the content for both paths
        content_a = self._get_hrönir_content(duel.path_A_uuid)
        content_b = self._get_hrönir_content(duel.path_B_uuid)

        if not content_a or not content_b:
            raise ValueError("Could not retrieve content for duel evaluation")

        # Get context for this position
        context = self.get_narrative_context(position)

        # Generate judgment prompt
        prompt = self.get_agent_prompt({
            "content_a": content_a,
            "content_b": content_b,
            "position": position,
            "context": context
        })

        # Get AI judgment
        judgment_text = self.generate_with_gemini(prompt)

        # Parse the judgment
        judgment = self._parse_judgment(judgment_text, duel)

        return judgment

    def _parse_judgment(self, judgment_text: str, duel: SessionDuel) -> dict[str, Any]:
        """Parse the AI judgment response."""
        lines = judgment_text.strip().split('\n')

        winner = None
        confidence = 0.5
        reasoning = ""

        for line in lines:
            line = line.strip()
            if line.startswith("WINNER:"):
                winner_char = line.split(":", 1)[1].strip().upper()
                winner = duel.path_A_uuid if winner_char == "A" else duel.path_B_uuid
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    confidence = 0.5
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()

        # Default to path A if parsing fails
        if winner is None:
            winner = duel.path_A_uuid

        return {
            "winner": winner,
            "loser": duel.path_B_uuid if winner == duel.path_A_uuid else duel.path_A_uuid,
            "confidence": confidence,
            "reasoning": reasoning,
            "duel_entropy": duel.entropy
        }

    def _get_hrönir_content(self, uuid: str) -> str | None:
        """Get hrönir content by UUID."""
        hrönir_data = self.data_manager.get_hrönir_by_uuid(uuid)
        return hrönir_data.text_content if hrönir_data else None

    def _get_session_data(self, session_id: str):
        """Get session data from storage."""
        # This would integrate with the existing session manager
        # For now, return a placeholder
        return None

    def _record_vote(self, position: int, judgment: dict[str, Any]) -> str:
        """Record the vote in the ratings system."""
        winner = judgment["winner"]
        loser = judgment["loser"]
        voter_id = f"agent_{self.config.name}"

        # Use existing ratings system
        ratings.record_vote(position, voter_id, winner, loser)

        # Return a mock vote UUID for now
        return f"vote_{position}_{winner[:8]}"

    def batch_judge_sessions(self, session_ids: list[str]) -> list[dict[str, Any]]:
        """Judge multiple sessions efficiently."""
        results = []

        for session_id in session_ids:
            try:
                # Get all positions for this session
                session_data = self._get_session_data(session_id)
                if not session_data:
                    continue

                for position_str in session_data.dossier.duels.keys():
                    result = self.execute_task({
                        "session_id": session_id,
                        "position": int(position_str)
                    })
                    results.append(result)

            except Exception as e:
                self.log_action("judgment_error", {
                    "session_id": session_id,
                    "error": str(e)
                })
                results.append({
                    "error": str(e),
                    "session_id": session_id
                })

        return results

    def get_judgment_statistics(self) -> dict[str, Any]:
        """Get statistics about this judge's voting patterns."""
        # This would analyze voting history
        return {
            "total_votes": 0,
            "avg_confidence": 0.0,
            "decision_patterns": {}
        }
