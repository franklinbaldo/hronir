import json  # For init-test
import logging
import shutil  # For init-test
import uuid  # For init-test
from pathlib import Path
from typing import Annotated

import typer

# Assuming these are needed based on original cli.py structure
from .. import (  # May need adjustment
    canon,
    cli_utils,  # Added for git_remove_deleted_files
    storage,
    utils,
)
from ..models import Path as PathModel  # For init-test

logger = logging.getLogger(__name__)

admin_app = typer.Typer(help="Administrative and maintenance commands.", no_args_is_help=True)


@admin_app.command(
    "recover-canon",
    help="Manual recovery tool: Triggers Temporal Cascade from position 0 to rebuild canon.",
)
def recover_canon(
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    max_positions_to_rebuild: Annotated[
        int, typer.Option(help="Maximum number of positions to attempt to rebuild.")
    ] = 100,
):
    typer.echo("WARNING: This is a manual recovery tool.")
    dm = storage.DataManager()  # Get DataManager instance
    if not dm._initialized:
        dm.initialize_and_load()

    canon.run_temporal_cascade(
        dm=dm,
        start_position=0,
        max_positions_to_consolidate=max_positions_to_rebuild,
        canonical_path_json_file_for_tests=canonical_path_file,  # Pass the json file path
        typer_echo=typer.echo,
        committed_verdicts=None,  # No specific verdicts for a full recovery from pos 0
    )
    typer.echo("Manual canon recovery attempt complete (current implementation is basic).")


@admin_app.command("init-test", help="Generate a minimal sample narrative for quick testing.")
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
    # import shutil # Already imported at top
    # import uuid # Already imported at top
    # import json # Needs to be imported if used, or remove json.dumps
    # from ..models import Path as PathModel # Already imported at top

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
    # sessions_dir = data_dir / "sessions" # Session related code removed
    transactions_dir = data_dir / "transactions"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    # clear_or_create_dir(sessions_dir) # Session related code removed
    clear_or_create_dir(transactions_dir)
    canonical_file_path = data_dir / "canonical_path.json"
    if canonical_file_path.exists():
        canonical_file_path.unlink()
    # consumed_paths_file = sessions_dir / "consumed_path_uuids.json" # Session related code removed
    # if consumed_paths_file.exists(): # Session related code removed
    #     consumed_paths_file.unlink() # Session related code removed

    h0_uuid_str = storage.store_chapter_text("Example Hrönir 0", base=library_dir)
    h1_uuid_str = storage.store_chapter_text("Example Hrönir 1", base=library_dir)
    h0_uuid, h1_uuid = uuid.UUID(h0_uuid_str), uuid.UUID(h1_uuid_str)

    data_manager = storage.DataManager()
    if not data_manager._initialized:
        data_manager.initialize_and_load()

    p0_path_uuid_val = storage.compute_narrative_path_uuid(0, "", h0_uuid_str)
    data_manager.add_path(
        PathModel(
            path_uuid=p0_path_uuid_val, position=0, prev_uuid=None, uuid=h0_uuid, status="PENDING"
        )
    )
    p1_path_uuid_val = storage.compute_narrative_path_uuid(1, h0_uuid_str, h1_uuid_str)
    data_manager.add_path(
        PathModel(
            path_uuid=p1_path_uuid_val,
            position=1,
            prev_uuid=h0_uuid,
            uuid=h1_uuid,
            status="PENDING",
        )
    )
    canonical_content = {  # Renamed variable to avoid conflict if json is imported later
        "title": "The Hrönir Encyclopedia - Canonical Path",
        "path": {
            "0": {"path_uuid": str(p0_path_uuid_val), "hrönir_uuid": h0_uuid_str},
            "1": {"path_uuid": str(p1_path_uuid_val), "hrönir_uuid": h1_uuid_str},
        },
    }
    # Need to import json for this line:
    (data_dir / "canonical_path.json").write_text(json.dumps(canonical_content, indent=2))
    data_manager.save_all_data_to_csvs()  # This method might not exist anymore if we fully rely on DuckDB
    typer.echo(f"Sample data initialized. P0: {p0_path_uuid_val}, P1: {p1_path_uuid_val}")


