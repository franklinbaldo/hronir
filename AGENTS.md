# AGENTS Instructions

## Test and linting
- Install dependencies using `pip install -r requirements.txt` if needed.
- Run `pytest` from the repository root after changes. Even if there are no tests, this must succeed.

## Code style
- Use standard Python style with 4-space indentation.
- Keep implementations minimal and self-explanatory.

## Documentation
- Update the README when adding new CLI commands or significant features.
# Agent Contributions and Generated Hrönirs

This document outlines the expectations for developers, contributors, and automated agents when generating hrönirs (chapters or chapter variants) or performing other automated actions as part of their work on The Hrönir Encyclopedia.

## Section 1: Committing Generated Content

### Guiding Principle: Commit Your Creations

When an agent (human developer, tester, or automated script/AI) generates new hrönirs for any of the following purposes:

*   Testing core functionalities (e.g., `store`, `vote`, `audit` commands).
*   Demonstrating a new feature or workflow.
*   Fulfilling Proof-of-Work requirements for voting simulations.
*   Exploring narrative possibilities as part of an analysis.
*   Seeding the encyclopedia with initial or example content.

**It is expected that these generated hrönirs, along with any associated updates to `forking_path/*.csv` files, should be committed to the repository.**

### Rationale for Committing Content

Committing these hrönirs offers several benefits:

1.  **Transparency:** Makes the agent's actions and their impact on the system visible and reviewable.
2.  **Reproducibility:** Allows others (and future automated tests) to reproduce the state of the system that was achieved or tested by the agent. This is crucial for debugging and verifying fixes or new features.
3.  **Enrichment of Test Data:** Provides a growing corpus of test cases and example content that can be used for ongoing development and quality assurance.
4.  **Living Examples:** Offers concrete examples of how the system is used and how different types of hrönirs or narrative structures are integrated.
5.  **Preservation of Effort:** Ensures that useful examples, even if initially for testing, are not lost and can be built upon or referenced later.

### How to Commit Content

1.  **Use the `store` command:** Ensure all generated hrönirs are correctly processed using the `python -m hronir_encyclopedia.cli store <markdown_file> --prev <previous_hrönir_uuid>` command. This will place the hrönir into the `the_library/` directory structure and (usually) update the relevant `forking_path/*.csv` file.
2.  **Identify changed files:** The `store` command will create new files under `the_library/` (specifically an `index.md` and `metadata.json` within a UUID-derived path) and may modify files in `forking_path/`.
3.  **Stage and Commit:** Add these new/modified files to your Git commit. Use a descriptive commit message explaining the purpose of the generated hrönirs (e.g., Test: Add hrönirs for testing vote command PoW).

## Section 2: Active Participation in Canon Evolution

Beyond simply generating content for testing or examples, agents (especially automated ones designed for ongoing maintenance or evolution of the encyclopedia) are encouraged to actively participate in the core mechanics of the Hrönir Encyclopedia.

### Expanded Expectations for Active Agents:

1.  **Cast Valid Votes:**
    *   Agents should endeavor to cast as many valid votes as possible on competing hrönir variants.
    *   Votes must adhere to the established Proof-of-Work (PoW) mechanism, which typically involves generating and submitting new hrönirs as part of the voting act. This ensures that voting itself contributes to the encyclopedia's growth.

2.  **Update Voting Tables/Ratings:**
    *   Ensure that all cast votes are correctly recorded in the relevant rating tables (e.g., `ratings/position_<n>.csv` files or the database if one is implemented).
    *   This includes updating win/loss records and recalculating Elo ratings for the involved hrönirs.

3.  **Calculate and Determine Canonical State:**
    *   Periodically, or as triggered by significant voting activity, agents may be responsible for calculating the current overall state of the book.
    *   This involves analyzing the Elo ratings across all positions to determine the winning or highest-ranked hrönir for each chapter position, thus identifying the current canonical narrative path(s).

4.  **Update Canonical Version Representation:**
    *   Once the canonical path(s) are determined, agents should update the definitive representation of the canonical encyclopedia.
    *   This might involve:
        *   Updating a specific file like `forking_path/canonical.csv`.
        *   Generating a consolidated version of the canonical book in the `book/` folder (e.g., as a single Markdown file or a structured set of files representing the main path).
        *   Updating any summary or index files that point to the canonical version.

5.  **Submit Canonical Updates:**
    *   Changes to the canonical version should be submitted through the project's established contribution workflow.
    *   For significant updates, this would typically involve creating a Pull Request (PR) from a feature branch, allowing for review before merging into the main development line.
    *   Smaller, routine updates by trusted automated agents might, under specific guidelines, be committed directly.

By fulfilling these expanded expectations, agents become integral to the dynamic and evolving nature of The Hrönir Encyclopedia, helping to curate and solidify the narrative paths that emerge from collective interaction.

---
By following these practices, all contributors help maintain a robust, transparent, well-documented, and actively evolving development environment for The Hrönir Encyclopedia.
