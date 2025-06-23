# The Hrönir Encyclopedia

> *"The true version will be the one that, upon being read, reveals itself as inevitable."*

The **Hrönir Encyclopedia** is a computational literary project creating an infinitely branching, self-reflective narrative inspired by Jorge Luis Borges' **Tlön, Uqbar, Orbis Tertius**.

See `GLOSSARY.md` for how various Borgesian concepts map onto project structures.

In this encyclopedia, each new chapter (**Chapter n**) is not simply a continuation of the immediately preceding chapter but is generated from the entire narrative space formed by all previously written chapters (0 to n-1). Each new branch is a probabilistic synthesis of previous narrative paths, preserving thematic coherence, stylistic unity, and Borgesian philosophical concepts.

Among infinite possibilities, one version will ultimately prove itself authentic—not by external authority, but because it resonates most powerfully within the minds of its readers.

---

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/franklinbaldo/hronir
   cd hronir
   ```

2. **Install `uv` (Python package manager):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   (On Windows, you might need to download the binary from [astral.sh/uv](https://astral.sh/uv) or use WSL.)

3. **Set up Python version (optional but recommended):**
   If you don't have Python 3.12 (or the version specified in `.python-version`), `uv` can install it for you.
   Ensure `.python-version` exists with your desired Python version (e.g., `3.12`).

4. **Create virtual environment and install dependencies:**
   ```bash
   uv sync --all-extras # Installs main and development dependencies
   ```

5. **Set up environment variables:**
   ```bash
   cp .env.example .env  # and add your GEMINI_API_KEY to .env
   ```

Dependencies are managed with `uv` using `pyproject.toml` and `uv.lock`. Core libraries include [**click**](https://palletsprojects.com/p/click/) for the CLI and [**pandas**](https://pandas.pydata.org/) for data manipulation.

---

## 🔮 How It Works

The encyclopedia grows through interconnected processes:

- **Generation**: AI creates new chapter variants (`hrönirs`) from the accumulated narrative space.
- **Collaboration**: Human contributors submit chapter variants.
- **Selection (Tribunal of the Future)**: The encyclopedia's canon evolves through the **Tribunal of the Future**. Instead of single votes, influence is now wielded through **Judgment Sessions**. When a contributor creates a new, high-quality fork that proves its relevance by performing well in duels, it becomes **`QUALIFIED`**. This grants a one-time right to initiate a session, acting as a judge over all of prior history. This mechanism ensures that only meaningful contributions can shape the past, providing a robust defense against low-effort Sybil attacks.
- **Evolution**: Veredicts from Judgment Sessions update Elo rankings for forks. The **Temporal Cascade**, triggered by `session commit`, recalculates the canonical path (`data/canonical_path.json`), which is a sequence of fork decisions representing the most "inevitable" narrative.

## 🤖 Daily Automated Generation

The encyclopedia writes itself through GitHub Actions workflows that run daily:

- **Morning Generation** (06:00 UTC): Analyzes the current narrative space and generates new chapter variants using Google's Gemini AI
- **Evening Synthesis** (18:00 UTC): Creates synthesis prompts from accumulated chapters and generates additional variants
- **Automatic Commits**: Each generated chapter is automatically committed to the repository with metadata about generation parameters

This creates a living document that grows organically, day by day, as if the encyclopedia is discovering itself rather than being written. The automation ensures continuous narrative expansion while maintaining the project's conceptual purity—the text emerges through systematic process rather than conscious authorial intent.

```yaml
# .github/workflows/daily-generation.yml
name: Daily Chapter Generation
on:
  schedule:
    - cron: '0 6 * * *'  # 06:00 UTC daily
    - cron: '0 18 * * *' # 18:00 UTC daily
