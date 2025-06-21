# TODO.md · Development Roadmap — **Hrönir Encyclopedia**

This document outlines the tasks required to implement the **Hrönir Encyclopedia** project as described in the README. The project is currently at an early stage, with only the README finalized.

## ✅ Phase 0 — Repository Setup

- [x] Initialize git repository structure:
  - [x] `hronir_encyclopedia/` (Python package)
  - [x] `book/` (canonical encyclopedia)
  - [x] `ratings/` (Elo rankings)
  - [x] `.github/workflows/` (for CI/CD)
- [x] Create essential files:
  - [x] `.gitignore`
  - [x] `LICENSE` (MIT)
  - [x] `requirements.txt`
  - [x] `book_index.json` (initial narrative tree)

---

## 🚧 Phase 1 — Seed Chapter & Basic CLI

- [x] Write Chapter 0 seed (`00_tlon_uqbar.md`)
- [x] Implement minimal CLI (`cli.py`):
  - [ ] Generate initial branches (`continue` command)
  - [ ] Update `book_index.json`

---

## 🚧 Phase 2 — Narrative Space Synthesis

- [ ] Implement semantic extraction module:
  - [ ] Generate embeddings from existing chapters (0 to n-1)
- [ ] Develop synthesis prompt builder:
  - [ ] Combine narrative space into unified prompt for LLM
- [ ] Generate chapters using LLM (Gemini/OpenAI):
  - [ ] Test initial generations for coherence and consistency

---

## 🚧 Phase 3 — Chapter Management

- [ ] Define clear file structure and naming conventions:
  - canonical chapters: `book/<position>.md`
  - new variants stored under `the_library/<uuid>/index.md`
- [x] Implement UUID-based chapter storage under `the_library/`
- [ ] Update `book_index.json` dynamically with new chapters
- [ ] Automate commit/version control of chapters

---

## 🚧 Phase 4 — Reader Voting & Elo System

- [ ] Implement voting API:
  - [ ] Endpoint `/vote` (JSON payload)
- [ ] Set up Elo ranking logic:
  - [ ] Calculate Elo ratings per chapter position
  - [x] Persist rankings in `ratings/position_<n>.csv`
- [ ] Create reader voting interface (CLI/web)

---

## 🚧 Phase 5 — CLI & API Completeness

- [ ] Expand CLI functionality:
  - [ ] `generate`
  - [x] `vote`
  - [ ] `ranking`
  - [x] `tree`
- [ ] Implement comprehensive logging and error handling
- [ ] Document CLI usage extensively

---

## 🚧 Phase 6 — Web Interface & Visualization

- [ ] Build web interface (e.g., Streamlit/FastAPI):
  - [ ] Visualize narrative tree
  - [ ] Allow interactive reading & voting
  - [ ] Display Elo rankings per chapter

---

## 🚧 Phase 7 — Export & Distribution

- [ ] Develop EPUB/HTML export functionality:
  - [ ] Interactive EPUB generation with selected path
- [ ] Provide export/download via web interface

---

## 🚧 Phase 8 — Quality Assurance

- [ ] Write comprehensive unit and integration tests
- [ ] Set up GitHub Actions workflows for continuous testing
- [ ] Maintain test coverage ≥ 80%

---

## 📌 Long-term Ideas & Enhancements

- [ ] Advanced narrative analytics (heatmaps of reader preferences)
- [ ] Integration with large-scale collaborative platforms
- [ ] Narrative pathway recommendations (AI-driven)

---

## 🗓️ Current Status

- **README**: ✅ completed
- **Repository structure**: ✅ completed (Phase 0)
- **Seed chapter (Tlön)**: ✅ completed (Phase 1)

This document will be updated as development progresses.

---

## 🛠️ Post-Refactor Action Items (Post-PR #1)

These items were identified during or after the initial engineering backlog implementation:

- **Pre-commit Hook Installation:**
  - The `pre-commit install` command failed during initial environment setup due to a potential conflict with `core.hooksPath`. This needs to be investigated and resolved to ensure hooks are automatically active in local development environments.
- **Remaining Linting Errors:**
  - After running `pre-commit run --all-files`, the following Ruff linting errors remained and need manual correction:
    - `E501 Line too long (> 100 characters)`: Several files may have lines exceeding the configured limit.
    - `E402 Module level import not at top of file`: Some imports might not be at the very top of their respective files.
    - `F841 Unused local variable`: There might be variables that are assigned but never used.
- **`git status` Anomaly during Subtasks:**
  - During subtask execution (e.g., `pre-commit run --all-files`), file modifications made by tools were reported, but `git status` within the same subtask often showed a clean working tree immediately after. This behavior should be understood, as it might affect how changes are automatically staged or committed in future automated tasks.
