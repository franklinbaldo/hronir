import json
import shutil
import subprocess
from pathlib import Path
from typing_extensions import Annotated # Use typing_extensions for compatibility

import typer

from . import database, gemini_util, ratings, storage

app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True, # Typer will handle shell completion
    no_args_is_help=True # Show help if no command is given
)

# Re-map old _cmd functions to new Typer command functions
# Original functions are kept with minimal changes to their core logic,
# only adapting their signatures to Typer's way of handling arguments.

@app.command(help="Consolidate chapter rankings and update the canonical book view.")
def consolidate_book(
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.", exists=True, file_okay=False, dir_okay=True, readable=True)] = Path("ratings"),
    library_dir: Annotated[Path, typer.Option(help="Directory containing all hrönirs.", exists=True, file_okay=False, dir_okay=True, readable=True)] = Path("the_library"),
    book_dir: Annotated[Path, typer.Option(help="Directory for the canonical book.", file_okay=False, dir_okay=True, writable=True)] = Path("book"),
    index_file: Annotated[Path, typer.Option(help="Path to the book index JSON file.", dir_okay=False, writable=True)] = Path("book/book_index.json"),
):
    """
    Analyzes chapter rankings and updates the canonical version of the book.
    """
    if not ratings_dir.is_dir():
        typer.echo(f"Ratings directory not found: {ratings_dir}", err=True)
        raise typer.Exit(code=1)

    try:
        book_index = (
            json.loads(index_file.read_text())
            if index_file.exists()
            else {"title": "The Hrönir Encyclopedia", "chapters": {}}
        )
    except json.JSONDecodeError:
        typer.echo(f"Error reading or parsing book index file: {index_file}", err=True)
        book_index = {"title": "The Hrönir Encyclopedia", "chapters": {}}

    updated_positions = 0
    for rating_file in ratings_dir.glob("position_*.csv"):
        try:
            position_str = rating_file.stem.split("_")[1]
            position = int(position_str)
        except (IndexError, ValueError):
            typer.echo(f"Could not parse position from rating file: {rating_file.name}", err=True)
            continue

        ranking_df = ratings.get_ranking(position, base=ratings_dir)
        if ranking_df.empty:
            typer.echo(f"No ranking data for position {position}.")
            continue

        winner_uuid = ranking_df.iloc[0]["uuid"]
        winner_elo = ranking_df.iloc[0]["elo"]

        if not storage.chapter_exists(winner_uuid, base=library_dir):
            typer.echo(f"Winner chapter {winner_uuid} for position {position} not found in library.", err=True)
            continue

        book_dir.mkdir(parents=True, exist_ok=True) # Ensure book_dir exists
        for old_file in book_dir.glob(f"{position}_*.md"):
            old_file.unlink()

        new_filename = f"{position}_{winner_uuid[:8]}.md"
        destination_path = book_dir / new_filename
        source_path = storage.uuid_to_path(winner_uuid, library_dir) / "index.md"

        try:
            shutil.copyfile(source_path, destination_path)
            book_index["chapters"][str(position)] = new_filename
            typer.echo(
                f"Position {position}: Set chapter {winner_uuid[:8]} (Elo: {winner_elo}) "
                f"as canonical. Copied to {destination_path}"
            )
            updated_positions += 1
        except Exception as e:
            typer.echo(f"Error copying chapter {winner_uuid} for position {position}: {e}", err=True)
            continue

    if updated_positions > 0:
        try:
            index_file.parent.mkdir(parents=True, exist_ok=True) # Ensure parent dir for index exists
            index_file.write_text(json.dumps(book_index, indent=2))
            typer.echo(f"Book index updated: {index_file}")
        except Exception as e:
            typer.echo(f"Error writing book index file: {e}", err=True)
    else:
        typer.echo("No positions were updated in the book index.")

    typer.echo("Book consolidation complete.")


