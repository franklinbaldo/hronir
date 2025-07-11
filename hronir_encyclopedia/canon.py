from collections.abc import Callable  # Added Callable

from . import ratings, storage

# Placeholder for future:
# from .models import CanonicalPath # Define a Pydantic model for canonical_path.json structure if needed


def run_temporal_cascade(
    dm: storage.DataManager,
    typer_echo: Callable,
    start_position: int,
    max_positions_to_consolidate: int,
    # committed_verdicts: dict[str, uuid.UUID] | None = None, # Removed, relies on DB ratings
    # canonical_path_json_file_for_tests: Path | None = None, # Removed
):
    """
    Updates the canonical path by re-evaluating path rankings starting from start_position.
    The canonical path is stored by setting the `is_canonical` flag on PathModel objects in the DB.
    """
    if not dm._initialized:  # Ensure DataManager is loaded
        dm.initialize_and_load()

    typer_echo(
        f"Temporal Cascade initiated from position {start_position} for max {max_positions_to_consolidate} positions."
    )

    # Clear existing canonical flags from the start_position onwards
    typer_echo(f"Clearing existing canonical path flags from position {start_position}...")
    dm.clear_canonical_statuses_from_position(
        start_position
    )  # Assumes this method exists on DataManager

    current_predecessor_hronir_uuid: str | None = None
    if start_position > 0:
        # Determine the predecessor for the start_position based on the *current* DB canonical path
        # This requires get_canonical_hronir_uuid_for_position to read from the DB's is_canonical flags.
        # This creates a slight challenge: get_canonical_hronir_uuid_for_position is for on-demand view,
        # while this cascade is for *setting* it.
        # For the very first step of the cascade (at start_position), if start_position > 0,
        # we need the hrönir_uuid of the path that *was* canonical at start_position - 1.
        # This means get_canonical_hronir_uuid_for_position should read the is_canonical flags.
        # Let's assume it does for now.
        # TODO: Refactor get_canonical_hronir_uuid_for_position to read is_canonical flag from DB.
        # For now, for simplicity in this step, we might re-derive it or make an assumption.
        # A simpler way for the cascade: it builds its OWN chain as it goes.

        # Re-deriving predecessor for start_position if it's not 0:
        # This re-derives based on ratings up to start_position-1.
        # This is okay, as the cascade is meant to fix things from start_position onwards.
        if start_position > 0:
            derived_path_before_start = get_canonical_path_from_db(
                dm, max_position=start_position - 1
            )
            if str(start_position - 1) in derived_path_before_start:
                current_predecessor_hronir_uuid = derived_path_before_start[
                    str(start_position - 1)
                ]["hrönir_uuid"]
            else:
                typer_echo(
                    f"Warning: Could not determine predecessor for cascade starting at {start_position}. Path might be broken.",
                    fg="yellow",
                )
                # Cascade cannot proceed reliably if predecessor for start_position > 0 is unknown.
                # For a full rebuild (start_position=0), this is not an issue.

    # Determine the actual maximum position to iterate up to.
    # This could be based on existing paths in DB or max_positions_to_consolidate.
    # For now, using max_positions_to_consolidate.
    # A more robust way: SELECT MAX(position) FROM paths
    max_existing_db_pos = dm.get_max_path_position()  # Assumes this method exists on DataManager

    # Ensure max_iter_pos does not exceed what's sensible
    # If max_existing_db_pos is None (no paths), then loop range will be empty.
    limit_iter_pos = start_position + max_positions_to_consolidate - 1
    if max_existing_db_pos is not None:
        limit_iter_pos = min(limit_iter_pos, max_existing_db_pos)

    for current_pos_int in range(start_position, limit_iter_pos + 1):
        ranking_df = ratings.get_ranking(current_pos_int, current_predecessor_hronir_uuid)

        if ranking_df.empty:
            typer_echo(
                f"  Pos {current_pos_int}: No paths found by ranking from predecessor {current_predecessor_hronir_uuid or 'None'}. Canonical path ends here for this branch."
            )
            break  # Canonical path stops here for this branch

        top_path_series = ranking_df.iloc[0]
        new_canonical_path_uuid = str(top_path_series["path_uuid"])
        new_canonical_hronir_uuid = str(top_path_series["hrönir_uuid"])

        # Set this path as canonical in the DB
        dm.set_path_canonical_status(new_canonical_path_uuid, True)  # Assumes this method exists

        typer_echo(
            f"  Pos {current_pos_int}: New canonical path is {new_canonical_path_uuid} (Hrönir: {new_canonical_hronir_uuid})"
        )
        current_predecessor_hronir_uuid = new_canonical_hronir_uuid  # For the next iteration

    dm.save_all_data()  # Commit all DB changes made during the cascade
    typer_echo("Temporal Cascade finished. Canonical path flags updated in DB.")


def get_canonical_path_from_db(
    dm: storage.DataManager,
    max_position: int | None = None,  # max_position can be used to limit depth
) -> dict[str, dict[str, str]]:
    """
    Reconstructs the canonical path by querying paths and ratings from DuckDB.
    Returns a dictionary similar in structure to the old canonical_path.json's "path" part.
    e.g., {"0": {"path_uuid": "...", "hrönir_uuid": "..."}, ...}
    This function DERIVES the canonical path based on current ratings; it does not read an is_canonical flag.
    """
    if not dm._initialized:  # Ensure DataManager is loaded
        dm.initialize_and_load()

    canonical_path_dict: dict[str, dict[str, str]] = {}
    current_predecessor_hronir_uuid: str | None = None

    # Determine how many positions to check
    # If max_position is not given, find the highest position number present in paths table
    # This could be inefficient if there are many paths. A more direct DB query for max(position) would be better.
    # For now, let's assume a reasonable upper limit if max_position is None.
    # A more robust way would be `SELECT MAX(position) FROM paths;` via DataManager.
    # For this implementation, let's iterate up to a practical limit or until no more paths are found.

    limit_positions = max_position if max_position is not None else 100  # Default practical limit

    for current_pos in range(limit_positions + 1):
        ranking_df = ratings.get_ranking(current_pos, current_predecessor_hronir_uuid)

        if ranking_df.empty:
            # No path found for this predecessor at this position, so the canonical path ends here.
            break

        top_path_series = ranking_df.iloc[0]
        top_path_uuid = top_path_series["path_uuid"]
        top_hronir_uuid = top_path_series["hrönir_uuid"]  # This is path.uuid from the PathModel

        canonical_path_dict[str(current_pos)] = {
            "path_uuid": str(top_path_uuid),
            "hrönir_uuid": str(top_hronir_uuid),
        }
        current_predecessor_hronir_uuid = str(top_hronir_uuid)  # For the next iteration

    return canonical_path_dict


def get_canonical_hronir_uuid_for_position(dm: storage.DataManager, position: int) -> str | None:
    """
    Gets the hrönir_uuid of the canonical path at a given position by deriving the full path.
    """
    if not dm._initialized:  # Ensure DataManager is loaded
        dm.initialize_and_load()

    # We need to derive the path up to at least the requested position.
    # max_position=position ensures we only calculate as much as needed.
    canonical_path = get_canonical_path_from_db(dm, max_position=position)

    position_str = str(position)
    if position_str in canonical_path:
        return canonical_path[position_str].get("hrönir_uuid")

    return None
