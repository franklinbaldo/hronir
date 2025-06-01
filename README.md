# The Hrönir Encyclopedia

> *“The true version will be the one that, upon being read, reveals itself as inevitable.”*

The **Hrönir Encyclopedia** is a computational literary project creating an infinitely branching, self-reflective narrative inspired by Jorge Luis Borges' **Tlön, Uqbar, Orbis Tertius**.

In this encyclopedia, each new chapter (**Chapter n**) is not simply a continuation of the immediately preceding chapter but is generated from the entire narrative space formed by all previously written chapters (0 to n-1). Each new branch is a probabilistic synthesis of previous narrative paths, preserving thematic coherence, stylistic unity, and Borgesian philosophical concepts.

Among infinite possibilities, one version will ultimately prove itself authentic—not by external authority, but because it resonates most powerfully within the minds of its readers.

---

## 📖 Structure and Generation of Chapters

Every new chapter (**n**):

- Is synthesized by considering the entire narrative space of all previously generated chapters (`0` through `n-1`).
- Employs a sophisticated language model (LLM), guided by a carefully crafted **synthesis prompt** that encapsulates themes, motifs, characters, and ideas accumulated thus far.
- Can exist in multiple variants (e.g., `2_a`, `2_b`, `2_c`), each exploring different interpretations of the collective narrative space.

The narrative expands exponentially, creating a network of infinite possibilities:

Chapter 0: Tlön, Uqbar… (seed summary) ├── Chapter 1_a, 1_b, 1_c … ├── Chapter 2_a, 2_b, 2_c … (synthesis from prior narrative space) └── Chapter n … (continuously broadening possibilities)

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

Example Elo ranking for Chapter 2 variants:

| Chapter 2 | Elo  | Wins | Losses |
|-----------|------|------|--------|
| `2_c`     | 1580 | 14   | 4      |
| `2_a`     | 1512 | 10   | 8      |
| `2_b`     | 1465 | 7    | 11     |

---

## 🗂️ Repository Structure

book/ ├── 00_tlon_uqbar.md             # Seed chapter (position 0) ├── 01/ │   ├── 01_a.md │   └── 01_b.md ├── 02/ │   ├── 02_a.md │   └── 02_b.md ├── book_index.json              # Detailed narrative tree ratings/ └── position_002.csv             # Elo ratings per chapter position

---

## ⚙️ Quickstart CLI Usage

### Generate a new chapter (e.g., Chapter 3 from previous narrative space):

```bash
python -m hronir_encyclopedia.cli synthesize --position 3 --variant_id 3_a

Vote on a literary duel:

curl -X POST /vote \
  -H "Content-Type: application/json" \
  -d '{ "position": 3, "winner": "3_a", "loser": "3_b" }'


---

🚧 Project Roadmap

[x] Initial structure (seed chapter, basic branching)

[ ] Complete implementation of generation from full narrative space

[ ] Comprehensive CLI (generation, voting, Elo ranking)

[ ] Web interface for comparative reading and voting

[ ] Interactive EPUB/HTML export with user-selected narrative paths



---

🧭 Philosophy of The Hrönir Encyclopedia

> In Tlön, duplicated objects (hrönir) redefine reality through perception and repetition.
In this encyclopedia, infinite narrative multiplication redefines literary truth, naturally selecting—through reading experience—the inevitable version.



The Hrönir Encyclopedia exists at the intersection of imagination and reality, possibility and inevitability, continually expanding within the reader's consciousness.


---

📜 License and Acknowledgements

Source code under MIT License.
Generated texts are released into the public domain (CC0), except explicit Borges references used strictly for critical and referential purposes.


---

> "In the end, only one among the infinite versions will reveal itself as true—because the reader will recognize it as inevitable. All others, though possible, will become mere shadows of themselves."





