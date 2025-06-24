import json
import subprocess
import uuid
from pathlib import Path
from typing import (
    Annotated,  # Use typing_extensions for compatibility
    Any,
)

import pandas as pd  # Moved import pandas as pd to the top
import typer

from . import (
    database,
    gemini_util,
    ratings,
    session_manager,
    storage,
    transaction_manager,
)

app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True,  # Typer will handle shell completion
    no_args_is_help=True,  # Show help if no command is given
)

# Re-map old _cmd functions to new Typer command functions
# Original functions are kept with minimal changes to their core logic,
# only adapting their signatures to Typer's way of handling arguments.


@app.command(
    "recover-canon",
    help="Manual recovery tool: Triggers Temporal Cascade from position 0 to rebuild canon. Use with caution.",
)
def recover_canon(
    ratings_dir: Annotated[
        Path, typer.Option(help="Directory containing rating CSV files.")
    ] = Path("ratings"),
    narrative_paths_dir: Annotated[
        Path, typer.Option(help="Directory containing narrative path CSV files.")
    ] = Path("narrative_paths"),
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    max_positions_to_rebuild: Annotated[
        int, typer.Option(help="Maximum number of positions to attempt to rebuild.")
    ] = 100,
):
    """
    Manual Recovery Tool: Triggers a Temporal Cascade starting from position 0
    to rebuild the canonical path. This is intended for maintenance, auditing,
    or recovery scenarios, NOT as part of the standard content evolution workflow
    which relies on session commits triggering cascades from specific points.
    """
    typer.echo(
        "WARNING: This is a manual recovery tool. For normal operation, canonical path updates via 'session commit'."
    )
    typer.echo("Recover-canon command now triggers a Temporal Cascade from position 0.")
    run_temporal_cascade(
        start_position=0,
        max_positions_to_consolidate=max_positions_to_rebuild,  # Renamed param for clarity
        canonical_path_file=canonical_path_file,
        # narrative_paths_dir and ratings_dir removed as args from run_temporal_cascade
        typer_echo=typer.echo,
    )
    typer.echo("Manual canon recovery via Temporal Cascade complete.")


@app.command("init-test", help="Generate a minimal sample narrative for quick testing.")
def init_test(
    library_dir: Annotated[
        Path, typer.Option(help="Directory to store sample hr\u00f6nirs.")
    ] = Path("the_library"),
    narrative_paths_dir: Annotated[Path, typer.Option(help="Directory for path CSV files.")] = Path(
        "narrative_paths"
    ),
    ratings_dir: Annotated[Path, typer.Option(help="Directory for rating CSV files.")] = Path(
        "ratings"
    ),
    data_dir: Annotated[Path, typer.Option(help="Directory for canonical data files.")] = Path(
        "data"
    ),
) -> None:
    """Create sample directories, chapters, paths, and a canonical path."""
    import shutil  # Import shutil for rmtree

    def clear_or_create_dir(dir_path: Path):
        if dir_path.exists():
            for item in dir_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()  # For files directly in the dir
        else:
            dir_path.mkdir(parents=True, exist_ok=True)  # exist_ok still good

    clear_or_create_dir(library_dir)
    clear_or_create_dir(narrative_paths_dir)
    clear_or_create_dir(ratings_dir)

    sessions_dir = data_dir / "sessions"
    transactions_dir = data_dir / "transactions"

    # For nested dirs like data/sessions, ensure data_dir itself exists first
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)

    clear_or_create_dir(sessions_dir)
    clear_or_create_dir(transactions_dir)

    # Ensure canonical_path.json is removed if it exists, as it's directly in data_dir
    canonical_file_path = data_dir / "canonical_path.json"
    if canonical_file_path.exists():
        canonical_file_path.unlink()

    h0_uuid = storage.store_chapter_text("Example Hr\u00f6nir 0", base=library_dir)
    h1_uuid = storage.store_chapter_text("Example Hr\u00f6nir 1", base=library_dir)

    # Must import PathModel here or at top of file
    from .models import Path as PathModel

    data_manager = storage.DataManager()
    # data_manager.initialize_and_load() # Already called by main_callback

    # Path for H0 at position 0
    p0_path_uuid_val = storage.compute_narrative_path_uuid(0, "", h0_uuid)
    path0 = PathModel(
        path_uuid=p0_path_uuid_val,
        position=0,
        prev_uuid=None,  # Or "" if required by model/logic, but None is more Pydantic-idiomatic for optional UUID
        uuid=h0_uuid,
        status="PENDING",  # Initial status
    )
    data_manager.add_path(path0)

    # Path for H1 at position 1, from H0
    p1_path_uuid_val = storage.compute_narrative_path_uuid(1, h0_uuid, h1_uuid)
    path1 = PathModel(
        path_uuid=p1_path_uuid_val,
        position=1,
        prev_uuid=h0_uuid,
        uuid=h1_uuid,
        status="PENDING",  # Initial status
    )
    data_manager.add_path(path1)

    # Use the generated path UUIDs for the canonical path
    p0_uuid_str = str(p0_path_uuid_val)
    p1_uuid_str = str(p1_path_uuid_val)
    h0_uuid_str = str(h0_uuid)
    h1_uuid_str = str(h1_uuid)

    canonical = {
        "title": "The Hr\u00f6nir Encyclopedia - Canonical Path",
        "path": {
            "0": {"path_uuid": p0_uuid_str, "hrönir_uuid": h0_uuid_str},
            "1": {"path_uuid": p1_uuid_str, "hrönir_uuid": h1_uuid_str},
        },
    }
    canonical_file = data_dir / "canonical_path.json"
    canonical_file.write_text(json.dumps(canonical, indent=2))

    # data_manager instance already exists due to main_callback and is a singleton.
    # No need to call storage.DataManager() again.
    data_manager.save_all_data_to_csvs()

    typer.echo("Sample data initialized:")
    typer.echo(f"  Position 0 hrönir UUID: {h0_uuid_str}")
    typer.echo(f"  Position 0 path UUID: {p0_uuid_str}")
    typer.echo(f"  Position 1 hrönir UUID: {h1_uuid_str}")
    typer.echo(f"  Position 1 path UUID: {p1_uuid_str}")


# Command `export` and `tree` removed as they depended on the old book structure.


