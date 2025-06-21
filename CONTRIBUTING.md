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

Remember to use `uv run` before `python -m hronir_encyclopedia.cli` if you are using the `uv` environment.

Check the current Elo rankings for a chapter position:
```bash
uv run python -m hronir_encyclopedia.cli ranking --position 1
```

To participate in voting (after obtaining a `fork_uuid` as described in `docs/proof_of_work_voting.md`):

1.  Discover the most informative duel for a position:
    ```bash
    uv run python -m hronir_encyclopedia.cli get-duel --position 1
    ```
    This will output JSON indicating the `hronir_A` and `hronir_B` for the duel.

2.  Cast your vote for the presented duel:
    ```bash
    uv run python -m hronir_encyclopedia.cli vote \
      --position 1 \
      --voter <your_fork_uuid> \
      --winner <uuid_A_from_get_duel> \
      --loser <uuid_B_from_get_duel>
    ```

Generate two new hrönir variants from a predecessor and record an initial assessment (this is mainly for automated agents but can be used manually):
```bash
uv run python -m hronir_encyclopedia.cli synthesize \
  --position 1 \
  --prev <previous_uuid>
```

Validate and store your own new chapter variant:
```bash
uv run python -m hronir_encyclopedia.cli validate --chapter drafts/01_my_variant.md
uv run python -m hronir_encyclopedia.cli store drafts/01_my_variant.md --prev <previous_uuid>
```

Happy writing—may your version prove itself the inevitable one.
