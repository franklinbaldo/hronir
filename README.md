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

Each new chapter (`n`) is created through:

1. **Semantic extraction**: Previous chapters (0 to n-1) are analyzed via semantic embeddings to extract themes, concepts, and stylistic markers.
2. **Prompt synthesis**: A unified prompt is formulated, combining these extracted narrative elements into a coherent instruction for the LLM.
3. **LLM Generation**: The model generates a chapter that logically and creatively integrates the accumulated narrative history, maintaining a consistent Borgesian tone and theme.

This process ensures each new chapter reflects not only isolated events but also echoes, reflections, and metaphorical nuances that have organically developed throughout the entire narrative journey.

---

## ⚔️ Selecting the True Chapter

- Variants within the same chapter position compete through **paired reader evaluations** (literary duels).
- Results of these duels are recorded using an **Elo-based literary ranking system**, establishing a probabilistic hierarchy among competing versions.
- Over time, a dominant version emerges for each chapter position—the "canonical Hrönir"—acknowledged by readers as the authentic narrative branch through their collective experience.
- Winning chapters are copied into the `book/` folder, and each selection constrains the possibilities for subsequent chapters via updated forking paths.

Example Elo ranking for Chapter 2 variants:

| Chapter 2 | Elo  | Wins | Losses |
|-----------|------|------|--------|
| `2_c`     | 1580 | 14   | 4      |
| `2_a`     | 1512 | 10   | 8      |
| `2_b`     | 1465 | 7    | 11     |

---

## 🗂️ Repository Structure

Forking paths are stored in `forking_path/yu-tsun.csv`, named after the protagonist of *The Garden of Forking Paths*.


```
the_library/                       # Hrönirs (conteúdo textual) armazenados por UUID
data/
└── canonical_path.json          # O caminho canônico de forks (UUIDs de bifurcações)
forking_path/
└── *.csv                        # Definições de forks (posição, prev_hrönir_uuid, hrönir_uuid_sucessor, fork_uuid)
ratings/
└── position_*.csv               # Votos registrados para duelos de forks em cada posição
```

---

## ⚙️ Quickstart CLI Usage

### Generate new chapters and cast a vote automatically:
(Nota: `synthesize` pode precisar de atualização para refletir a lógica de `fork_uuid` se for usado para votação direta)
```bash
uv run python -m hronir_encyclopedia.cli synthesize \
  --position 1 \
  --prev <uuid_do_hronir_predecessor_canonico_da_posicao_0>

# Check Elo rankings for a specific position (ranking de forks)
uv run python -m hronir_encyclopedia.cli ranking --position 1
# (O comando ranking pode precisar ser adaptado para mostrar rankings de forks se ainda mostra hrönirs)

# Validate a human-contributed chapter
uv run python -m hronir_encyclopedia.cli validate --chapter drafts/03_my_variant.md

# Store chapter using UUID layout
uv run python -m hronir_encyclopedia.cli store drafts/03_my_variant.md --prev 123e4567-e89b-12d3-a456-426614174000

# Validate and repair stored chapters
uv run python -m hronir_encyclopedia.cli audit
# Each forking entry receives a deterministic UUID

# Remove invalid hrönirs, forking paths or votes
uv run python -m hronir_encyclopedia.cli clean --git

# These commands load ratings and forking_path CSV files into a temporary
# SQLite database via SQLAlchemy. Changes are written back to CSV when the
# command finishes.

# Export the highest-ranked path as EPUB
# uv run python -m hronir_encyclopedia.cli export --format epub --path canonical # Temporariamente comentado se o comando export não estiver pronto

# Obtenha o Duelo de Máxima Entropia entre forks para uma posição:
uv run python -m hronir_encyclopedia.cli get-duel --position 1

# Exemplo de saída:
# {
#   "position": 1,
#   "strategy": "max_entropy_duel",
#   "entropy": 0.998,
#   "duel_pair": { "fork_A": "fork_uuid_A...", "fork_B": "fork_uuid_B..." }
# }

# Submeta seu voto para o duelo de forks apresentado por get-duel:
uv run python -m hronir_encyclopedia.cli vote \
  --position 1 \
  --voter-fork-uuid <seu_fork_uuid_de_prova_de_trabalho> \
  --winner-fork-uuid <fork_uuid_A_do_get_duel> \
  --loser-fork-uuid <fork_uuid_B_do_get_duel>
# (Substitua os placeholders <> pelos valores reais)
```

## 🔏 Proof-of-Work e Votação Entrópica de Bifurcações

O direito de votar é conquistado contribuindo para a expansão da narrativa (Proof-of-Work). Ao usar `store` para novos `hrönirs` e conectá-los em `forking_path/*.csv`, o `fork_uuid` gerado para essa conexão atua como sua identidade de votante (seu PoW).

Com seu `fork_uuid` de PoW, você participa do processo de votação guiado por entropia:
1. Use `hronir_encyclopedia.cli get-duel --position <num>` para descobrir o "Duelo de Máxima Entropia" entre dois `forks` que o sistema identificou como o mais crítico para resolver a incerteza no ranking daquela posição e linhagem.
2. Use `hronir_encyclopedia.cli vote --position <num> --voter-fork-uuid <seu_fork_uuid_pow> --winner-fork-uuid <fork_A_uuid> --loser-fork-uuid <fork_B_uuid>` para registrar seu voto **apenas para o par de `forks` exato apresentado por `get-duel`**.

Este processo de dois passos garante que seu esforço intelectual seja direcionado à escolha da transição narrativa (fork) de maior necessidade informacional na estrutura evolutiva da enciclopédia. Consulte [docs/proof_of_work_voting.md](docs/proof_of_work_voting.md) para uma explicação mais profunda.

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