# @app.command(help="Export the canonical book to a file.") # Command removed
# def export(
#     output_file: Annotated[Path, typer.Argument(help="Path to the output file (e.g., book.epub, book.pdf).", writable=True, dir_okay=False)],
#     format_str: Annotated[str, typer.Option("--format", "-f", help="Output format (e.g., epub, pdf, markdown). Requires Pandoc.")] = "epub",
#     index_file: Annotated[Path, typer.Option(help="Path to the book index JSON file.", exists=True, dir_okay=False, readable=True)] = Path("book/book_index.json"),
#     book_dir: Annotated[Path, typer.Option(help="Directory for the canonical book files.", exists=True, file_okay=False, dir_okay=True, readable=True)] = Path("book"),
# ):
#     """
#     Exports the canonical book from book_index.json and chapter files into a single output file.
#     """
#     try:
#         book_index = json.loads(index_file.read_text())
#     except json.JSONDecodeError:
#         typer.echo(f"Error reading or parsing book index file: {index_file}", err=True)
#         raise typer.Exit(code=1)

#     chapter_files = []
#     sorted_chapters = sorted(book_index.get("chapters", {}).items(), key=lambda x: int(x[0]))

#     if not sorted_chapters:
#         typer.echo("No chapters found in the book index.")
#         raise typer.Exit(code=1)

#     for position, filename in sorted_chapters:
#         chapter_path = book_dir / filename
#         if chapter_path.exists():
#             chapter_files.append(str(chapter_path))
#         else:
#             typer.echo(f"Warning: Chapter file {filename} for position {position} not found in {book_dir}.", err=True)

#     if not chapter_files:
#         typer.echo("No valid chapter files found to export.")
#         raise typer.Exit(code=1)

#     try:
#         # import pypandoc # This import would now be problematic
#         typer.echo(f"Exporting book to {output_file} in {format_str} format...")
#         output_file.parent.mkdir(parents=True, exist_ok=True)

#         # pypandoc.convert_files( # This call would now be problematic
#         #     chapter_files,
#         #     outputfile=str(output_file),
#         #     format=format_str,
#         #     extra_args=['--metadata', f'title="{book_index.get("title", "Hrönir Encyclopedia")}"']
#         # )
#         typer.echo(f"Book successfully exported to {output_file}")
#     except ImportError:
#         typer.echo("pypandoc is not installed. Please install it (and Pandoc itself) to use the export command.", err=True)
#         typer.echo("Pandoc installation: https://pandoc.org/installing.html", err=True)
#         raise typer.Exit(code=1)
#     except OSError as e:
#         if "No such file or directory: 'pandoc'" in str(e):
#             typer.echo("Pandoc executable not found. Please ensure Pandoc is installed and in your PATH.", err=True)
#             typer.echo("Installation instructions: https://pandoc.org/installing.html", err=True)
#         else:
#             typer.echo(f"An error occurred during export (OSError): {e}", err=True)
#         raise typer.Exit(code=1)
#     except Exception as e:
#         typer.echo(f"An unexpected error occurred during export: {e}", err=True)
#         raise typer.Exit(code=1)


@app.command(help="Print the chapter tree from the book index.")
def tree(
    index: Annotated[Path, typer.Option(help="Path to the book index JSON file.", exists=True, dir_okay=False, readable=True)] = Path("book/book_index.json"),
):
    """
    Displays the title and sorted chapter list from the book_index.json.
    """
    data = json.loads(index.read_text())
    typer.echo(data.get("title", "Hrönir Encyclopedia"))
    for pos, fname in sorted(data.get("chapters", {}).items(), key=lambda x: int(x[0])):
        typer.echo(f"{pos}: {fname}")


@app.command(help="Validate a chapter file (basic check).")
def validate(
    chapter: Annotated[Path, typer.Argument(help="Path to chapter markdown file.", exists=True, dir_okay=False, readable=True)],
):
    """
    Performs a basic validation check on a chapter file.
    Currently, just checks for existence.
    """
    # The original logic was just a print, keeping it simple.
    # More complex validation would go into storage.validate_or_move
    typer.echo(f"Chapter file {chapter} exists and is readable. Basic validation passed.")
    # For a more meaningful validation, one might call storage.validate_or_move or parts of it.


@app.command(help="Store a chapter by UUID in the library.")
def store(
    chapter: Annotated[Path, typer.Argument(help="Path to chapter markdown file.", exists=True, dir_okay=False, readable=True)],
    prev: Annotated[str, typer.Option(help="UUID of the previous chapter.")] = None, # Made optional as in original
):
    """
    Stores a given chapter file into the hrönir library, associating it with a predecessor UUID if provided.
    """
    uuid_str = storage.store_chapter(chapter, prev_uuid=prev)
    typer.echo(uuid_str)


