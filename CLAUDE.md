# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Hrönir Encyclopedia is a Python-based literary protocol inspired by Jorge Luis Borges. It's an adversarial environment where AI and human agents compete to influence an evolving narrative through game theory, blockchain-like ledger, and narrative proof-of-work.

## Development Commands

### Environment Setup

```bash
# Install dependencies with uv
uv sync --all-extras
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
uv run ruff format .

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
```

### ⚠️ Code Quality Requirements

**MANDATORY**: Before committing any changes, ensure code quality is maintained:

```bash
# 1. Always run linting and formatting before committing
uv run ruff check .        # Must pass with 0 issues
uv run ruff format .       # Auto-format all code

# 2. Run tests to ensure functionality
uv run pytest             # All tests must pass

# 3. Only commit if everything passes
# DO NOT commit code with linting issues or failing tests
```

- **Zero tolerance** for linting issues - all `ruff check` errors must be fixed
- Code must be formatted with `ruff format` before committing
- All tests must pass before committing
- Use `uv run ruff check --fix .` to auto-fix common issues
- Manual fixes required for complex linting issues (unused variables, etc.)

### CLI Usage

```bash
# Main CLI entry point
uv run hronir

# Quick setup for experimentation
uv run hronir init-test

# Store a new chapter
uv run hronir store drafts/chapter.md
# Create the path
uv run hronir path --position N --source <uuid_of_previous> --target <new_uuid>

# Start judgment session
uv run hronir session start --path-uuid <qualified_path_uuid>

# Commit session verdicts
uv run hronir session commit --session-id <id> --verdicts '{"position": "winning_path_uuid"}'

# View rankings
uv run hronir ranking <position>

# List paths (optional --position to filter)
uv run hronir list-paths --position <position>

# Check status of a specific path
uv run hronir path-status <path_uuid>

# Show canonical path status
uv run hronir status
uv run hronir status --counts

# Get duel information
uv run hronir get-duel --position <position>

# Trigger manual canonical path recovery
uv run hronir recover-canon
```

## Architecture

### Storage Architecture

**CORE PRINCIPLE**: The system uses DuckDB as its primary data store, with Pydantic for data validation.

- **Persistence**: A DuckDB database file (e.g., `data/encyclopedia.duckdb`) serves as the canonical storage. This file is version-controlled in Git.
- **Runtime**: Data is queried from and written to DuckDB.
- **Validation**: Pydantic models ensure data integrity before persistence and after retrieval.
- **Graph Operations**: NetworkX can be used for narrative consistency validation on data retrieved from DuckDB.

**Why this approach:**

- DuckDB provides ACID compliance, efficient querying, and a robust SQL interface for data operations.
- Storing the database file in Git allows for versioning of the entire dataset state.
- Pydantic ensures type safety and validation.

### Core System Flow

The system follows a Protocol v2 architecture with these key phases:

1. **Path Creation**: Agents store new chapters and then register paths using the `path` command
2. **Qualification**: Paths earn `QUALIFIED` status through duel performance
3. **Judgment Sessions**: Qualified paths grant mandate to judge prior history
4. **Temporal Cascade**: Session commits trigger canonical path recalculation

### Key Components

#### `hronir_encyclopedia/` Package

- **`cli.py`**: Main CLI interface with Typer commands for all user interactions
- **`storage.py`**: Core data persistence via `DataManager`, UUID management, and data validation. Uses `duckdb_storage.py`.
- **`duckdb_storage.py`**: DuckDB-based data access layer.
- **`models.py`**: Pure Pydantic models for data validation and business logic.
- **`graph_logic.py`**: NetworkX-based narrative consistency validation (operates on data from DuckDB).
- **`session_manager.py`**: Manages judgment sessions and dossier generation.
- **`transaction_manager.py`**: Immutable ledger for session commits and path promotions (data stored in DuckDB).
- **`ratings.py`**: Elo ranking system and duel determination logic (data stored in DuckDB).
- **`gemini_util.py`**: AI generation utilities using Google Gemini.

#### Data Structure

```
data/
├── encyclopedia.duckdb    # Main DuckDB database file containing all persistent data (paths, votes, transactions, hrönirs, sessions, etc.)
└── backup/                # Backups of previous data formats or DB states.
# sessions/                # (Legacy, session data now in DuckDB)
# the_library/             # Hrönir Markdown files (Kept for now due to deletion issues, but canonical data is in DuckDB)
# narrative_paths/         # (Legacy, data moved to DuckDB)
# ratings/                 # (Legacy, data moved to DuckDB)
# data/transactions/       # (Legacy, data moved to DuckDB)
# data/canonical_path.json # (Legacy, data/logic moved to DuckDB or generated dynamically)
```

Primary data (paths, votes, hrönir content, transactions, **sessions**) is stored in tables within the `data/encyclopedia.duckdb` file.
The `data/sessions/` directory is now legacy and its contents should be migrated to DuckDB using `scripts/migrate_sessions_to_duckdb.py`.
The `the_library/` directory is currently left in the repository but its content is considered secondary to the `hronirs` table in DuckDB.