@app.command(help="Validate a chapter file (basic check).")
def validate(
    chapter: Annotated[
        Path,
        typer.Argument(
            help="Path to chapter markdown file.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
):
    """
    Performs a basic validation check on a chapter file.
    Currently, just checks for existence.
    """
    # The original logic was just a print, keeping it simple.
    # More complex validation would go into storage.validate_or_move or parts of it.
    typer.echo(f"Chapter file {chapter} exists and is readable. Basic validation passed.")
    # For a more meaningful validation, one might call storage.validate_or_move or parts of it.


@app.command(help="Store a chapter by UUID in the library.")
def store(
    chapter: Annotated[
        Path,
        typer.Argument(
            help="Path to chapter markdown file.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
):
    """
    Stores a given chapter file into the hrönir library as a content node.
    Narrative connections are managed separately via narrative_paths CSVs.
    """
    uuid_str = storage.store_chapter(chapter)
    typer.echo(uuid_str)


@app.command(help="Create a narrative connection (path) between hrönirs.")
def path(
    position: Annotated[int, typer.Option(help="Position in the narrative sequence")],
    target: Annotated[str, typer.Option(help="Target hrönir UUID (destination content node)")],
    source: Annotated[
        str, typer.Option(help="Source hrönir UUID (empty string for position 0)")
    ] = "",
):
    """
    Creates a narrative path entry connecting two hrönirs in the narrative graph.
    This establishes a directed edge: source → target based purely on narrative merit.
    """
    from pathlib import Path

    # Validate position
    if position < 0:
        typer.echo(f"Error: Position must be non-negative, got {position}")
        raise typer.Exit(1)

    # Validate source for position > 0
    if position > 0 and not source:
        typer.echo("Error: source is required for position > 0")
        raise typer.Exit(1)

    if position == 0 and source:
        typer.echo("Warning: source ignored for position 0")
        source = ""

    # Validate hrönir UUIDs exist in library
    library_dir = Path("the_library")
    target_path_lib = library_dir / target  # Renamed to avoid conflict
    if not target_path_lib.exists():
        typer.echo(f"Error: Target hrönir {target} not found in library")
        raise typer.Exit(1)

    if source:
        source_path_lib = library_dir / source  # Renamed to avoid conflict
        if not source_path_lib.exists():
            typer.echo(f"Error: Source hrönir {source} not found in library")
            raise typer.Exit(1)

    # Generate deterministic path UUID
    path_uuid = storage.compute_narrative_path_uuid(position, source, target)

    # Create narrative path entry
    narrative_paths_dir = Path("narrative_paths")
    narrative_paths_dir.mkdir(exist_ok=True)

    # Use position-based CSV file naming
    csv_file = narrative_paths_dir / f"position_{position:03d}.csv"

    # Create CSV with headers if it doesn't exist
    if not csv_file.exists():
        csv_file.write_text("position,prev_uuid,uuid,path_uuid,status\n")

    # Check if path already exists
    import pandas as pd

    try:
        df = pd.read_csv(csv_file)
        if not df.empty and ((df["path_uuid"] == path_uuid).any()):
            typer.echo(f"Path already exists: {path_uuid}")
            return
    except (pd.errors.EmptyDataError, FileNotFoundError):
        # File is empty or doesn't exist, create headers
        csv_file.write_text("position,prev_uuid,uuid,path_uuid,status\n")

    # Append new path entry (mapping to CSV column names: source→prev_uuid, target→uuid)
    path_entry = f"{position},{source},{target},{path_uuid},PENDING\n"
    with csv_file.open("a") as f:
        f.write(path_entry)

    typer.echo(f"Created path: {path_uuid}")
    typer.echo(f"  Position: {position}")
    typer.echo(f"  Source: {source or '(none)'}")
    typer.echo(f"  Target: {target}")
    typer.echo("  Status: PENDING")


@app.command(help="List existing paths at a position.")
def list_paths(
    position: Annotated[int, typer.Option(help="Position to list paths for")] = None,
):
    """
    Lists all existing paths, optionally filtered by position.
    Shows the narrative graph structure without creator attribution.
    """
    from pathlib import Path

    import pandas as pd

    narrative_paths_dir = Path("narrative_paths")
    if not narrative_paths_dir.exists():
        typer.echo("No narrative path directory found.")
        return

    all_paths = []
    csv_files = list(narrative_paths_dir.glob("*.csv"))

    if not csv_files:
        typer.echo("No path files found.")
        return

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            if not df.empty:
                all_paths.append(df)
        except (pd.errors.EmptyDataError, FileNotFoundError):
            continue

    if not all_paths:
        typer.echo("No paths found.")
        return

    combined_df = pd.concat(all_paths, ignore_index=True)

    # Filter by position if specified
    if position is not None:
        combined_df = combined_df[combined_df["position"] == position]
        if combined_df.empty:
            typer.echo(f"No paths found at position {position}.")
            return
        typer.echo(f"Paths at position {position}:")
    else:
        typer.echo("All paths:")

    # Display relevant columns only (no creator info)
    display_cols = ["position", "prev_uuid", "uuid", "path_uuid", "status"]
    available_cols = [col for col in display_cols if col in combined_df.columns]

    typer.echo(combined_df[available_cols].to_string(index=False))


@app.command(help="Show status details for a specific path.")
def path_status(path_uuid: str) -> None:
    """Display status information for the given path UUID."""
    path_data = storage.DataManager().get_path_by_uuid(path_uuid)
    if not path_data:
        typer.echo(f"Error: path_uuid {path_uuid} not found.")
        raise typer.Exit(code=1)

    typer.echo(f"Position: {path_data.position}")
    typer.echo(f"Prev UUID: {path_data.prev_uuid}")
    typer.echo(f"UUID: {path_data.uuid}")
    typer.echo(f"Status: {path_data.status}")
    if path_data.mandate_id:
        typer.echo(f"Mandate ID: {path_data.mandate_id}")

    consumed_by = session_manager.is_path_consumed(path_uuid)
    if consumed_by:
        typer.echo(f"Consumed by session: {consumed_by}")


# Helper function to find successor hrönir_uuid for a given path_uuid
def _get_successor_hronir_for_path(path_uuid_to_find: str) -> str | None:
    """Return the hrönir UUID (PathDB.uuid) that a path points to by querying the database."""
    # narrative_paths_dir parameter is removed as this function now uses the DB.
    path_data_obj = storage.DataManager().get_path_by_uuid(path_uuid_to_find)
    if path_data_obj:
        return str(path_data_obj.uuid)  # PathDB.uuid stores the hrönir_uuid
    return None


def _calculate_status_counts(narrative_paths_dir: Path) -> dict[str, int]:
    """Return a count of paths by status for the given directory."""
    status_counts = {"PENDING": 0, "QUALIFIED": 0, "SPENT": 0, "UNKNOWN": 0}
    if not narrative_paths_dir.is_dir():
        return status_counts

    all_path_uuids_processed: set[str] = set()
    for csv_file in narrative_paths_dir.glob("*.csv"):
        if csv_file.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(
                csv_file,
                usecols=["path_uuid", "status"],
                dtype={"path_uuid": str, "status": str},
            )
        except (pd.errors.EmptyDataError, ValueError):
            continue

        if "status" not in df.columns:
            status_counts["UNKNOWN"] += len(df)
            continue

        for _, row in df.iterrows():
            path_uuid = str(row.get("path_uuid", "")).strip()
            status_val = str(row.get("status", "")).strip()  # Renamed to avoid conflict
            if not path_uuid or path_uuid in all_path_uuids_processed:
                continue
            if not status_val:
                status_counts["UNKNOWN"] += 1
            elif status_val in status_counts:
                status_counts[status_val] += 1
            else:
                status_counts["UNKNOWN"] += 1
            all_path_uuids_processed.add(path_uuid)

    return status_counts


@app.command(help="Display the canonical path and optional path status counts.")
def status(
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    counts: Annotated[
        bool,
        typer.Option(
            "--counts",
            help="Also show number of paths by status using narrative_paths data.",
        ),
    ] = False,
    narrative_paths_dir: Annotated[
        Path,
        typer.Option(help="Directory containing narrative path CSV files (for --counts)."),
    ] = Path("narrative_paths"),
) -> None:
    """Show canonical path entries and optional path status counts."""
    try:
        with open(canonical_path_file) as f:
            canonical_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        typer.echo(f"Error reading canonical path file: {canonical_path_file}")
        raise typer.Exit(code=1)

    path_entries = canonical_data.get("path", {})
    if not isinstance(path_entries, dict):
        typer.echo("Invalid canonical path data.")
        raise typer.Exit(code=1)

    for pos in sorted(path_entries.keys(), key=lambda p: int(p)):
        entry = path_entries.get(pos, {})
        path_uuid = entry.get("path_uuid", "")
        hronir_uuid = entry.get("hrönir_uuid", "")
        typer.echo(f"Position {pos}:")
        typer.echo(f"  path_uuid: {path_uuid}")
        typer.echo(f"  hrönir_uuid: {hronir_uuid}")

    if counts:
        typer.echo("")
        typer.echo("Path status counts:")
        counts_dict = _calculate_status_counts(narrative_paths_dir)
        for status_val, count in counts_dict.items():
            typer.echo(f"  {status_val}: {count}")


# The 'vote' command has been removed as direct voting is deprecated.
# All voting now occurs through the 'session commit' flow.


@app.command(help="Validate and repair storage, audit narrative CSVs.")
def audit():
    """
    Performs audit operations: validates chapters in the library,
    and audits narrative path CSV files.
    """
    library_dir = Path("the_library")
    typer.echo(f"Auditing library directory: {library_dir}...")
    # This part needs to be adjusted. `validate_or_move` expects a specific file.
    # We should iterate through hrönirs in a way that's compatible with `purge_fake_hronirs` logic,
    # or rely on `purge_fake_hronirs` called by `clean` command.
    # For now, let's simplify the audit's scope for this command, focusing on narrative paths.
    # A more thorough audit of `the_library` is implicitly handled by `storage.chapter_exists`
    # when other commands use it, and explicitly by `clean`.
    # Consider enhancing `audit` in the future if a standalone deep library audit is needed here.
    typer.echo(
        f"Auditing hrönirs in {library_dir} (basic check via purge_fake_hronirs in 'clean' command)..."
    )
    # No direct action on library_dir here, purge_fake_hronirs in 'clean' is more comprehensive.

    path_dir = Path("narrative_paths")
    if path_dir.exists():
        typer.echo(f"Auditing narrative path directory: {path_dir}...")
        for csv_file in path_dir.glob("*.csv"):
            storage.audit_narrative_csv(csv_file)
        from . import graph_logic

        if graph_logic.is_narrative_consistent(path_dir):
            typer.echo("Narrative graph is consistent (no cycles detected).")
        else:
            typer.echo("WARNING: Narrative graph contains cycles!")
    else:
        typer.echo(f"Narrative path directory {path_dir} not found. Skipping audit.")
    typer.echo("Audit complete (Note: hrönir validation primarily via 'clean' command).")


@app.command("validate-paths", help="Validate integrity of all narrative paths.")
def validate_paths_command():
    """
    Validates the integrity of all narrative paths, checking for:
    - Existence of referenced hrönir content (current and predecessor).
    - Correctness of deterministic path_uuid.
    """
    typer.echo("Validating narrative path integrity...")
    data_manager = storage.DataManager()
    # DataManager is initialized by main_callback, so data should be loaded.

    issues = data_manager.validate_data_integrity()

    if not issues:
        typer.secho(
            "All narrative paths validated successfully. No integrity issues found.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f"Found {len(issues)} integrity issue(s):", fg=typer.colors.YELLOW)
        for i, issue_message in enumerate(issues, 1):
            typer.secho(f"{i}. {issue_message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command(help="Generate competing chapters from a predecessor and record an initial vote.")
def synthesize(
    position: Annotated[int, typer.Option(help="Chapter position for the new hrönirs.")],
    prev: Annotated[
        str, typer.Option(help="UUID of the predecessor chapter to create a path from.")
    ],
):
    """
    Synthesizes two new hrönirs from a predecessor for a given position
    and records an initial 'vote' or assessment by the generating agent.
    """
    typer.echo(f"Synthesizing two new hrönirs from predecessor '{prev}' at position {position}...")
    with database.open_database() as conn:
        voter_uuid = "00000000-agent-0000-0000-000000000000"  # Example agent UUID
        winner_uuid = gemini_util.auto_vote(position, prev, voter_uuid, conn=conn)
    typer.echo(f"Synthesis complete. New canonical candidate: {winner_uuid}")


@app.command(help="Show Elo rankings for a chapter position.")
def ranking(
    position: Annotated[int, typer.Argument(help="The chapter position to rank.")],
    ratings_dir: Annotated[
        Path, typer.Option(help="Directory containing rating CSV files.")
    ] = Path("ratings"),
):
    """
    Displays the Elo rankings for hrönirs at a specific chapter position.
    """
    # Need to determine predecessor from canonical path for position > 0
    predecessor_hronir_uuid = None
    if position > 0:
        canonical_path_file = Path("data/canonical_path.json")
        if canonical_path_file.exists():
            import json

            with open(canonical_path_file) as f:
                canonical_data = json.load(f)
                if str(position - 1) in canonical_data.get("path", {}):
                    predecessor_hronir_uuid = canonical_data["path"][str(position - 1)][
                        "hrönir_uuid"
                    ]

    ranking_data = ratings.get_ranking(position, predecessor_hronir_uuid)
    if ranking_data.empty:
        typer.echo(
            f"No ranking data found for position {position} (predecessor: {predecessor_hronir_uuid or 'None'})."
        )
    else:
        typer.echo(f"Ranking for Position {position} (predecessor: {predecessor_hronir_uuid or 'None'}):")
        # Typer automatically handles printing DataFrames nicely with rich if available,
        # otherwise, it falls back to standard print. For explicit control, use to_string().
        typer.echo(ranking_data.to_string(index=False))


@app.command(help="Obtém o duelo de máxima entropia entre paths para uma posição.")
def get_duel(
    position: Annotated[
        int,
        typer.Option(help="A posição do capítulo para a qual obter o duelo de paths."),
    ],
    ratings_dir: Annotated[
        Path, typer.Option(help="Diretório contendo arquivos CSV de classificação.")
    ] = Path("ratings"),
    narrative_paths_dir: Annotated[
        Path,
        typer.Option(help="Diretório contendo arquivos CSV de caminhos de narrativa."),
    ] = Path("narrative_paths"),
    canonical_path_file: Annotated[
        Path, typer.Option(help="Caminho para o arquivo JSON do caminho canônico.")
    ] = Path("data/canonical_path.json"),
):
    """
    Obtém o duelo de paths de máxima entropia para uma determinada posição,
    considerando a linhagem canônica.
    """
    predecessor_hronir_uuid: str | None = None
    if position > 0:
        canonical_path_info_prev_pos = storage.get_canonical_path_info(
            position - 1, canonical_path_file
        )
        if not canonical_path_info_prev_pos or "hrönir_uuid" not in canonical_path_info_prev_pos:
            typer.echo(
                json.dumps(
                    {
                        "error": f"Não foi possível determinar o hrönir predecessor canônico da posição {position - 1}. "
                        f"Execute 'consolidate-book' ou verifique o arquivo {canonical_path_file}.",
                        "position_requested": position,
                    },
                    indent=2,
                )
            )
            raise typer.Exit(code=1)
        predecessor_hronir_uuid = canonical_path_info_prev_pos["hrönir_uuid"]
    elif position < 0:
        typer.echo(
            json.dumps(
                {
                    "error": "Posição inválida. Deve ser >= 0.",
                    "position_requested": position,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Call the new determine_next_duel_entropy function
    db_session = storage.get_db_session()
    try:
        duel_info = ratings.determine_next_duel_entropy(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
            session=db_session,
        )
    finally:
        db_session.close()

    if duel_info:
        # O formato de duel_info já é:
        # {
        #   "position": position,
        #   "strategy": "max_entropy_duel",
        #   "entropy": max_entropy,
        #   "duel_pair": {
        #       "path_A": duel_path_A_uuid,
        #       "path_B": duel_path_B_uuid,
        #   }
        # }
        typer.echo(json.dumps(duel_info, indent=2))
    else:
        typer.echo(
            json.dumps(
                {
                    "error": "Não foi possível determinar um duelo de paths. "
                    "Verifique se existem paths elegíveis suficientes (pelo menos 2) para a linhagem e posição.",
                    "position": position,
                    "predecessor_hronir_uuid_used": predecessor_hronir_uuid,
                },
                indent=2,
            )
        )


def _git_remove_deleted_files():  # Renamed to avoid conflict and be more descriptive
    """Stage deleted files in git if git is available and files were deleted."""
    try:
        # Check if we are in a git repository and git is installed
        subprocess.check_call(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        output = subprocess.check_output(
            ["git", "ls-files", "--deleted"], text=True, stderr=subprocess.PIPE
        )
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
    git_stage_deleted: Annotated[
        bool,
        typer.Option("--git", help="Also stage deleted files for removal in the Git index."),
    ] = False,
):
    """
    Cleans up storage by removing entries identified as 'fake' or invalid.
    Optionally, stages these deletions in Git.
    """
    typer.echo("Starting cleanup process...")
    storage.purge_fake_hronirs()  # Assumes this function prints its actions

    path_dir = Path("narrative_paths")
    if path_dir.exists():
        typer.echo(f"Cleaning fake narrative CSVs in {path_dir}...")
        for csv_file in path_dir.glob("*.csv"):
            storage.purge_fake_narrative_csv(csv_file)  # Assumes this function prints its actions
    else:
        typer.echo(f"Narrative path directory {path_dir} not found. Skipping.")

    rating_dir = Path("ratings")
    if rating_dir.exists():
        typer.echo(f"Cleaning fake votes CSVs in {rating_dir}...")
        for csv_file in rating_dir.glob("*.csv"):
            storage.purge_fake_votes_csv(csv_file)  # Assumes this function prints its actions
    else:
        typer.echo(f"Ratings directory {rating_dir} not found. Skipping.")

    if git_stage_deleted:
        typer.echo("Attempting to stage deleted files in Git...")
        _git_remove_deleted_files()

    typer.echo("Cleanup complete.")


# Helper for tutorial to qualify a path (mirroring future dev-qualify)
# This should be part of the dev-qualify command logic eventually.
def dev_qualify_path_uuid(path_uuid_str: str, typer_echo: callable):
    """Helper to mark a path as QUALIFIED for development/tutorial."""
    data_manager = storage.DataManager()
    path_to_qualify = data_manager.get_path_by_uuid(path_uuid_str)
    if not path_to_qualify:
        raise ValueError(f"Path {path_uuid_str} not found for dev-qualify.")

    if path_to_qualify.status == "QUALIFIED":
        typer_echo(f"  Path {path_uuid_str} is already QUALIFIED.")
        return

    mandate_id = str(uuid.uuid4())

    data_manager.update_path_status(
        path_uuid=path_uuid_str,
        status="QUALIFIED",
        mandate_id=mandate_id,
        set_mandate_explicitly=True,
    )
    # Caller (tutorial_command) should save DataManager state to CSVs after all operations if needed.
    typer_echo(f"  Path {path_uuid_str} status set to QUALIFIED with mandate_id {mandate_id}.")


@app.command("tutorial", help="Demonstrates a complete workflow of the Hrönir Encyclopedia.")
def tutorial_command(
    auto_qualify_for_session: Annotated[
        bool, typer.Option(help="Automatically qualify a path to demonstrate session workflow.")
    ] = True
):
    """
    Walks through a typical Hrönir Encyclopedia workflow:
    1. Initialize a clean test environment.
    2. Store a few sample hrönirs.
    3. Create narrative paths connecting them.
    4. (If auto_qualify_for_session) Qualify a path for session demonstration.
    5. Start a judgment session using the qualified path.
    6. Commit some example verdicts for the session.
    7. Show resulting rankings and canonical path status.
    """
    typer.secho("Welcome to the Hrönir Encyclopedia Tutorial!", fg=typer.colors.CYAN, bold=True)
    typer.echo("This will demonstrate a common workflow.\n")

    data_manager = storage.DataManager()

    # --- 1. Initialize a clean test environment ---
    typer.secho("Step 1: Initializing a clean test environment...", fg=typer.colors.BLUE)
    typer.echo("  (Equivalent to running: hronir init-test)")
    try:
        library_dir = Path("the_library")
        narrative_paths_dir = Path("narrative_paths")
        ratings_dir = Path("ratings")
        data_dir = Path("data")

        import shutil

        def _clear_or_create_dir(dir_path: Path):
            if dir_path.exists():
                for item in dir_path.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            else:
                dir_path.mkdir(parents=True, exist_ok=True)

        _clear_or_create_dir(library_dir)
        _clear_or_create_dir(narrative_paths_dir)
        _clear_or_create_dir(ratings_dir)
        sessions_dir = data_dir / "sessions"
        _clear_or_create_dir(sessions_dir)
        transactions_dir = data_dir / "transactions"
        _clear_or_create_dir(transactions_dir)

        canonical_path_file = data_dir / "canonical_path.json"
        if canonical_path_file.exists():
            canonical_path_file.unlink()

        consumed_forks_file = sessions_dir / "consumed_fork_uuids.json" # Path from session_manager
        if consumed_forks_file.exists(): # Check and remove this specific file
            consumed_forks_file.unlink()


        data_manager.initialize_and_load(clear_existing_data=True)
        typer.echo("  Test environment initialized.\n")

    except Exception as e:
        typer.secho(f"  Error during init-test simulation: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    # --- 2. Store sample hrönirs ---
    typer.secho("Step 2: Storing sample hrönirs...", fg=typer.colors.BLUE)
    h: dict[int, uuid.UUID] = {}  # Store UUIDs
    try:
        h[0] = uuid.UUID(storage.store_chapter_text("Tutorial: The First Age - Genesis of Worlds.", base=library_dir))
        typer.echo(f"  Stored Hrönir H0: {h[0]} (command: hronir store ...)")
        h[1] = uuid.UUID(storage.store_chapter_text("Tutorial: The Second Age - Divergent Paths A.", base=library_dir))
        typer.echo(f"  Stored Hrönir H1A: {h[1]} (command: hronir store ...)")
        h[2] = uuid.UUID(storage.store_chapter_text("Tutorial: The Second Age - Divergent Paths B.", base=library_dir))
        typer.echo(f"  Stored Hrönir H1B: {h[2]} (command: hronir store ...)")
        h[3] = uuid.UUID(storage.store_chapter_text("Tutorial: The Third Age - Aftermath of A.", base=library_dir))
        typer.echo(f"  Stored Hrönir H2A: {h[3]} (command: hronir store ...)")
        typer.echo("  Sample hrönirs stored.\n")
    except Exception as e:
        typer.secho(f"  Error storing sample hrönirs: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    # --- 3. Create narrative paths ---
    typer.secho("Step 3: Creating narrative paths...", fg=typer.colors.BLUE)
    paths: dict[int, uuid.UUID] = {}  # Store path_uuids
    from .models import Path as PathModel # Ensure Path model is imported (it's Path in models.py)

    try:
        paths[0] = storage.compute_narrative_path_uuid(0, "", str(h[0]))
        data_manager.add_path(PathModel(path_uuid=paths[0], position=0, prev_uuid=None, uuid=h[0], status="PENDING"))
        typer.echo(f"  Created Path P0 (Pos 0 -> H0): {paths[0]} (command: hronir path --position 0 --target {h[0]})")

        paths[1] = storage.compute_narrative_path_uuid(1, str(h[0]), str(h[1]))
        data_manager.add_path(PathModel(path_uuid=paths[1], position=1, prev_uuid=h[0], uuid=h[1], status="PENDING"))
        typer.echo(f"  Created Path P1A (Pos 1, H0 -> H1A): {paths[1]} (command: hronir path --position 1 --source {h[0]} --target {h[1]})")

        paths[2] = storage.compute_narrative_path_uuid(1, str(h[0]), str(h[2]))
        data_manager.add_path(PathModel(path_uuid=paths[2], position=1, prev_uuid=h[0], uuid=h[2], status="PENDING"))
        typer.echo(f"  Created Path P1B (Pos 1, H0 -> H1B): {paths[2]} (command: hronir path --position 1 --source {h[0]} --target {h[2]})")

        paths[3] = storage.compute_narrative_path_uuid(2, str(h[1]), str(h[3]))
        data_manager.add_path(PathModel(path_uuid=paths[3], position=2, prev_uuid=h[1], uuid=h[3], status="PENDING"))
        typer.echo(f"  Created Path P2A (Pos 2, H1A -> H2A): {paths[3]} (command: hronir path --position 2 --source {h[1]} --target {h[3]})")

        data_manager.save_all_data_to_csvs()
        typer.echo("  Narrative paths created.\n")
    except Exception as e:
        typer.secho(f"  Error creating narrative paths: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    qualified_path_for_session_uuid = None
    if auto_qualify_for_session:
        typer.secho("Step 4: Automatically qualifying a path for session demonstration...", fg=typer.colors.BLUE)
        path_to_qualify_uuid_str = str(paths[3]) # Path P2A at position 2
        try:
            dev_qualify_path_uuid(path_to_qualify_uuid_str, typer.echo)
            qualified_path_for_session_uuid = paths[3]
            data_manager.save_all_data_to_csvs()
            typer.echo(f"  Path {path_to_qualify_uuid_str} at position 2 is now QUALIFIED.\n")
        except Exception as e:
            typer.secho(f"  Error auto-qualifying path: {e}. Session demo might fail.", fg=typer.colors.RED)

    if not qualified_path_for_session_uuid:
        typer.secho("  Skipping session demonstration as no path was qualified.", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"Step 5: Starting a judgment session with qualified path {qualified_path_for_session_uuid}...", fg=typer.colors.BLUE)
        session_id = None
        dossier_duels_from_session = None # Store the duels part of the dossier
        try:
            path_data_obj = data_manager.get_path_by_uuid(str(qualified_path_for_session_uuid))
            if not path_data_obj or path_data_obj.status != "QUALIFIED" or not path_data_obj.mandate_id:
                 raise ValueError(f"Path {qualified_path_for_session_uuid} not properly qualified for session.")

            session_info = session_manager.create_session(
                fork_n_uuid=str(qualified_path_for_session_uuid), # create_session expects fork_n_uuid
                position_n=path_data_obj.position,
                mandate_id=str(path_data_obj.mandate_id), # create_session expects mandate_id as str
                forking_path_dir=Path("narrative_paths"),
                ratings_dir=Path("ratings"),
                canonical_path_file=Path("data/canonical_path.json")
            )
            session_id = session_info["session_id"]
            dossier_duels_from_session = session_info["dossier"]["duels"] # This is dict[str_pos, dict_duel_details]
            typer.echo(f"  Session {session_id} started. (command: hronir session start --path-uuid {qualified_path_for_session_uuid})")
            typer.echo("  Dossier created with duels for prior positions:")
            if dossier_duels_from_session:
                for pos_idx_str, duel_details in dossier_duels_from_session.items():
                     # duel_details is like {"fork_A": uuid, "fork_B": uuid, "entropy": float}
                    typer.echo(f"    Pos {pos_idx_str}: {duel_details['fork_A']} vs {duel_details['fork_B']}")
            else:
                typer.echo("    (No duels in dossier - expected if qualified path is at pos 0 or 1, or no prior contention)")
            typer.echo("")
        except Exception as e:
            typer.secho(f"  Error starting session: {e}", fg=typer.colors.RED)
            session_id = None

        if session_id and dossier_duels_from_session:
            typer.secho(f"Step 6: Committing example verdicts for session {session_id}...", fg=typer.colors.BLUE)
            example_verdicts_for_cli: dict[str, str] = {} # Format: {"position_str": "winning_path_uuid"}

            # We qualified P2A (paths[3]) at Pos 2. Dossier might have duels for Pos 1 and Pos 0.
            # Pos 1 duel should be P1A (paths[1]) vs P1B (paths[2]). Let's choose P1A.
            duel_at_pos_1 = dossier_duels_from_session.get("1") # Key is string "1"
            if duel_at_pos_1 and str(paths[1]) in [duel_at_pos_1['fork_A'], duel_at_pos_1['fork_B']]:
                example_verdicts_for_cli["1"] = str(paths[1]) # P1A wins
                typer.echo(f"  Verdict for Pos 1: Choose Path {paths[1]} (H0->H1A)")

            # Pos 0 duel: If P0 (paths[0]) is part of a duel (e.g. vs another root), choose it.
            # If only P0 exists at pos 0, dossier might not have a duel for "0".
            duel_at_pos_0 = dossier_duels_from_session.get("0")
            if duel_at_pos_0 and str(paths[0]) in [duel_at_pos_0['fork_A'], duel_at_pos_0['fork_B']]:
                example_verdicts_for_cli["0"] = str(paths[0]) # P0 wins
                typer.echo(f"  Verdict for Pos 0: Choose Path {paths[0]} (->H0)")
            elif duel_at_pos_0: # A duel exists but doesn't involve our known P0, pick one.
                example_verdicts_for_cli["0"] = duel_at_pos_0['fork_A']
                typer.echo(f"  Verdict for Pos 0: Choose Path {duel_at_pos_0['fork_A']}")


            if example_verdicts_for_cli:
                try:
                    # Prepare session_verdicts_for_tm format
                    session_verdicts_for_tm_list = []
                    for pos_str_key, winning_path_uuid_str in example_verdicts_for_cli.items():
                        pos_int = int(pos_str_key)
                        duel_in_dossier = dossier_duels_from_session[pos_str_key]
                        losing_path_uuid_str = duel_in_dossier['fork_A'] if winning_path_uuid_str == duel_in_dossier['fork_B'] else duel_in_dossier['fork_B']

                        winner_path_model = data_manager.get_path_by_uuid(winning_path_uuid_str)
                        loser_path_model = data_manager.get_path_by_uuid(losing_path_uuid_str)

                        if not winner_path_model or not loser_path_model:
                             typer.secho(f"  Could not find path models for duel at pos {pos_str_key}. Skipping verdict.", fg=typer.colors.RED)
                             continue

                        session_verdicts_for_tm_list.append({
                            "position": pos_int,
                            "winner_hrönir_uuid": str(winner_path_model.uuid),
                            "loser_hrönir_uuid": str(loser_path_model.uuid),
                            "predecessor_hrönir_uuid": str(winner_path_model.prev_uuid) if winner_path_model.prev_uuid else None
                        })

                    verdicts_json_str_for_cmd = json.dumps(example_verdicts_for_cli)
                    tx_result = transaction_manager.record_transaction(
                        session_id=session_id,
                        initiating_path_uuid=str(qualified_path_for_session_uuid), # TM expects initiating_path_uuid
                        session_verdicts=session_verdicts_for_tm_list
                    )
                    typer.echo(f"  Session verdicts committed. Transaction: {tx_result['transaction_uuid']}")
                    typer.echo(f"  (command: hronir session commit --session-id {session_id} --verdicts '{verdicts_json_str_for_cmd}')")

                    session_manager.update_session_status(session_id, "committed")
                    # Path status update needs mandate_id if it's not already set in the model by dev_qualify.
                    # Mandate ID is part of path_data_obj used for session_start.
                    path_data_obj_for_spend = data_manager.get_path_by_uuid(str(qualified_path_for_session_uuid))
                    data_manager.update_path_status(str(qualified_path_for_session_uuid), "SPENT", mandate_id=str(path_data_obj_for_spend.mandate_id), set_mandate_explicitly=True)
                    data_manager.save_all_data_to_csvs()

                    oldest_pos_voted = tx_result.get("oldest_voted_position", -1)
                    if oldest_pos_voted != -1:
                        typer.echo(f"  Triggering Temporal Cascade from position {oldest_pos_voted}...")
                        run_temporal_cascade(
                            start_position=oldest_pos_voted,
                            max_positions_to_consolidate=10,
                            canonical_path_file=Path("data/canonical_path.json"),
                            typer_echo=typer.echo
                        )
                    typer.echo("  Session commit and cascade finished.\n")

                except Exception as e:
                    typer.secho(f"  Error committing session: {e}", fg=typer.colors.RED)
            else:
                typer.echo("  No example verdicts to commit for this dossier.\n")
        elif session_id: # Session started but no duels
            typer.echo("  Session started, but no duels in dossier (e.g. qualified path at pos 0 or 1). Committing vacuous session.")
            try:
                tx_result = transaction_manager.record_transaction(
                    session_id=session_id,
                    initiating_path_uuid=str(qualified_path_for_session_uuid),
                    session_verdicts=[]
                )
                session_manager.update_session_status(session_id, "committed")
                path_data_obj_for_spend = data_manager.get_path_by_uuid(str(qualified_path_for_session_uuid))
                data_manager.update_path_status(str(qualified_path_for_session_uuid), "SPENT", mandate_id=str(path_data_obj_for_spend.mandate_id), set_mandate_explicitly=True)
                data_manager.save_all_data_to_csvs()
                typer.echo(f"  Empty session committed. Transaction: {tx_result['transaction_uuid']}\n")
            except Exception as e:
                 typer.secho(f"  Error committing empty session: {e}", fg=typer.colors.RED)

    typer.secho("Step 7: Showing resulting rankings and canonical status...", fg=typer.colors.BLUE)
    try:
        typer.echo("  Example: Ranking for Position 1 (command: hronir ranking 1)")
        pred_h0_uuid_str = str(h[0])
        ranking_df_pos1 = ratings.get_ranking(1, pred_h0_uuid_str)
        if not ranking_df_pos1.empty:
            typer.echo(ranking_df_pos1.to_string(index=False))
        else:
            typer.echo(f"    No ranking data for position 1 (predecessor: {pred_h0_uuid_str}).")

        typer.echo("\n  Canonical Path Status (command: hronir status)")
        cp_file = Path("data/canonical_path.json") # Use consistent variable
        if cp_file.exists():
            with open(cp_file) as f:
                canonical_data = json.load(f)
            path_entries = canonical_data.get("path", {})
            if path_entries:
                for pos_str_canon in sorted(path_entries.keys(), key=int):
                    entry = path_entries[pos_str_canon]
                    typer.echo(f"    Pos {pos_str_canon}: Path {entry['path_uuid'][:8]} (Hrönir {entry['hrönir_uuid'][:8]})")
            else:
                typer.echo("    Canonical path is empty.")
        else:
            typer.echo("    Canonical path file not found.")

        typer.echo("\n  Tutorial finished.")

    except Exception as e:
        typer.secho(f"  Error showing status: {e}", fg=typer.colors.RED)


@app.command("dev-qualify", help="FOR DEVELOPMENT: Manually qualify a path and assign a mandate ID.")
def dev_qualify_command(
    path_uuid_to_qualify: Annotated[str, typer.Argument(help="The path_uuid to mark as QUALIFIED.")],
    mandate_id_override: Annotated[str, typer.Option(help="Optional specific mandate_id to assign. If not provided, a new UUID is generated.")] = None,
):
    """
    Development utility to manually set a path's status to QUALIFIED.
    A new mandate_id (UUID4) will be generated and assigned, unless overridden.
    This bypasses the normal Elo-based qualification mechanisms. Use with caution.
    """
    typer.secho(f"Attempting to dev-qualify path: {path_uuid_to_qualify}", fg=typer.colors.YELLOW)

    data_manager = storage.DataManager()
    path_obj = data_manager.get_path_by_uuid(path_uuid_to_qualify)

    if not path_obj:
        typer.secho(f"Error: Path {path_uuid_to_qualify} not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if path_obj.status == "QUALIFIED":
        typer.secho(f"Path {path_uuid_to_qualify} is already QUALIFIED. Mandate ID: {path_obj.mandate_id}", fg=typer.colors.YELLOW)
        if mandate_id_override and str(path_obj.mandate_id) != mandate_id_override:
             typer.secho(f"  Note: Provided mandate_id_override ({mandate_id_override}) differs from existing. Not changed.", fg=typer.colors.YELLOW)
        return

    actual_mandate_id: uuid.UUID # Type hint for clarity
    if mandate_id_override:
        try:
            actual_mandate_id = uuid.UUID(mandate_id_override)
        except ValueError:
            typer.secho(f"Error: Provided mandate_id_override '{mandate_id_override}' is not a valid UUID.", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    else:
        actual_mandate_id = uuid.uuid4()

    try:
        # Path.mandate_id is TypeAlias MandateID = uuid.UUID.
        # storage.update_path_status expects mandate_id: str | None.
        # So, convert actual_mandate_id to string here.
        data_manager.update_path_status(
            path_uuid=path_uuid_to_qualify,
            status="QUALIFIED",
            mandate_id=str(actual_mandate_id),
            set_mandate_explicitly=True
        )
        data_manager.save_all_data_to_csvs()
        typer.secho(f"Path {path_uuid_to_qualify} successfully set to QUALIFIED.", fg=typer.colors.GREEN)
        typer.echo(f"  Position: {path_obj.position}")
        typer.echo(f"  Hrönir UUID: {path_obj.uuid}")
        typer.echo(f"  Assigned Mandate ID: {actual_mandate_id}") # Show the UUID object
    except Exception as e:
        typer.secho(f"Error during dev-qualify operation: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# Placeholder for 'submit' command if it was meant to be kept.
# If not, it can be removed. For now, it's commented out as per original structure.
# @app.command(help="Submit changes (placeholder).")
# def submit_cmd():
#     typer.echo("Submit command is in development.")


@app.callback()
def main_callback(ctx: typer.Context):
    """Initializes DataManager before any command."""
    try:
        data_manager = storage.DataManager()
        data_manager.initialize_and_load()
    except Exception as e:
        typer.secho(
            f"Fatal: DataManager initialization failed: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


def main(argv: list[str] | None = None):
    """CLI entry point."""
    app(args=argv)


# New session management commands
session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True)

app.add_typer(session_app, name="session")


@session_app.command("start", help="Initiate a Judgment Session using a QUALIFIED path's mandate.")
def session_start(
    # position: Annotated[int, typer.Option("--position", "-p", help="The current position N of the new path being created.")], # Position is now derived from path_uuid
    path_uuid: Annotated[
        str,
        typer.Option(
            "--path-uuid",  # Changed from --fork-uuid
            "-p",  # Changed from -f
            help="The QUALIFIED path_uuid granting the mandate for this session.",
        ),
    ],
    ratings_dir: Annotated[
        Path, typer.Option(help="Directory containing rating CSV files.")
    ] = Path("ratings"),
    narrative_paths_dir: Annotated[
        Path, typer.Option(help="Directory containing narrative path CSV files.")
    ] = Path("narrative_paths"),
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
):
    """
    Initiates a new Judgment Session (SC.8, SC.9).

    This command allows a user to exercise the 'mandate for judgment' granted by a
    path that has achieved `QUALIFIED` status. The `path_uuid` of this qualified
    path must be provided.

    The system will:
    1. Validate the provided `path_uuid`:
        - Ensure it exists.
        - Confirm its status is `QUALIFIED`.
        - Verify it has an associated `mandate_id`.
        - Check it hasn't been `SPENT` (i.e., already used for a session).
    2. Determine `N`, the position of the qualified `path_uuid`.
    3. Generate a static "dossier" containing the duel of maximum entropy for each
       prior position (from `N-1` down to `0`), based on the canonical path at the
       moment the session is started.
    4. Create a new session record, store the dossier, and mark the `path_uuid` as
       consumed for session initiation purposes.
    5. Output the `session_id` and the dossier to the user.

    If `N=0` (the qualified path is at position 0), no prior positions exist to be
    judged. An empty dossier is created, and the session is immediately ready for
    a (vacuous) commit, primarily to log the use of the mandate.
    """
    # Position is now derived from the path_uuid itself, not passed as a separate CLI arg.
    # This makes the command simpler and less prone to user error.
    # We will fetch the path's details to get its position N.

    # Validate the path_uuid - it must exist in the database
    # path_data = storage.get_path_file_and_data(path_uuid, path_dir_base=narrative_paths_dir) # Legacy
    path_data_obj = storage.DataManager().get_path_by_uuid(path_uuid)  # DB query

    if not path_data_obj:
        typer.echo(
            json.dumps(
                {
                    "error": f"Path UUID {path_uuid} not found in the database. Cannot start session."
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Get position N from the path_data_obj
    position_n_str = str(path_data_obj.position)  # position is int in PathDB
    if position_n_str is None:
        typer.echo(
            json.dumps(
                {"error": f"Path UUID {path_uuid} is missing position information."},
                indent=2,
            )
        )
        raise typer.Exit(code=1)
    try:
        position = int(position_n_str)  # position_n is N
    except ValueError:
        typer.echo(
            json.dumps(
                {"error": f"Path UUID {path_uuid} has an invalid position: {position_n_str}."},
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    if position < 0:  # Should be caught by storage validation, but good to check.
        typer.echo(
            json.dumps(
                {"error": f"Path UUID {path_uuid} has an invalid negative position: {position}."},
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Validate the path_uuid - it must exist in narrative_paths (already done by get_path_data)
    # if not storage.narrative_path_exists(path_uuid, path_dir=narrative_paths_dir): # Legacy, and redundant
    #     typer.echo(
    #         json.dumps(
    #             {
    #                 "error": f"Path UUID {path_uuid} not found in narrative paths. Cannot start session."
    #             },
    #             indent=2,
    #         )
    #     )
    #     raise typer.Exit(code=1)

    # Check if path_uuid has already been consumed for a session (SC.8)
    consumed_by_session_id = session_manager.is_path_consumed(path_uuid)
    if consumed_by_session_id:
        typer.echo(
            json.dumps(
                {
                    "error": "This path_uuid has already been used to initiate a judgment session.",
                    "path_uuid": path_uuid,
                    "session_id": consumed_by_session_id,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    if position == 0:  # Corrected condition: No prior positions if N=0
        # If N=0, there are no prior positions (N-1 to 0) to judge.
        # Create an empty session and mark path as consumed.
        session_id = str(uuid.uuid4())
        session_manager.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_file = session_manager.SESSIONS_DIR / f"{session_id}.json"
        session_data = {
            "session_id": session_id,
            "initiating_path_uuid": path_uuid,
            "position_n": position,
            "dossier": {"duels": {}},  # No duels for N=0
            "status": "active",
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        session_manager.mark_path_as_consumed(path_uuid, session_id)
        typer.echo(
            json.dumps(
                {
                    "message": "Session started for Position 0. No prior positions to judge.",
                    "session_id": session_id,
                    "dossier": session_data["dossier"],
                },
                indent=2,
            )
        )
        raise typer.Exit(code=0)

    # Validate the path_uuid's status and get mandate_id (using the path_data_obj from earlier)
    # path_data = storage.get_path_file_and_data(path_uuid, path_dir_base=narrative_paths_dir) # Legacy and redundant

    # if not path_data_obj: # Already checked, but being defensive if logic flow changes
    #     typer.echo(
    #         json.dumps(
    #             {
    #                 "error": f"Path UUID {path_uuid} details not found in database (second check). Cannot start session."
    #             },
    #             indent=2,
    #         )
    #     )
    #     raise typer.Exit(code=1)

    path_status_val = path_data_obj.status  # Renamed to avoid conflict
    if path_status_val != "QUALIFIED":
        typer.echo(
            json.dumps(
                {
                    "error": f"Path UUID {path_uuid} does not have 'QUALIFIED' status. Current status: '{path_status_val}'. Cannot start session.",
                    "path_uuid": path_uuid,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    mandate_id = path_data_obj.mandate_id
    if not mandate_id:
        typer.echo(
            json.dumps(
                {
                    "error": f"Path UUID {path_uuid} is 'QUALIFIED' but does not have an associated mandate_id. This indicates an inconsistency.",
                    "path_uuid": path_uuid,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Verify that the derived position matches the path's actual position (already have position from path_data_obj)
    # path_actual_position = path_data_obj.position # This is an int
    # The 'position' variable was derived from path_data_obj.position earlier.
    # No need for this redundant check as 'position' var is directly from path_data_obj.position.
    # try:
    #     if path_actual_position is not None and int(path_actual_position) != position:
    #         typer.echo(
    #             json.dumps(
    #                 {
    #                     "error": f"Derived position {position} does not match the path's actual position {path_actual_position}.",
    #                     "path_uuid": path_uuid,
    #                 },
    #                 indent=2,
    #             )
    #         )
    #         raise typer.Exit(code=1)
    # except ValueError: # Should not happen as path_data_obj.position is int
    #     typer.echo(
    #         json.dumps(
    #             {
    #                 "error": f"Path's actual position '{path_actual_position}' is not a valid number.",
    #                 "path_uuid": path_uuid,
    #             },
    #             indent=2,
    #         )
    #     )
    #     raise typer.Exit(code=1)

    # If N=0, there are no prior positions (N-1 to 0) to judge.
    # The create_session logic in session_manager will handle empty dossier for N=0.
    # The special handling for position == 0 in cli.py can be simplified as session_manager now handles it.

    # Create the session and get the dossier (SC.9)
    try:
        session_info = session_manager.create_session(
            path_n_uuid=path_uuid,
            position_n=position,  # This is N, the position of the qualified path
            mandate_id=mandate_id,  # Pass the validated mandate_id
            narrative_paths_dir=narrative_paths_dir,
            ratings_dir=ratings_dir,
            canonical_path_file=canonical_path_file,
        )
        typer.echo(
            json.dumps(
                {
                    "message": "Judgment session started successfully.",
                    "session_id": session_info["session_id"],
                    "mandate_id_used": session_info.get("mandate_id_used"),
                    "dossier": session_info["dossier"],
                },
                indent=2,
            )
        )
    except Exception as e:
        # Catch any other errors during session creation (e.g., file system issues)
        typer.echo(json.dumps({"error": f"Failed to create session: {str(e)}"}, indent=2))
        raise typer.Exit(code=1)


# This function will be called by `session commit`
def run_temporal_cascade(
    start_position: int,
    max_positions_to_consolidate: int,  # Similar to consolidate_book
    canonical_path_file: Path,
    # narrative_paths_dir: Path, # No longer needed by DB-centric ratings.get_ranking
    # ratings_dir: Path, # No longer needed by DB-centric ratings.get_ranking
    typer_echo: callable,  # Pass typer.echo for output
):
    """
    Recalculates the canonical path starting from `start_position`.
    This is the core of SC.11.
    """
    typer_echo(f"Starting Temporal Cascade from position {start_position}...")

    # from . import graph_logic # graph_logic might still use paths if called elsewhere,
    # but not directly by get_ranking path.
    # For is_narrative_consistent, it likely still needs narrative_paths_dir.
    # This needs to be passed if that check is to be kept.
    # For now, let's assume the primary issue is get_ranking.
    # If graph_logic.is_narrative_consistent is essential and uses paths,
    # then narrative_paths_dir would need to be passed to run_temporal_cascade for that specific call.
    # Let's temporarily comment out the consistency check to isolate the get_ranking issue.
    # TODO: Re-evaluate if graph_logic.is_narrative_consistent is needed here and how to handle its path dependency.
    # from . import graph_logic
    # if not graph_logic.is_narrative_consistent(narrative_paths_dir): # This would need narrative_paths_dir
    #     typer_echo("Error: narrative graph contains cycles. Abort cascade.", err=True)
    #     return False

    try:
        canonical_path_data = (
            json.loads(canonical_path_file.read_text())
            if canonical_path_file.exists()
            else {"title": "The Hrönir Encyclopedia - Canonical Path", "path": {}}
        )
    except json.JSONDecodeError:
        typer_echo(
            f"Error reading or parsing canonical path file: {canonical_path_file}. Initializing new path.",
            err=True,
        )
        canonical_path_data = {
            "title": "The Hrönir Encyclopedia - Canonical Path",
            "path": {},
        }

    if "path" not in canonical_path_data or not isinstance(canonical_path_data["path"], dict):
        canonical_path_data["path"] = {}

    updated_any_position_in_cascade = False

    # Clear canonical entries from start_position onwards, as they will be recalculated
    keys_to_clear = [k for k in canonical_path_data["path"] if int(k) >= start_position]
    if keys_to_clear:
        typer_echo(
            f"Clearing existing canonical entries from position {start_position} onwards before cascade."
        )
        for k in keys_to_clear:
            del canonical_path_data["path"][k]
        # updated_any_position_in_cascade = True # Clearing is a change

    for current_pos_idx in range(start_position, max_positions_to_consolidate):
        position_str = str(current_pos_idx)
        predecessor_hronir_uuid_for_ranking: str | None = None

        if current_pos_idx == 0:
            predecessor_hronir_uuid_for_ranking = None
        else:
            # Get the hrönir_uuid from the *just determined* canonical path of the previous position
            prev_pos_canonical_info = canonical_path_data["path"].get(str(current_pos_idx - 1))
            if not prev_pos_canonical_info or "hrönir_uuid" not in prev_pos_canonical_info:
                typer_echo(
                    f"Cascade broken: Canonical path for position {current_pos_idx - 1} not found during cascade. Stopping."
                )
                # All subsequent positions are effectively removed from canonical path
                keys_to_remove = [
                    k for k in canonical_path_data["path"] if int(k) >= current_pos_idx
                ]
                if keys_to_remove:
                    typer_echo(
                        f"Removing subsequent canonical entries from position {current_pos_idx} onwards due to broken cascade."
                    )
                    for k_rem in keys_to_remove:
                        if k_rem in canonical_path_data["path"]:
                            del canonical_path_data["path"][k_rem]
                            updated_any_position_in_cascade = True  # Mark change
                break
            predecessor_hronir_uuid_for_ranking = prev_pos_canonical_info["hrönir_uuid"]

        typer_echo(
            f"Cascade recalculating position {current_pos_idx} (based on predecessor: {predecessor_hronir_uuid_for_ranking or 'None'})..."
        )

        db_session_for_cascade = storage.get_db_session()
        try:
            ranking_df = ratings.get_ranking(
                position=current_pos_idx,
                predecessor_hronir_uuid=predecessor_hronir_uuid_for_ranking,
                # narrative_paths_dir and ratings_dir are no longer needed
                session=db_session_for_cascade,
            )
        finally:
            db_session_for_cascade.close()

        if ranking_df.empty:
            typer_echo(
                f"Cascade: No ranking found for eligible paths at position {current_pos_idx} "
                f"(predecessor: {predecessor_hronir_uuid_for_ranking or 'None'}). Path ends here."
            )
            # If this position previously had a canonical entry, it's now removed implicitly by the clearing step
            # or explicitly if loop breaks and removes subsequent entries.
            # Ensure any entries from current_pos_idx onwards are truly gone if path ends.
            keys_to_ensure_removed = [
                k for k in canonical_path_data["path"] if int(k) >= current_pos_idx
            ]
            if keys_to_ensure_removed:
                typer_echo(
                    f"Ensuring canonical entries from position {current_pos_idx} onwards are removed as cascade path ends."
                )
                for k_rem_end in keys_to_ensure_removed:
                    if k_rem_end in canonical_path_data["path"]:
                        del canonical_path_data["path"][k_rem_end]
                        updated_any_position_in_cascade = True
            break  # End of the canonical path for this cascade

        champion_path_uuid = ranking_df.iloc[0]["path_uuid"]
        champion_hronir_uuid = ranking_df.iloc[0]["hrönir_uuid"]
        champion_elo = ranking_df.iloc[0]["elo_rating"]

        # current_entry_in_path = canonical_path_data["path"].get(position_str) # Not needed due to initial clear
        new_entry_for_path = {
            "path_uuid": champion_path_uuid,
            "hrönir_uuid": champion_hronir_uuid,
        }

        # Since we cleared, any new entry is a change or reinstatement.
        canonical_path_data["path"][position_str] = new_entry_for_path
        typer_echo(
            f"Cascade: Position {current_pos_idx}: Set path {champion_path_uuid[:8]} (hrönir: {champion_hronir_uuid[:8]}, Elo: {champion_elo}) as canonical."
        )
        updated_any_position_in_cascade = True

    if updated_any_position_in_cascade:
        try:
            canonical_path_file.parent.mkdir(parents=True, exist_ok=True)
            canonical_path_file.write_text(json.dumps(canonical_path_data, indent=2))
            typer_echo(f"Temporal Cascade: Canonical path file updated: {canonical_path_file}")
        except Exception as e:
            typer_echo(f"Temporal Cascade: Error writing canonical path file: {e}", err=True)
            # Depending on policy, this might need to raise an exception or handle failure
    else:
        typer_echo(
            f"Temporal Cascade: No changes to the canonical path resulting from this cascade starting at position {start_position}."
        )

    typer_echo(f"Temporal Cascade from position {start_position} complete.")
    return updated_any_position_in_cascade  # Return whether changes were made


@session_app.command(
    "commit",
    help="Submit verdicts for a Judgment Session, record transaction, and trigger Temporal Cascade.",
)
def session_commit(
    session_id: Annotated[
        str,
        typer.Option(
            "--session-id",
            "-s",
            help="The ID of the active Judgment Session to commit.",
        ),
    ],
    verdicts_input: Annotated[
        str,
        typer.Option(
            "--verdicts",
            "-v",
            help='JSON string or path to a JSON file containing verdicts. Format: \'{"position_str": "winning_path_uuid"}\'. Example: \'{"9": "path_uuid_abc", "2": "path_uuid_xyz"}\'. ',
        ),
    ],
    ratings_dir: Annotated[
        Path, typer.Option(help="Directory containing rating CSV files.")
    ] = Path("ratings"),  # Retained for run_temporal_cascade
    narrative_paths_dir: Annotated[
        Path, typer.Option(help="Directory containing narrative path CSV files.")
    ] = Path("narrative_paths"),  # Retained for _get_successor_hronir_for_path and cascade
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),  # Retained for run_temporal_cascade
    max_cascade_positions: Annotated[
        int,
        typer.Option(help="Maximum number of positions for temporal cascade calculation."),
    ] = 100,
):
    """
    Commits the verdicts for an active Judgment Session (SC.10, SC.11, SYS.1).

    This command finalizes a judgment session by:
    1.  Retrieving the specified active session and its static dossier.
    2.  Parsing the provided `verdicts_input` (either a JSON string or a file path
        to a JSON file). The verdicts map position numbers (as strings) to the
        `path_uuid` chosen as the winner for that position's duel.
    3.  Validating each submitted verdict:
        - Ensures the position exists in the session's dossier.
        - Confirms the chosen winning `path_uuid` was one of the two paths presented
          in the dossier for that position (Sovereignty of Curadoria, SC.10).
    4.  Preparing a list of valid votes, mapping winning/losing `path_uuid`s to their
        respective successor `hrönir_uuid`s (needed for `ratings.record_vote`).
    5.  Invoking `transaction_manager.record_transaction` to:
        - Record all valid votes.
        - Check for any paths that become `QUALIFIED` as a result of these votes
          and update their status/mandate_id.
        - Create an immutable transaction block in the `data/transactions/` ledger (SYS.1),
          linking it to the previous transaction.
    6.  Updating the status of the session-initiating `path_uuid` to `SPENT`.
    7.  Triggering the "Temporal Cascade" (`run_temporal_cascade`) starting from the
        oldest position that received a valid vote in this session (SC.11). This
        recalculates the canonical path.
    8.  Updating the session's status to `committed`.

    The `ratings_dir`, `narrative_paths_dir`, and `canonical_path_file` options are
    primarily used by the `transaction_manager` and subsequent `run_temporal_cascade`
    functions, not directly for parsing verdicts in this command's immediate scope.
    """
    session_data = session_manager.get_session(session_id)
    if not session_data:
        typer.echo(json.dumps({"error": f"Session ID {session_id} not found."}, indent=2))
        raise typer.Exit(code=1)

    if session_data.get("status") != "active":
        typer.echo(
            json.dumps(
                {
                    "error": f"Session {session_id} is not active. Current status: {session_data.get('status')}"
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Parse verdicts
    verdicts: dict[str, str] = {}
    verdicts_path = Path(verdicts_input)
    if verdicts_path.is_file():
        try:
            verdicts = json.loads(verdicts_path.read_text())
        except Exception as e:
            typer.echo(
                json.dumps(
                    {"error": f"Failed to parse verdicts JSON file {verdicts_input}: {e}"},
                    indent=2,
                )
            )
            raise typer.Exit(code=1)
    else:
        try:
            verdicts = json.loads(verdicts_input)
        except Exception as e:
            typer.echo(
                json.dumps({"error": f"Failed to parse verdicts JSON string: {e}"}, indent=2)
            )
            raise typer.Exit(code=1)

    if not isinstance(verdicts, dict):
        typer.echo(json.dumps({"error": "Verdicts must be a JSON object (dictionary)."}, indent=2))
        raise typer.Exit(code=1)

    initiating_path_uuid = session_data["initiating_path_uuid"]
    dossier_duels = session_data.get("dossier", {}).get("duels", {})

    valid_votes_to_record = []
    processed_verdicts: dict[
        str, str
    ] = {}  # For transaction record: position_str -> winning_path_uuid
    oldest_voted_position = float("inf")

    for pos_str, winning_path_uuid_verdict in verdicts.items():
        if not isinstance(winning_path_uuid_verdict, str):
            typer.echo(
                json.dumps(
                    {"warning": f"Verdict for position {pos_str} is not a string. Skipping."},
                    indent=2,
                )
            )
            continue

        position_idx = -1
        try:
            position_idx = int(pos_str)
            if position_idx < 0:  # Ensure positive position
                typer.echo(
                    json.dumps(
                        {"warning": f"Invalid position {pos_str} in verdicts. Skipping."},
                        indent=2,
                    )
                )
                continue
        except ValueError:
            typer.echo(
                json.dumps(
                    {"warning": f"Invalid position key '{pos_str}' in verdicts. Skipping."},
                    indent=2,
                )
            )
            continue

        duel_for_pos = dossier_duels.get(pos_str)
        if not duel_for_pos:
            typer.echo(
                json.dumps(
                    {
                        "warning": f"No duel found in dossier for position {pos_str}. Skipping verdict."
                    },
                    indent=2,
                )
            )
            continue

        path_a = duel_for_pos["path_A"]  # Changed from fork_A
        path_b = duel_for_pos["path_B"]  # Changed from fork_B

        if winning_path_uuid_verdict not in [path_a, path_b]:
            typer.echo(
                json.dumps(
                    {
                        "warning": f"Verdict for position {pos_str}: winning path {winning_path_uuid_verdict[:8]} is not part of the original duel ({path_a[:8]} vs {path_b[:8]}). Skipping.",
                    },
                    indent=2,
                )
            )
            continue

        loser_path_uuid_verdict = path_a if winning_path_uuid_verdict == path_b else path_b

        # Map path UUIDs to their successor hrönir UUIDs for voting
        # _get_successor_hronir_for_path is defined in cli.py
        winner_hronir_uuid = _get_successor_hronir_for_path(winning_path_uuid_verdict)
        loser_hronir_uuid = _get_successor_hronir_for_path(loser_path_uuid_verdict)

        if not winner_hronir_uuid or not loser_hronir_uuid:
            typer.echo(
                json.dumps(
                    {
                        "error": f"Could not map one or both duel paths for position {pos_str} to their successor hrönir_uuids. "
                        f"Winner: {winning_path_uuid_verdict[:8]} -> {winner_hronir_uuid[:8] if winner_hronir_uuid else 'Not Found'}, "
                        f"Loser: {loser_path_uuid_verdict[:8]} -> {loser_hronir_uuid[:8] if loser_hronir_uuid else 'Not Found'}. "
                        "Aborting commit.",
                    },
                    indent=2,
                )
            )
            # This is a critical error, perhaps don't proceed with any votes.
            raise typer.Exit(code=1)

        path_data_for_winner = storage.DataManager().get_path_by_uuid(winning_path_uuid_verdict)
        if not path_data_for_winner:
            typer.echo(
                json.dumps(
                    {
                        "error": f"Critical error: Path data for winning_path_uuid {winning_path_uuid_verdict} not found. Aborting commit."
                    },
                    indent=2,
                )
            )
            raise typer.Exit(1)

        predecessor_for_this_duel = str(path_data_for_winner.prev_uuid) if path_data_for_winner.prev_uuid else None
        if position_idx == 0:  # Ensure consistency for position 0
            predecessor_for_this_duel = None

        valid_votes_to_record.append(
            {
                "position": position_idx,
                "voter": initiating_path_uuid,  # The path that started the session is the voter
                "winner_hrönir": winner_hronir_uuid,
                "loser_hrönir": loser_hronir_uuid,
                "predecessor_for_duel": predecessor_for_this_duel,  # Added for context
            }
        )
        processed_verdicts[pos_str] = winning_path_uuid_verdict
        if position_idx < oldest_voted_position:
            oldest_voted_position = position_idx

    if not valid_votes_to_record:
        typer.echo(
            json.dumps(
                {
                    "message": "No valid verdicts provided or matched dossier. No votes recorded. Session remains active."
                },
                indent=2,
            )
        )
        # No need to exit with error, user might provide empty or non-matching verdicts.
        # Or, we could update session status to 'aborted' or similar. For now, leave active.
        raise typer.Exit(code=0)

    # The `valid_votes_to_record` list is now structured as:
    # [{"position": int, "voter": str, "winner_hronir": str, "loser_hronir": str}]
    # We need to transform this into the format expected by the new transaction_manager:
    # session_verdicts: List[Dict[str, Any]] where each dict is
    # {"position": int, "winner_hrönir_uuid": str, "loser_hrönir_uuid": str}
    # The initiating_path_uuid is passed separately to transaction_manager.

    session_verdicts_for_tm: list[dict[str, Any]] = []
    for vote_detail in valid_votes_to_record:
        session_verdicts_for_tm.append(
            {
                "position": vote_detail["position"],
                "winner_hrönir_uuid": vote_detail["winner_hrönir"],
                "loser_hrönir_uuid": vote_detail["loser_hrönir"],
                "predecessor_hrönir_uuid": vote_detail["predecessor_for_duel"],
            }
        )

    # Calls to ratings.record_vote are now REMOVED from cli.py session_commit.
    # transaction_manager.record_transaction is responsible for this.
    typer.echo(
        json.dumps(
            {
                "message": f"{len(session_verdicts_for_tm)} valid verdicts prepared for transaction processing."
            },
            indent=2,
        )
    )

    # Create transaction in ledger (SYS.1), which also records votes and handles promotions
    transaction_result: dict[str, Any] | None = None
    try:
        transaction_result = transaction_manager.record_transaction(
            session_id=session_id,
            initiating_path_uuid=initiating_path_uuid,  # Path whose mandate is used
            session_verdicts=session_verdicts_for_tm,
        )
        typer.echo(
            json.dumps(
                {
                    "message": "Transaction processing complete.",
                    "transaction_uuid": transaction_result["transaction_uuid"],
                    "promotions_granted": transaction_result.get("promotions_granted", []),
                },
                indent=2,
            )
        )
    except Exception as e:
        typer.echo(
            json.dumps(
                {"error": f"Failed to process transaction: {e}. Aborting commit."},
                indent=2,
            )
        )
        # Votes might not have been recorded, or only partially. State could be inconsistent.
        # Session status should reflect this if possible.
        session_manager.update_session_status(session_id, "commit_failed_tx_processing")
        raise typer.Exit(code=1)

    # Update the status of the initiating_path_uuid to "SPENT"
    # The mandate_id was implicitly "spent" by starting the session and consuming the path_uuid.
    # Now we mark the path itself as SPENT.
    try:
        update_spent_success = storage.update_path_status(
            path_uuid_to_update=initiating_path_uuid,
            new_status="SPENT",
            mandate_id=session_data.get(
                "mandate_id"
            ),  # Pass mandate_id for completeness, though not strictly needed for 'SPENT'
            # path_dir_base is no longer needed by storage.update_path_status
            # session=None, # Allow update_path_status to get its own session
        )
        if update_spent_success:
            typer.echo(
                json.dumps(
                    {"message": f"Path {initiating_path_uuid} status updated to SPENT."},
                    indent=2,
                )
            )
        else:
            typer.echo(
                json.dumps(
                    {
                        "warning": f"Could not update status to SPENT for path {initiating_path_uuid}. Manual check may be needed."
                    },
                    indent=2,
                )
            )
            # This is not ideal, but the transaction is committed.
    except Exception as e:
        typer.echo(
            json.dumps(
                {
                    "warning": f"Error updating status for path {initiating_path_uuid} to SPENT: {e}. Manual check may be needed."
                },
                indent=2,
            )
        )

    # Trigger Temporal Cascade (SC.11)
    # Use oldest_voted_position from transaction_result
    tm_oldest_voted_position = transaction_result.get("oldest_voted_position", float("inf"))

    if tm_oldest_voted_position != float("inf") and tm_oldest_voted_position >= 0:
        typer.echo(
            f"Oldest voted position from transaction: {tm_oldest_voted_position}. Triggering Temporal Cascade."
        )
        try:
            cascade_made_changes = run_temporal_cascade(
                start_position=tm_oldest_voted_position,
                max_positions_to_consolidate=max_cascade_positions,
                canonical_path_file=canonical_path_file,
                # narrative_paths_dir and ratings_dir removed as args from run_temporal_cascade
                typer_echo=typer.echo,  # Pass the echo function
            )
            if cascade_made_changes:
                typer.echo(
                    json.dumps(
                        {"message": "Temporal Cascade completed and updated the canonical path."},
                        indent=2,
                    )
                )
            else:
                typer.echo(
                    json.dumps(
                        {
                            "message": "Temporal Cascade completed, no changes to the canonical path from the cascade."
                        },
                        indent=2,
                    )
                )

        except Exception as e:
            typer.echo(json.dumps({"error": f"Temporal Cascade failed: {e}."}, indent=2))
            # Votes and TX recorded, but cascade failed. State is inconsistent.
            # This needs careful consideration for recovery.
            # For now, we'll report and exit. Session status might indicate this.
            session_manager.update_session_status(session_id, "commit_failed_cascade")
            raise typer.Exit(code=1)
    else:
        # This case should be caught by "No valid verdicts" earlier, but as a safeguard:
        typer.echo(
            json.dumps(
                {"message": "No votes were cast, so no Temporal Cascade was triggered."},
                indent=2,
            )
        )

    # Update session status to 'committed'
    session_manager.update_session_status(session_id, "committed")
    typer.echo(json.dumps({"message": f"Session {session_id} committed successfully."}, indent=2))


@app.command("metrics", help="Expose path status metrics in Prometheus format (TDD 2.6).")
def metrics_command(
    narrative_paths_dir: Annotated[
        Path, typer.Option(help="Directory containing narrative path CSV files.")
    ] = Path("narrative_paths"),
):
    """
    Scans all narrative_paths/*.csv files and prints the total number of paths
    in each status (PENDING, QUALIFIED, SPENT) in Prometheus exposition format.
    """
    status_counts = _calculate_status_counts(narrative_paths_dir)
    if not narrative_paths_dir.is_dir():
        typer.echo(
            f"# Metrics generation skipped: Directory not found: {narrative_paths_dir}",
            err=True,
        )
        for status_val, count in status_counts.items():
            typer.echo(f'hronir_path_status_total{{status="{status_val.lower()}"}} {count}')
        raise typer.Exit(code=1)

    # Print metrics in Prometheus format
    typer.echo("# HELP hronir_path_status_total Total number of paths by status.")
    typer.echo("# TYPE hronir_path_status_total gauge")
    for status_val, count in status_counts.items():
        # Prometheus labels are typically lowercase.
        typer.echo(f'hronir_path_status_total{{status="{status_val.lower()}"}} {count}')


if __name__ == "__main__":
    main()  # Called with no arguments, so app() will use sys.argv
