# Contributing to The Hrönir Encyclopedia

Thank you for your interest in helping expand this labyrinthine narrative. This project grows chapter by chapter through community pull requests. The guidelines below describe how to structure your contributions and the review process.

## Style and Chapter Structure

- **Borgesian Tone**: Write in a concise, philosophical style with references, mirrors and metafictional hints. Each chapter should feel like a natural continuation of the themes introduced so far.
- **Markdown format**: All chapters are Markdown files.
- **File naming**: Create your chapter anywhere (e.g. `drafts/<position>_<variant>.md`). Use a two-digit numeric position and a lower case letter for the variant.
- **Heading**: Begin the file with a level-one heading `# Chapter <position>` followed by the variant letter.
- **Length**: Aim for roughly two to four short paragraphs (about 300–500 words total).
- **Cross references**: When appropriate, refer back to earlier chapters or motifs to preserve continuity.

## Pull Requests and Review

1. **Fork** this repository and create a branch for your chapter.
2. Run `pre-commit install` to set up the git hooks.
3. **Add your file** following the naming conventions above.
4. **Validate** locally (optional) using:
   ```bash
   python -m hronir_encyclopedia.cli validate --chapter drafts/<position>_<variant>.md
   ```
5. **Store** the chapter under `the_library/`:
   ```bash
   python -m hronir_encyclopedia.cli store drafts/<position>_<variant>.md --prev <previous_uuid>
   ```
6. **Commit** your change with a clear message, e.g. `Add 02_a chapter variant`.
7. **Open a pull request** on GitHub. Briefly describe your chapter and its relation to the narrative.
8. **Automated checks** will run to confirm basic formatting.
9. **Review** happens publicly; maintainers may request adjustments to tone or structure.
10. Once approved, your chapter is merged and enters the Elo ranking system.

### Helpful CLI commands

Remember to use `uv run` before `python -m hronir_encyclopedia.cli` if you are using the `uv` environment, as shown in the examples below.

Check the current Elo rankings for forks at a chapter position:
```bash
uv run python -m hronir_encyclopedia.cli ranking --position 1
```

To participate in the "Tribunal of the Future" (after creating a new hrönir and its `fork_uuid` at position `N`):

1.  **Start a Judgment Session:**
    Use your new `fork_uuid` (from position `N`) to start a session. This provides a `session_id` and a dossier of duels for prior positions.
    ```bash
    # Example: Your new fork at position N=3 is fork_N_uuid
    uv run python -m hronir_encyclopedia.cli session start \
      --position 3 \
      --fork-uuid <your_fork_N_uuid>
    ```

2.  **Deliberate and Form Veredicts (Offline):**
    Review the dossier. Decide which duels to vote on and select winners.

3.  **Commit Your Veredicts:**
    Submit your veredicts using the `session_id`.
    ```bash
    # Example: Committing veredicts for positions 2 and 0
    uv run python -m hronir_encyclopedia.cli session commit \
      --session-id <your_session_id> \
      --verdicts '{"2": "winning_fork_for_pos2", "0": "winning_fork_for_pos0"}'
    ```
    Refer to `README.md` for more details on the session workflow.

Validate and store your own new chapter variant (this is how you get a `fork_uuid` to start a session):
```bash
# First, validate the content (optional, but good practice)
uv run python -m hronir_encyclopedia.cli validate --chapter drafts/01_my_variant.md

# Then, store it to get a hrönir UUID.
# You also need to ensure a forking_path entry is created for this hrönir,
# which will define its `fork_uuid`. The `store` command may be enhanced in the future
# to streamline `fork_uuid` creation/reporting.
uv run python -m hronir_encyclopedia.cli store drafts/01_my_variant.md --prev <uuid_of_predecessor_hronir>
```

Happy writing—may your version prove itself the inevitable one.
