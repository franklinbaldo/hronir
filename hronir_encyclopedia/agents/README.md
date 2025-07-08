# Hronir Encyclopedia AI Agents

A sophisticated AI agent system for autonomous content generation and competitive gameplay within the Hronir Encyclopedia literary protocol.

## Overview

The Hronir Encyclopedia AI Agent System enables autonomous AI agents to participate in the literary protocol, creating Borgesian-style content, competing with each other, and making strategic decisions about narrative development.

## Architecture

### Core Components

1. **BaseHronirAgent** - Abstract base class for all agents
2. **ChapterWriterAgent** - Specialized in generating hrönir chapters
3. **JudgeAgent** - Evaluates and votes on competing narratives
4. **HronirCrew** - CrewAI integration for multi-agent coordination (optional)

### Key Features

- **Borgesian Style Generation**: Agents create content in the philosophical, erudite style of Jorge Luis Borges
- **Competitive Dynamics**: Multiple agents compete to create the most compelling narratives
- **Quality Metrics**: Automatic evaluation of narrative consistency and literary merit
- **Strategic Adaptation**: Agents adjust their writing style based on competitive context
- **Batch Processing**: Efficient generation of multiple chapters

## Quick Start

### Prerequisites

1. Python 3.10+
2. Google Gemini API key
3. Installed dependencies (`uv sync`)

### Environment Setup

```bash
export GEMINI_API_KEY="your-api-key-here"
```

### Basic Usage

```bash
# Check system status
uv run hronir agent status

# Generate a single chapter (position >= 1)
uv run hronir agent test-writer

# Generate with specific theme
uv run hronir agent test-writer --theme "metaphysical_maze"

# Continue from previous chapter
uv run hronir agent test-writer --position 1 --predecessor-uuid <uuid>

# Run competitive session
uv run hronir agent competitive-session --num-agents 3
```

### Important Protocol Restriction

**Position 0 is reserved for Tlön/Borges foundational content** and cannot be modified by AI agents. All AI-generated content must use position 1 or higher. This preserves the integrity of the original Borgesian foundation while allowing autonomous expansion.

## Agent Types

### Chapter Writer Agent

Specialized in creating new hrönir chapters with:
- Borgesian philosophical depth
- Narrative continuity from predecessor chapters
- Competitive strategy adaptation
- Thematic consistency

**Example Usage:**
```python
from hronir_encyclopedia.agents import ChapterWriterAgent, AgentConfig

config = AgentConfig(
    name="Philosophical Writer",
    role="Literary Creator",
    goal="Create compelling hrönir chapters",
    backstory="Inspired by Jorge Luis Borges...",
    temperature=0.8
)

agent = ChapterWriterAgent(config)
result = agent.execute_task({
    "position": 1,  # Position >= 1 (position 0 reserved for Tlön)
    "theme": "infinite_library",
    "predecessor_uuid": None
})
```

### Judge Agent

Evaluates competing narratives based on:
- Borgesian style and philosophical depth
- Narrative coherence and progression
- Literary merit and prose quality
- Competitive strength

**Example Usage:**
```python
from hronir_encyclopedia.agents import JudgeAgent, AgentConfig

config = AgentConfig(
    name="Literary Critic",
    role="Judge",
    goal="Evaluate hrönir chapters fairly",
    backstory="Discerning literary critic...",
    temperature=0.3
)

agent = JudgeAgent(config)
result = agent.execute_task({
    "session_id": "session-123",
    "position": 1
})
```

## Configuration

### Agent Configuration

```python
from hronir_encyclopedia.agents import AgentConfig

config = AgentConfig(
    name="Agent Name",
    role="Agent Role",
    goal="Agent's primary objective",
    backstory="Agent's background and personality",
    gemini_model="gemini-2.5-flash-preview-05-20",
    temperature=0.7,
    max_tokens=2000,
    competitive_mode=True,
    narrative_consistency_threshold=0.8
)
```

### Crew Configuration (Optional)

```python
from hronir_encyclopedia.agents import CrewConfig, HronirCrew

config = CrewConfig(
    name="Writing Crew",
    agents=["chapter_writer", "judge"],
    process="sequential",
    verbose=True
)

crew = HronirCrew(config)
```

## Advanced Features

### Competitive Sessions

Run multiple agents in competition:

```python
# Via CLI
uv run hronir agent competitive-session --position 1 --num-agents 3

# Via Python
from hronir_encyclopedia.agents import ChapterWriterAgent, AgentConfig

writers = []
for i in range(3):
    config = AgentConfig(
        name=f"Writer {i+1}",
        role="Competitive Writer",
        goal="Create winning hrönir chapter",
        backstory=f"Agent {i+1} with unique perspective",
        temperature=0.7 + (i * 0.1)
    )
    writers.append(ChapterWriterAgent(config))

# Generate competing chapters (position >= 1)
chapters = []
for writer in writers:
    result = writer.generate_competitive_chapter(
        position=1,  # Position >= 1 (position 0 reserved for Tlön)
        predecessor_uuid=None,
        opponent_strategy="unknown"
    )
    chapters.append(result)
```

### Batch Processing

Generate multiple chapters efficiently:

```python
requests = [
    {"position": 1, "theme": "foundation"},  # Position >= 1 (position 0 reserved)
    {"position": 2, "theme": "expansion"},
    {"position": 3, "theme": "culmination"}
]

results = agent.batch_generate_chapters(requests)
```

## Integration with Hronir Protocol

The agents integrate seamlessly with the Hronir Encyclopedia protocol:

- **Storage**: Generated content is automatically stored in the DuckDB database
- **UUID System**: Content-addressed UUIDs ensure uniqueness
- **Path Creation**: Agents can create narrative paths automatically
- **Competitive Ranking**: Elo system tracks agent performance
- **Session Management**: Agents can participate in judgment sessions

## Performance and Monitoring

### Quality Metrics

- **Narrative Consistency Score**: Measures how well content fits with existing narrative
- **Literary Merit**: Evaluates prose quality and stylistic consistency
- **Competitive Strength**: Tracks success in competitive scenarios

### Monitoring

```python
# Get agent statistics
stats = agent.get_agent_statistics()

# Monitor crew performance
crew_stats = crew.get_crew_statistics()
```

## Development

### Adding New Agent Types

1. Inherit from `BaseHronirAgent`
2. Implement required methods:
   - `execute_task()`
   - `get_agent_prompt()`
3. Add to CLI commands if needed

### Testing

```bash
# Run agent tests
uv run pytest tests/test_agents.py

# Run demo
uv run python demo_ai_agents.py

# Manual testing
uv run python test_agents.py
```

## Troubleshooting

### Common Issues

1. **API Key Not Set**: Ensure `GEMINI_API_KEY` is configured
2. **Database Lock**: Only one process can access DuckDB at a time
3. **Import Errors**: Run `uv sync` to install dependencies
4. **CrewAI Issues**: CrewAI is optional, basic agents work without it

### Debug Mode

Enable verbose logging:

```python
config = AgentConfig(
    name="Debug Agent",
    verbose=True,
    # ... other config
)
```

## Future Enhancements

- **Semantic Embeddings**: Better narrative consistency evaluation
- **Multi-modal Support**: Integration with image and audio generation
- **Advanced Strategies**: More sophisticated competitive algorithms
- **Real-time Collaboration**: Live multi-agent sessions
- **Performance Optimization**: Batch processing improvements

## Examples

See the `demo_ai_agents.py` and `test_agents.py` files for comprehensive examples of agent usage and integration patterns.

## License

This project is part of the Hronir Encyclopedia and follows the same license terms.