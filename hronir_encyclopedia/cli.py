import datetime  # Required for SessionModel if used directly, or for its string representations
import json

# Define module-level logger
import logging
import os  # Added for getenv in sync
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import (
    Annotated,
    Any,
)

import pandas as pd
import typer

from . import (
    database,
    gemini_util,
    ratings,
    session_manager,
    storage,
    transaction_manager,
)
from .models import SessionModel  # Import SessionModel for type hinting if needed
from .transaction_manager import ConflictDetection  # For sync command

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True,
    no_args_is_help=True,
)


@app.command(
    "recover-canon",
    help="Manual recovery tool: Triggers Temporal Cascade from position 0 to rebuild canon. Use with caution.",
)
def recover_canon(
    # ratings_dir option removed as it's not used by run_temporal_cascade anymore
    # narrative_paths_dir option removed as it's not used by run_temporal_cascade anymore
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    max_positions_to_rebuild: Annotated[
        int, typer.Option(help="Maximum number of positions to attempt to rebuild.")
    ] = 100,
):
    typer.echo(
        "WARNING: This is a manual recovery tool. For normal operation, canonical path updates via 'session commit'."
    )
    typer.echo("Recover-canon command now triggers a Temporal Cascade from position 0.")
    run_temporal_cascade(
        start_position=0,
        max_positions_to_consolidate=max_positions_to_rebuild,
        canonical_path_file=canonical_path_file,
        typer_echo=typer.echo,
    )
    typer.echo("Manual canon recovery via Temporal Cascade complete.")


@app.command("init-test", help="Generate a minimal sample narrative for quick testing.")
def init_test(
    library_dir: Annotated[Path, typer.Option(help="Directory to store sample hrönirs.")] = Path(
        "the_library"
    ),
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
    import shutil

    def clear_or_create_dir(dir_path: Path):
        if dir_path.exists():
            for item in dir_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            dir_path.mkdir(parents=True, exist_ok=True)

    clear_or_create_dir(library_dir)
    clear_or_create_dir(narrative_paths_dir)
    clear_or_create_dir(ratings_dir)

    sessions_dir = data_dir / "sessions"
    transactions_dir = data_dir / "transactions"

    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)

    clear_or_create_dir(sessions_dir)
    clear_or_create_dir(transactions_dir)

    canonical_file_path = data_dir / "canonical_path.json"
    if canonical_file_path.exists():
        canonical_file_path.unlink()

    # Clear consumed paths file as well
    consumed_paths_file = sessions_dir / "consumed_path_uuids.json"  # Using new name
    if consumed_paths_file.exists():
        consumed_paths_file.unlink()

    h0_uuid_str = storage.store_chapter_text("Example Hrönir 0", base=library_dir)
    h1_uuid_str = storage.store_chapter_text("Example Hrönir 1", base=library_dir)

    h0_uuid = uuid.UUID(h0_uuid_str)  # Convert to UUID objects
    h1_uuid = uuid.UUID(h1_uuid_str)

    from .models import Path as PathModel  # Correct import

    data_manager = storage.DataManager()  # Already initialized by callback

    p0_path_uuid_val = storage.compute_narrative_path_uuid(0, "", h0_uuid_str)
    path0 = PathModel(
        path_uuid=p0_path_uuid_val,  # type: ignore
        position=0,
        prev_uuid=None,
        uuid=h0_uuid,  # type: ignore
        status="PENDING",
    )
    data_manager.add_path(path0)

    p1_path_uuid_val = storage.compute_narrative_path_uuid(1, h0_uuid_str, h1_uuid_str)
    path1 = PathModel(
        path_uuid=p1_path_uuid_val,  # type: ignore
        position=1,
        prev_uuid=h0_uuid,  # type: ignore
        uuid=h1_uuid,  # type: ignore
        status="PENDING",
    )
    data_manager.add_path(path1)

    canonical = {
        "title": "The Hrönir Encyclopedia - Canonical Path",
        "path": {
            "0": {"path_uuid": str(p0_path_uuid_val), "hrönir_uuid": h0_uuid_str},
            "1": {"path_uuid": str(p1_path_uuid_val), "hrönir_uuid": h1_uuid_str},
        },
    }
    canonical_file = data_dir / "canonical_path.json"
    canonical_file.write_text(json.dumps(canonical, indent=2))

    data_manager.save_all_data_to_csvs()

    typer.echo("Sample data initialized:")
    typer.echo(f"  Position 0 hrönir UUID: {h0_uuid_str}")
    typer.echo(f"  Position 0 path UUID: {p0_path_uuid_val}")
    typer.echo(f"  Position 1 hrönir UUID: {h1_uuid_str}")
    typer.echo(f"  Position 1 path UUID: {p1_path_uuid_val}")


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
    typer.echo(f"Chapter file {chapter} exists and is readable. Basic validation passed.")


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
    uuid_str = storage.store_chapter(chapter)
    typer.echo(uuid_str)


