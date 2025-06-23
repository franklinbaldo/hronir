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
- **Collaboration**: Human contributors submit chapter variants via GitHub pull requests.
- **Selection (Votação Guiada Puramente por Entropia de Bifurcações)**: O sistema de votação é governado por um único princípio: maximizar a informação sobre qual **transição narrativa (fork)** é a mais inevitável. A cada momento, o sistema identifica o **"Duelo de Máxima Entropia"** — o confronto entre os dois `forks` (para uma dada posição e linhagem canônica) cujo resultado é mais incerto (ou seja, seus Elos são mais próximos) e que, portanto, mais beneficiará o ranking com um novo voto.
- **Evolution**: Elo rankings de `forks`, atualizados por estes duelos, determinam o emergente **caminho canônico de bifurcações** (`data/canonical_path.json`) através do reconhecimento coletivo. O cânone não é uma coleção de capítulos, mas uma sequência de decisões de bifurcação.

Este sistema puramente entrópico garante que cada voto seja o mais impactante possível, focando a atenção do leitor na escolha da transição narrativa mais ambígua e crucial do sistema.

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

## ⚖️ The Tribunal of the Future: Judgment Sessions

The core mechanism for evolving the canonical narrative is the "Tribunal of the Future." Creating a new hrönir and its corresponding fork at position `N` grants you a one-time "mandate" (using its `fork_uuid`) to initiate a **Judgment Session**.

1.  **Initiate a Session (`session start`):**
    Use your new `fork_uuid` (from position `N`) to start a session. The system provides a `session_id` and a "dossier" of duels for all prior positions (`N-1` down to `0`). Each duel in the dossier is the "duel of maximum entropy" for its respective position at that moment.
    ```bash
    # Example: Your new fork at position 10 is fork_N_uuid
    uv run python -m hronir_encyclopedia.cli session start \
      --position 10 \
      --fork-uuid <fork_N_uuid>
    ```
    This returns a `session_id` and the dossier.

2.  **Deliberate and Form Veredicts (Offline):**
    Review the static dossier. You have complete freedom to choose which duels to vote on. For each duel you address, select a winner. Abstention is implicit for duels you don't include in your veredict.

3.  **Commit Veredicts (`session commit`):**
    Submit all your chosen veredicts in a single, atomic commit using the `session_id`.
    Provide veredicts as a JSON string or a path to a JSON file. The JSON object maps position numbers (as strings) to the `fork_uuid` you chose as the winner for that position's duel.
    ```bash
    # Example: Veredicts in a JSON string
    uv run python -m hronir_encyclopedia.cli session commit \
      --session-id <your_session_id> \
      --verdicts '{"9": "winning_fork_for_pos9", "7": "winning_fork_for_pos7", "2": "winning_fork_for_pos2"}'

    # Example: Veredicts from a file (e.g., my_verdicts.json)
    # Contents of my_verdicts.json:
    # {
    #   "9": "winning_fork_for_pos9",
    #   "7": "winning_fork_for_pos7",
    #   "2": "winning_fork_for_pos2"
    # }
    uv run python -m hronir_encyclopedia.cli session commit \
      --session-id <your_session_id> \
      --verdicts my_verdicts.json
    ```

**Consequences of Committing:**
*   **Votes Recorded:** Your veredicts are recorded as votes in the respective `ratings/position_*.csv` files.
*   **Transaction Logged:** The entire session commit (your identity, veredicts, timestamp, previous transaction) is immutably recorded in the `data/transactions/` ledger.
*   **Temporal Cascade Triggered:** The "Temporal Cascade" recalculates the canonical path (`data/canonical_path.json`) starting from the oldest position you voted on, propagating changes forward. This is the sole mechanism for updating the canon.

This process ensures that every significant contribution (a new fork) has the potential to reshape the entire history that precedes it, governed by transparent, auditable rules.

---

## ⚙️ Other CLI Usage

### Basic Operations
```bash
# Store a new hrönir chapter (and create its forking path entry implicitly or explicitly)
# This is your Proof-of-Work to get a <fork_uuid> for starting a session.
uv run python -m hronir_encyclopedia.cli store drafts/my_chapter.md --prev <uuid_of_previous_hronir_in_path>
# The output will include the new hrönir's UUID. You'll also need to ensure a forking_path entry is made.
# (The `store` command might need enhancement to also create/output the `fork_uuid` directly)

# Check Elo rankings for forks at a specific position
uv run python -m hronir_encyclopedia.cli ranking --position 1

# Validate a human-contributed chapter (basic check)
# Note: Validation is primarily for the textual content. The hrönir's place in the
# narrative structure is defined by its forking path entry.
uv run python -m hronir_encyclopedia.cli validate --chapter drafts/my_chapter.md

# Audit and repair stored hrönirs, forking paths, and votes
uv run python -m hronir_encyclopedia.cli audit

# Remove invalid hrönirs, forking paths, or votes
uv run python -m hronir_encyclopedia.cli clean --git

# Get the current "Duel of Maximum Entropy" for a position (used internally by `session start`)
# This can be useful to understand what duel a new session might present for a given position.
uv run python -m hronir_encyclopedia.cli get-duel --position 1

# Consolidate book (trigger Temporal Cascade from position 0)
# Under the "Tribunal of the Future" protocol, the canonical path is primarily updated
# by the Temporal Cascade triggered by `session commit` (starting from the oldest voted position).
# The `consolidate-book` command now serves as a manual way to trigger this cascade
# from the very beginning (position 0), useful for initialization, full recalculations, or recovery.
uv run python -m hronir_encyclopedia.cli consolidate-book
```

The `store` command is crucial for generating new `hrönir` and, through associated forking path entries, the `fork_uuid` necessary to initiate a Judgment Session. Direct voting via a `vote` command is deprecated; all judgments are now channeled through the `session commit` mechanism.

## 🔏 Proof-of-Work (Mandate for Judgment)

Creating a new `fork_uuid` (by storing a hrönir at Position `N` and ensuring its corresponding entry in a forking path CSV) serves as your Proof-of-Work.

This `fork_uuid` acts as a **mandate** to initiate a `session start --position N --fork-uuid <your_fork_N_uuid>`.
This session grants you the right to cast veredicts on *any subset* of duels from prior positions (`N-1` down to `0`), as presented in the session's static dossier. Each duel in the dossier is the one of maximum entropy for its position at the time the session was started.

This system elevates the impact of each contribution, allowing a single act of creation to potentially influence the entire preceding narrative history through a structured and auditable judgment process. The `get-duel` command can still be used to see what the current maximum entropy duel for a specific position is, which is what `session start` uses internally to build the dossier.

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