### Key Protocol Concepts

#### Path Status Lifecycle

- `PENDING` → `QUALIFIED` → `SPENT`
- Only `QUALIFIED` paths can initiate judgment sessions
- Qualification requires strong duel performance (Elo-based)

#### Session Workflow

1. Agent creates hrönir → receives `path_uuid`
2. Path becomes `QUALIFIED` through competitive performance
3. Agent uses qualified path to start session → receives dossier of maximum entropy duels
4. Agent submits verdicts → triggers transaction recording and temporal cascade

#### Temporal Cascade

- Recalculates canonical path from oldest voted position forward (based on data in DuckDB).
- Ensures narrative consistency after judgment sessions.
- The canonical path is determined dynamically from DuckDB data or can be stored in a dedicated table/view within DuckDB if needed. The file `data/canonical_path.json` is no longer the primary source.

### UUID System

- All content uses deterministic UUIDv5 generation
- Path UUIDs: `uuid5(position:prev_uuid:current_uuid)`
- Content UUIDs: `uuid5(text_content)`
- Mandate IDs: `blake3(path_uuid + previous_transaction_hash)[:16]`

### Testing Strategy

Tests focus on protocol dynamics:

- `test_storage_and_votes.py`: Core storage and voting mechanics
- `test_sessions_and_cascade.py`: Session management and temporal cascade
- `test_protocol_v2.py`: End-to-end protocol validation
- `test_system_dynamics.py`: Game theory and agent interactions

### File Validation

- `audit` command validates all stored content integrity
- `clean` command removes invalid entries (use `--git` to stage deletions)

## Development Notes

### Data Persistence Guidelines

**CORE**: The primary data store is a DuckDB database file (`data/encyclopedia.duckdb`).

- **Interaction**: Instantiate `hronir_encyclopedia.storage.DataManager` for all data operations. It interfaces with `DuckDBDataManager`. Avoid using any global/singleton instance.
- **Schema**: The DuckDB schema is defined and managed within `hronir_encyclopedia/duckdb_storage.py` and initialized by `scripts/migrate_to_duckdb.py`.
- **Validation**: Pydantic models (`hronir_encyclopedia/models.py`) are used for data validation before writing to and after reading from DuckDB.
- **Committing**: The `data/encyclopedia.duckdb` file **is version-controlled** in Git. Ensure it is staged and committed with your changes if data modifications are part of your work.
- **Large Datasets**: For very large data changes, consider implications for repository size and Git performance.
- **Data Integrity**: Use NetworkX for narrative consistency validation on data retrieved from DuckDB as needed.

### Core Principles

- The system uses DuckDB as its canonical storage for data, providing ACID transactions and SQL querying.
- The `data/encyclopedia.duckdb` file is version-controlled.
- All UUIDs are deterministic and content-addressed.
- The canonical path is emergent, derived from data in DuckDB.
- Session commits are atomic and trigger cascading updates, with transaction data stored in DuckDB.
- Fork qualification uses Elo ratings with configurable thresholds (ratings stored in DuckDB).
- NetworkX can be used to ensure narrative graph remains acyclic.

## Practical Testing Protocol

### Full System Testing Workflow

For comprehensive testing of the Hrönir Encyclopedia, follow this standardized workflow:

#### 1. Create Test Content (10 Meta Hrönirs)

```bash
# Create test content in test_temp/ directory
# Each hrönir should be meta-commentary about:
# - Project development journey and technical insights
# - AI-human collaboration in code development
# - System architecture and philosophical implications
# - Protocol evolution and design decisions
# - User experience and interface considerations
```

#### 2. Execute Complete Protocol Testing

```bash
# Test the full happy path: store → path → session → vote

# Store all test hrönirs
uv run hronir store test_temp/hrönir1.md
uv run hronir store test_temp/hrönir2.md
# ... (repeat for all test files)

# Create narrative paths
uv run hronir path --position N --source <prev_uuid> --target <new_uuid>

# Generate and execute judgment sessions
uv run hronir session start --path-uuid <qualified_path_uuid>
uv run hronir session commit --session-id <id> --verdicts '{"position": "winning_path_uuid"}'

# Validate system state
uv run hronir audit
uv run hronir status --counts
```

#### 3. Collect Development Insights

```bash
# Document findings in TODO.md with rationale:
# - Workflow friction points and UX issues
# - Performance bottlenecks or error conditions
# - Missing CLI commands or functionality gaps
# - Architecture improvements needed
# - Documentation clarifications required
```

#### 4. System Validation

```bash
# Ensure system integrity after testing
uv run hronir audit              # Validate all stored content
uv run hronir clean --git        # Remove any invalid entries
uv run pytest                    # Run full test suite
uv run ruff check .              # Verify code quality
```

**Usage Note**: This testing protocol should be run periodically to validate system stability and identify areas for improvement. Each test session provides valuable data about real-world usage patterns and edge cases.
