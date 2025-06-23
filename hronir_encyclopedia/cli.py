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

from . import database, gemini_util, ratings, storage, transaction_manager

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
    forking_path_dir: Annotated[
        Path, typer.Option(help="Directory containing forking path CSV files.")
    ] = Path("forking_path"),
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
        forking_path_dir=forking_path_dir,
        ratings_dir=ratings_dir,
        typer_echo=typer.echo,
    )
    typer.echo("Manual canon recovery via Temporal Cascade complete.")


# Command `export` and `tree` removed as they depended on the old book structure.


@app.command(help="Validate a chapter file (basic check).")
def validate(
    chapter: Annotated[
        Path,
        typer.Argument(
            help="Path to chapter markdown file.", exists=True, dir_okay=False, readable=True
        ),
    ],
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
    chapter: Annotated[
        Path,
        typer.Argument(
            help="Path to chapter markdown file.", exists=True, dir_okay=False, readable=True
        ),
    ],
    prev: Annotated[
        str, typer.Option(help="UUID of the previous chapter.")
    ] = None,  # Made optional as in original
):
    """
    Stores a given chapter file into the hrönir library, associating it with a predecessor UUID if provided.
    """
    uuid_str = storage.store_chapter(chapter, prev_uuid=prev)
    typer.echo(uuid_str)


# Helper function to find successor hrönir_uuid for a given fork_uuid
# This could also live in storage.py if it's deemed generally useful
def _get_successor_hronir_for_fork(fork_uuid_to_find: str, forking_path_dir: Path) -> str | None:
    """Return the hrönir UUID that a fork points to using the narrative graph."""
    from . import graph_logic

    graph = graph_logic.get_narrative_graph(forking_path_dir)
    for _u, v, data in graph.edges(data=True):
        if data.get("fork_uuid") == fork_uuid_to_find:
            return v
    return None


# The 'vote' command has been removed as direct voting is deprecated.
# All voting now occurs through the 'session commit' flow.


@app.command(help="Validate and repair storage, audit forking CSVs.")
def audit():
    """
    Performs audit operations: validates chapters in the library,
    and audits forking path CSV files.
    """
    library_dir = Path("the_library")
    typer.echo(f"Auditing library directory: {library_dir}...")
    # This part needs to be adjusted. `validate_or_move` expects a specific file.
    # We should iterate through hrönirs in a way that's compatible with `purge_fake_hronirs` logic,
    # or rely on `purge_fake_hronirs` called by `clean` command.
    # For now, let's simplify the audit's scope for this command, focusing on forking paths.
    # A more thorough audit of `the_library` is implicitly handled by `storage.chapter_exists`
    # when other commands use it, and explicitly by `clean`.
    # Consider enhancing `audit` in the future if a standalone deep library audit is needed here.
    typer.echo(
        f"Auditing hrönirs in {library_dir} (basic check via purge_fake_hronirs in 'clean' command)..."
    )
    # No direct action on library_dir here, purge_fake_hronirs in 'clean' is more comprehensive.

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Auditing forking path directory: {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"):
            storage.audit_forking_csv(csv_file)
        from . import graph_logic

        if graph_logic.is_narrative_consistent(fork_dir):
            typer.echo("Narrative graph is consistent (no cycles detected).")
        else:
            typer.echo("WARNING: Narrative graph contains cycles!")
    else:
        typer.echo(f"Forking path directory {fork_dir} not found. Skipping audit.")
    typer.echo("Audit complete (Note: hrönir validation primarily via 'clean' command).")


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
        f"Synthesizing two new hrönirs from predecessor '{prev}' " f"at position {position}..."
    )
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
    # The 'base' argument for get_ranking was Path(base), so passing ratings_dir directly.
    ranking_data = ratings.get_ranking(position, base=ratings_dir)
    if ranking_data.empty:
        typer.echo(f"No ranking data found for position {position}.")
    else:
        typer.echo(f"Ranking for Position {position}:")
        # Typer automatically handles printing DataFrames nicely with rich if available,
        # otherwise, it falls back to standard print. For explicit control, use to_string().
        typer.echo(ranking_data.to_string(index=False))


