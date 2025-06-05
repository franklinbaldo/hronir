# Contributing to The Hrönir Encyclopedia

Thank you for your interest in helping expand this labyrinthine narrative. This project grows chapter by chapter through community pull requests. The guidelines below describe how to structure your contributions and the review process.

## Style and Chapter Structure

- **Borgesian Tone**: Write in a concise, philosophical style with references, mirrors and metafictional hints. Each chapter should feel like a natural continuation of the themes introduced so far.
- **Markdown format**: All chapters are Markdown files.
- **File naming**: Place your chapter at `book/<position>/<position>_<variant>.md` (e.g. `book/02/02_a.md`). Use a two-digit numeric position and a lower case letter for the variant.
- **Heading**: Begin the file with a level-one heading `# Chapter <position>` followed by the variant letter.
- **Length**: Aim for roughly two to four short paragraphs (about 300–500 words total).
- **Cross references**: When appropriate, refer back to earlier chapters or motifs to preserve continuity.

## Pull Requests and Review

1. **Fork** this repository and create a branch for your chapter.
2. **Add your file** following the naming conventions above.
3. **Validate** locally (optional) using:
   ```bash
   python -m hronir_encyclopedia.cli validate --chapter book/<position>/<position>_<variant>.md
   ```
4. **Commit** your change with a clear message, e.g. `Add 02_a chapter variant`.
5. **Open a pull request** on GitHub. Briefly describe your chapter and its relation to the narrative.
6. **Automated checks** will run to confirm basic formatting.
7. **Review** happens publicly; maintainers may request adjustments to tone or structure.
8. Once approved, your chapter is merged and enters the Elo ranking system.

Happy writing—may your version prove itself the inevitable one.
