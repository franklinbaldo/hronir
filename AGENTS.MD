# Agent Contributions and Generated Hrönirs

This document outlines the expectations for developers, contributors, and automated agents when generating hrönirs (chapters or chapter variants) as part of their work on The Hrönir Encyclopedia.

## Guiding Principle: Commit Your Creations

When an agent (human developer, tester, or automated script/AI) generates new hrönirs for any of the following purposes:

*   Testing core functionalities (e.g., `store`, `vote`, `audit` commands).
*   Demonstrating a new feature or workflow.
*   Fulfilling Proof-of-Work requirements for voting simulations.
*   Exploring narrative possibilities as part of an analysis.
*   Seeding the encyclopedia with initial or example content.

**It is expected that these generated hrönirs, along with any associated updates to `forking_path/*.csv` files, should be committed to the repository.**

## Rationale

Committing these hrönirs offers several benefits:

1.  **Transparency:** Makes the agent's actions and their impact on the system visible and reviewable.
2.  **Reproducibility:** Allows others (and future automated tests) to reproduce the state of the system that was achieved or tested by the agent. This is crucial for debugging and verifying fixes or new features.
3.  **Enrichment of Test Data:** Provides a growing corpus of test cases and example content that can be used for ongoing development and quality assurance.
4.  **Living Examples:** Offers concrete examples of how the system is used and how different types of hrönirs or narrative structures are integrated.
5.  **Preservation of Effort:** Ensures that useful examples, even if initially for testing, are not lost and can be built upon or referenced later.

## How to Commit

1.  **Use the `store` command:** Ensure all generated hrönirs are correctly processed using the `python -m hronir_encyclopedia.cli store <markdown_file> --prev <previous_hrönir_uuid>` command. This will place the hrönir into the `hronirs/` directory structure and (usually) update the relevant `forking_path/*.csv` file.
2.  **Identify changed files:** The `store` command will create new files under `hronirs/` (specifically an `index.md` and `metadata.json` within a UUID-derived path) and may modify files in `forking_path/`.
3.  **Stage and Commit:** Add these new/modified files to your Git commit. Use a descriptive commit message explaining the purpose of the generated hrönirs (e.g., Test: Add hrönirs for testing vote command PoW).

By following this practice, all contributors help maintain a robust, transparent, and well-documented development environment for The Hrönir Encyclopedia.
