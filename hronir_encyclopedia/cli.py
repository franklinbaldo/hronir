import logging
import os

import typer

# Snapshot app import will be added here later
# Local application imports
from . import (
    storage as storage_module,
)

# Command app imports (Option A: move to top)
from .commands.admin import admin_app
from .commands.path import path_app
from .commands.query import query_app
from .commands.snapshot import snapshot_app
from .commands.store import store_app
from .commands.vote import vote_app  # Added import

# Removed 'canon' and 'utils' as they are no longer directly used in cli.py

logger = logging.getLogger(__name__)


app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True,
    no_args_is_help=True,
)

# session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True) # Removed
# app.add_typer(session_app, name="session") # Removed

# Import command groups first

# Add AI agents commands (optional)
try:
    from .agents.cli_commands import agent_app
except ImportError:
    agent_app = None  # Explicitly set to None if not available

# Register command groups
app.add_typer(store_app, name="store", help="Manage Hrönir storing and validation.")
app.add_typer(path_app, name="path", help="Manage Hrönir narrative paths.")
app.add_typer(query_app, name="query", help="Query Hrönir data (status, rankings, duels).")
app.add_typer(admin_app, name="admin", help="Administrative and maintenance commands.")
app.add_typer(snapshot_app, name="snapshot", help="Manage Hrönir snapshots (sync, export, push).")
app.add_typer(vote_app, name="vote", help="Submit votes using a qualified mandate.")  # Added

if agent_app:
    app.add_typer(agent_app, name="agent")


# All specific commands below this point have been moved to submodules or are placeholders for snapshot commands.

# @app.command( # Moved to commands/admin.py
#     "recover-canon",
#     help="Manual recovery tool: Triggers Temporal Cascade from position 0 to rebuild canon.",
# )
# def recover_canon(
#     canonical_path_file: Annotated[
#         Path, typer.Option(help="Path to the canonical path JSON file.")
#     ] = Path("data/canonical_path.json"),
#     max_positions_to_rebuild: Annotated[
#         int, typer.Option(help="Maximum number of positions to attempt to rebuild.")
#     ] = 100,
# ):
#     typer.echo("WARNING: This is a manual recovery tool.")
#     dm = storage_module.DataManager()  # Get DataManager instance
#     if not dm._initialized:
#         dm.initialize_and_load()
#
#     canon.run_temporal_cascade(
#         dm=dm,
#         start_position=0,
#         max_positions_to_consolidate=max_positions_to_rebuild,
#         canonical_path_json_file_for_tests=canonical_path_file,  # Pass the json file path
#         typer_echo=typer.echo,
#         committed_verdicts=None,  # No specific verdicts for a full recovery from pos 0
#     )
#     typer.echo("Manual canon recovery attempt complete (current implementation is basic).")


