"""
Hronir Encyclopedia AI Agent System

A CrewAI-based multi-agent system for autonomous content generation and competitive gameplay
within the Hronir Encyclopedia literary protocol.
"""

from .base import BaseHronirAgent
from .chapter_writer import ChapterWriterAgent
from .judge import JudgeAgent

__all__ = [
    "BaseHronirAgent",
    "ChapterWriterAgent",
    "JudgeAgent",
]

# Optional imports that may not be available
try:
    from .crew_manager import HronirCrew
    __all__.append("HronirCrew")
except ImportError:
    pass