@app.command(help="Obtém o duelo de máxima entropia entre forks para uma posição.")
def get_duel(
    position: Annotated[
        int, typer.Option(help="A posição do capítulo para a qual obter o duelo de forks.")
    ],
    ratings_dir: Annotated[
        Path, typer.Option(help="Diretório contendo arquivos CSV de classificação.")
    ] = Path("ratings"),
    forking_path_dir: Annotated[
        Path, typer.Option(help="Diretório contendo arquivos CSV de caminhos de bifurcação.")
    ] = Path("forking_path"),
    canonical_path_file: Annotated[
        Path, typer.Option(help="Caminho para o arquivo JSON do caminho canônico.")
    ] = Path("data/canonical_path.json"),
):
    """
    Obtém o duelo de forks de máxima entropia para uma determinada posição,
    considerando a linhagem canônica.
    """
    predecessor_hronir_uuid: str | None = None
    if position > 0:
        canonical_fork_info_prev_pos = storage.get_canonical_fork_info(
            position - 1, canonical_path_file
        )
        if not canonical_fork_info_prev_pos or "hrönir_uuid" not in canonical_fork_info_prev_pos:
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
        predecessor_hronir_uuid = canonical_fork_info_prev_pos["hrönir_uuid"]
    elif position < 0:
        typer.echo(
            json.dumps(
                {"error": "Posição inválida. Deve ser >= 0.", "position_requested": position},
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # `determine_next_duel` agora lida com forks
    duel_info = ratings.determine_next_duel(
        position=position,
        predecessor_hronir_uuid=predecessor_hronir_uuid,
        forking_path_dir=forking_path_dir,
        ratings_dir=ratings_dir,
    )

    if duel_info:
        # O formato de duel_info já é:
        # {
        #   "position": position,
        #   "strategy": "max_entropy_duel",
        #   "entropy": max_entropy,
        #   "duel_pair": {
        #       "fork_A": duel_fork_A_uuid,
        #       "fork_B": duel_fork_B_uuid,
        #   }
        # }
        typer.echo(json.dumps(duel_info, indent=2))
    else:
        typer.echo(
            json.dumps(
                {
                    "error": "Não foi possível determinar um duelo de forks. "
                    "Verifique se existem forks elegíveis suficientes (pelo menos 2) para a linhagem e posição.",
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
        bool, typer.Option("--git", help="Also stage deleted files for removal in the Git index.")
    ] = False,
):
    """
    Cleans up storage by removing entries identified as 'fake' or invalid.
    Optionally, stages these deletions in Git.
    """
    typer.echo("Starting cleanup process...")
    storage.purge_fake_hronirs()  # Assumes this function prints its actions

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Cleaning fake forking CSVs in {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"):
            storage.purge_fake_forking_csv(csv_file)  # Assumes this function prints its actions
    else:
        typer.echo(f"Forking path directory {fork_dir} not found. Skipping.")

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


# Placeholder for 'submit' command if it was meant to be kept.
# If not, it can be removed. For now, it's commented out as per original structure.
# @app.command(help="Submit changes (placeholder).")
# def submit_cmd():
#     typer.echo("Submit command is in development.")


def main(argv: list[str] | None = None):
    # If argv is None, Typer's app() will use sys.argv by default (which is what we want for CLI execution).
    # If argv is provided (e.g., from a test), app() will use that specific list of arguments.
    app(args=argv)


# New session management commands
session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True)

# Import placed here to avoid circular imports
from . import session_manager  # noqa: E402

app.add_typer(session_app, name="session")


@session_app.command("start", help="Initiate a Judgment Session using a QUALIFIED fork's mandate.")
def session_start(
    # position: Annotated[int, typer.Option("--position", "-p", help="The current position N of the new fork being created.")], # Position is now derived from fork_uuid
    fork_uuid: Annotated[
        str,
        typer.Option(
            "--fork-uuid",
            "-f",
            help="The QUALIFIED fork_uuid granting the mandate for this session.",
        ),
    ],
    ratings_dir: Annotated[
        Path, typer.Option(help="Directory containing rating CSV files.")
    ] = Path("ratings"),
    forking_path_dir: Annotated[
        Path, typer.Option(help="Directory containing forking path CSV files.")
    ] = Path("forking_path"),
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
):
    """
    Initiates a new Judgment Session (SC.8, SC.9).

    This command allows a user to exercise the 'mandate for judgment' granted by a
    fork that has achieved `QUALIFIED` status. The `fork_uuid` of this qualified
    fork must be provided.

    The system will:
    1. Validate the provided `fork_uuid`:
        - Ensure it exists.
        - Confirm its status is `QUALIFIED`.
        - Verify it has an associated `mandate_id`.
        - Check it hasn't been `SPENT` (i.e., already used for a session).
    2. Determine `N`, the position of the qualified `fork_uuid`.
    3. Generate a static "dossier" containing the duel of maximum entropy for each
       prior position (from `N-1` down to `0`), based on the canonical path at the
       moment the session is started.
    4. Create a new session record, store the dossier, and mark the `fork_uuid` as
       consumed for session initiation purposes.
    5. Output the `session_id` and the dossier to the user.

    If `N=0` (the qualified fork is at position 0), no prior positions exist to be
    judged. An empty dossier is created, and the session is immediately ready for
    a (vacuous) commit, primarily to log the use of the mandate.
    """
    # Position is now derived from the fork_uuid itself, not passed as a separate CLI arg.
    # This makes the command simpler and less prone to user error.
    # We will fetch the fork's details to get its position N.

    # Validate the fork_uuid - it must exist in forking_path
    fork_data = storage.get_fork_file_and_data(fork_uuid, fork_dir_base=forking_path_dir)

    if not fork_data:
        typer.echo(
            json.dumps(
                {
                    "error": f"Fork UUID {fork_uuid} not found in any forking path CSV. Cannot start session."
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Get position N from the fork_data
    position_n_str = fork_data.get("position")
    if position_n_str is None:
        typer.echo(
            json.dumps(
                {"error": f"Fork UUID {fork_uuid} is missing position information."}, indent=2
            )
        )
        raise typer.Exit(code=1)
    try:
        position = int(position_n_str)  # position_n is N
    except ValueError:
        typer.echo(
            json.dumps(
                {"error": f"Fork UUID {fork_uuid} has an invalid position: {position_n_str}."},
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    if position < 0:  # Should be caught by storage validation, but good to check.
        typer.echo(
            json.dumps(
                {"error": f"Fork UUID {fork_uuid} has an invalid negative position: {position}."},
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Validate the fork_uuid - it must exist in forking_path
    if not storage.forking_path_exists(fork_uuid, fork_dir=forking_path_dir):
        typer.echo(
            json.dumps(
                {
                    "error": f"Fork UUID {fork_uuid} not found in forking paths. Cannot start session."
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Check if fork_uuid has already been consumed for a session (SC.8)
    consumed_by_session_id = session_manager.is_fork_consumed(fork_uuid)
    if consumed_by_session_id:
        typer.echo(
            json.dumps(
                {
                    "error": "This fork_uuid has already been used to initiate a judgment session.",
                    "fork_uuid": fork_uuid,
                    "session_id": consumed_by_session_id,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    if position == 0:  # Corrected condition: No prior positions if N=0
        # If N=0, there are no prior positions (N-1 to 0) to judge.
        # Create an empty session and mark fork as consumed.
        session_id = str(uuid.uuid4())
        session_manager.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_file = session_manager.SESSIONS_DIR / f"{session_id}.json"
        session_data = {
            "session_id": session_id,
            "initiating_fork_uuid": fork_uuid,
            "position_n": position,
            "dossier": {"duels": {}},  # No duels for N=0
            "status": "active",
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        session_manager.mark_fork_as_consumed(fork_uuid, session_id)
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

    # Validate the fork_uuid's status and get mandate_id
    fork_data = storage.get_fork_file_and_data(fork_uuid, fork_dir_base=forking_path_dir)

    if not fork_data:
        typer.echo(
            json.dumps(
                {
                    "error": f"Fork UUID {fork_uuid} details not found in any forking path CSV. Cannot start session."
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    fork_status = fork_data.get("status")
    if fork_status != "QUALIFIED":
        typer.echo(
            json.dumps(
                {
                    "error": f"Fork UUID {fork_uuid} does not have 'QUALIFIED' status. Current status: '{fork_status}'. Cannot start session.",
                    "fork_uuid": fork_uuid,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    mandate_id = fork_data.get("mandate_id")
    if not mandate_id:
        typer.echo(
            json.dumps(
                {
                    "error": f"Fork UUID {fork_uuid} is 'QUALIFIED' but does not have an associated mandate_id. This indicates an inconsistency.",
                    "fork_uuid": fork_uuid,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # Verify that the provided --position matches the fork's actual position
    fork_actual_position = fork_data.get("position")
    # fork_actual_position might be string if read directly, ensure comparison is fair
    try:
        if fork_actual_position is not None and int(fork_actual_position) != position:
            typer.echo(
                json.dumps(
                    {
                        "error": f"Provided --position {position} does not match the fork's actual position {fork_actual_position}.",
                        "fork_uuid": fork_uuid,
                    },
                    indent=2,
                )
            )
            raise typer.Exit(code=1)
    except ValueError:
        typer.echo(
            json.dumps(
                {
                    "error": f"Fork's actual position '{fork_actual_position}' is not a valid number.",
                    "fork_uuid": fork_uuid,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=1)

    # If N=0, there are no prior positions (N-1 to 0) to judge.
    # The create_session logic in session_manager will handle empty dossier for N=0.
    # The special handling for position == 0 in cli.py can be simplified as session_manager now handles it.

    # Create the session and get the dossier (SC.9)
    try:
        session_info = session_manager.create_session(
            fork_n_uuid=fork_uuid,
            position_n=position,  # This is N, the position of the qualified fork
            mandate_id=mandate_id,  # Pass the validated mandate_id
            forking_path_dir=forking_path_dir,
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
    forking_path_dir: Path,
    ratings_dir: Path,
    typer_echo: callable,  # Pass typer.echo for output
):
    """
    Recalculates the canonical path starting from `start_position`.
    This is the core of SC.11.
    """
    typer_echo(f"Starting Temporal Cascade from position {start_position}...")

    from . import graph_logic

    if not graph_logic.is_narrative_consistent(forking_path_dir):
        typer_echo("Error: narrative graph contains cycles. Abort cascade.", err=True)
        return False

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
        canonical_path_data = {"title": "The Hrönir Encyclopedia - Canonical Path", "path": {}}

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
            # Get the hrönir_uuid from the *just determined* canonical fork of the previous position
            prev_pos_canonical_info = canonical_path_data["path"].get(str(current_pos_idx - 1))
            if not prev_pos_canonical_info or "hrönir_uuid" not in prev_pos_canonical_info:
                typer_echo(
                    f"Cascade broken: Canonical fork for position {current_pos_idx - 1} not found during cascade. Stopping."
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

        ranking_df = ratings.get_ranking(
            position=current_pos_idx,
            predecessor_hronir_uuid=predecessor_hronir_uuid_for_ranking,
            forking_path_dir=forking_path_dir,
            ratings_dir=ratings_dir,
        )

        if ranking_df.empty:
            typer_echo(
                f"Cascade: No ranking found for eligible forks at position {current_pos_idx}. Path ends here."
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

        champion_fork_uuid = ranking_df.iloc[0]["fork_uuid"]
        champion_hronir_uuid = ranking_df.iloc[0]["hrönir_uuid"]
        champion_elo = ranking_df.iloc[0]["elo_rating"]

        # current_entry_in_path = canonical_path_data["path"].get(position_str) # Not needed due to initial clear
        new_entry_for_path = {"fork_uuid": champion_fork_uuid, "hrönir_uuid": champion_hronir_uuid}

        # Since we cleared, any new entry is a change or reinstatement.
        canonical_path_data["path"][position_str] = new_entry_for_path
        typer_echo(
            f"Cascade: Position {current_pos_idx}: Set fork {champion_fork_uuid[:8]} (hrönir: {champion_hronir_uuid[:8]}, Elo: {champion_elo}) as canonical."
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
        typer.Option("--session-id", "-s", help="The ID of the active Judgment Session to commit."),
    ],
    verdicts_input: Annotated[
        str,
        typer.Option(
            "--verdicts",
            "-v",
            help='JSON string or path to a JSON file containing verdicts. Format: \'{"position_str": "winning_fork_uuid"}\'. Example: \'{"9": "fork_uuid_abc", "2": "fork_uuid_xyz"}\'. ',
        ),
    ],
    ratings_dir: Annotated[
        Path, typer.Option(help="Directory containing rating CSV files.")
    ] = Path(
        "ratings"
    ),  # Retained for run_temporal_cascade
    forking_path_dir: Annotated[
        Path, typer.Option(help="Directory containing forking path CSV files.")
    ] = Path(
        "forking_path"
    ),  # Retained for _get_successor_hronir_for_fork and cascade
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path(
        "data/canonical_path.json"
    ),  # Retained for run_temporal_cascade
    max_cascade_positions: Annotated[
        int, typer.Option(help="Maximum number of positions for temporal cascade calculation.")
    ] = 100,
):
    """
    Commits the verdicts for an active Judgment Session (SC.10, SC.11, SYS.1).

    This command finalizes a judgment session by:
    1.  Retrieving the specified active session and its static dossier.
    2.  Parsing the provided `verdicts_input` (either a JSON string or a file path
        to a JSON file). The verdicts map position numbers (as strings) to the
        `fork_uuid` chosen as the winner for that position's duel.
    3.  Validating each submitted verdict:
        - Ensures the position exists in the session's dossier.
        - Confirms the chosen winning `fork_uuid` was one of the two forks presented
          in the dossier for that position (Sovereignty of Curadoria, SC.10).
    4.  Preparing a list of valid votes, mapping winning/losing `fork_uuid`s to their
        respective successor `hrönir_uuid`s (needed for `ratings.record_vote`).
    5.  Invoking `transaction_manager.record_transaction` to:
        - Record all valid votes.
        - Check for any forks that become `QUALIFIED` as a result of these votes
          and update their status/mandate_id.
        - Create an immutable transaction block in the `data/transactions/` ledger (SYS.1),
          linking it to the previous transaction.
    6.  Updating the status of the session-initiating `fork_uuid` to `SPENT`.
    7.  Triggering the "Temporal Cascade" (`run_temporal_cascade`) starting from the
        oldest position that received a valid vote in this session (SC.11). This
        recalculates the canonical path.
    8.  Updating the session's status to `committed`.

    The `ratings_dir`, `forking_path_dir`, and `canonical_path_file` options are
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
                    {"error": f"Failed to parse verdicts JSON file {verdicts_input}: {e}"}, indent=2
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

    initiating_fork_uuid = session_data["initiating_fork_uuid"]
    dossier_duels = session_data.get("dossier", {}).get("duels", {})

    valid_votes_to_record = []
    processed_verdicts: dict[str, str] = (
        {}
    )  # For transaction record: position_str -> winning_fork_uuid
    oldest_voted_position = float("inf")

    for pos_str, winning_fork_uuid_verdict in verdicts.items():
        if not isinstance(winning_fork_uuid_verdict, str):
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
                        {"warning": f"Invalid position {pos_str} in verdicts. Skipping."}, indent=2
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

        fork_a = duel_for_pos["fork_A"]
        fork_b = duel_for_pos["fork_B"]

        if winning_fork_uuid_verdict not in [fork_a, fork_b]:
            typer.echo(
                json.dumps(
                    {
                        "warning": f"Verdict for position {pos_str}: winning fork {winning_fork_uuid_verdict[:8]} is not part of the original duel ({fork_a[:8]} vs {fork_b[:8]}). Skipping.",
                    },
                    indent=2,
                )
            )
            continue

        loser_fork_uuid_verdict = fork_a if winning_fork_uuid_verdict == fork_b else fork_b

        # Map fork UUIDs to their successor hrönir UUIDs for voting
        # _get_successor_hronir_for_fork is defined in cli.py
        winner_hronir_uuid = _get_successor_hronir_for_fork(
            winning_fork_uuid_verdict, forking_path_dir
        )
        loser_hronir_uuid = _get_successor_hronir_for_fork(
            loser_fork_uuid_verdict, forking_path_dir
        )

        if not winner_hronir_uuid or not loser_hronir_uuid:
            typer.echo(
                json.dumps(
                    {
                        "error": f"Could not map one or both duel forks for position {pos_str} to their successor hrönir_uuids. "
                        f"Winner: {winning_fork_uuid_verdict[:8]} -> {winner_hronir_uuid[:8] if winner_hronir_uuid else 'Not Found'}, "
                        f"Loser: {loser_fork_uuid_verdict[:8]} -> {loser_hronir_uuid[:8] if loser_hronir_uuid else 'Not Found'}. "
                        "Aborting commit.",
                    },
                    indent=2,
                )
            )
            # This is a critical error, perhaps don't proceed with any votes.
            raise typer.Exit(code=1)

        valid_votes_to_record.append(
            {
                "position": position_idx,
                "voter": initiating_fork_uuid,  # The fork that started the session is the voter
                "winner_hronir": winner_hronir_uuid,
                "loser_hronir": loser_hronir_uuid,
            }
        )
        processed_verdicts[pos_str] = winning_fork_uuid_verdict
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
    # The initiating_fork_uuid is passed separately to transaction_manager.

    session_verdicts_for_tm: list[dict[str, Any]] = []
    for vote_detail in valid_votes_to_record:
        session_verdicts_for_tm.append(
            {
                "position": vote_detail["position"],
                "winner_hrönir_uuid": vote_detail["winner_hronir"],
                "loser_hrönir_uuid": vote_detail["loser_hronir"],
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
            initiating_fork_uuid=initiating_fork_uuid,  # Fork whose mandate is used
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
            json.dumps({"error": f"Failed to process transaction: {e}. Aborting commit."}, indent=2)
        )
        # Votes might not have been recorded, or only partially. State could be inconsistent.
        # Session status should reflect this if possible.
        session_manager.update_session_status(session_id, "commit_failed_tx_processing")
        raise typer.Exit(code=1)

    # Update the status of the initiating_fork_uuid to "SPENT"
    # The mandate_id was implicitly "spent" by starting the session and consuming the fork_uuid.
    # Now we mark the fork itself as SPENT.
    try:
        update_spent_success = storage.update_fork_status(
            fork_uuid_to_update=initiating_fork_uuid,
            new_status="SPENT",
            mandate_id=session_data.get(
                "mandate_id"
            ),  # Pass mandate_id for completeness, though not strictly needed for 'SPENT'
            fork_dir_base=forking_path_dir,
        )
        if update_spent_success:
            typer.echo(
                json.dumps(
                    {"message": f"Fork {initiating_fork_uuid} status updated to SPENT."}, indent=2
                )
            )
        else:
            typer.echo(
                json.dumps(
                    {
                        "warning": f"Could not update status to SPENT for fork {initiating_fork_uuid}. Manual check may be needed."
                    },
                    indent=2,
                )
            )
            # This is not ideal, but the transaction is committed.
    except Exception as e:
        typer.echo(
            json.dumps(
                {
                    "warning": f"Error updating status for fork {initiating_fork_uuid} to SPENT: {e}. Manual check may be needed."
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
                forking_path_dir=forking_path_dir,
                ratings_dir=ratings_dir,
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
                {"message": "No votes were cast, so no Temporal Cascade was triggered."}, indent=2
            )
        )

    # Update session status to 'committed'
    session_manager.update_session_status(session_id, "committed")
    typer.echo(json.dumps({"message": f"Session {session_id} committed successfully."}, indent=2))


@app.command("metrics", help="Expose fork status metrics in Prometheus format (TDD 2.6).")
def metrics_command(
    forking_path_dir: Annotated[
        Path, typer.Option(help="Directory containing forking path CSV files.")
    ] = Path("forking_path"),
):
    """
    Scans all forking_path/*.csv files and prints the total number of forks
    in each status (PENDING, QUALIFIED, SPENT) in Prometheus exposition format.
    """
    status_counts = {
        "PENDING": 0,
        "QUALIFIED": 0,
        "SPENT": 0,
        "UNKNOWN": 0,
    }  # Add UNKNOWN for robustness

    if not forking_path_dir.is_dir():
        typer.echo(
            f"# Metrics generation skipped: Directory not found: {forking_path_dir}", err=True
        )
        # Output empty metrics if dir not found, or specific error metrics
        for status_val, count in status_counts.items():
            typer.echo(f'hronir_fork_status_total{{status="{status_val.lower()}"}} {count}')
        raise typer.Exit(code=1)

    all_fork_uuids_processed = (
        set()
    )  # To count unique fork_uuids across potentially overlapping CSVs (though ideally they don't overlap by fork_uuid)

    for csv_file in forking_path_dir.glob("*.csv"):
        if csv_file.stat().st_size == 0:
            continue
        try:
            # Ensure 'status' and 'fork_uuid' columns are read.
            # storage.audit_forking_csv should ensure 'status' exists, defaulting to PENDING.
            df = pd.read_csv(
                csv_file, usecols=["fork_uuid", "status"], dtype={"fork_uuid": str, "status": str}
            )

            if "status" not in df.columns:  # Should not happen if audit_forking_csv is effective
                # typer.echo(f"# Warning: 'status' column missing in {csv_file}. Skipping this file for metrics.", err=True)
                # Or count all as UNKNOWN or PENDING
                status_counts["UNKNOWN"] += len(df)  # Example: count them as unknown
                continue

            for index, row in df.iterrows():
                fork_uuid = row["fork_uuid"]
                status = row["status"]

                if pd.isna(fork_uuid) or not fork_uuid.strip():  # Skip rows with no fork_uuid
                    continue

                # Only count unique fork_uuids once, even if they appear in multiple files (defensive)
                if fork_uuid not in all_fork_uuids_processed:
                    if (
                        pd.isna(status) or not status.strip()
                    ):  # Handle NaN or empty status as UNKNOWN
                        status_counts["UNKNOWN"] += 1
                    elif status in status_counts:
                        status_counts[status] += 1
                    else:
                        status_counts["UNKNOWN"] += 1  # Catch any other unexpected status values
                    all_fork_uuids_processed.add(fork_uuid)

        except pd.errors.EmptyDataError:
            continue
        except ValueError as ve:  # e.g. if usecols specifies a col that's not there
            typer.echo(
                f"# Warning: Could not process {csv_file} for metrics due to ValueError: {ve}. Skipping.",
                err=True,
            )
            continue
        except Exception as e:
            typer.echo(
                f"# Warning: Error processing {csv_file} for metrics: {e}. Skipping.", err=True
            )
            continue

    # Print metrics in Prometheus format
    typer.echo("# HELP hronir_fork_status_total Total number of forks by status.")
    typer.echo("# TYPE hronir_fork_status_total gauge")
    for status_val, count in status_counts.items():
        # Prometheus labels are typically lowercase.
        typer.echo(f'hronir_fork_status_total{{status="{status_val.lower()}"}} {count}')


if __name__ == "__main__":
    main()  # Called with no arguments, so app() will use sys.argv