@app.command(help="Record a duel result (vote).")
def vote(
    position: Annotated[int, typer.Option(help="Chapter position being voted on.")],
    voter: Annotated[str, typer.Option(help="UUID of the forking path or entity casting the vote.")],
    winner: Annotated[str, typer.Option(help="Winning chapter UUID.")],
    loser: Annotated[str, typer.Option(help="Losing chapter UUID.")],
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"), # Adicionado para determinar o duelo oficial
):
    """
    Records a vote for a winner against a loser for a given chapter position,
    only if the vote corresponds to the officially curated duel.
    """
    official_duel = ratings.determine_next_duel(position, base=ratings_dir)

    if not official_duel:
        typer.echo(json.dumps({
            "error": "Não foi possível determinar um duelo oficial para esta posição. Voto não pode ser validado.",
            "position": position
        }, indent=2))
        raise typer.Exit(code=1)

    official_hronir_A = official_duel.get("hronir_A")
    official_hronir_B = official_duel.get("hronir_B")

    # Normaliza o par submetido para comparação (ordem não importa)
    submitted_pair = set([winner, loser])
    official_pair = set([official_hronir_A, official_hronir_B])

    if submitted_pair != official_pair:
        typer.echo(json.dumps({
            "error": "Voto rejeitado. O par submetido não corresponde ao duelo curado oficialmente.",
            "submitted_duel": {"hronir_A": winner, "hronir_B": loser},
            "expected_duel": {"hronir_A": official_hronir_A, "hronir_B": official_hronir_B},
            "strategy": official_duel.get("strategy"),
            "position": position
        }, indent=2))
        raise typer.Exit(code=1)

    # Se a validação passar, registra o voto
    with database.open_database() as conn:
        ratings.record_vote(position, voter, winner, loser, conn=conn)
    typer.echo(json.dumps({
        "message": "Voto registrado. A incerteza do sistema foi reduzida.",
        "position": position,
        "winner": winner,
        "loser": loser,
        "voter": voter,
        "duel_strategy": official_duel.get("strategy")
    }, indent=2))


