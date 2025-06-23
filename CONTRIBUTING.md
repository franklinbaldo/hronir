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

### How to Influence the Narrative

Your primary goal as a contributor is to create a high-quality hrönir whose fork becomes **`QUALIFIED`** in duels. Once qualified, you can use its `fork_uuid` to initiate a **Judgment Session** and influence the entire canon.

Remember to use `uv run` before `hronir_encyclopedia.cli` if you are using the `uv` environment.

1.  **Create and Store a High-Quality Hrönir:**
    Write your chapter (e.g., `drafts/05_my_masterpiece.md`). Then store it, specifying its predecessor to create the fork.
    ```bash
    uv run hronir_encyclopedia.cli store drafts/05_my_masterpiece.md --prev <previous_uuid>
    # Note the fork_uuid from the output, or find it in forking_path/*.csv
    ```
2.  **Monitor Your Fork's Performance:**
    Use `hronir ranking --position <your_fork_position>` to track its Elo rating and duel performance.
    ```bash
    uv run hronir_encyclopedia.cli ranking --position 5
    ```
3.  **Check for Qualification:**
    Use the `hronir metrics` command or inspect the `forking_path/<your_book_name>.csv` file. Look for your `fork_uuid` and check if its `status` has changed from `PENDING` to `QUALIFIED`.
    ```bash
    uv run hronir_encyclopedia.cli metrics
    # Or check the CSV directly.
    ```
4.  **Start Your Judgment Session:**
    Once your fork is `QUALIFIED`, use its `fork_uuid` to start a session.
    ```bash
    uv run hronir_encyclopedia.cli session start --fork-uuid <your_now_qualified_fork_uuid>
    # This will output a session_id and a dossier of duels.
    ```
5.  **Deliberate and Commit Your Veredicts:**
    Review the dossier. Then, submit your judgments using the `session_id`.
    ```bash
    uv run hronir_encyclopedia.cli session commit \
      --session-id <id_from_start> \
      --verdicts '{"4": "winning_fork_uuid_for_pos4", "1": "another_winning_fork_uuid_for_pos1"}'
    ```

Happy writing—may your version prove itself the inevitable one.