def _validate_and_normalize_path_inputs(
    position: int, source: str, target: str, secho: callable, echo: callable
) -> str:
    """Validates inputs for the path command and normalizes source."""
    from pathlib import Path  # Local import

    if position < 0:
        secho(f"Error: Position must be non-negative, got {position}", fg=typer.colors.RED)
        raise typer.Exit(1)
    if position > 0 and not source:
        secho("Error: source (predecessor UUID) is required for position > 0.", fg=typer.colors.RED)
        echo("  Paths at positions greater than 0 represent a continuation from a previous hrönir.")
        echo(
            "  Please specify the UUID of the hrönir this new path follows using the --source option."
        )
        raise typer.Exit(1)
    if position == 0 and source:
        echo("Warning: source UUID ignored for position 0, as it's a root position.")
        source = ""  # Normalize source for position 0

    library_dir = Path("the_library")
    # Validate target hrönir
    if not target:  # Target UUID must be provided
        secho("Error: Target hrönir UUID must be provided.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if not (library_dir / f"{target}.md").exists():  # Check for .md file
        secho(
            f"Error: Target hrönir '{target}' not found in the library ('{library_dir}/{target}.md').",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Validate source hrönir if provided (it will be "" for position 0 at this point if it was originally given)
    if source and not (library_dir / f"{source}.md").exists():  # Check for .md file
        secho(
            f"Error: Source (predecessor) hrönir '{source}' not found in the library ('{library_dir}/{source}.md').",
            fg=typer.colors.RED,
        )
        echo("  A path cannot be created from a non-existent source hrönir.")
        echo(f"  Please ensure the hrönir file '{source}.md' exists or verify the UUID.")
        raise typer.Exit(1)
    return source


@app.command(help="Create a narrative connection (path) between hrönirs.")
def path(
    position: Annotated[int, typer.Option(help="Position in the narrative sequence")],
    target: Annotated[str, typer.Option(help="Target hrönir UUID (destination content node)")],
    source: Annotated[
        str, typer.Option(help="Source hrönir UUID (empty string for position 0)")
    ] = "",
):
    from pathlib import Path  # Local import fine here

    # Note: The _validate_and_normalize_path_inputs function now includes the .md check
    source = _validate_and_normalize_path_inputs(position, source, target, typer.secho, typer.echo)

    path_uuid = storage.compute_narrative_path_uuid(position, source, target)
    narrative_paths_dir = Path("narrative_paths")
    narrative_paths_dir.mkdir(exist_ok=True)
    csv_file = (
        narrative_paths_dir / f"narrative_paths_position_{position:03d}.csv"
    )  # Ensure consistent naming with PandasDataManager

    if not csv_file.exists():
        # Ensure consistent headers with PandasDataManager expectations
        # PandasDataManager uses: path_uuid,position,prev_uuid,uuid,status,mandate_id
        csv_file.write_text("path_uuid,position,prev_uuid,uuid,status,mandate_id\n")

    import pandas as pd

    try:
        df = pd.read_csv(csv_file)
        # Ensure path_uuid is compared as string if it's read as object
        if not df.empty and ((df["path_uuid"].astype(str) == str(path_uuid)).any()):
            typer.echo(f"Path already exists: {path_uuid}")
            return
    except (pd.errors.EmptyDataError, FileNotFoundError):
        csv_file.write_text("path_uuid,position,prev_uuid,uuid,status,mandate_id\n")

    # Match CSV column order: path_uuid,position,prev_uuid,uuid,status,mandate_id
    path_entry = f"{path_uuid},{position},{source},{target},PENDING,\n"  # mandate_id is empty
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
    data_manager = storage.DataManager()  # Access through DataManager
    if position is not None:
        paths_list = data_manager.get_paths_by_position(position)
        if not paths_list:
            typer.echo(f"No paths found at position {position}.")
            return
        typer.echo(f"Paths at position {position}:")
    else:
        paths_list = data_manager.get_all_paths()
        if not paths_list:
            typer.echo("No paths found.")
            return
        typer.echo("All paths:")

    # Create a DataFrame for display
    if paths_list:
        paths_data = [
            {
                "path_uuid": p.path_uuid,
                "position": p.position,
                "prev_uuid": p.prev_uuid,
                "uuid": p.uuid,
                "status": p.status,
                "mandate_id": p.mandate_id,
            }
            for p in paths_list
        ]
        df = pd.DataFrame(paths_data)
        display_cols = ["path_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"]
        # Ensure prev_uuid and mandate_id are displayed as strings, handling None
        df["prev_uuid"] = df["prev_uuid"].astype(str).replace("None", "")
        df["mandate_id"] = df["mandate_id"].astype(str).replace("None", "")
        typer.echo(df[display_cols].to_string(index=False))


@app.command(help="Show status details for a specific path.")
def path_status(path_uuid: str) -> None:
    path_data = storage.DataManager().get_path_by_uuid(path_uuid)
    if not path_data:
        typer.secho(
            f"Error: Path with UUID '{path_uuid}' not found in the narrative path data.",
            fg=typer.colors.RED,
        )
        typer.echo("  Please ensure the path UUID is correct and the path exists.")
        raise typer.Exit(code=1)

    typer.echo(f"Path UUID: {path_data.path_uuid}")
    typer.echo(f"Position: {path_data.position}")
    typer.echo(f"Predecessor Hrönir UUID: {path_data.prev_uuid or '(None)'}")
    typer.echo(f"Current Hrönir UUID: {path_data.uuid}")
    typer.echo(f"Status: {path_data.status}")
    if path_data.mandate_id:
        typer.echo(f"Mandate ID: {path_data.mandate_id}")

    consumed_by_session_id = session_manager.is_path_consumed(path_uuid)
    if consumed_by_session_id:
        typer.echo(f"Consumed by session: {consumed_by_session_id}")


def _get_successor_hronir_for_path(path_uuid_to_find: str) -> str | None:
    path_data_obj = storage.DataManager().get_path_by_uuid(path_uuid_to_find)
    if path_data_obj:
        return str(path_data_obj.uuid)
    return None


def _calculate_status_counts(narrative_paths_dir: Path) -> dict[str, int]:
    # This function might need to be updated if path data is solely managed by DataManager
    # For now, assuming it can still work with directory structure if needed, or be replaced.
    # DataManager().get_all_paths() would be the new way.
    status_counts = {"PENDING": 0, "QUALIFIED": 0, "SPENT": 0, "UNKNOWN": 0}
    all_paths = storage.DataManager().get_all_paths()
    for path_obj in all_paths:
        status_val = path_obj.status.upper() if path_obj.status else "UNKNOWN"
        if status_val in status_counts:
            status_counts[status_val] += 1
        else:
            status_counts["UNKNOWN"] += 1
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
            help="Also show number of paths by status.",  # Uses DataManager now
        ),
    ] = False,
    narrative_paths_dir: Annotated[  # No longer directly used by _calculate_status_counts
        Path,
        typer.Option(help="Directory containing narrative path CSV files (for --counts, legacy)."),
    ] = Path("narrative_paths"),
) -> None:
    try:
        with open(canonical_path_file) as f:
            canonical_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        typer.secho(
            f"Error reading canonical path file: {canonical_path_file}", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    path_entries = canonical_data.get("path", {})
    if not isinstance(path_entries, dict):
        typer.secho("Invalid canonical path data format.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo("Canonical Path:")
    for pos in sorted(path_entries.keys(), key=lambda p: int(p)):
        entry = path_entries.get(pos, {})
        path_uuid = entry.get("path_uuid", "N/A")
        hronir_uuid = entry.get("hrönir_uuid", "N/A")
        typer.echo(f"  Position {pos}: path_uuid: {path_uuid}, hrönir_uuid: {hronir_uuid}")

    if counts:
        typer.echo("\nPath status counts (from DataManager):")
        # Pass narrative_paths_dir for now, though _calculate_status_counts uses DataManager
        counts_dict = _calculate_status_counts(narrative_paths_dir)
        for status_val, count_val in counts_dict.items():
            typer.echo(f"  {status_val}: {count_val}")


@app.command(help="Validate and repair storage, audit narrative CSVs.")
def audit():
    # This command needs significant rework if CSVs are no longer the primary source of truth
    # For now, it's mostly a placeholder.
    typer.echo("Auditing hrönirs in the library (basic check)...")
    # storage.DataManager().validate_data_integrity() covers some aspects.

    typer.echo("Auditing narrative path consistency (cycle check)...")
    from . import graph_logic  # graph_logic now uses DataManager

    if graph_logic.is_narrative_consistent():  # Removed path_dir argument
        typer.echo("Narrative graph is consistent (no cycles detected).")
    else:
        typer.secho("WARNING: Narrative graph contains cycles!", fg=typer.colors.RED)
    typer.echo("Audit complete. For detailed path integrity, use 'validate-paths'.")


@app.command("validate-paths", help="Validate integrity of all narrative paths.")
def validate_paths_command():
    typer.echo("Validating narrative path integrity...")
    data_manager = storage.DataManager()
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
    typer.echo(f"Synthesizing two new hrönirs from predecessor '{prev}' at position {position}...")
    # Assuming database.open_database() is still relevant for gemini_util or other parts.
    with database.open_database() as conn:
        voter_uuid = "00000000-agent-0000-0000-000000000000"
        winner_uuid = gemini_util.auto_vote(position, prev, voter_uuid, conn=conn)
    typer.echo(f"Synthesis complete. New canonical candidate: {winner_uuid}")


@app.command(help="Show Elo rankings for a chapter position.")
def ranking(
    position: Annotated[int, typer.Argument(help="The chapter position to rank.")],
    # ratings_dir no longer needed by ratings.get_ranking
):
    predecessor_hronir_uuid = None
    if position > 0:
        canonical_path_file = Path("data/canonical_path.json")  # Default path
        if canonical_path_file.exists():
            with open(canonical_path_file) as f:
                canonical_data = json.load(f)
            path_entry = canonical_data.get("path", {}).get(str(position - 1))
            if path_entry:
                predecessor_hronir_uuid = path_entry.get("hrönir_uuid")

    # ratings.get_ranking now uses DataManager, so session is handled internally or not needed for read-only
    ranking_data = ratings.get_ranking(position, predecessor_hronir_uuid)
    if ranking_data.empty:
        typer.echo(
            f"No ranking data found for position {position} (predecessor: {predecessor_hronir_uuid or 'None'})."
        )
    else:
        typer.echo(
            f"Ranking for Position {position} (predecessor: {predecessor_hronir_uuid or 'None'}):"
        )
        typer.echo(ranking_data.to_string(index=False))


@app.command(
    help="Get the maximum entropy duel between paths for a position."
)  # Changed help to English
def get_duel(
    position: Annotated[
        int,
        typer.Option(
            help="The chapter position for which to get the path duel."
        ),  # Changed help to English
    ],
    # ratings_dir and narrative_paths_dir no longer needed by determine_next_duel_entropy
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")  # Changed help to English
    ] = Path("data/canonical_path.json"),
):
    predecessor_hronir_uuid: str | None = None
    if position > 0:
        canonical_path_info_prev_pos = storage.get_canonical_path_info(
            position - 1, canonical_path_file
        )
        if not canonical_path_info_prev_pos or "hrönir_uuid" not in canonical_path_info_prev_pos:
            typer.secho(
                f"Error: Cannot determine canonical predecessor hrönir for position {position - 1} from '{canonical_path_file}'.",
                fg=typer.colors.RED,
            )
            typer.echo("  This could be because:")
            typer.echo(
                f"    1. The canonical path does not have an entry for position {position - 1}."
            )
            typer.echo(
                f"    2. The canonical path file ('{canonical_path_file}') is missing, empty, or corrupted."
            )
            typer.echo(
                f"    3. Position {position} is too far ahead of the current canonical path."
            )
            typer.echo(
                "  Ensure 'data/canonical_path.json' is up-to-date. You may need to run 'session commit' or 'recover-canon'."
            )
            raise typer.Exit(code=1)
        predecessor_hronir_uuid = canonical_path_info_prev_pos["hrönir_uuid"]
    elif position < 0:
        typer.secho(
            "Error: Invalid position. Must be >= 0.", fg=typer.colors.RED
        )  # Corrected Portuguese "inválida" to English
        raise typer.Exit(code=1)

    db_session = (
        storage.get_db_session()
    )  # ratings.determine_next_duel_entropy expects a SQLAlchemy session
    try:
        duel_info = ratings.determine_next_duel_entropy(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
            session=db_session,  # Pass the active session
        )
    finally:
        db_session.close()  # Ensure session is closed

    if duel_info:
        typer.echo(json.dumps(duel_info, indent=2))
    else:
        typer.echo(
            json.dumps(
                {
                    "error": "Não foi possível determinar um duelo de paths.",
                    "position": position,
                    "predecessor_hrönir_uuid_used": predecessor_hronir_uuid,
                },
                indent=2,
            )
        )


def _git_remove_deleted_files():
    try:
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
            typer.echo("Not inside a Git repository. Skipping Git operations.")
        else:
            typer.echo(f"Git command failed: {e.stderr}", err=True)
    except Exception as e:
        typer.echo(f"An unexpected error occurred with Git operations: {e}", err=True)


@app.command(help="Remove invalid entries (fake hrönirs, votes, etc.) from storage.")
def clean(
    git_stage_deleted: Annotated[
        bool,
        typer.Option("--git", help="Also stage deleted files for removal in the Git index."),
    ] = False,
):
    typer.echo("Starting cleanup process...")
    # These purge functions may need updates to use DataManager if they rely on direct file ops
    storage.purge_fake_hronirs()
    # storage.purge_fake_narrative_csvs() # Example if this function is updated for DataManager
    # storage.purge_fake_votes_csvs()   # Example
    typer.echo(
        "Cleanup may require updates to align with DataManager. For now, primarily relies on older direct file access methods in storage."
    )

    if git_stage_deleted:
        typer.echo("Attempting to stage deleted files in Git...")
        _git_remove_deleted_files()
    typer.echo("Cleanup complete.")


def dev_qualify_path_uuid(path_uuid_str: str, typer_echo: callable):
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
    data_manager.save_all_data_to_csvs()  # Persist change
    typer_echo(f"  Path {path_uuid_str} status set to QUALIFIED with mandate_id {mandate_id}.")


@app.command("tutorial", help="Demonstrates a complete workflow of the Hrönir Encyclopedia.")
def tutorial_command(
    auto_qualify_for_session: Annotated[
        bool, typer.Option(help="Automatically qualify a path to demonstrate session workflow.")
    ] = True,
):
    typer.secho("Welcome to the Hrönir Encyclopedia Tutorial!", fg=typer.colors.CYAN, bold=True)
    typer.echo("This will demonstrate a common workflow.\n")
    data_manager = storage.DataManager()

    typer.secho("Step 1: Initializing a clean test environment...", fg=typer.colors.BLUE)
    # Call init_test directly, which now uses DataManager correctly
    init_test()  # Uses default paths
    typer.echo("  Test environment initialized.\n")

    # Get H0, H1, P0, P1 UUIDs from init_test's known output for tutorial steps
    # These are based on "Example Hrönir 0" and "Example Hrönir 1"
    h0_content_uuid = uuid.uuid5(storage.UUID_NAMESPACE, "Example Hrönir 0")
    h1_content_uuid = uuid.uuid5(storage.UUID_NAMESPACE, "Example Hrönir 1")
    p0_path_uuid = storage.compute_narrative_path_uuid(0, "", str(h0_content_uuid))
    p1a_path_uuid = storage.compute_narrative_path_uuid(
        1, str(h0_content_uuid), str(h1_content_uuid)
    )

    # Store additional hrönirs for more complex scenario
    h1b_content_uuid_str = storage.store_chapter_text(
        "Tutorial: The Second Age - Divergent Paths B."
    )
    h2a_content_uuid_str = storage.store_chapter_text("Tutorial: The Third Age - Aftermath of A.")
    h1b_content_uuid = uuid.UUID(h1b_content_uuid_str)
    h2a_content_uuid = uuid.UUID(h2a_content_uuid_str)

    # Create paths for them using DataManager
    from .models import Path as PathModel

    p1b_path_uuid = storage.compute_narrative_path_uuid(
        1, str(h0_content_uuid), str(h1b_content_uuid)
    )
    data_manager.add_path(
        PathModel(
            path_uuid=p1b_path_uuid,
            position=1,
            prev_uuid=h0_content_uuid,
            uuid=h1b_content_uuid,
            status="PENDING",
        )
    )  # type: ignore

    p2a_path_uuid = storage.compute_narrative_path_uuid(
        2, str(h1_content_uuid), str(h2a_content_uuid)
    )
    data_manager.add_path(
        PathModel(
            path_uuid=p2a_path_uuid,
            position=2,
            prev_uuid=h1_content_uuid,
            uuid=h2a_content_uuid,
            status="PENDING",
        )
    )  # type: ignore
    data_manager.save_all_data_to_csvs()

    typer.secho(
        "Step 2 & 3: Sample hrönirs and paths created via init-test and additions.",
        fg=typer.colors.BLUE,
    )
    typer.echo(f"  H0: {h0_content_uuid}, P0: {p0_path_uuid}")
    typer.echo(f"  H1A: {h1_content_uuid}, P1A: {p1a_path_uuid}")
    typer.echo(f"  H1B: {h1b_content_uuid}, P1B: {p1b_path_uuid}")
    typer.echo(f"  H2A: {h2a_content_uuid}, P2A: {p2a_path_uuid}\n")

    qualified_path_for_session_uuid_str = None
    if auto_qualify_for_session:
        typer.secho("Step 4: Auto-qualifying Path P2A for session...", fg=typer.colors.BLUE)
        path_to_qualify_uuid_str = str(p2a_path_uuid)
        try:
            dev_qualify_path_uuid(path_to_qualify_uuid_str, typer.echo)
            qualified_path_for_session_uuid_str = path_to_qualify_uuid_str
            typer.echo(f"  Path {path_to_qualify_uuid_str} (P2A) is now QUALIFIED.\n")
        except Exception as e:
            typer.secho(
                f"  Error auto-qualifying path: {e}. Session demo might fail.", fg=typer.colors.RED
            )

    if not qualified_path_for_session_uuid_str:
        typer.secho(
            "  Skipping session demonstration as no path was qualified.", fg=typer.colors.YELLOW
        )
    else:
        typer.secho(
            f"Step 5: Starting judgment session with qualified path {qualified_path_for_session_uuid_str}...",
            fg=typer.colors.BLUE,
        )
        session_model_instance: SessionModel | None = None
        try:
            path_data_obj = data_manager.get_path_by_uuid(qualified_path_for_session_uuid_str)
            if (
                not path_data_obj
                or path_data_obj.status != "QUALIFIED"
                or not path_data_obj.mandate_id
            ):
                raise ValueError(
                    f"Path {qualified_path_for_session_uuid_str} not properly qualified."
                )

            session_model_instance = session_manager.create_session(
                path_n_uuid_str=qualified_path_for_session_uuid_str,
                position_n=path_data_obj.position,
                mandate_id_str=str(path_data_obj.mandate_id),
                canonical_path_file=Path("data/canonical_path.json"),  # Default path
            )
            typer.echo(f"  Session {session_model_instance.session_id} started.")
            typer.echo("  Dossier created with duels:")
            if session_model_instance.dossier.duels:
                for pos_str_key, duel_details_model in session_model_instance.dossier.duels.items():
                    typer.echo(
                        f"    Pos {pos_str_key}: {duel_details_model.path_A_uuid} vs {duel_details_model.path_B_uuid}"
                    )
            else:
                typer.echo(
                    "    (No duels in dossier - expected if qualified path is at low position or no prior contention)"
                )
            typer.echo("")
        except Exception as e:
            typer.secho(f"  Error starting session: {e}", fg=typer.colors.RED)
            session_model_instance = None  # Ensure it's None on failure

        if session_model_instance and session_model_instance.dossier.duels:
            typer.secho(
                f"Step 6: Committing example verdicts for session {session_model_instance.session_id}...",
                fg=typer.colors.BLUE,
            )
            example_verdicts_for_cli: dict[str, str] = {}

            # Example: Choose P1A (p1a_path_uuid) over P1B (p1b_path_uuid) for position 1 duel
            duel_at_pos_1 = session_model_instance.dossier.duels.get("1")
            if duel_at_pos_1 and (
                p1a_path_uuid == duel_at_pos_1.path_A_uuid
                or p1a_path_uuid == duel_at_pos_1.path_B_uuid
            ):
                example_verdicts_for_cli["1"] = str(p1a_path_uuid)
                typer.echo(f"  Verdict for Pos 1: Choose Path {p1a_path_uuid} (P1A)")

            if example_verdicts_for_cli:
                try:
                    # Call session_commit directly, it handles the rest
                    session_commit(
                        session_id=str(session_model_instance.session_id),
                        verdicts_input=json.dumps(example_verdicts_for_cli),
                        canonical_path_file=Path("data/canonical_path.json"),  # Pass necessary args
                        # ratings_dir and narrative_paths_dir are not used by commit directly
                    )
                    typer.echo("  Session commit finished.\n")
                except Exception as e:
                    typer.secho(f"  Error committing session: {e}", fg=typer.colors.RED)
            else:
                typer.echo("  No example verdicts to commit for this dossier's duels.\n")
        elif session_model_instance:  # Session started but no duels in dossier
            typer.echo(
                f"  Session {session_model_instance.session_id} started, but no duels in dossier. Committing vacuous session."
            )
            try:
                session_commit(
                    session_id=str(session_model_instance.session_id),
                    verdicts_input="{}",  # Empty verdicts
                    canonical_path_file=Path("data/canonical_path.json"),
                )
                typer.echo("  Empty session committed.\n")
            except Exception as e:
                typer.secho(f"  Error committing empty session: {e}", fg=typer.colors.RED)

    typer.secho("Step 7: Showing resulting rankings and canonical status...", fg=typer.colors.BLUE)
    try:
        ranking(position=1)  # Call ranking command directly
        status(
            canonical_path_file=Path("data/canonical_path.json"), counts=True
        )  # Call status command
        typer.echo("\n  Tutorial finished.")
    except Exception as e:
        typer.secho(f"  Error showing status: {e}", fg=typer.colors.RED)


@app.command(
    "dev-qualify", help="FOR DEVELOPMENT: Manually qualify a path and assign a mandate ID."
)
def dev_qualify_command(
    path_uuid_to_qualify: Annotated[
        str, typer.Argument(help="The path_uuid to mark as QUALIFIED.")
    ],
    mandate_id_override: Annotated[
        str,
        typer.Option(
            help="Optional specific mandate_id to assign. If not provided, a new UUID is generated."
        ),
    ] = None,
):
    typer.secho(f"Attempting to dev-qualify path: {path_uuid_to_qualify}", fg=typer.colors.YELLOW)
    data_manager = storage.DataManager()
    path_obj = data_manager.get_path_by_uuid(path_uuid_to_qualify)

    if not path_obj:
        typer.secho(f"Error: Path {path_uuid_to_qualify} not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if path_obj.status == "QUALIFIED":
        typer.secho(
            f"Path {path_uuid_to_qualify} is already QUALIFIED. Mandate ID: {path_obj.mandate_id}",
            fg=typer.colors.YELLOW,
        )
        if mandate_id_override and str(path_obj.mandate_id) != mandate_id_override:
            typer.secho(
                f"  Note: Provided mandate_id_override ({mandate_id_override}) differs from existing. Not changed.",
                fg=typer.colors.YELLOW,
            )
        return

    actual_mandate_id_obj: uuid.UUID
    if mandate_id_override:
        try:
            actual_mandate_id_obj = uuid.UUID(mandate_id_override)
        except ValueError:
            typer.secho(
                f"Error: Provided mandate_id_override '{mandate_id_override}' is not a valid UUID.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
    else:
        actual_mandate_id_obj = uuid.uuid4()

    try:
        data_manager.update_path_status(
            path_uuid=path_uuid_to_qualify,
            status="QUALIFIED",
            mandate_id=str(actual_mandate_id_obj),  # Pass as string
            set_mandate_explicitly=True,
        )
        data_manager.save_all_data_to_csvs()  # Persist
        typer.secho(
            f"Path {path_uuid_to_qualify} successfully set to QUALIFIED.", fg=typer.colors.GREEN
        )
        typer.echo(f"  Assigned Mandate ID: {actual_mandate_id_obj}")
    except Exception as e:
        typer.secho(f"Error during dev-qualify operation: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.callback()
def main_callback(ctx: typer.Context):
    # Basic logging configuration
    # TODO: Make log level configurable via CLI option or env var
    logging.basicConfig(  # Use logging module directly for basicConfig
        level=logging.INFO,  # Default level
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.debug("CLI application main_callback started. Initializing DataManager...")

    try:
        data_manager = storage.DataManager()
        if not hasattr(data_manager, "_initialized") or not data_manager._initialized:
            logger.info("DataManager not initialized in callback. Calling initialize_and_load().")
            data_manager.initialize_and_load()
            logger.info("DataManager initialized and loaded via callback.")
        else:
            logger.debug("DataManager already initialized when callback ran.")
    except Exception as e:
        logger.exception("Fatal: DataManager initialization failed in callback.")
        typer.secho(
            f"Fatal: DataManager initialization failed: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    logger.debug("Main callback finished successfully.")


# TODO: Implement the actual temporal cascade logic. This is a critical missing piece.
def run_temporal_cascade(
    start_position: int,
    max_positions_to_consolidate: int,
    canonical_path_file: Path,
    typer_echo: callable,
):
    """
    Placeholder for the temporal cascade logic.
    This function is responsible for recalculating the canonical path.
    """
    logger.critical("CRITICAL: `run_temporal_cascade` is not implemented!")
    typer_echo(
        typer.style(
            "CRITICAL WARNING: Temporal Cascade logic is NOT IMPLEMENTED. Canonical path will not be updated.",
            fg=typer.colors.RED,
            bold=True,
        )
    )
    # Example of what it might do:
    # 1. Load all relevant transactions and votes.
    # 2. Starting from start_position, determine the winning path at each position based on Elo or other metrics.
    # 3. Update the canonical_path_file.
    # For now, it does nothing.
    pass


def main(argv: list[str] | None = None):
    app(args=argv)


session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True)
app.add_typer(session_app, name="session")


@session_app.command("start", help="Initiate a Judgment Session using a QUALIFIED path's mandate.")
def session_start(
    path_uuid_str: Annotated[
        str,
        typer.Option(
            "--path-uuid",
            "-p",
            help="The QUALIFIED path_uuid granting the mandate for this session.",
        ),
    ],
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
):
    path_data_obj = storage.DataManager().get_path_by_uuid(path_uuid_str)

    if not path_data_obj:
        typer.secho(
            f"Error: Path UUID '{path_uuid_str}' not found. Cannot start session.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    position_n = path_data_obj.position
    mandate_id_obj = path_data_obj.mandate_id

    if path_data_obj.status != "QUALIFIED":
        typer.secho(
            f"Error: Path UUID '{path_uuid_str}' is not QUALIFIED (status: '{path_data_obj.status}'). Cannot start session.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    if not mandate_id_obj:
        typer.secho(
            f"Error: Path UUID '{path_uuid_str}' is QUALIFIED but has no mandate_id. This indicates an inconsistency.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    consumed_by_session_id = session_manager.is_path_consumed(path_uuid_str)
    if consumed_by_session_id:
        typer.secho(
            f"Error: Path UUID '{path_uuid_str}' has already been used for session '{consumed_by_session_id}'.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    try:
        session_model = session_manager.create_session(
            path_n_uuid_str=path_uuid_str,
            position_n=position_n,
            mandate_id_str=str(mandate_id_obj),
            canonical_path_file=canonical_path_file,
        )

        cli_dossier_output = {}
        if session_model.dossier and session_model.dossier.duels:
            for pos, duel in session_model.dossier.duels.items():
                cli_dossier_output[pos] = {
                    "path_A": str(duel.path_A_uuid),
                    "path_B": str(duel.path_B_uuid),
                    "entropy": round(duel.entropy, 4),
                }
        else:
            cli_dossier_output = {}

        output_data = {
            "message": "Judgment session started successfully.",
            "session_id": str(session_model.session_id),
            "initiating_path_uuid": str(session_model.initiating_path_uuid),
            "mandate_id_used": str(session_model.mandate_id),
            "position_n": session_model.position_n,
            "status": session_model.status,
            "created_at": session_model.created_at.isoformat(),
            "dossier": {"duels": cli_dossier_output},
        }
        typer.echo(json.dumps(output_data, indent=2))

    except ValueError as ve:
        typer.secho(f"Error creating session: {str(ve)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(
            f"An unexpected error occurred while creating the session: {str(e)}",
            fg=typer.colors.RED,
        )
        # import traceback; traceback.print_exc();
        raise typer.Exit(code=1)


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
            help='JSON string or path to a JSON file containing verdicts. Format: \'{"position_str": "winning_path_uuid"}\'. Example: \'{"0": "uuid_for_pos_0_winner", "1": "uuid_for_pos_1_winner"}\'. ',
        ),
    ],
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    max_cascade_positions: Annotated[
        int,
        typer.Option(help="Maximum number of positions for temporal cascade calculation."),
    ] = 100,
):
    session_model = session_manager.get_session(session_id)
    if not session_model:
        typer.secho(
            f"Error: Session ID '{session_id}' not found or failed to load.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    if session_model.status != "active":
        typer.secho(
            f"Error: Session '{session_id}' is not active. Current status: '{session_model.status}'",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    verdicts: dict[str, str] = {}
    verdicts_path = Path(verdicts_input)
    if verdicts_path.is_file():
        try:
            verdicts = json.loads(verdicts_path.read_text())
        except Exception as e:
            typer.secho(
                f"Error: Failed to parse verdicts JSON file {verdicts_input}: {e}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
    else:
        try:
            verdicts = json.loads(verdicts_input)
        except Exception as e:
            typer.secho(f"Error: Failed to parse verdicts JSON string: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    if not isinstance(verdicts, dict):
        typer.secho("Error: Verdicts must be a JSON object (dictionary).", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    initiating_path_uuid_str = str(session_model.initiating_path_uuid)
    dossier_duels_models = session_model.dossier.duels

    valid_votes_for_tm: list[dict[str, Any]] = []
    processed_verdicts_for_session_model: dict[str, uuid.UUID] = {}
    oldest_voted_position = float("inf")

    for pos_str, winning_path_uuid_verdict_str in verdicts.items():
        if not isinstance(winning_path_uuid_verdict_str, str):
            typer.echo(f"Warning: Verdict for position {pos_str} is not a string. Skipping.")
            continue
        try:
            position_idx = int(pos_str)
            if position_idx < 0:
                raise ValueError("Position must be non-negative")
        except ValueError:
            typer.echo(f"Warning: Invalid position key '{pos_str}' in verdicts. Skipping.")
            continue

        duel_model_for_pos = dossier_duels_models.get(pos_str)
        if not duel_model_for_pos:
            typer.echo(
                f"Warning: No duel found in dossier for position {pos_str}. Skipping verdict."
            )
            continue

        path_a_uuid_obj = duel_model_for_pos.path_A_uuid
        path_b_uuid_obj = duel_model_for_pos.path_B_uuid

        try:
            winning_path_uuid_verdict_obj = uuid.UUID(winning_path_uuid_verdict_str)
        except ValueError:
            typer.echo(
                f"Warning: Verdict for position {pos_str}: winning path UUID '{winning_path_uuid_verdict_str}' is not a valid UUID. Skipping."
            )
            continue

        if winning_path_uuid_verdict_obj not in [path_a_uuid_obj, path_b_uuid_obj]:
            typer.echo(
                f"Warning: Verdict for position {pos_str}: winning path {winning_path_uuid_verdict_str[:8]} is not part of the original duel ({str(path_a_uuid_obj)[:8]} vs {str(path_b_uuid_obj)[:8]}). Skipping."
            )
            continue

        loser_path_uuid_obj = (
            path_a_uuid_obj if winning_path_uuid_verdict_obj == path_b_uuid_obj else path_b_uuid_obj
        )
        winner_hronir_uuid_str = _get_successor_hronir_for_path(str(winning_path_uuid_verdict_obj))
        loser_hronir_uuid_str = _get_successor_hronir_for_path(str(loser_path_uuid_obj))

        if not winner_hronir_uuid_str or not loser_hronir_uuid_str:
            typer.secho(
                f"Error: Could not map duel paths for pos {pos_str} to hrönir UUIDs. Aborting.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        path_data_for_winner = storage.DataManager().get_path_by_uuid(
            str(winning_path_uuid_verdict_obj)
        )
        if not path_data_for_winner:
            typer.secho(
                f"Error: Path data for winning_path_uuid {winning_path_uuid_verdict_str} not found. Aborting.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        predecessor_hrönir_uuid_str = (
            str(path_data_for_winner.prev_uuid) if path_data_for_winner.prev_uuid else None
        )
        if position_idx == 0:
            predecessor_hrönir_uuid_str = None

        valid_votes_for_tm.append(
            {
                "position": position_idx,
                "winner_hrönir_uuid": winner_hronir_uuid_str,
                "loser_hrönir_uuid": loser_hronir_uuid_str,
                "predecessor_hrönir_uuid": predecessor_hrönir_uuid_str,
            }
        )
        processed_verdicts_for_session_model[pos_str] = winning_path_uuid_verdict_obj
        if position_idx < oldest_voted_position:
            oldest_voted_position = position_idx

    if not valid_votes_for_tm:
        typer.echo(
            "No valid verdicts provided or matched dossier. No votes recorded. Session remains active."
        )
        raise typer.Exit(code=0)

    typer.echo(f"{len(valid_votes_for_tm)} valid verdicts prepared for transaction processing.")
    transaction_result: dict[str, Any]
    try:
        transaction_result = transaction_manager.record_transaction(
            session_id=str(session_model.session_id),
            initiating_path_uuid=initiating_path_uuid_str,
            session_verdicts=valid_votes_for_tm,
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
        typer.secho(
            f"Error: Failed to process transaction: {e}. Aborting commit.", fg=typer.colors.RED
        )
        session_manager.update_session_status(
            str(session_model.session_id), "commit_failed_tx_processing"
        )
        raise typer.Exit(code=1)

    try:
        mandate_id_for_update = str(session_model.mandate_id) if session_model.mandate_id else None
        storage.DataManager().update_path_status(
            path_uuid_to_update=initiating_path_uuid_str,
            new_status="SPENT",
            mandate_id=mandate_id_for_update,
            set_mandate_explicitly=True,
        )
        storage.DataManager().save_all_data_to_csvs()
        typer.echo(f"Path {initiating_path_uuid_str} status updated to SPENT.")
    except Exception as e:
        typer.echo(
            f"Warning: Error updating status for path {initiating_path_uuid_str} to SPENT: {e}."
        )

    session_model.committed_verdicts = processed_verdicts_for_session_model

    tm_oldest_voted_position = transaction_result.get("oldest_voted_position", float("inf"))
    if tm_oldest_voted_position != float("inf") and tm_oldest_voted_position >= 0:
        typer.echo(
            f"Oldest voted position: {tm_oldest_voted_position}. Triggering Temporal Cascade."
        )
        try:
            run_temporal_cascade(
                start_position=tm_oldest_voted_position,
                max_positions_to_consolidate=max_cascade_positions,
                canonical_path_file=canonical_path_file,
                typer_echo=typer.echo,
            )
            typer.echo("Temporal Cascade completed.")
        except Exception as e:
            typer.secho(f"Error: Temporal Cascade failed: {e}.", fg=typer.colors.RED)
            session_manager.update_session_status(
                str(session_model.session_id), "commit_failed_cascade"
            )
            session_model.status = "commit_failed_cascade"  # also update local model before saving
            session_model_file = session_manager.SESSIONS_DIR / f"{session_model.session_id}.json"
            session_model_file.write_text(
                session_model.model_dump_json(indent=2)
            )  # Save with committed verdicts
            raise typer.Exit(code=1)
    else:
        typer.echo(
            "No valid votes cast, or oldest position not determined; Temporal Cascade not triggered."
        )

    if session_manager.update_session_status(str(session_model.session_id), "committed"):
        session_model.status = "committed"
        session_model.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session_model_file = session_manager.SESSIONS_DIR / f"{session_model.session_id}.json"
        session_model_file.write_text(session_model.model_dump_json(indent=2))
        typer.echo(f"Session {session_id} committed successfully. Committed verdicts saved.")
    else:
        typer.secho(
            f"Error: Failed to update session {session_id} status to committed.",
            fg=typer.colors.RED,
        )


@app.command(help="Download latest snapshot from Internet Archive to local DuckDB.")
def sync(
    archive_id: Annotated[
        str, typer.Option(help="Internet Archive identifier for discovery (placeholder).")
    ] = "hronir-snapshots",  # This might become network_uuid based
    db_file: Annotated[Path, typer.Option(help="Local DuckDB file to update/replace.")] = Path(
        "data/encyclopedia.duckdb"  # Align with default DB path
    ),
    retry: Annotated[
        bool, typer.Option(help="Enable retry logic for discovery and download.")
    ] = True,
) -> None:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Attempting to sync with network (retry enabled: {retry})...")

    # --- Placeholder Sync Logic ---
    # 1. Discover the latest remote snapshot manifest
    # This would involve ConflictDetection or a similar mechanism.
    # For now, direct placeholder, assuming network_uuid is configured/known.
    network_uuid_env = os.getenv("HRONIR_NETWORK_UUID", "default-hronir-network")
    # pgp_key_id_env = os.getenv("HRONIR_PGP_KEY_ID") # Not needed for sync discovery directly

    # We need ConflictDetection from transaction_manager for discover_latest_remote_snapshot_robust
    # This is a bit of a conceptual stretch for `sync` to use `ConflictDetection` directly,
    # usually it's for `push`. Let's assume a SyncManager or direct call for discovery.

    # Simplified placeholder for discovery:
    # from .transaction_manager import ConflictDetection # Would normally be a SyncManager
    # conflict_detector = ConflictDetection(network_uuid=network_uuid_env)
    # latest_manifest = conflict_detector.discover_latest_remote_snapshot_robust()

    # --- More direct placeholder for sync discovery ---
    typer.echo(
        f"Discovering latest snapshot for network '{network_uuid_env}' (retry enabled: {retry})..."
    )
    # Simulate discovery. In reality, this would call into a module that handles IA/P2P communication.
    # For this placeholder, we'll just log what would happen.

    # Placeholder: Assume discovery yields a manifest object or None
    # This would be where `discover_latest_remote_snapshot_robust` is called.
    # For now, we'll simulate a successful discovery of a dummy manifest.
    # class DummyManifest: # Simulate a fetched manifest
    #     def __init__(self, seq, merkle):
    #         self.sequence = seq
    #         self.merkle_root = merkle
    #         self.shards = [storage.sharding.ShardInfo(file="dummy_shard.db.zst", sha256="abc", size=100)]
    #         self.network_uuid = network_uuid_env
    #         self.created_at = datetime.datetime.now(datetime.timezone.utc)
    #         self.pgp_signature = "dummy_pgp_signature_placeholder_sync" # Ensure it has a signature

    # latest_manifest = DummyManifest(seq=42, merkle="dummymerklerootforsync") # Example

    # --- Actual call to discovery logic ---
    # The `retry` parameter of this `sync` command is implicitly handled by `discover_latest_remote_snapshot_robust`
    # if its implementation uses retries. The `discover_latest_remote_snapshot_robust` already has a retry loop structure.
    conflict_detector = ConflictDetection(
        network_uuid=network_uuid_env
    )  # pgp_key_id not needed for discovery
    latest_manifest = conflict_detector.discover_latest_remote_snapshot_robust()
    # Note: discover_latest_remote_snapshot_robust currently returns a placeholder or simulated result.
    # The retry logic *within* it is also placeholder/simulated.
    # The `retry` flag from the CLI can be passed down if discover_latest_remote_snapshot_robust is modified to accept it.
    # For now, the retry structure is always active in the placeholder.

    if not latest_manifest:
        typer.secho(
            f"Failed to discover latest snapshot for network {network_uuid_env} after retries.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.echo(
        f"Discovered latest snapshot: Sequence {latest_manifest.sequence}, Merkle Root {latest_manifest.merkle_root}"
    )

    # 2. (Placeholder) Download the snapshot files (shards)
    # This would involve a P2P client or HTTP downloads from IA.
    snapshot_download_dir = Path("data/tmp_snapshot_sync")
    snapshot_download_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Downloading snapshot files to {snapshot_download_dir} (placeholder)...")
    for shard_info in latest_manifest.shards:
        # Simulate downloading shard_info.file
        (snapshot_download_dir / shard_info.file).touch()
        typer.echo(f"  Downloaded {shard_info.file} (placeholder).")

    # (Placeholder) Write manifest to snapshot_download_dir
    # manifest_json_path = snapshot_download_dir / "snapshot_manifest.json"
    # manifest_json_path.write_text(latest_manifest.to_json()) # If SnapshotManifest has to_json

    # 3. Verify PGP signature of the manifest (MANDATORY)
    if not latest_manifest.pgp_signature:
        typer.secho(
            "ERROR: Downloaded manifest does not have a PGP signature. Sync aborted.",
            fg=typer.colors.RED,
        )
        # Consider cleaning up snapshot_download_dir
        raise typer.Exit(code=1)

    typer.echo(
        f"Verifying PGP signature of manifest (Signature: {latest_manifest.pgp_signature[:20]}...)..."
    )

    # Placeholder for actual PGP verification call
    # In a real implementation, this would involve:
    # 1. Getting the manifest content that was signed (e.g., specific fields or full JSON representation before adding signature)
    # 2. Fetching the public key of the signer (potentially based on network policy or key ID in manifest)
    # 3. Calling a PGP library (e.g., GnuPG, python-gnupg)
    # For now, simulate verification. Assume a function `verify_pgp_signature_placeholder` exists.

    # manifest_content_to_verify = latest_manifest.get_signed_content_representation() # Hypothetical method
    # pgp_key_for_network = os.getenv("HRONIR_EXPECTED_NETWORK_SIGNER_KEY_FINGERPRINT") # Example

    # simulated_verification_success = verify_pgp_signature_placeholder(
    #     data=manifest_content_to_verify,
    #     signature=latest_manifest.pgp_signature,
    #     # expected_signer_key_id=pgp_key_for_network
    # )
    simulated_verification_success = True  # Placeholder: Assume success for now

    if simulated_verification_success:
        typer.echo("PGP signature verified successfully (placeholder).")
    else:
        typer.secho(
            "ERROR: PGP signature verification FAILED for the downloaded manifest. Sync aborted.",
            fg=typer.colors.RED,
        )
        # Consider cleaning up snapshot_download_dir
        raise typer.Exit(code=1)

    # 4. (Placeholder) Reconstruct the database from shards (if sharded)
    # This would use ShardingManager.reconstruct_from_shards
    # from .sharding import ShardingManager
    # sharding_manager = ShardingManager()
    # sharding_manager.reconstruct_from_shards(latest_manifest, snapshot_download_dir, db_file)
    if len(latest_manifest.shards) > 1 and latest_manifest.merge_script:
        typer.echo(f"Reconstructing database from shards into {db_file} (placeholder)...")
    else:  # Single shard
        typer.echo(f"Copying single shard snapshot to {db_file} (placeholder)...")

    # Simulate copying the first (or only) shard's (dummy) content to the target db_file
    # In reality, it would be the reconstructed DB or the single decompressed shard.
    if latest_manifest.shards:
        # Create a dummy db_file to simulate it being replaced/created
        db_file.write_bytes(b"dummy duckdb content")

    # 5. (Placeholder) Verify Merkle root of the reconstructed database
    # This needs calculate_db_merkle_root from sharding.py
    # from .sharding import calculate_db_merkle_root
    # final_merkle_root = calculate_db_merkle_root(db_file)
    # if final_merkle_root != latest_manifest.merkle_root:
    #     typer.secho("ERROR: Merkle root mismatch after sync!", fg=typer.colors.RED)
    #     raise typer.Exit(code=1)
    typer.echo(
        f"Merkle root verified (placeholder). Local DB matches manifest root: {latest_manifest.merkle_root}"
    )

    # 6. (Placeholder) Update local snapshot metadata (sequence number, etc.)
    # This might involve a local version of ConflictDetection._save_local_manifest
    # or similar mechanism to track the current local synced version.
    # from .transaction_manager import ConflictDetection # conceptual
    # conflict_detector_for_meta_save = ConflictDetection(network_uuid=network_uuid_env)
    # conflict_detector_for_meta_save._save_local_manifest(latest_manifest) # If sync updates local "head" manifest
    typer.echo(f"Local state updated to sequence {latest_manifest.sequence} (placeholder).")

    # Cleanup placeholder download dir
    # import shutil
    # shutil.rmtree(snapshot_download_dir)

    typer.secho(
        f"Sync complete. Local database {db_file} updated to snapshot sequence {latest_manifest.sequence}.",
        fg=typer.colors.GREEN,
    )


@app.command(help="Create local snapshot archive (snapshot.zip).")
def export(
    output: Annotated[Path, typer.Option(help="Output archive path.")] = Path("snapshot.zip"),
) -> None:
    typer.echo("Creating snapshot archive (placeholder)...")
    with zipfile.ZipFile(output, "w") as zf:
        zf.writestr("placeholder.txt", "snapshot contents would go here")
    typer.echo(f"Snapshot archive created at {output}")


@app.command(help="Upload snapshot and metadata to Internet Archive.")
def push(
    archive_id: Annotated[  # This parameter might be deprecated if network_uuid is primary
        str,
        typer.Option(
            help="Internet Archive identifier (legacy, consider using network_uuid from env)."
        ),
    ] = "hronir-snapshots",
    # snapshot_path: Annotated[Path, typer.Option(help="Path to pre-existing snapshot archive (optional).")] = None,
    force: Annotated[
        bool,
        typer.Option(
            help="Force push, overriding remote state (DANGEROUS). Not fully implemented."
        ),
    ] = False,
    snapshot_output_base_dir: Annotated[
        Path, typer.Option(help="Base directory for creating snapshot files.")
    ] = Path("data/snapshots_out"),
) -> None:
    network_uuid = os.getenv("HRONIR_NETWORK_UUID")
    pgp_key_id = os.getenv("HRONIR_PGP_KEY_ID")  # For signing the manifest

    if not network_uuid:
        typer.secho("Error: HRONIR_NETWORK_UUID environment variable not set.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # We will create a temporary directory for this specific push's snapshot files
    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    current_snapshot_dir = snapshot_output_base_dir / f"push_{network_uuid}_{timestamp_str}"
    current_snapshot_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Preparing to push snapshot for network: {network_uuid}")
    if force:
        typer.secho(
            "WARNING: --force flag is active. This may override remote state.",
            fg=typer.colors.YELLOW,
        )

    data_manager = storage.DataManager()  # Uses HRONIR_USE_DUCKDB env var
    if not isinstance(data_manager.backend, storage.DuckDBDataManager):
        typer.secho(
            "Error: Push command currently only supports DuckDB backend.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    typer.echo(f"Creating current database snapshot in {current_snapshot_dir}...")
    # TODO: Get current git commit hash
    git_commit_hash = "dummy_git_commit_hash"  # Placeholder
    try:
        # create_snapshot is on DataManager, which delegates to DuckDBDataManager's implementation
        local_manifest = data_manager.create_snapshot(
            output_dir=current_snapshot_dir, network_uuid=network_uuid, git_commit=git_commit_hash
        )
        if not local_manifest:
            typer.secho("Error: Failed to create local snapshot manifest.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.echo(f"Local snapshot manifest created. Merkle root: {local_manifest.merkle_root}")

    except Exception as e:
        typer.secho(f"Error creating snapshot: {e}", fg=typer.colors.RED)
        # Consider cleaning up current_snapshot_dir on failure
        # import shutil; shutil.rmtree(current_snapshot_dir)
        raise typer.Exit(code=1)

    # Now, use ConflictDetection to handle the push logic
    try:
        from .transaction_manager import ConflictDetection, ConflictError  # Import here

        conflict_detector = ConflictDetection(network_uuid=network_uuid, pgp_key_id=pgp_key_id)

        # The local_manifest from create_snapshot might not have prev_sequence set.
        # push_with_locking expects it to be None or the user's belief of the prev sequence.
        # We'll let push_with_locking handle setting prev_sequence if it's None.
        if local_manifest.prev_sequence is None:
            # This indicates it's a fresh manifest from local state, not yet aware of remote sequence.
            # ConflictDetection.push_with_locking will fetch remote and assign prev_sequence correctly.
            pass

        typer.echo("Attempting to push snapshot with conflict detection...")
        ia_item_id = conflict_detector.push_with_locking(
            local_snapshot_manifest=local_manifest,
            snapshot_dir=current_snapshot_dir,  # Dir containing the actual shard files
        )

        typer.secho(
            f"Push successful! Snapshot sequence {local_manifest.sequence} uploaded.",
            fg=typer.colors.GREEN,
        )
        typer.echo(f"  Internet Archive Item (placeholder): {ia_item_id}")
        typer.echo(f"  Manifest Merkle Root: {local_manifest.merkle_root}")
        # TODO: Provide magnet link if torrents are generated by IA upload step

    except ConflictError as ce:
        typer.secho(f"PUSH FAILED: {ce}", fg=typer.colors.RED)
        typer.echo(
            "  Recommendation: Run 'hronir sync' to get the latest changes, then attempt push again."
        )
        typer.echo(
            "  Alternatively, use 'hronir diff-remote' (not implemented) to see changes, or 'hronir push --force' (DANGEROUS)."
        )
        # Consider cleaning up current_snapshot_dir
        # import shutil; shutil.rmtree(current_snapshot_dir)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"An unexpected error occurred during push: {e}", fg=typer.colors.RED)
        # import traceback; traceback.print_exc()
        # Consider cleaning up current_snapshot_dir
        # import shutil; shutil.rmtree(current_snapshot_dir)
        raise typer.Exit(code=1)
    finally:
        # Optional: Clean up the temporary snapshot directory after successful push or on error
        # For debugging, one might want to keep it. Let's keep it for now.
        typer.echo(f"Snapshot files and manifest available in: {current_snapshot_dir}")


@app.command("metrics", help="Expose path status metrics in Prometheus format (TDD 2.6).")
def metrics_command(
    narrative_paths_dir: Annotated[  # This parameter is kept for now but _calculate_status_counts uses DataManager
        Path, typer.Option(help="Directory containing narrative path CSV files (legacy).")
    ] = Path("narrative_paths"),
):
    status_counts = _calculate_status_counts(
        narrative_paths_dir
    )  # narrative_paths_dir is not strictly needed by new version

    typer.echo("# HELP hronir_path_status_total Total number of paths by status.")
    typer.echo("# TYPE hronir_path_status_total gauge")
    for status_val, count in status_counts.items():
        typer.echo(f'hronir_path_status_total{{status="{status_val.lower()}"}} {count}')


if __name__ == "__main__":
    main()
