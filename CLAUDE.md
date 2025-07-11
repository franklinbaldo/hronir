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

# Discover duels (after a path at N is QUALIFIED)
uv run hronir query get-duel --position <P> # Where P < N

# Submit votes using a qualified mandate path
# Mandate path at position N allows sqrt(N) votes.
uv run hronir vote submit --mandate-path-uuid <qualified_path_uuid_at_pos_N> \
  --votes-json '[{"position": "<P1>", "winner_hrönir_uuid": "...", "loser_hrönir_uuid": "...", "predecessor_hrönir_uuid": "..."}, \
                   {"position": "<P2>", "winner_hrönir_uuid": "...", "loser_hrönir_uuid": "...", "predecessor_hrönir_uuid": "..."}]'

# View rankings
uv run hronir query ranking <position>

# List paths (optional --position to filter)
uv run hronir list-paths --position <position>

# Check status of a specific path
uv run hronir path-status <path_uuid>

# Show canonical path status
uv run hronir status
uv run hronir query status --counts # Corrected command path

# Get duel information (used by agents to find duels to vote on)
uv run hronir query get-duel --position <position> # Corrected command path

# Trigger manual canonical path recovery
uv run hronir admin recover-canon # Corrected command path
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

1. **Path Creation**: Agents store new chapters and then register paths using the `hronir store` and `hronir path` commands.
2. **Qualification**: Paths earn `QUALIFIED` status through strong performance in duels against other paths at their position.
3. **Voting with Mandate**: A `QUALIFIED` path (at position `N`) grants a voting mandate. The agent can then use `hronir query get-duel` to find duels at prior positions and submit up to `sqrt(N)` votes using `hronir vote submit`.
4. **Temporal Cascade**: Vote submissions are recorded as transactions and trigger a Temporal Cascade, which recalculates the canonical path based on updated Elo ratings.

### Key Components

#### `hronir_encyclopedia/` Package

- **`cli.py`**: Main CLI interface with Typer commands for all user interactions
- **`storage.py`**: Core data persistence via `DataManager`, UUID management, and data validation. Uses `duckdb_storage.py`.
- **`duckdb_storage.py`**: DuckDB-based data access layer.
- **`models.py`**: Pure Pydantic models for data validation and business logic (including `Transaction`, `TransactionContent`, `SessionVerdict` for votes).
- **`graph_logic.py`**: NetworkX-based narrative consistency validation (operates on data from DuckDB).
- **`transaction_manager.py`**: Manages the recording of vote transactions to the DuckDB ledger and triggers path promotions/qualifications.
- **`ratings.py`**: Elo ranking system, duel determination logic (`get_max_entropy_duel`), and path qualification checks. Operates on data in DuckDB.
- **`canon.py`**: Handles Temporal Cascade logic and derivation of the canonical path from DuckDB data.
- **`gemini_util.py`**: AI generation utilities using Google Gemini.

#### Data Structure

```
data/
├── encyclopedia.duckdb    # Main DuckDB database file containing all persistent data (paths, votes, transactions, hrönirs, etc.)
└── backup/                # Backups of previous data formats or DB states.
# the_library/             # (Legacy) Hrönir Markdown files. Canonical content is in DuckDB's `hronirs` table.
# narrative_paths/         # (Legacy) CSV storage for paths. Canonical data in DuckDB's `paths` table.
# ratings/                 # (Legacy) CSV storage for votes. Canonical data in DuckDB's `votes` table.
# data/transactions/       # (Legacy) JSON storage for transaction ledger. Canonical data in DuckDB's `transactions` table.
# data/sessions/           # (Removed) No longer used with the new voting protocol.
# data/canonical_path.json # (Legacy) Canonical path is now stored as `is_canonical` flags in DuckDB's `paths` table.
```

Primary data (hrönir content, paths, votes, transactions) is stored in dedicated tables within the `data/encyclopedia.duckdb` file. The canonical path is determined by `is_canonical` flags on path records in the database.

### Key Protocol Concepts

#### Path Status Lifecycle

- `PENDING` → `QUALIFIED` → `SPENT`
- Only `QUALIFIED` paths grant a voting mandate.
- `QUALIFIED` status is earned through strong duel performance (Elo-based) against peers at its own position.
- `SPENT` status indicates a path's voting mandate has been consumed.

