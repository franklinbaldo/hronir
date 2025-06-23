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

### Core Development Commands
```bash
# Run tests
uv run pytest

# Lint code
uv run ruff check .

# Format code
uv run black .

# Run specific test
uv run pytest tests/test_specific_file.py

# Clean invalid entries
uv run hronir clean --git
```

### CLI Usage
```bash
# Main CLI entry point
uv run hronir

# Store a new chapter (creates fork)
uv run hronir store drafts/chapter.md --prev <uuid_of_previous>

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

### Core System Flow
The system follows a Protocol v2 architecture with these key phases:
1. **Fork Creation**: Agents create new narrative variants (hrönirs) via `store` command
2. **Qualification**: Forks earn `QUALIFIED` status through duel performance 
3. **Judgment Sessions**: Qualified forks grant mandate to judge prior history
4. **Temporal Cascade**: Session commits trigger canonical path recalculation

### Key Components

#### `hronir_encyclopedia/` Package
- **`cli.py`**: Main CLI interface with Typer commands for all user interactions
- **`storage.py`**: Core data persistence, UUID management, and file validation
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

- The system uses CSV files as primary storage with optional SQLAlchemy backend
- All UUIDs are deterministic and content-addressed
- The canonical path is emergent, not predetermined
- Session commits are atomic and trigger cascading updates
- Fork qualification uses Elo ratings with configurable thresholds