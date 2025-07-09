import logging
import os # Required for _validate_path_inputs_helper, though it's in cli_utils
import uuid # Required for PathModel
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from .. import utils # Changed from cli_utils
from .. import storage # Relative import
from ..models import Path as PathModel # Relative import

logger = logging.getLogger(__name__)

path_app = typer.Typer(help="Manage Hrönir narrative paths.", no_args_is_help=True)


@path_app.command(help="Create a narrative path.")
def path(
    position: Annotated[int, typer.Option()],
    target: Annotated[str, typer.Option()],
    source: Annotated[str, typer.Option()] = "",
):
    try:
        norm_source = utils.validate_path_inputs_helper_v2(position, source, target)
    except utils.PathInputError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    path_uuid_obj = storage.compute_narrative_path_uuid(position, norm_source, target)
    dm = storage.DataManager()
    if not dm._initialized: # Ensure DM is loaded
        dm.initialize_and_load()
    if any(p.path_uuid == path_uuid_obj for p in dm.get_paths_by_position(position)):
        typer.echo(f"Path already exists: {path_uuid_obj}")
        return

    dm.add_path(
        PathModel(
            path_uuid=path_uuid_obj,
            position=position,
            prev_uuid=uuid.UUID(norm_source) if norm_source else None,
            uuid=uuid.UUID(target),
            status="PENDING",
        )
    )
    dm.save_all_data() # Ensure data is saved
    typer.echo(
        f"Created path: {path_uuid_obj} (Pos: {position}, Src: {norm_source or 'None'}, Tgt: {target}, Status: PENDING)"
    )


@path_app.command(help="List paths.")
def list_paths(position: Annotated[int, typer.Option(help="Position to list paths for.")] = None):
    dm = storage.DataManager()
    paths_list = dm.get_paths_by_position(position) if position is not None else dm.get_all_paths()
    if not paths_list:
        typer.echo(f"No paths found{f' at position {position}' if position is not None else ''}.")
        return
    typer.echo(f"{'Paths at position ' + str(position) if position is not None else 'All paths'}:")
    # df = pd.DataFrame([p.dict() for p in paths_list]) # Use model_dump for Pydantic v2
    df = pd.DataFrame([p.model_dump() for p in paths_list])
    for col in ["prev_uuid", "mandate_id"]: # Ensure these columns exist or handle missing
        if col in df.columns:
            df[col] = df[col].astype(str).replace("None", "")
        else:
            df[col] = "" # Add empty column if missing

    typer.echo(
        df[["path_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"]].to_string(
            index=False
        )
    )


@path_app.command(help="Show path status.")
def path_status(path_uuid: str):
    path_data = storage.DataManager().get_path_by_uuid(path_uuid)
    if not path_data:
        typer.secho(f"Error: Path '{path_uuid}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(
        f"Path UUID: {path_data.path_uuid}\nPosition: {path_data.position}\nPredecessor: {path_data.prev_uuid or '(None)'}\nCurrent Hrönir: {path_data.uuid}\nStatus: {path_data.status}"
    )
    if path_data.mandate_id:
        typer.echo(f"Mandate ID: {path_data.mandate_id}")

    # Check if path is consumed (Optional, requires session_manager import if we move that logic here or call it)
    # from .. import session_manager # If needed
    # if csid := session_manager.is_path_consumed(path_uuid):
    # typer.echo(f"Consumed by session: {csid}")


@path_app.command("validate-paths", help="Validate integrity of all narrative paths.")
def validate_paths_command():
    # This was a placeholder in the original cli.py.
    # Actual implementation would involve:
    # 1. Iterating through all paths from storage.DataManager().get_all_paths()
    # 2. For each path, check:
    #    - Its own UUID validity (e.g., format, or recompute if necessary for some definition of valid)
    #    - Existence of its hrönir (path.uuid)
    #    - If position > 0, existence of its predecessor hrönir (path.prev_uuid)
    #    - Consistency of position vs prev_uuid (e.g., prev_uuid must be None if position is 0)
    #    - Status validity (e.g., PENDING, QUALIFIED, SPENT)
    #    - If QUALIFIED or SPENT, mandate_id should ideally exist.
    # 3. Report errors or success.
    dm = storage.DataManager()
    all_paths = dm.get_all_paths()
    errors_found = 0
    typer.echo(f"Validating {len(all_paths)} narrative paths...")

    for p_obj in all_paths:
        # Basic check: hrönir existence
        if not dm.hrönir_exists(str(p_obj.uuid)):
            typer.secho(f"Error: Path {p_obj.path_uuid} points to non-existent hrönir {p_obj.uuid}", fg=typer.colors.RED)
            errors_found += 1

        if p_obj.position > 0:
            if not p_obj.prev_uuid:
                typer.secho(f"Error: Path {p_obj.path_uuid} (Pos {p_obj.position}) is missing prev_uuid.", fg=typer.colors.RED)
                errors_found +=1
            elif not dm.hrönir_exists(str(p_obj.prev_uuid)):
                typer.secho(f"Error: Path {p_obj.path_uuid} points to non-existent prev_uuid hrönir {p_obj.prev_uuid}", fg=typer.colors.RED)
                errors_found += 1
        elif p_obj.position == 0 and p_obj.prev_uuid is not None:
            typer.secho(f"Error: Path {p_obj.path_uuid} (Pos 0) has a prev_uuid {p_obj.prev_uuid}. Should be None.", fg=typer.colors.RED)
            errors_found += 1

        # Recompute path_uuid for verification
        expected_path_uuid = storage.compute_narrative_path_uuid(
            p_obj.position,
            str(p_obj.prev_uuid) if p_obj.prev_uuid else "",
            str(p_obj.uuid)
        )
        if p_obj.path_uuid != expected_path_uuid:
            typer.secho(f"Error: Path {p_obj.path_uuid} has mismatched UUID. Expected {expected_path_uuid}", fg=typer.colors.RED)
            errors_found += 1

    if errors_found == 0:
        typer.secho("All narrative paths validated successfully.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Found {errors_found} errors in narrative path validation.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
    # Placeholder logic from original cli.py was minimal. This is a more fleshed out version.
    # This command was a placeholder in the original cli.py.
    # Full implementation would iterate paths, check UUIDs, existence of hrönirs, etc.
    # typer.echo("Path validation logic to be implemented here.")
    # logger.info("validate_paths_command called, but not fully implemented.")
