import logging
import os
import uuid
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from . import canon_new
from . import storage as storage_module
from .commands.store import store_command, synthesize_command, validate_command

logger = logging.getLogger(__name__)


app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True,
    no_args_is_help=True,
)

# Add AI agents commands
try:
    from .agents.cli_commands import agent_app

    app.add_typer(agent_app, name="agent")
except ImportError:
    # Agents module not available
    pass

# Register top-level commands from store module
app.command(name="store", help="Store a chapter and link it to a predecessor.")(store_command)
app.command(name="synthesize", help="Generate and store a new chapter using AI.")(
    synthesize_command
)
app.command(name="validate", help="Validate a chapter file.")(validate_command)


@app.command(
    "recover-canon",
    help="Manual recovery tool: Triggers Temporal Cascade from position 0 to rebuild canon.",
)
def recover_canon(
    max_positions_to_rebuild: Annotated[
        int, typer.Option(help="Maximum number of positions to attempt to rebuild.")
    ] = 100,
):
    typer.echo(
        "Refactoring in progress. This command may be deprecated or updated to use new canon logic."
    )
    # Placeholder for new logic if needed, or removal.


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
    consumed_paths_file = sessions_dir / "consumed_path_uuids.json"
    if consumed_paths_file.exists():
        consumed_paths_file.unlink()

    # Init basic data
    h0_uuid_str = storage_module.store_chapter_text("Example Hrönir 0", base=library_dir)
    h1_uuid_str = storage_module.store_chapter_text("Example Hrönir 1", base=library_dir)
    h0_uuid, h1_uuid = uuid.UUID(h0_uuid_str), uuid.UUID(h1_uuid_str)
    from .models import Path as PathModel

    data_manager = storage_module.DataManager()
    if not data_manager._initialized:  # Ensure DM is loaded
        data_manager.initialize_and_load()

    p0_path_uuid_val = storage_module.compute_narrative_path_uuid(0, "", h0_uuid_str)
    data_manager.add_path(
        PathModel(
            path_uuid=p0_path_uuid_val, position=0, prev_uuid=None, uuid=h0_uuid, status="PENDING"
        )
    )
    p1_path_uuid_val = storage_module.compute_narrative_path_uuid(1, h0_uuid_str, h1_uuid_str)
    data_manager.add_path(
        PathModel(
            path_uuid=p1_path_uuid_val,
            position=1,
            prev_uuid=h0_uuid,
            uuid=h1_uuid,
            status="PENDING",
        )
    )
    data_manager.save_all_data()
    typer.echo(f"Sample data initialized. P0: {p0_path_uuid_val}, P1: {p1_path_uuid_val}")


@app.command(help="Display the canonical path.")
def status():
    dm = storage_module.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    canonical_chain = canon_new.calculate_canonical_path(dm)

    if not canonical_chain:
        typer.echo("No canonical path found.")
        return

    typer.echo("Canonical Path:")
    for entry in canonical_chain:
        typer.echo(
            f"Pos {entry['position']}: Path {entry['path_uuid']} (Hrönir {entry['hrönir_uuid']})"
        )


@app.command(help="Show rankings (quadratic influence scores) for a chapter position.")
def ranking(
    position: Annotated[int, typer.Argument(help="The chapter position to rank.")],
    predecessor: Annotated[str, typer.Option(help="Filter by predecessor hrönir UUID.")] = None,
):
    dm = storage_module.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    candidates = canon_new.get_candidates_with_scores(dm, position, predecessor)

    if not candidates:
        typer.echo(f"No candidates found for position {position}.")
        return

    typer.echo(f"Candidates for Position {position}:")
    table_data = []
    for cand in candidates:
        table_data.append(
            {
                "Score": f"{cand['score']:.2f}",
                "Continuations": cand["continuations"],
                "Hrönir": cand["hrönir_uuid"],
                "Path": cand["path_uuid"],
            }
        )

    df = pd.DataFrame(table_data)
    typer.echo(df.to_string(index=False))


@app.command(help="Validate and repair storage, audit narrative CSVs.")
def audit():
    # Placeholder or keeping legacy audit logic if applicable
    # The original audit command was mainly for CSVs.
    pass


@app.command(help="Remove invalid entries from storage.")
def clean(
    git_stage_deleted: Annotated[
        bool, typer.Option("--git", help="Stage deleted files in Git.")
    ] = False,
):
    dm = storage_module.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    cleaned_item_issues = dm.clean_invalid_data()
    if cleaned_item_issues:
        typer.echo("Issues found/cleaned by DataManager:")
        for issue in cleaned_item_issues:
            typer.echo(f"- {issue}")

    typer.echo("Clean command finished.")


@app.command("tutorial", help="Demonstrates a complete workflow of the Hrönir Encyclopedia.")
def tutorial_command():
    typer.echo("Tutorial needs update for simplified protocol.")


@app.command("dev-qualify", help="DEV: Manually qualify a path.")
def dev_qualify_command(
    path_uuid_to_qualify: Annotated[str, typer.Argument(help="Path UUID to qualify.")],
    mandate_id_override: Annotated[str, typer.Option(help="Optional specific mandate_id.")] = None,
):
    # This command might be obsolete as qualification is removed?
    # "Remove path qualification requirements"
    # So I should probably remove this command or mark deprecated.
    typer.echo("Qualification is no longer required in the new protocol.")


@app.command(help="Download latest snapshot from Internet Archive to local DuckDB.")
def sync(
    archive_id: Annotated[
        str, typer.Option(help="IA identifier (placeholder).")
    ] = "hronir-snapshots",
    db_file: Annotated[Path, typer.Option(help="Local DuckDB file.")] = Path(
        "data/encyclopedia.duckdb"
    ),
    retry: Annotated[bool, typer.Option(help="Enable retry logic.")] = True,
):
    typer.echo(
        f"Sync command placeholder. (archive_id: {archive_id}, db_file: {db_file}, retry: {retry})"
    )


@app.command(help="Create local snapshot archive (snapshot.zip).")
def export(
    output: Annotated[Path, typer.Option(help="Output archive path.")] = Path("snapshot.zip"),
):
    typer.echo(f"Export command placeholder. (output: {output})")


@app.command(help="Upload snapshot and metadata to Internet Archive.")
def push(
    archive_id: Annotated[str, typer.Option(help="IA identifier (legacy).")] = "hronir-snapshots",
    force: Annotated[bool, typer.Option(help="Force push (DANGEROUS).")] = False,
    snapshot_output_base_dir: Annotated[
        Path, typer.Option(help="Base dir for snapshot files.")
    ] = Path("data/snapshots_out"),
):
    typer.echo(f"Push command placeholder. (archive_id: {archive_id}, force: {force})")


@app.command("metrics", help="Expose path status metrics in Prometheus format.")
def metrics_command(
    narrative_paths_dir: Annotated[Path, typer.Option(help="Dir for path CSVs (legacy).")] = Path(
        "narrative_paths"
    ),
):
    typer.echo("Metrics command placeholder.")


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
