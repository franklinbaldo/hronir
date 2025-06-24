# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Hrönir Encyclopedia is a Python-based literary protocol inspired by Jorge Luis Borges. It's an adversarial environment where AI and human agents compete to influence an evolving narrative through game theory, blockchain-like ledger, and narrative proof-of-work.

## Development Commands

### Environment Setup
```bash
# Install dependencies with uv
uv sync --all-features

# Set up pre-commit hooks
uv run pre-commit install

# If pre-commit issues occur, use the fix script
bash scripts/fix_hooks.sh
```

### ⚠️ Important: Always Use `uv run`

**CRITICAL**: Always prefix Python commands with `uv run` to ensure you're using the properly configured virtual environment:

```bash
# ✅ Correct - uses project virtual environment
uv run python script.py
uv run pytest
uv run hronir store chapter.md

# ❌ Wrong - may use system Python or wrong environment  
python script.py
pytest
hronir store chapter.md
```

This ensures:
- Correct Python version and dependencies
- Project-specific package versions
- Proper module resolution
- Consistent environment across all operations

### Core Development Commands
```bash
# Run tests
uv run pytest

# Lint code (check for issues)
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run black .

# Run specific test
uv run pytest tests/test_specific_file.py

# Clean invalid entries
uv run hronir clean --git

# Generate AI-friendly codebase summary
uv run repomix .
```

### Repomix Integration

The project uses repomix to generate AI-friendly codebase summaries:

```bash
# Generate codebase summary (outputs to dist/hronir-codebase.md)
uv run repomix .

# Configuration in repomix.config.json
# - Ignores: uv.lock, the_library/, test_temp/, dist/
# - Output: dist/hronir-codebase.md with header and stats
# - Runs automatically in pre-commit hooks
```

### ⚠️ Code Quality Requirements

**MANDATORY**: Before committing any changes, ensure code quality is maintained:

```bash
# 1. Always run linting and formatting before committing
uv run ruff check .        # Must pass with 0 issues
uv run black .             # Auto-format all code

# 2. Run tests to ensure functionality
uv run pytest             # All tests must pass

# 3. Only commit if everything passes
# DO NOT commit code with linting issues or failing tests
```

**Code Quality Standards:**
- **Zero tolerance** for linting issues - all `ruff check` errors must be fixed
- Code must be formatted with `black` before committing
- All tests must pass before committing
- Use `uv run ruff check --fix .` to auto-fix common issues
- Manual fixes required for complex linting issues (unused variables, etc.)

### CLI Usage
```bash
# Main CLI entry point
uv run hronir

# Store a new chapter
uv run hronir store drafts/chapter.md
# Create the fork
uv run hronir fork --position N --source <uuid_of_previous> --target <new_uuid>

# Start judgment session
uv run hronir session start --fork-uuid <qualified_fork_uuid>

# Commit session verdicts
uv run hronir session commit --session-id <id> --verdicts '{"position": "winning_fork_uuid"}'

# View rankings
uv run hronir ranking <position>

# Get duel information
uv run hronir get-duel --position <position>

# Trigger manual canonical path recovery
uv run hronir recover-canon
```

## Architecture

### Hybrid Storage Architecture

**CRITICAL PRINCIPLE**: The system uses a hybrid approach for transparency and performance:

- **Runtime**: SQLAlchemy ORM + NetworkX for fast queries and graph analysis
- **Persistence**: CSV files as canonical storage for git transparency
- **In-Memory SQLite**: Temporary database loaded from CSV on startup
- **Validation**: Pydantic models ensure data integrity throughout

**Why this approach:**
- CSV files remain human-readable and git-friendly
- ORM provides transactional safety during runtime
- NetworkX enables narrative consistency validation
- No persistent database files in repository

### Core System Flow
The system follows a Protocol v2 architecture with these key phases:
1. **Fork Creation**: Agents store new chapters and then register forks using the `fork` command
2. **Qualification**: Forks earn `QUALIFIED` status through duel performance 
3. **Judgment Sessions**: Qualified forks grant mandate to judge prior history
4. **Temporal Cascade**: Session commits trigger canonical path recalculation

### Key Components

#### `hronir_encyclopedia/` Package
- **`cli.py`**: Main CLI interface with Typer commands for all user interactions
- **`storage.py`**: Core data persistence, UUID management, and file validation
- **`models.py`**: Pydantic models and SQLAlchemy ORM definitions
- **`graph_logic.py`**: NetworkX-based narrative consistency validation
- **`session_manager.py`**: Manages judgment sessions and dossier generation
- **`transaction_manager.py`**: Immutable ledger for session commits and fork promotions
- **`ratings.py`**: Elo ranking system and duel determination logic
- **`gemini_util.py`**: AI generation utilities using Google Gemini
- **`database.py`**: SQLAlchemy database utilities (secondary to CSV storage)

#### Data Structure
```
the_library/           # Hrönirs (chapters) stored by UUID
data/
├── canonical_path.json    # Current canonical narrative path
├── sessions/             # Active/completed judgment sessions
└── transactions/         # Immutable ledger of all commits
forking_path/            # Fork definitions (CSV files)
ratings/                 # Vote records and Elo calculations (CSV files)
```

### Key Protocol Concepts

#### Fork Status Lifecycle
- `PENDING` → `QUALIFIED` → `SPENT`
- Only `QUALIFIED` forks can initiate judgment sessions
- Qualification requires strong duel performance (Elo-based)

#### Session Workflow
1. Agent creates hrönir → receives `fork_uuid`
2. Fork becomes `QUALIFIED` through competitive performance
3. Agent uses qualified fork to start session → receives dossier of maximum entropy duels
4. Agent submits verdicts → triggers transaction recording and temporal cascade

#### Temporal Cascade
- Recalculates canonical path from oldest voted position forward
- Ensures narrative consistency after judgment sessions
- Updates `data/canonical_path.json`

### UUID System
- All content uses deterministic UUIDv5 generation
- Fork UUIDs: `uuid5(position:prev_uuid:current_uuid)`
- Content UUIDs: `uuid5(text_content)`
- Mandate IDs: `blake3(fork_uuid + previous_transaction_hash)[:16]`

### Testing Strategy
Tests focus on protocol dynamics:
- `test_storage_and_votes.py`: Core storage and voting mechanics
- `test_sessions_and_cascade.py`: Session management and temporal cascade
- `test_protocol_v2.py`: End-to-end protocol validation
- `test_system_dynamics.py`: Game theory and agent interactions

### File Validation
- `audit` command validates all stored content integrity
- `clean` command removes invalid entries (use `--git` to stage deletions)
- Pre-commit hooks automatically run validation

## Development Notes

### Data Persistence Guidelines

**CRITICAL**: Always maintain CSV-first approach for repository transparency:

- **Read**: Load CSV data into in-memory SQLite on startup
- **Process**: Use ORM models and NetworkX for runtime operations  
- **Write**: Save all changes back to CSV files before exit
- **Validate**: Use NetworkX to check narrative consistency
- **Never commit**: Database files (.db, .sqlite) to repository

### Core Principles

- The system uses CSV files as canonical storage with SQLAlchemy for runtime performance
- All UUIDs are deterministic and content-addressed
- The canonical path is emergent, not predetermined
- Session commits are atomic and trigger cascading updates
- Fork qualification uses Elo ratings with configurable thresholds
- NetworkX ensures narrative graph remains acyclic (no time paradoxes)