# @app.command("init-test", help="Generate a minimal sample narrative for quick testing.") # Moved to commands/admin.py
# def init_test(
#     library_dir: Annotated[Path, typer.Option(help="Directory to store sample hrönirs.")] = Path(
#         "the_library"
#     ),
#     narrative_paths_dir: Annotated[Path, typer.Option(help="Directory for path CSV files.")] = Path(
#         "narrative_paths"
#     ),
#     ratings_dir: Annotated[Path, typer.Option(help="Directory for rating CSV files.")] = Path(
#         "ratings"
#     ),
#     data_dir: Annotated[Path, typer.Option(help="Directory for canonical data files.")] = Path(
#         "data"
#     ),
# ) -> None:
#     import shutil
#
#     def clear_or_create_dir(dir_path: Path):
#         if dir_path.exists():
#             for item in dir_path.iterdir():
#                 if item.is_dir():
#                     shutil.rmtree(item)
#                 else:
#                     item.unlink()
#         else:
#             dir_path.mkdir(parents=True, exist_ok=True)
#
#     clear_or_create_dir(library_dir)
#     clear_or_create_dir(narrative_paths_dir)
#     clear_or_create_dir(ratings_dir)
#     # sessions_dir = data_dir / "sessions" # Removed
#     transactions_dir = data_dir / "transactions"
#     if not data_dir.exists():
#         data_dir.mkdir(parents=True, exist_ok=True)
#     # clear_or_create_dir(sessions_dir) # Removed
#     clear_or_create_dir(transactions_dir)
#     canonical_file_path = data_dir / "canonical_path.json"
#     if canonical_file_path.exists():
#         canonical_file_path.unlink()
#     # consumed_paths_file = sessions_dir / "consumed_path_uuids.json" # Removed
#     # if consumed_paths_file.exists(): # Removed
#     #     consumed_paths_file.unlink() # Removed
#     # Uses storage_module directly for these legacy helpers
#     h0_uuid_str = storage_module.store_chapter_text("Example Hrönir 0", base=library_dir)
#     h1_uuid_str = storage_module.store_chapter_text("Example Hrönir 1", base=library_dir)
#     h0_uuid, h1_uuid = uuid.UUID(h0_uuid_str), uuid.UUID(h1_uuid_str)
#     from .models import Path as PathModel
#
#     data_manager = storage_module.DataManager()
#     if not data_manager._initialized:  # Ensure DM is loaded
#         data_manager.initialize_and_load()
#     p0_path_uuid_val = storage_module.compute_narrative_path_uuid(0, "", h0_uuid_str)
#     data_manager.add_path(
#         PathModel(
#             path_uuid=p0_path_uuid_val, position=0, prev_uuid=None, uuid=h0_uuid, status="PENDING"
#         )
#     )
#     p1_path_uuid_val = storage_module.compute_narrative_path_uuid(1, h0_uuid_str, h1_uuid_str)
#     data_manager.add_path(
#         PathModel(
#             path_uuid=p1_path_uuid_val,
#             position=1,
#             prev_uuid=h0_uuid,
#             uuid=h1_uuid,
#             status="PENDING",
#         )
#     )
#     canonical = {
#         "title": "The Hrönir Encyclopedia - Canonical Path",
#         "path": {
#             "0": {"path_uuid": str(p0_path_uuid_val), "hrönir_uuid": h0_uuid_str},
#             "1": {"path_uuid": str(p1_path_uuid_val), "hrönir_uuid": h1_uuid_str},
#         },
#     }
#     (data_dir / "canonical_path.json").write_text(json.dumps(canonical, indent=2))
#     data_manager.save_all_data_to_csvs()
#     typer.echo(f"Sample data initialized. P0: {p0_path_uuid_val}, P1: {p1_path_uuid_val}")


# @app.command(help="Display the canonical path and optional path status counts.") # Moved to commands/query.py
# def status(
#     canonical_path_file: Annotated[
#         Path, typer.Option(help="Path to the canonical path JSON file.")
#     ] = Path("data/canonical_path.json"),
#     counts: Annotated[
#         bool, typer.Option("--counts", help="Also show number of paths by status.")
#     ] = False,
#     narrative_paths_dir: Annotated[
#         Path,
#         typer.Option(help="Directory containing narrative path CSV files (for --counts, legacy)."),
#     ] = Path("narrative_paths"),
# ):
#     # ... (status command implementation from previous cli.py)
#     pass  # Placeholder for brevity


# @app.command(help="Validate and repair storage, audit narrative CSVs.") # Moved to commands/admin.py
# def audit():  # ... (audit command implementation from previous cli.py)
#     pass  # Placeholder for brevity


# @app.command(help="Show Elo rankings for a chapter position.") # Moved to commands/query.py
# def ranking(position: Annotated[int, typer.Argument(help="The chapter position to rank.")]):
#     # ... (ranking command implementation)
#     pass  # Placeholder for brevity


# @app.command(help="Get the maximum entropy duel between paths for a position.") # Moved to commands/query.py
# def get_duel(
#     position: Annotated[
#         int, typer.Option(help="The chapter position for which to get the path duel.")
#     ],
#     canonical_path_file: Annotated[
#         Path, typer.Option(help="Path to the canonical path JSON file.")
#     ] = Path("data/canonical_path.json"),
# ):
#     # ... (get_duel command implementation)
#     pass  # Placeholder for brevity