```

## 🤝 Human Collaboration via GitHub

Human contributors can participate in the encyclopedia's evolution by submitting chapter variants through GitHub pull requests:

### Contributing a Chapter Variant

1. **Fork the repository** and create a branch for your contribution
2. **Write your chapter** as a Markdown file anywhere (e.g., `drafts/03_my_variant.md`)
3. **Store it** under `the_library/` using the CLI:
   ```bash
   uv run python -m hronir_encyclopedia.cli store drafts/03_my_variant.md --prev <previous_uuid>
   ```
4. **Follow Borgesian style guidelines** (see `CONTRIBUTING.md`)
5. **Submit a pull request** with your stored hrön

### Review Process

- **Automated validation**: GitHub Actions verify format, position, and basic style compliance
- **Community review**: Contributors and maintainers review for thematic consistency with the narrative space
- **Integration**: Approved variants enter the Elo ranking system alongside AI-generated chapters

### Human vs. AI Competition

Human-authored and AI-generated variants compete on equal terms in the literary duels. Readers vote without knowing the origin—the most inevitable version emerges regardless of whether it springs from human consciousness or artificial synthesis.

```bash
# Contributing via CLI
uv run python -m hronir_encyclopedia.cli validate --chapter drafts/03_my_variant.md
uv run python -m hronir_encyclopedia.cli store drafts/03_my_variant.md --prev <previous_uuid>
```

---

## 📖 Structure and Generation of Chapters

Every new chapter (**n**):

- Is synthesized by considering the entire narrative space of all previously generated chapters (`0` through `n-1`).
- Employs a sophisticated language model (LLM), guided by a carefully crafted **synthesis prompt** that encapsulates themes, motifs, characters, and ideas accumulated thus far.
- Can exist in multiple variants (e.g., `2_a`, `2_b`, `2_c`), each exploring different interpretations of the collective narrative space.

The narrative expands exponentially, creating a network of infinite possibilities:

```
Chapter 0: The Mirror of Enigmas (seed)
├── Chapter 1: The Garden of Forking Paths
│   ├── 1_a: The Labyrinth of Time
│   ├── 1_b: The Library of Sand
│   └── 1_c: The Aleph of Memory
├── Chapter 2: The Lottery in Babylon
│   ├── 2_a: The Map of the Empire
│   └── 2_b: The Zahir of Dreams
└── Chapter n: [infinite emerging possibilities]
```

---

## 🧩 The Mechanics of Narrative Possibility Space

Each new chapter (`n`):

- Is synthesized by considering the entire narrative space of all previously generated chapters (`0` through `n-1`).
- Employs a sophisticated language model (LLM), guided by a carefully crafted **synthesis prompt** that encapsulates themes, motifs, characters, and ideas accumulated thus far.
- Can exist in multiple variants (e.g., `2_a`, `2_b`, `2_c`), each exploring different interpretations of the collective narrative space.

The narrative expands exponentially, creating a network of infinite possibilities. Each act of creation (generating a new hrönir and its associated `fork_uuid`) grants the author a mandate to participate in a **Judgment Session**, potentially influencing the canonical interpretation of all preceding history.

---

## ⚔️ Selecting the True Narrative Path (Canonical Forks)

- Forks (transitions between hrönirs) at the same position and lineage compete through **Judgment Sessions**.
- Veredicts from these sessions are recorded as votes, updating Elo ratings for the involved forks.
- An Elo-based ranking system establishes a probabilistic hierarchy among competing forks.
- The **Temporal Cascade**, triggered by `session commit`, recalculates the `data/canonical_path.json`. This path represents the sequence of forks deemed most "inevitable" by collective judgment.
- The "canonical hrönirs" are those that lie along this canonical path of forks.

Example Elo ranking for forks at Position 2 (assuming a specific predecessor from Position 1):

| Fork UUID (leading to Hrönir) | Elo  | Wins | Losses |
|-------------------------------|------|------|--------|
| `fork_uuid_2c_xyz...`         | 1580 | 14   | 4      |
| `fork_uuid_2a_abc...`         | 1512 | 10   | 8      |
| `fork_uuid_2b_pqr...`         | 1465 | 7    | 11     |

---

## 🗂️ Repository Structure

Forking paths are stored in `forking_path/yu-tsun.csv`, named after the protagonist of *The Garden of Forking Paths*.

```
the_library/                       # Hrönirs (textual content) stored by UUID
data/
├── canonical_path.json          # The canonical path of forks (fork UUIDs)
├── sessions/                    # Active judgment session files (e.g., <session_id>.json)
│   └── consumed_fork_uuids.json # Record of fork_uuids used to start sessions
└── transactions/                # Chronological ledger of all judgment session commits
    ├── HEAD                     # Pointer to the latest transaction_uuid
    └── <transaction_uuid>.json  # Individual transaction records
forking_path/
└── *.csv                        # Fork definitions (position, prev_hrönir_uuid, successor_hrönir_uuid, fork_uuid)
ratings/
└── position_*.csv               # Recorded votes for fork duels at each position
```

---

## ⚖️ The Tribunal of the Future: The Main Workflow

The core mechanism for evolving the canonical narrative is the "Tribunal of the Future." After your new fork becomes **`QUALIFIED`** through duels, you can initiate a Judgment Session.

1.  **Initiate a Session (`session start`):**
    Use your qualified `fork_uuid` to start a session. The system provides a `session_id` and a "dossier" of duels for prior positions.
    ```bash
    # Your new fork at position 10 (fork_N_uuid) has been QUALIFIED.
    uv run hronir_encyclopedia.cli session start \
      --fork-uuid <your_qualified_fork_uuid>
    ```

2.  **Deliberate and Form Veredicts (Offline):**
    Review the static dossier. For each duel you wish to judge, select a winner.

3.  **Commit Veredicts (`session commit`):**
    Submit your veredicts in a single, atomic commit using the `session_id`.
    ```bash
    # Provide veredicts as a JSON string mapping position -> winning_fork_uuid
    uv run hronir_encyclopedia.cli session commit \
      --session-id <your_session_id> \
      --verdicts '{"9": "winning_fork_for_pos9", "2": "winning_fork_for_pos2"}'
    ```

**Consequences of Committing:**
*   Your veredicts are recorded as permanent votes.
*   The session is immutably logged in the `data/transactions/` ledger.
*   The **Temporal Cascade** is triggered, recalculating the canonical path from the oldest position you judged. This is now the sole mechanism for updating the canon.

---

## ⚙️ Advanced/Legacy Commands

### Basic Operations
```bash
# Store a new hrönir chapter
uv run python -m hronir_encyclopedia.cli store drafts/my_chapter.md --prev <uuid_of_previous_hronir_in_path>