@app.command(help="Validate and repair storage, audit forking CSVs.")
def audit():
    """
    Performs audit operations: validates chapters in the book directory,
    moves invalid ones, and audits forking path CSV files.
    """
    book_dir = Path("book")
    typer.echo(f"Auditing book directory: {book_dir}...")
    for chapter_file in book_dir.glob("**/*.md"): # Corrected from 'chapter' to 'chapter_file'
        storage.validate_or_move(chapter_file) # Assuming this function prints its own status

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Auditing forking path directory: {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"): # Corrected from 'csv' to 'csv_file'
            storage.audit_forking_csv(csv_file) # Assuming this function prints its own status
    else:
        typer.echo(f"Forking path directory {fork_dir} not found. Skipping audit.")
    typer.echo("Audit complete.")


@app.command(help="Generate competing chapters from a predecessor and record an initial vote.")
def synthesize(
    position: Annotated[int, typer.Option(help="Chapter position for the new hrönirs.")],
    prev: Annotated[str, typer.Option(help="UUID of the predecessor chapter to fork from.")],
):
    """
    Synthesizes two new hrönirs from a predecessor for a given position
    and records an initial 'vote' or assessment by the generating agent.
    """
    typer.echo(
        f"Synthesizing two new hrönirs from predecessor '{prev}' "
        f"at position {position}..."
    )
    with database.open_database() as conn:
        voter_uuid = "00000000-agent-0000-0000-000000000000" # Example agent UUID
        winner_uuid = gemini_util.auto_vote(position, prev, voter_uuid, conn=conn)
    typer.echo(f"Synthesis complete. New canonical candidate: {winner_uuid}")


@app.command(help="Show Elo rankings for a chapter position.")
def ranking(
    position: Annotated[int, typer.Argument(help="The chapter position to rank.")],
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"),
):
    """
    Displays the Elo rankings for hrönirs at a specific chapter position.
    """
    # The 'base' argument for get_ranking was Path(base), so passing ratings_dir directly.
    ranking_data = ratings.get_ranking(position, base=ratings_dir)
    if ranking_data.empty:
        typer.echo(f"No ranking data found for position {position}.")
    else:
        typer.echo(f"Ranking for Position {position}:")
        # Typer automatically handles printing DataFrames nicely with rich if available,
        # otherwise, it falls back to standard print. For explicit control, use to_string().
        typer.echo(ranking_data.to_string(index=False))

@app.command(help="Obtém o duelo mais relevante para uma posição.")
def get_duel(
    position: Annotated[int, typer.Option(help="A posição do capítulo para a qual obter o duelo.")],
    ratings_dir: Annotated[Path, typer.Option(help="Diretório contendo arquivos CSV de classificação.")] = Path("ratings"),
):
    """
    Obtém o duelo mais relevante (calibração ou máxima entropia) para uma determinada posição.
    """
    duel_info = ratings.determine_next_duel(position, base=ratings_dir)
    if duel_info:
        # Adiciona a estrutura duel_pair para corresponder ao output de exemplo do plano
        output_data = {
            "position": duel_info.get("position"), # Pega de duel_info se existir
            "strategy": duel_info.get("strategy"),
            "entropy": duel_info.get("entropy"), # Pode ser None para calibração
            "duel_pair": {
                "hronir_A": duel_info.get("hronir_A"),
                "hronir_B": duel_info.get("hronir_B"),
            }
        }
        typer.echo(json.dumps(output_data, indent=2))
    else:
        typer.echo(json.dumps({"error": "Não foi possível determinar um duelo. Verifique se há hrönirs suficientes.", "position": position}, indent=2))


def _git_remove_deleted_files(): # Renamed to avoid conflict and be more descriptive
    """Stage deleted files in git if git is available and files were deleted."""
    try:
        # Check if we are in a git repository and git is installed
        subprocess.check_call(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        output = subprocess.check_output(["git", "ls-files", "--deleted"], text=True, stderr=subprocess.PIPE)
        if not output.strip():
            typer.echo("No deleted files to stage in Git.")
            return

        for path_str in output.splitlines():
            if path_str:
                typer.echo(f"Staging deleted file for removal in Git: {path_str}")
                subprocess.run(["git", "rm", "--ignore-unmatch", path_str], check=True)
        typer.echo("Staged deleted files in Git.")

    except FileNotFoundError:
        typer.echo("Git command not found. Skipping Git operations.", err=True)
    except subprocess.CalledProcessError as e:
        if "not a git repository" in e.stderr.lower():
             typer.echo("Not inside a Git repository. Skipping Git operations for deleted files.")
        else:
            typer.echo(f"Git ls-files or rm command failed: {e.stderr}", err=True)
    except Exception as e:
        typer.echo(f"An unexpected error occurred with Git operations: {e}", err=True)


@app.command(help="Remove invalid entries (fake hrönirs, votes, etc.) from storage.")
def clean(
    git_stage_deleted: Annotated[bool, typer.Option("--git", help="Also stage deleted files for removal in the Git index.")] = False,
):
    """
    Cleans up storage by removing entries identified as 'fake' or invalid.
    Optionally, stages these deletions in Git.
    """
    typer.echo("Starting cleanup process...")
    storage.purge_fake_hronirs() # Assumes this function prints its actions

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Cleaning fake forking CSVs in {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"):
            storage.purge_fake_forking_csv(csv_file) # Assumes this function prints its actions
    else:
        typer.echo(f"Forking path directory {fork_dir} not found. Skipping.")

    rating_dir = Path("ratings")
    if rating_dir.exists():
        typer.echo(f"Cleaning fake votes CSVs in {rating_dir}...")
        for csv_file in rating_dir.glob("*.csv"):
            storage.purge_fake_votes_csv(csv_file) # Assumes this function prints its actions
    else:
        typer.echo(f"Ratings directory {rating_dir} not found. Skipping.")

    if git_stage_deleted:
        typer.echo("Attempting to stage deleted files in Git...")
        _git_remove_deleted_files()

    typer.echo("Cleanup complete.")


# Placeholder for 'submit' command if it was meant to be kept.
# If not, it can be removed. For now, it's commented out as per original structure.
# @app.command(help="Submit changes (placeholder).")
# def submit_cmd():
#     typer.echo("Submit command is in development.")


def main(argv: list[str] | None = None):
    # If argv is None, Typer's app() will use sys.argv by default (which is what we want for CLI execution).
    # If argv is provided (e.g., from a test), app() will use that specific list of arguments.
    app(args=argv)

if __name__ == "__main__":
    main() # Called with no arguments, so app() will use sys.argv
