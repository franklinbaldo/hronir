import json
import shutil
import subprocess
from pathlib import Path
from typing_extensions import Annotated # Use typing_extensions for compatibility
from typing import Optional, Dict # Added Optional and Dict

import typer
import pandas as pd # Moved import pandas as pd to the top

from . import database, gemini_util, ratings, storage

app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True, # Typer will handle shell completion
    no_args_is_help=True # Show help if no command is given
)

# Re-map old _cmd functions to new Typer command functions
# Original functions are kept with minimal changes to their core logic,
# only adapting their signatures to Typer's way of handling arguments.

@app.command(help="Consolidate fork rankings and update the canonical path.")
def consolidate_book(
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Directory containing forking path CSV files.")] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Path to the canonical path JSON file.")] = Path("data/canonical_path.json"),
    max_positions_to_consolidate: Annotated[int, typer.Option(help="Maximum number of positions to attempt to consolidate.")] = 100
):
    """
    Triggers a Temporal Cascade starting from position 0.
    This is now a shortcut to the unified Temporal Cascade mechanism.
    """
    typer.echo("Consolidate-book command now triggers a Temporal Cascade from position 0.")
    run_temporal_cascade(
        start_position=0,
        max_positions_to_consolidate=max_positions_to_consolidate,
        canonical_path_file=canonical_path_file,
        forking_path_dir=forking_path_dir,
        ratings_dir=ratings_dir,
        typer_echo=typer.echo
    )
    typer.echo("Consolidation via Temporal Cascade complete.")


# Command `export` and `tree` removed as they depended on the old book structure.

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


# Helper function to find successor hrönir_uuid for a given fork_uuid
# This could also live in storage.py if it's deemed generally useful
def _get_successor_hronir_for_fork(fork_uuid_to_find: str, forking_path_dir: Path) -> str | None:
    if not forking_path_dir.is_dir():
        return None
    for csv_file in forking_path_dir.glob("*.csv"):
        if csv_file.stat().st_size > 0:
            try:
                # Ensure pandas (pd) is available; it's imported at the top of the file.
                df_forks = pd.read_csv(csv_file, dtype=str) # Ler tudo como string
                # Ensure required columns are present
                if not all(col in df_forks.columns for col in ["fork_uuid", "uuid"]):
                    continue
                # Search for the fork_uuid
                # Using .astype(str) again for fork_uuid just in case, though dtype=str should handle it.
                match = df_forks[df_forks["fork_uuid"].astype(str) == fork_uuid_to_find]
                if not match.empty:
                    return match.iloc[0]["uuid"] # 'uuid' is the successor hrönir_uuid
            except pd.errors.EmptyDataError:
                continue
            except Exception: # Broad exception for other parsing errors
                # Consider logging this error
                continue
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
    typer.echo(f"Auditing hrönirs in {library_dir} (basic check via purge_fake_hronirs in 'clean' command)...")
    # No direct action on library_dir here, purge_fake_hronirs in 'clean' is more comprehensive.

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Auditing forking path directory: {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"):
            storage.audit_forking_csv(csv_file)
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

@app.command(help="Obtém o duelo de máxima entropia entre forks para uma posição.")
def get_duel(
    position: Annotated[int, typer.Option(help="A posição do capítulo para a qual obter o duelo de forks.")],
    ratings_dir: Annotated[Path, typer.Option(help="Diretório contendo arquivos CSV de classificação.")] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Diretório contendo arquivos CSV de caminhos de bifurcação.")] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Caminho para o arquivo JSON do caminho canônico.")] = Path("data/canonical_path.json"),
):
    """
    Obtém o duelo de forks de máxima entropia para uma determinada posição,
    considerando a linhagem canônica.
    """
    predecessor_hronir_uuid: str | None = None
    if position > 0:
        canonical_fork_info_prev_pos = storage.get_canonical_fork_info(position - 1, canonical_path_file)
        if not canonical_fork_info_prev_pos or "hrönir_uuid" not in canonical_fork_info_prev_pos:
            typer.echo(json.dumps({
                "error": f"Não foi possível determinar o hrönir predecessor canônico da posição {position - 1}. "
                         f"Execute 'consolidate-book' ou verifique o arquivo {canonical_path_file}.",
                "position_requested": position
            }, indent=2))
            raise typer.Exit(code=1)
        predecessor_hronir_uuid = canonical_fork_info_prev_pos["hrönir_uuid"]
    elif position < 0:
        typer.echo(json.dumps({"error": "Posição inválida. Deve ser >= 0.", "position_requested": position}, indent=2))
        raise typer.Exit(code=1)

    # `determine_next_duel` agora lida com forks
    duel_info = ratings.determine_next_duel(
        position=position,
        predecessor_hronir_uuid=predecessor_hronir_uuid,
        forking_path_dir=forking_path_dir,
        ratings_dir=ratings_dir
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
        typer.echo(json.dumps({
            "error": "Não foi possível determinar um duelo de forks. "
                     "Verifique se existem forks elegíveis suficientes (pelo menos 2) para a linhagem e posição.",
            "position": position,
            "predecessor_hronir_uuid_used": predecessor_hronir_uuid
            }, indent=2))


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

# New session management commands
session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True)
app.add_typer(session_app, name="session")