# @app.command(help="Remove invalid entries (fake hrönirs, votes, etc.) from storage.") # Moved to commands/admin.py
# def clean(
#     git_stage_deleted: Annotated[
#         bool, typer.Option("--git", help="Stage deleted files in Git.")
#     ] = False,
# ):
#     # ... (clean command implementation)
#     pass


# @app.command("tutorial", help="Demonstrates a complete workflow of the Hrönir Encyclopedia.") # Removed
# def tutorial_command( # Removed
#     auto_qualify_for_session: Annotated[ # Removed
#         bool, typer.Option(help="Auto-qualify path for session demo.") # Removed
#     ] = True, # Removed
# ): # Removed
#     # ... (tutorial command implementation) # Removed
#     pass  # Placeholder for brevity # Removed


# @app.command("dev-qualify", help="DEV: Manually qualify a path.") # Moved to commands/admin.py
# def dev_qualify_command(
#     path_uuid_to_qualify: Annotated[str, typer.Argument(help="Path UUID to qualify.")],
#     mandate_id_override: Annotated[str, typer.Option(help="Optional specific mandate_id.")] = None,
# ):
#     # ... (dev-qualify command implementation)
#     pass


# @app.command(help="Download latest snapshot from Internet Archive to local DuckDB.") # Moved to commands/snapshot.py
# def sync(
#     archive_id: Annotated[
#         str, typer.Option(help="IA identifier (placeholder).")
#     ] = "hronir-snapshots",
#     db_file: Annotated[Path, typer.Option(help="Local DuckDB file.")] = Path(
#         "data/encyclopedia.duckdb"
#     ),
#     retry: Annotated[bool, typer.Option(help="Enable retry logic.")] = True,
# ):
#     typer.echo(
#         f"Sync command placeholder. (archive_id: {archive_id}, db_file: {db_file}, retry: {retry})"
#     )


# @app.command(help="Create local snapshot archive (snapshot.zip).") # Moved to commands/snapshot.py
# def export(
#     output: Annotated[Path, typer.Option(help="Output archive path.")] = Path("snapshot.zip"),
# ):
#     typer.echo(f"Export command placeholder. (output: {output})")


# @app.command(help="Upload snapshot and metadata to Internet Archive.") # Moved to commands/snapshot.py
# def push(
#     archive_id: Annotated[str, typer.Option(help="IA identifier (legacy).")] = "hronir-snapshots",
#     force: Annotated[bool, typer.Option(help="Force push (DANGEROUS).")] = False,
#     snapshot_output_base_dir: Annotated[
#         Path, typer.Option(help="Base dir for snapshot files.")
#     ] = Path("data/snapshots_out"),
# ):
#     typer.echo(f"Push command placeholder. (archive_id: {archive_id}, force: {force})")


# @app.command("metrics", help="Expose path status metrics in Prometheus format.") # Moved to commands/admin.py
# def metrics_command(
#     narrative_paths_dir: Annotated[Path, typer.Option(help="Dir for path CSVs (legacy).")] = Path(
#         "narrative_paths"
#     ),
# ):
#     typer.echo("Metrics command placeholder.")


@app.callback()
def main_callback(ctx: typer.Context):
    log_level_str = os.getenv("HRONIR_LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.debug("CLI main_callback: Initializing DataManager...")
    try:
        data_manager = storage_module.DataManager()  # Use the alias
        if not hasattr(data_manager, "_initialized") or not data_manager._initialized:
            logger.info("DataManager not initialized in callback. Calling initialize_and_load().")
            data_manager.initialize_and_load()
            logger.info("DataManager initialized and loaded via callback.")
        else:
            logger.debug("DataManager already initialized.")
    except Exception as e:
        logger.exception("Fatal: DataManager init failed in callback.")
        typer.secho(f"Fatal: DataManager init failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    logger.debug("Main callback finished.")


def main(argv: list[str] | None = None):
    app(args=argv)


if __name__ == "__main__":
    main()
