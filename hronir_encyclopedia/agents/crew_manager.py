"""
CrewAI Integration for Hronir Encyclopedia

Manages crews of AI agents for collaborative hrönir generation and judgment.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

try:
    from crewai import Agent, Crew, Process, Task
    from crewai.llm import LLM
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # Fallback classes for when CrewAI is not available
    class Agent:
        pass
    class Task:
        pass
    class Crew:
        pass
    class Process:
        pass
    class LLM:
        pass

from .. import storage


@dataclass
class CrewConfig:
    """Configuration for a Hronir crew."""
    name: str
    agents: list[str]  # Agent types to include
    process: str = "sequential"  # or "hierarchical"
    verbose: bool = False
    max_execution_time: int = 300  # seconds


class HronirCrew:
    """Manages a crew of AI agents for collaborative Hronir tasks."""

    def __init__(self, config: CrewConfig):
        if not CREWAI_AVAILABLE:
            raise ImportError("CrewAI is not installed. Install with: pip install crewai")

        self.config = config
        self.agents = {}
        self.crew = None
        self.data_manager = storage.DataManager()

        # Initialize agents
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize the specified agents."""
        for agent_type in self.config.agents:
            if agent_type == "chapter_writer":
                self.agents[agent_type] = self._create_chapter_writer_crew_agent()
            elif agent_type == "judge":
                self.agents[agent_type] = self._create_judge_crew_agent()
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")

    def _create_gemini_llm(self) -> LLM:
        """Create a Gemini LLM instance for CrewAI."""
        return LLM(
            model="gemini/gemini-2.0-flash-experimental",
            api_key="GEMINI_API_KEY"  # Will be read from environment
        )

    def _create_chapter_writer_crew_agent(self) -> Agent:
        """Create a CrewAI agent for chapter writing."""
        return Agent(
            role="Chapter Writer",
            goal="Create compelling hrönir chapters that advance the narrative while maintaining Borgesian philosophical depth",
            backstory="""You are a literary agent inspired by Jorge Luis Borges, capable of weaving
            philosophical concepts into narrative prose. You understand the metaphysical implications
            of forking narratives and the weight of each textual choice in shaping reality.""",
            verbose=self.config.verbose,
            llm=self._create_gemini_llm(),
            allow_delegation=False,
            max_iter=3
        )

    def _create_judge_crew_agent(self) -> Agent:
        """Create a CrewAI agent for judgment tasks."""
        return Agent(
            role="Literary Judge",
            goal="Evaluate hrönir chapters fairly and vote for the most compelling narratives",
            backstory="""You are a discerning literary critic with deep appreciation for Borgesian
            philosophy. You evaluate texts not just for their prose quality, but for their
            metaphysical depth, narrative coherence, and contribution to the greater literary labyrinth.""",
            verbose=self.config.verbose,
            llm=self._create_gemini_llm(),
            allow_delegation=False,
            max_iter=2
        )

    def create_writing_crew(self, task_data: dict[str, Any]) -> Crew:
        """Create a crew for collaborative writing tasks."""
        if "chapter_writer" not in self.agents:
            raise ValueError("Chapter writer agent not available")

        # Create writing task
        writing_task = Task(
            description=f"""
            Write a new hrönir chapter for position {task_data.get('position', 0)}.

            Context: {task_data.get('context', 'No previous context')}
            Theme: {task_data.get('theme', 'continuation')}

            Requirements:
            - Maintain Borgesian philosophical style
            - Build meaningfully on previous content
            - Include metaphysical ambiguity
            - Aim for 300-800 words
            - Consider competitive aspects
            """,
            expected_output="A complete hrönir chapter in Markdown format",
            agent=self.agents["chapter_writer"]
        )

        return Crew(
            agents=[self.agents["chapter_writer"]],
            tasks=[writing_task],
            process=Process.sequential,
            verbose=self.config.verbose
        )

    def create_judgment_crew(self, task_data: dict[str, Any]) -> Crew:
        """Create a crew for judgment tasks."""
        if "judge" not in self.agents:
            raise ValueError("Judge agent not available")

        # Create judgment task
        judgment_task = Task(
            description=f"""
            Evaluate two competing hrönir chapters and determine the winner.

            Position: {task_data.get('position', 0)}
            Context: {task_data.get('context', 'No previous context')}

            Chapter A: {task_data.get('content_a', 'Content A')}
            Chapter B: {task_data.get('content_b', 'Content B')}

            Evaluate based on:
            1. Borgesian style and philosophical depth
            2. Narrative coherence and progression
            3. Literary merit and prose quality
            4. Competitive strength
            5. Thematic resonance

            Provide your judgment in this format:
            WINNER: [A or B]
            CONFIDENCE: [0.0-1.0]
            REASONING: [Detailed explanation]
            """,
            expected_output="A structured judgment with winner, confidence, and reasoning",
            agent=self.agents["judge"]
        )

        return Crew(
            agents=[self.agents["judge"]],
            tasks=[judgment_task],
            process=Process.sequential,
            verbose=self.config.verbose
        )

    async def execute_writing_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a collaborative writing task."""
        crew = self.create_writing_crew(task_data)

        try:
            result = crew.kickoff()

            # Store the generated content
            content = result if isinstance(result, str) else str(result)
            chapter_uuid = storage.store_chapter_text(content)

            return {
                "uuid": chapter_uuid,
                "content": content,
                "position": task_data.get("position", 0),
                "crew": self.config.name,
                "success": True
            }

        except Exception as e:
            return {
                "error": str(e),
                "crew": self.config.name,
                "success": False
            }

    async def execute_judgment_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a judgment task."""
        crew = self.create_judgment_crew(task_data)

        try:
            result = crew.kickoff()

            # Parse the judgment result
            judgment = self._parse_crew_judgment(str(result))

            return {
                "judgment": judgment,
                "crew": self.config.name,
                "success": True
            }

        except Exception as e:
            return {
                "error": str(e),
                "crew": self.config.name,
                "success": False
            }

    def _parse_crew_judgment(self, result: str) -> dict[str, Any]:
        """Parse judgment result from CrewAI output."""
        lines = result.strip().split('\n')

        winner = None
        confidence = 0.5
        reasoning = ""

        for line in lines:
            line = line.strip()
            if line.startswith("WINNER:"):
                winner = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    confidence = 0.5
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()

        return {
            "winner": winner,
            "confidence": confidence,
            "reasoning": reasoning
        }

    async def run_competitive_writing_session(self, position: int,
                                            predecessor_uuid: str | None = None,
                                            num_chapters: int = 3) -> list[dict[str, Any]]:
        """Run a competitive writing session with multiple chapters."""

        # Get context
        context = ""
        if predecessor_uuid:
            hrönir_data = self.data_manager.get_hrönir_by_uuid(predecessor_uuid)
            if hrönir_data:
                context = hrönir_data.text_content[:500]

        # Generate multiple chapters
        tasks = []
        for i in range(num_chapters):
            task_data = {
                "position": position,
                "predecessor_uuid": predecessor_uuid,
                "context": context,
                "theme": f"variation_{i+1}",
                "iteration": i+1
            }
            tasks.append(self.execute_writing_task(task_data))

        # Execute all tasks
        results = await asyncio.gather(*tasks)

        return results

    def get_crew_statistics(self) -> dict[str, Any]:
        """Get statistics about crew performance."""
        return {
            "name": self.config.name,
            "agents": list(self.agents.keys()),
            "tasks_completed": 0,  # Would track actual statistics
            "success_rate": 0.0,
            "avg_execution_time": 0.0
        }