import uuid # Added import for uuid
from . import session_manager # Placed here to avoid circular import if session_manager needs cli parts

@session_app.command("start", help="Start a new judgment session (SC.8, SC.9).")
def session_start(
    position: Annotated[int, typer.Option("--position", "-p", help="The current position N of the new fork being created.")],
    fork_uuid: Annotated[str, typer.Option("--fork-uuid", "-f", help="The fork_uuid of the new fork at position N, serving as the 'mandate'.")],
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Directory containing forking path CSV files.")] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Path to the canonical path JSON file.")] = Path("data/canonical_path.json"),
):
    """
    Starts a new judgment session.
    A new fork at 'position' N (identified by 'fork_uuid') grants the right to judge positions N-1 down to 0.
    Generates a static dossier of duels for these prior positions.
    """
    if position < 0:
        typer.echo(json.dumps({"error": "Position N cannot be negative."}, indent=2))
        raise typer.Exit(code=1)

    # Validate the fork_uuid - it must exist in forking_path
    if not storage.forking_path_exists(fork_uuid, fork_dir=forking_path_dir):
        typer.echo(json.dumps({"error": f"Fork UUID {fork_uuid} not found in forking paths. Cannot start session."}, indent=2))
        raise typer.Exit(code=1)

    # Check if fork_uuid has already been consumed for a session (SC.8)
    consumed_by_session_id = session_manager.is_fork_consumed(fork_uuid)
    if consumed_by_session_id:
        typer.echo(json.dumps({
            "error": "This fork_uuid has already been used to initiate a judgment session.",
            "fork_uuid": fork_uuid,
            "session_id": consumed_by_session_id
        }, indent=2))
        raise typer.Exit(code=1)

    if position == 0: # Corrected condition: No prior positions if N=0
         # If N=0, there are no prior positions (N-1 to 0) to judge.
         # Create an empty session and mark fork as consumed.
        session_id = str(uuid.uuid4())
        session_manager.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_file = session_manager.SESSIONS_DIR / f"{session_id}.json"
        session_data = {
            "session_id": session_id,
            "initiating_fork_uuid": fork_uuid,
            "position_n": position,
            "dossier": {
                "duels": {} # No duels for N=0
            },
            "status": "active"
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        session_manager.mark_fork_as_consumed(fork_uuid, session_id)
        typer.echo(json.dumps({
            "message": "Session started for Position 0. No prior positions to judge.",
            "session_id": session_id,
            "dossier": session_data["dossier"]
        }, indent=2))
        raise typer.Exit(code=0)


    # Create the session and get the dossier (SC.9)
    try:
        session_info = session_manager.create_session(
            fork_n_uuid=fork_uuid,
            position_n=position,
            forking_path_dir=forking_path_dir,
            ratings_dir=ratings_dir, # Pass ratings_dir here
            canonical_path_file=canonical_path_file
        )
        typer.echo(json.dumps({
            "message": "Judgment session started successfully.",
            "session_id": session_info["session_id"],
            "dossier": session_info["dossier"]
        }, indent=2))
    except Exception as e:
        # Catch any other errors during session creation (e.g., file system issues)
        typer.echo(json.dumps({"error": f"Failed to create session: {str(e)}"}, indent=2))
        raise typer.Exit(code=1)

# This function will be called by `session commit`
def run_temporal_cascade(
    start_position: int,
    max_positions_to_consolidate: int, # Similar to consolidate_book
    canonical_path_file: Path,
    forking_path_dir: Path,
    ratings_dir: Path,
    typer_echo: callable # Pass typer.echo for output
):
    """
    Recalculates the canonical path starting from `start_position`.
    This is the core of SC.11.
    """
    typer_echo(f"Starting Temporal Cascade from position {start_position}...")

    try:
        canonical_path_data = (
            json.loads(canonical_path_file.read_text())
            if canonical_path_file.exists()
            else {"title": "The Hrönir Encyclopedia - Canonical Path", "path": {}}
        )
    except json.JSONDecodeError:
        typer_echo(f"Error reading or parsing canonical path file: {canonical_path_file}. Initializing new path.", err=True)
        canonical_path_data = {"title": "The Hrönir Encyclopedia - Canonical Path", "path": {}}

    if "path" not in canonical_path_data or not isinstance(canonical_path_data["path"], dict):
        canonical_path_data["path"] = {}

    updated_any_position_in_cascade = False

    # Clear canonical entries from start_position onwards, as they will be recalculated
    keys_to_clear = [k for k in canonical_path_data["path"] if int(k) >= start_position]
    if keys_to_clear:
        typer_echo(f"Clearing existing canonical entries from position {start_position} onwards before cascade.")
        for k in keys_to_clear:
            del canonical_path_data["path"][k]
        # updated_any_position_in_cascade = True # Clearing is a change

    for current_pos_idx in range(start_position, max_positions_to_consolidate):
        position_str = str(current_pos_idx)
        predecessor_hronir_uuid_for_ranking: Optional[str] = None

        if current_pos_idx == 0:
            predecessor_hronir_uuid_for_ranking = None
        else:
            # Get the hrönir_uuid from the *just determined* canonical fork of the previous position
            prev_pos_canonical_info = canonical_path_data["path"].get(str(current_pos_idx - 1))
            if not prev_pos_canonical_info or "hrönir_uuid" not in prev_pos_canonical_info:
                typer_echo(f"Cascade broken: Canonical fork for position {current_pos_idx - 1} not found during cascade. Stopping.")
                # All subsequent positions are effectively removed from canonical path
                keys_to_remove = [k for k in canonical_path_data["path"] if int(k) >= current_pos_idx]
                if keys_to_remove:
                    typer_echo(f"Removing subsequent canonical entries from position {current_pos_idx} onwards due to broken cascade.")
                    for k_rem in keys_to_remove:
                        if k_rem in canonical_path_data["path"]:
                             del canonical_path_data["path"][k_rem]
                             updated_any_position_in_cascade = True # Mark change
                break
            predecessor_hronir_uuid_for_ranking = prev_pos_canonical_info["hrönir_uuid"]

        typer_echo(f"Cascade recalculating position {current_pos_idx} (based on predecessor: {predecessor_hronir_uuid_for_ranking or 'None'})...")

        ranking_df = ratings.get_ranking(
            position=current_pos_idx,
            predecessor_hronir_uuid=predecessor_hronir_uuid_for_ranking,
            forking_path_dir=forking_path_dir,
            ratings_dir=ratings_dir
        )

        if ranking_df.empty:
            typer_echo(f"Cascade: No ranking found for eligible forks at position {current_pos_idx}. Path ends here.")
            # If this position previously had a canonical entry, it's now removed implicitly by the clearing step
            # or explicitly if loop breaks and removes subsequent entries.
            # Ensure any entries from current_pos_idx onwards are truly gone if path ends.
            keys_to_ensure_removed = [k for k in canonical_path_data["path"] if int(k) >= current_pos_idx]
            if keys_to_ensure_removed:
                typer_echo(f"Ensuring canonical entries from position {current_pos_idx} onwards are removed as cascade path ends.")
                for k_rem_end in keys_to_ensure_removed:
                    if k_rem_end in canonical_path_data["path"]:
                        del canonical_path_data["path"][k_rem_end]
                        updated_any_position_in_cascade = True
            break # End of the canonical path for this cascade

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
        typer_echo(f"Temporal Cascade: No changes to the canonical path resulting from this cascade starting at position {start_position}.")

    typer_echo(f"Temporal Cascade from position {start_position} complete.")
    return updated_any_position_in_cascade # Return whether changes were made

from . import transaction_manager # Import transaction_manager

@session_app.command("commit", help="Commit verdicts for a session and trigger temporal cascade (SC.10, SC.11, SYS.1).")
def session_commit(
    session_id: Annotated[str, typer.Option("--session-id", "-s", help="The ID of the session to commit.")],
    verdicts_input: Annotated[str, typer.Option("--verdicts", "-v", help="JSON string or path to a JSON file containing verdicts '{\"pos\": \"winning_fork_uuid\"}'.")],
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Directory containing forking path CSV files.")] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Path to the canonical path JSON file.")] = Path("data/canonical_path.json"),
    max_cascade_positions: Annotated[int, typer.Option(help="Maximum number of positions for temporal cascade.")] = 100, # Similar to consolidate_book
):
    """
    Commits the verdicts for an active session.
    - Validates verdicts against the session's dossier.
    - Records votes.
    - Creates a transaction in the chronological ledger.
    - Triggers the Temporal Cascade to update the canonical path.
    """
    session_data = session_manager.get_session(session_id)
    if not session_data:
        typer.echo(json.dumps({"error": f"Session ID {session_id} not found."}, indent=2))
        raise typer.Exit(code=1)

    if session_data.get("status") != "active":
        typer.echo(json.dumps({"error": f"Session {session_id} is not active. Current status: {session_data.get('status')}"}, indent=2))
        raise typer.Exit(code=1)

    # Parse verdicts
    verdicts: Dict[str, str] = {}
    verdicts_path = Path(verdicts_input)
    if verdicts_path.is_file():
        try:
            verdicts = json.loads(verdicts_path.read_text())
        except Exception as e:
            typer.echo(json.dumps({"error": f"Failed to parse verdicts JSON file {verdicts_input}: {e}"}, indent=2))
            raise typer.Exit(code=1)
    else:
        try:
            verdicts = json.loads(verdicts_input)
        except Exception as e:
            typer.echo(json.dumps({"error": f"Failed to parse verdicts JSON string: {e}"}, indent=2))
            raise typer.Exit(code=1)

    if not isinstance(verdicts, dict):
        typer.echo(json.dumps({"error": "Verdicts must be a JSON object (dictionary)."}, indent=2))
        raise typer.Exit(code=1)

    initiating_fork_uuid = session_data["initiating_fork_uuid"]
    dossier_duels = session_data.get("dossier", {}).get("duels", {})

    valid_votes_to_record = []
    processed_verdicts: Dict[str, str] = {} # For transaction record: position_str -> winning_fork_uuid
    oldest_voted_position = float('inf')

    for pos_str, winning_fork_uuid_verdict in verdicts.items():
        if not isinstance(winning_fork_uuid_verdict, str):
            typer.echo(json.dumps({"warning": f"Verdict for position {pos_str} is not a string. Skipping."}, indent=2))
            continue

        position_idx = -1
        try:
            position_idx = int(pos_str)
            if position_idx < 0 : # Ensure positive position
                 typer.echo(json.dumps({"warning": f"Invalid position {pos_str} in verdicts. Skipping."}, indent=2))
                 continue
        except ValueError:
            typer.echo(json.dumps({"warning": f"Invalid position key '{pos_str}' in verdicts. Skipping."}, indent=2))
            continue

        duel_for_pos = dossier_duels.get(pos_str)
        if not duel_for_pos:
            typer.echo(json.dumps({"warning": f"No duel found in dossier for position {pos_str}. Skipping verdict."}, indent=2))
            continue

        fork_a = duel_for_pos["fork_A"]
        fork_b = duel_for_pos["fork_B"]

        if winning_fork_uuid_verdict not in [fork_a, fork_b]:
            typer.echo(json.dumps({
                "warning": f"Verdict for position {pos_str}: winning fork {winning_fork_uuid_verdict[:8]} is not part of the original duel ({fork_a[:8]} vs {fork_b[:8]}). Skipping.",
            }, indent=2))
            continue

        loser_fork_uuid_verdict = fork_a if winning_fork_uuid_verdict == fork_b else fork_b

        # Map fork UUIDs to their successor hrönir UUIDs for voting
        # _get_successor_hronir_for_fork is defined in cli.py
        winner_hronir_uuid = _get_successor_hronir_for_fork(winning_fork_uuid_verdict, forking_path_dir)
        loser_hronir_uuid = _get_successor_hronir_for_fork(loser_fork_uuid_verdict, forking_path_dir)

        if not winner_hronir_uuid or not loser_hronir_uuid:
            typer.echo(json.dumps({
                "error": f"Could not map one or both duel forks for position {pos_str} to their successor hrönir_uuids. "
                         f"Winner: {winning_fork_uuid_verdict[:8]} -> {winner_hronir_uuid[:8] if winner_hronir_uuid else 'Not Found'}, "
                         f"Loser: {loser_fork_uuid_verdict[:8]} -> {loser_hronir_uuid[:8] if loser_hronir_uuid else 'Not Found'}. "
                         "Aborting commit.",
            }, indent=2))
            # This is a critical error, perhaps don't proceed with any votes.
            raise typer.Exit(code=1)

        valid_votes_to_record.append({
            "position": position_idx,
            "voter": initiating_fork_uuid, # The fork that started the session is the voter
            "winner_hronir": winner_hronir_uuid,
            "loser_hronir": loser_hronir_uuid
        })
        processed_verdicts[pos_str] = winning_fork_uuid_verdict
        if position_idx < oldest_voted_position:
            oldest_voted_position = position_idx

    if not valid_votes_to_record:
        typer.echo(json.dumps({"message": "No valid verdicts provided or matched dossier. No votes recorded. Session remains active."}, indent=2))
        # No need to exit with error, user might provide empty or non-matching verdicts.
        # Or, we could update session status to 'aborted' or similar. For now, leave active.
        raise typer.Exit(code=0)

    # Record all valid votes (SC.10)
    for vote_info in valid_votes_to_record:
        try:
            # Assuming ratings.record_vote uses ratings_dir internally or takes it as arg
            # Current record_vote signature: position, voter, winner, loser, base="ratings", conn=None
            ratings.record_vote(
                position=vote_info["position"],
                voter=vote_info["voter"],
                winner=vote_info["winner_hronir"],
                loser=vote_info["loser_hronir"],
                base=ratings_dir # Pass ratings_dir
            )
            typer.echo(json.dumps({
                "info": f"Vote recorded for position {vote_info['position']}: "
                        f"Winner Hronir {vote_info['winner_hronir'][:8]}, "
                        f"Loser Hronir {vote_info['loser_hronir'][:8]}"
            }, indent=2))
        except Exception as e:
            typer.echo(json.dumps({"error": f"Failed to record vote for position {vote_info['position']}: {e}. Aborting commit."}, indent=2))
            # If one vote fails, should we roll back or stop? For now, abort.
            raise typer.Exit(code=1)

    typer.echo(json.dumps({"message": f"All {len(valid_votes_to_record)} valid votes recorded."}, indent=2))

    # Create transaction in ledger (SYS.1)
    try:
        tx_uuid = transaction_manager.record_transaction(
            session_id=session_id,
            initiating_fork_uuid=initiating_fork_uuid,
            verdicts=processed_verdicts # Store the validated verdicts
        )
        typer.echo(json.dumps({"message": "Transaction recorded in ledger.", "transaction_uuid": tx_uuid}, indent=2))
    except Exception as e:
        typer.echo(json.dumps({"error": f"Failed to record transaction: {e}. Aborting commit."}, indent=2))
        # This is critical. Votes might be recorded but not the TX.
        # Manual intervention might be needed or a rollback mechanism.
        raise typer.Exit(code=1)

    # Trigger Temporal Cascade (SC.11)
    if oldest_voted_position != float('inf'):
        typer.echo(f"Oldest voted position: {oldest_voted_position}. Triggering Temporal Cascade.")
        try:
            cascade_made_changes = run_temporal_cascade(
                start_position=oldest_voted_position,
                max_positions_to_consolidate=max_cascade_positions,
                canonical_path_file=canonical_path_file,
                forking_path_dir=forking_path_dir,
                ratings_dir=ratings_dir,
                typer_echo=typer.echo # Pass the echo function
            )
            if cascade_made_changes:
                 typer.echo(json.dumps({"message": "Temporal Cascade completed and updated the canonical path."}, indent=2))
            else:
                 typer.echo(json.dumps({"message": "Temporal Cascade completed, no changes to the canonical path from the cascade."}, indent=2))

        except Exception as e:
            typer.echo(json.dumps({"error": f"Temporal Cascade failed: {e}."}, indent=2))
            # Votes and TX recorded, but cascade failed. State is inconsistent.
            # This needs careful consideration for recovery.
            # For now, we'll report and exit. Session status might indicate this.
            session_manager.update_session_status(session_id, "commit_failed_cascade")
            raise typer.Exit(code=1)
    else:
        # This case should be caught by "No valid verdicts" earlier, but as a safeguard:
        typer.echo(json.dumps({"message": "No votes were cast, so no Temporal Cascade was triggered."}, indent=2))

    # Update session status to 'committed'
    session_manager.update_session_status(session_id, "committed")
    typer.echo(json.dumps({"message": f"Session {session_id} committed successfully."}, indent=2))


if __name__ == "__main__":
    main() # Called with no arguments, so app() will use sys.argv