# Check Elo rankings for forks at a specific position
uv run python -m hronir_encyclopedia.cli ranking --position 1

# Validate a human-contributed chapter (basic check)
uv run python -m hronir_encyclopedia.cli validate --chapter drafts/my_chapter.md

# Audit and repair stored hrönirs, forking paths, and votes
uv run python -m hronir_encyclopedia.cli audit

# Remove invalid hrönirs, forking paths, or votes
uv run python -m hronir_encyclopedia.cli clean --git

# Get the current "Duel of Maximum Entropy" for a position (used internally by `session start`)
# This can be useful to understand what duel a new session might present for a given position.
# Under Protocol v2, this is mainly for inspection; user voting is via `session commit`.
uv run python -m hronir_encyclopedia.cli get-duel --position 1

# Recover canon / Consolidate book (trigger Temporal Cascade from position 0)
# Under the "Tribunal of the Future" protocol, the canonical path is primarily updated
# by the Temporal Cascade triggered by `session commit`.
# The `recover-canon` (formerly `consolidate-book`) command serves as a manual way
# to trigger this cascade from the very beginning (position 0), useful for initialization,
# full recalculations, or recovery.
uv run python -m hronir_encyclopedia.cli recover-canon
```

## 🔏 Proof-of-Work (Mandate for Judgment)

Under Protocol v2, Proof-of-Work has been elevated. Creating a new fork is just the beginning. True influence—the **mandate for judgment**—is earned through **Proof of Relevance**. Only when your fork proves its value in duels and becomes `QUALIFIED` do you gain the right to initiate a `session` and reshape the narrative's history.

## Development Setup

Ensure you have development dependencies installed:
```bash
uv sync --all-extras
```

Then, install and enable the pre-commit hook to automatically clean invalid hrönirs and votes:
```bash
uv run pre-commit install
```

### Troubleshooting Pre-commit Hooks

If you encounter issues when running `uv run pre-commit install`, such as errors related to `core.hooksPath`, or if the hooks don't seem to run automatically when you commit, you can use the `scripts/fix_hooks.sh` script to help diagnose and potentially resolve common problems.

To run it:
```bash
bash scripts/fix_hooks.sh
```
This script will:
- Check your local and global Git `core.hooksPath` configurations.
- Inform you of potential conflicts with `pre-commit`.
- Offer to unset a conflicting local `core.hooksPath` if found.
- Attempt to run `pre-commit install` again.
- Provide guidance if issues persist.

Make sure the script is executable:
```bash
chmod +x scripts/fix_hooks.sh
```

---

## 🚧 Project Roadmap

- [x] Initial structure (seed chapter, basic branching)
- [ ] Complete implementation of generation from full narrative space
- [ ] Comprehensive CLI (generation, voting, Elo ranking)
- [ ] Web interface for comparative reading and voting
- [ ] Interactive EPUB/HTML export with user-selected narrative paths

---

## 🧭 Philosophy of The Hrönir Encyclopedia

> In Tlön, duplicated objects (hrönir) redefine reality through perception and repetition.
> In this encyclopedia, infinite narrative multiplication redefines literary truth, naturally selecting—through reading experience—the inevitable version.

The Hrönir Encyclopedia exists at the intersection of imagination and reality, possibility and inevitability, continually expanding within the reader's consciousness. Each generated variant—whether born from artificial intelligence or human creativity—exists in a state of potential authenticity until collective recognition determines which version was always meant to be.

Just as the **Library of Babel** contains every possible book, the `the_library/` directory holds innumerable variants. Each branch's summary hash functions as an **Aleph**, a point that contains all other points. Some branches become a **Zahir**, monopolising attention, while a Funes-like audit log recalls every change. Our Git history unfolds like the **Book of Sand**, without a first or last page, and any author may himself be dreamed by another, echoing **The Circular Ruins**.

The project explores fundamental questions about literary truth: Is authenticity inherent in a text, or does it emerge through recognition? Can computational generation achieve the same inevitability as human inspiration? When human and artificial minds collaborate unknowingly, which produces the more "true" version? In the end, the readers themselves become the final arbiters of what feels most inevitable, regardless of its origin.
[^menard]: This approach echoes Borges' 'Pierre Menard, Author of the Quixote' (1939), in which identical text gains new meaning through context.

---

## 📜 License and Acknowledgements

Source code under MIT License.
Generated texts are released into the public domain (CC0), except explicit Borges references used strictly for critical and referential purposes.

---

> *"In the end, only one among the infinite versions will reveal itself as true—because the reader will recognize it as inevitable. All others, though possible, will become mere shadows of themselves, echoes in the vast library of what might have been."*