#### Voting Workflow (Replaces Session Workflow)

1. Agent creates a hrönir and its associated path (e.g., at position `N`).
2. This path competes and, if successful, becomes `QUALIFIED`, granting a voting mandate.
3. Agent uses the `QUALIFIED` path's UUID (`mandate_path_uuid`) to:
    a. Discover duels at prior positions (`P < N`) using `hronir query get-duel --position <P>`.
    b. Submit up to `sqrt(N)` votes for chosen duels using `hronir vote submit --mandate-path-uuid <mandate_path_uuid> --votes-json '[...]'`.
4. Vote submission is recorded as a transaction, updates Elo ratings, marks the mandate path as `SPENT`, and triggers a Temporal Cascade.

#### Temporal Cascade

- Recalculates the canonical path from the oldest voted-upon position forward, based on updated Elo ratings in DuckDB.
- Ensures narrative consistency after vote submissions.
- The canonical path is stored as `is_canonical` boolean flags on path records in the DuckDB `paths` table. The `data/canonical_path.json` file is legacy.

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

- **Interaction**: Use the `DataManager` (`hronir_encyclopedia.storage.data_manager`) for all data operations. It interfaces with `DuckDBDataManager`.
- **Schema**: The DuckDB schema is defined and managed within `hronir_encyclopedia/duckdb_storage.py` and initialized by `scripts/migrate_to_duckdb.py`.
- **Validation**: Pydantic models (`hronir_encyclopedia/models.py`) are used for data validation before writing to and after reading from DuckDB.
- **Committing**: The `data/encyclopedia.duckdb` file **is version-controlled** in Git. Ensure it is staged and committed with your changes if data modifications are part of your work.
- **Large Datasets**: For very large data changes, consider implications for repository size and Git performance.
- **Data Integrity**: Use NetworkX for narrative consistency validation on data retrieved from DuckDB as needed.

### Core Principles

- The system uses DuckDB as its canonical storage for data, providing ACID transactions and SQL querying.
- The `data/encyclopedia.duckdb` file is version-controlled.
- All UUIDs are deterministic and content-addressed.
- The canonical path is emergent, derived from data in DuckDB (via `is_canonical` flags on paths).
- Vote submissions result in atomic transactions (stored in DuckDB) that trigger cascading updates to the canonical path.
- Path qualification (to `QUALIFIED` status, granting a voting mandate) uses Elo ratings with configurable thresholds.
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
# Test the full happy path: store → path → qualification → query duels → submit votes

# Store all test hrönirs
uv run hronir store test_temp/hrönir1.md
# (Assume output is <hronir1_uuid>)
uv run hronir store test_temp/hrönir2.md
# (Assume output is <hronir2_uuid>)
# ... create other hrönirs for duels, e.g. <hronir_alt1_uuid>

# Create narrative paths
# e.g., Path P0 for position 0, using <hronir1_uuid>
uv run hronir path --position 0 --target <hronir1_uuid>
# (Assume output is <path_P0_uuid>)

# e.g., Path P1 for position 1, using <hronir2_uuid>, prev <hronir1_uuid>
uv run hronir path --position 1 --source <hronir1_uuid> --target <hronir2_uuid>
# (Assume output is <path_P1_uuid>. This will be our mandate path after qualification)

# Manually qualify path P1 for testing purposes (or ensure it wins duels)
uv run hronir admin dev-qualify --path-uuid <path_P1_uuid>

# Discover duels (e.g., for position 0)
uv run hronir query get-duel --position 0
# (Review output to find winner/loser UUIDs for the vote)

# Submit votes (Path P1 is at N=1, so sqrt(1)=1 vote allowed)
# Assume duel at pos 0 was between hronirX (winner) and hronirY (loser)
uv run hronir vote submit --mandate-path-uuid <path_P1_uuid> \
  --votes-json '[{"position": 0, "winner_hrönir_uuid": "<hronirX_uuid>", "loser_hrönir_uuid": "<hronirY_uuid>", "predecessor_hrönir_uuid": null}]'

# Validate system state
uv run hronir admin audit
uv run hronir query status --counts
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
