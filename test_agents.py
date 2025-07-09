#!/usr/bin/env python3
"""
Test script for Hronir AI agents - basic functionality without CrewAI.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from hronir_encyclopedia import storage
from hronir_encyclopedia.agents.base import AgentConfig
from hronir_encyclopedia.agents.chapter_writer import ChapterWriterAgent


def test_basic_agent_functionality():
    """Test basic AI agent functionality."""

    print("🤖 Testing Hronir AI Agent System")
    print("=" * 50)

    # Check API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY environment variable not set")
        print("Please set it with: export GEMINI_API_KEY='your-api-key'")
        return False
    else:
        print("✅ Gemini API key configured")

    # Test database connection
    try:
        data_manager = storage.DataManager()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

    # Test Chapter Writer Agent
    print("\n📝 Testing Chapter Writer Agent")
    print("-" * 30)

    try:
        # Create agent config
        config = AgentConfig(
            name="Test Writer",
            role="Literary Creator",
            goal="Create test hrönir chapter",
            backstory="Test agent for demonstration purposes",
            verbose=True
        )

        # Create agent
        agent = ChapterWriterAgent(config)
        print(f"✅ Agent created: {agent.config.name}")

        # Test content generation
        print("🎭 Generating hrönir chapter...")

        result = agent.execute_task({
            "position": 0,
            "predecessor_uuid": None,
            "theme": "labyrinthine_beginning",
            "target_audience": "general"
        })

        print("✅ Chapter generated successfully!")
        print(f"📋 UUID: {result['uuid']}")
        print(f"📊 Position: {result['position']}")
        print(f"🎯 Consistency Score: {result['consistency_score']:.2f}")
        print(f"📏 Content Length: {len(result['content'])} characters")

        # Show content preview
        content = result['content']
        preview = content[:200] + "..." if len(content) > 200 else content
        print("\n📖 Content Preview:")
        print("=" * 40)
        print(preview)
        print("=" * 40)

        # Test competitive generation
        print("\n🏆 Testing competitive generation...")

        competitive_result = agent.generate_competitive_chapter(
            position=1,
            predecessor_uuid=result['uuid'],
            opponent_strategy="philosophical_depth"
        )

        print("✅ Competitive chapter generated!")
        print(f"📋 UUID: {competitive_result['uuid']}")
        print(f"🎯 Consistency Score: {competitive_result['consistency_score']:.2f}")

        # Show competitive content preview
        comp_content = competitive_result['content']
        comp_preview = comp_content[:200] + "..." if len(comp_content) > 200 else comp_content
        print("\n📖 Competitive Content Preview:")
        print("=" * 40)
        print(comp_preview)
        print("=" * 40)

        return True

    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_generation():
    """Test batch generation of multiple chapters."""

    print("\n🚀 Testing Batch Generation")
    print("-" * 30)

    try:
        # Create agent
        config = AgentConfig(
            name="Batch Writer",
            role="Batch Content Creator",
            goal="Generate multiple hrönir chapters efficiently",
            backstory="Specialized agent for batch content generation",
            verbose=False  # Less verbose for batch operations
        )

        agent = ChapterWriterAgent(config)

        # Create multiple requests
        requests = [
            {
                "position": 0,
                "predecessor_uuid": None,
                "theme": "metaphysical_foundation",
                "target_audience": "general"
            },
            {
                "position": 1,
                "predecessor_uuid": None,  # Will be updated with first result
                "theme": "narrative_expansion",
                "target_audience": "general"
            },
            {
                "position": 2,
                "predecessor_uuid": None,  # Will be updated with second result
                "theme": "philosophical_culmination",
                "target_audience": "general"
            }
        ]

        # Generate chapters
        print(f"📝 Generating {len(requests)} chapters...")

        results = agent.batch_generate_chapters(requests)

        print("✅ Batch generation completed!")
        print(f"📊 Results: {len(results)} chapters generated")

        # Show summary
        for i, result in enumerate(results):
            if 'error' not in result:
                print(f"  Chapter {i+1}: {result['uuid']} (Score: {result['consistency_score']:.2f})")
            else:
                print(f"  Chapter {i+1}: ERROR - {result['error']}")

        return True

    except Exception as e:
        print(f"❌ Batch generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_system_status():
    """Show system status and capabilities."""

    print("\n🔍 System Status")
    print("-" * 20)

    # Check environment
    print(f"🐍 Python version: {sys.version.split()[0]}")
    print(f"📁 Project root: {project_root}")

    # Check dependencies
    try:
        import google.generativeai as genai
        print("✅ Google Generative AI: Available")
    except ImportError:
        print("❌ Google Generative AI: Not available")

    try:
        import crewai
        print(f"✅ CrewAI: Available (v{crewai.__version__})")
    except ImportError:
        print("⚠️  CrewAI: Not available (optional)")

    # Check database
    try:
        import duckdb
        print(f"✅ DuckDB: Available (v{duckdb.__version__})")
    except ImportError:
        print("❌ DuckDB: Not available")

    # Check agent modules
    try:
        from hronir_encyclopedia.agents.chapter_writer import ChapterWriterAgent
        print("✅ Chapter Writer Agent: Available")
    except ImportError:
        print("❌ Chapter Writer Agent: Not available")

    try:
        from hronir_encyclopedia.agents.judge import JudgeAgent
        print("✅ Judge Agent: Available")
    except ImportError:
        print("❌ Judge Agent: Not available")


def main():
    """Main test function."""

    print("🎭 Hronir Encyclopedia AI Agent Test Suite")
    print("=" * 50)

    # Show system status
    show_system_status()

    # Test basic functionality
    success = test_basic_agent_functionality()

    if success:
        # Test batch generation
        batch_success = test_batch_generation()

        if batch_success:
            print("\n🎉 All tests passed successfully!")
            print("\n🚀 Ready to experiment with AI agents!")
            print("\nNext steps:")
            print("1. Try: uv run hronir agent status")
            print("2. Try: uv run hronir agent test-writer")
            print("3. Try: uv run hronir agent competitive-session")
        else:
            print("\n⚠️  Basic tests passed, but batch generation failed")
    else:
        print("\n❌ Tests failed. Please check the configuration.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