@admin_app.command(help="Validate and repair storage, audit narrative data integrity.")
def audit():
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    issues_found = dm.audit_all_data()  # This method needs to be robust in DataManager

    if issues_found:
        typer.secho(f"Audit found {len(issues_found)} issues:", fg=typer.colors.YELLOW)
        for issue in issues_found:
            typer.echo(f"- {issue}")
    else:
        typer.secho("Audit complete. No integrity issues found.", fg=typer.colors.GREEN)


@admin_app.command(help="Remove invalid entries (fake hrönirs, votes, etc.) from storage.")
def clean(
    git_stage_deleted: Annotated[
        bool, typer.Option("--git", help="Stage deleted files in Git.")
    ] = False,
):
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    cleaned_item_issues = dm.clean_invalid_data()  # This currently returns issues, not file paths.
    if cleaned_item_issues:
        typer.echo("Issues found/cleaned by DataManager (details depend on implementation):")
        for issue in cleaned_item_issues:
            typer.echo(f"- {issue}")

    # This part is a placeholder until clean_invalid_data's return is clarified for file paths
    # for git removal. The current storage.clean_invalid_data focuses on DB internal cleaning.
    # If file system artifacts (like old .md files if the_library was still primary)
    # were to be cleaned, clean_invalid_data would need to return their paths.
    files_to_remove_from_git = []
    if git_stage_deleted:
        if not files_to_remove_from_git:
            typer.echo(
                "Info: `clean_invalid_data` in its current form primarily handles database consistency."
            )
            typer.echo(
                "If file system artifacts need git removal, `clean_invalid_data` would need to return their paths."
            )
            typer.echo(
                "Assuming no specific files for Git removal based on current `clean_invalid_data` behavior."
            )
        if files_to_remove_from_git:  # Only call if there are files
            cli_utils.git_remove_deleted_files(
                files_to_remove_from_git, typer.echo
            )  # Changed to cli_utils
        else:
            typer.echo("No files specified by `clean_invalid_data` for Git removal.")
    else:
        typer.echo("Git staging not requested.")

    typer.echo("Clean command finished.")


@admin_app.command("dev-qualify", help="DEV: Manually qualify a path.")
def dev_qualify_command(
    path_uuid_to_qualify: Annotated[str, typer.Argument(help="Path UUID to qualify.")],
    mandate_id_override: Annotated[str, typer.Option(help="Optional specific mandate_id.")] = None,
):
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()
    try:
        qualified_path_uuid, new_mandate_id = utils.dev_qualify_path_uuid_v2(
            dm, path_uuid_to_qualify, mandate_id_override
        )
        dm.save_all_data()  # Ensure data is saved
        typer.echo(
            f"Path {qualified_path_uuid} has been QUALIFIED with Mandate ID: {new_mandate_id}."
        )
    except utils.PathNotFoundError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except utils.PathInputError as e:  # For invalid mandate_id_override format
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)


@admin_app.command("metrics", help="Expose path status metrics in Prometheus format.")
def metrics_command(
    narrative_paths_dir: Annotated[Path, typer.Option(help="Dir for path CSVs (legacy).")] = Path(
        "narrative_paths"  # This parameter is likely obsolete if data is in DuckDB
    ),
):
    # Actual implementation would query DataManager for path statuses and format as Prometheus.
    # For now, it's a placeholder as in the original cli.py.
    # dm = storage.DataManager()
    # status_counts = dm.get_path_status_counts()
    # output = []
    # for status, count in status_counts.items():
    #     output.append(f'hronir_paths_status_total{{status="{status}"}} {count}')
    # typer.echo("\\n".join(output))
    typer.echo("Metrics command placeholder. (Legacy narrative_paths_dir ignored if using DuckDB)")
