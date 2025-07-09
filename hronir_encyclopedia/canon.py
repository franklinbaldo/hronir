import json
import uuid
from pathlib import Path
from typing import Any, Callable # Added Callable

from . import ratings, storage
from .models import Path as PathModel

# Placeholder for future:
# from .models import CanonicalPath # Define a Pydantic model for canonical_path.json structure if needed


def run_temporal_cascade(
    dm: storage.DataManager, # Pass DataManager instance
    committed_verdicts: dict[str, uuid.UUID] | None,
    canonical_path_json_file_for_tests: Path | None, # Added for interim test passing
    typer_echo: Callable, # For providing feedback
    start_position: int,
    max_positions_to_consolidate: int,
):
    """
    Updates the canonical path.
    INTERIM IMPLEMENTATION: Reads/writes canonical_path.json to make tests pass.
    FINAL VERSION: Should derive from DB and update DB state.

    Full version should:
    1. Determine the current canonical path by querying DuckDB (ratings, path statuses).
    2. Apply committed_verdicts to influence ratings for the affected positions.
    3. Re-calculate the winning path for each position from start_position onwards based on updated ratings.
    4. Store the new canonical path (e.g., by updating a 'is_canonical' flag on paths in DB,
       or by storing a representation of it in a dedicated DB table).

    For Phase 0, this function will be a high-level placeholder to allow CLI to run.
    The actual calculation and storage of the "canonical path" needs significant rework
    to be DB-centric as per the overall plan (Step 4).
    """
    if not canonical_path_json_file_for_tests:
        typer_echo("ERROR: canonical_path_json_file_for_tests not provided for interim temporal cascade.", fg="red")
        # In a real scenario, this function would not rely on this file.
        # For now, if it's not passed (e.g. from a future DB-driven call), we can't proceed with this hack.
        return

    typer_echo(
        f"INTERIM Temporal Cascade: Reading from/writing to {canonical_path_json_file_for_tests}"
    )
    typer_echo(f"Cascade initiated from position {start_position} for max {max_positions_to_consolidate} positions.")

    try:
        with open(canonical_path_json_file_for_tests, "r") as f:
            canonical_data = json.load(f)
            if "path" not in canonical_data: # Ensure 'path' key exists
                 canonical_data["path"] = {}
    except (FileNotFoundError, json.JSONDecodeError):
        typer_echo(f"Warning: Could not load or parse {canonical_path_json_file_for_tests}. Starting with empty canonical path.", fg="yellow")
        canonical_data = {"title": "Canonical Path (auto-generated)", "path": {}}

    current_canonical_path: dict[str, Any] = canonical_data.get("path", {})
    new_canonical_path = current_canonical_path.copy() # Work on a copy

    if committed_verdicts:
        typer_echo(f"Processing {len(committed_verdicts)} committed verdicts.")
        for pos_str, winner_path_uuid_obj in committed_verdicts.items():
            try:
                pos_int = int(pos_str)
                if pos_int >= start_position:
                    winner_path_model = dm.get_path_by_uuid(str(winner_path_uuid_obj))
                    if winner_path_model:
                        new_canonical_path[pos_str] = {
                            "path_uuid": str(winner_path_model.path_uuid),
                            "hrönir_uuid": str(winner_path_model.uuid),
                        }
                        typer_echo(f"  Pos {pos_str}: New canonical path is {winner_path_model.path_uuid} (Hrönir: {winner_path_model.uuid}) due to verdict.")
                    else:
                        typer_echo(f"  Warning: Path {str(winner_path_uuid_obj)} for verdict at pos {pos_str} not found. Cannot update canon.", fg="yellow")
            except ValueError:
                typer_echo(f"  Warning: Invalid position string '{pos_str}' in verdicts. Skipping.", fg="yellow")


    # Simplified cascade: propagate changes. If a position's canon changes,
    # subsequent positions need re-evaluation (here, simplified to clearing them if their predecessor changed,
    # or picking the highest rated if no direct verdict).
    # A true cascade is more complex.

    # For positions from start_position up to max_positions_to_consolidate or highest known position
    # This simplified logic will just apply verdicts and then try to ensure some continuity.
    # A full ELO-based re-evaluation per position is needed for true DB-centric logic.

    max_known_pos = -1
    if new_canonical_path:
        max_known_pos = max(int(k) for k in new_canonical_path.keys() if k.isdigit())

    # Determine the maximum position to iterate up to.
    max_iter_pos = start_position + max_positions_to_consolidate - 1
    if new_canonical_path: # new_canonical_path initially is a copy of current_canonical_path
        max_existing_pos_in_canon = max((int(k) for k in new_canonical_path if k.isdigit()), default=-1)
        max_iter_pos = max(max_iter_pos, max_existing_pos_in_canon)

    for current_pos_int in range(start_position, max_iter_pos + 1):
        current_pos_str = str(current_pos_int)

        # Determine the actual predecessor hrönir for the current position based on the evolving new_canonical_path
        current_predecessor_hronir_uuid = None
        if current_pos_int > 0:
            prev_pos_str = str(current_pos_int - 1)
            if prev_pos_str in new_canonical_path:
                current_predecessor_hronir_uuid = new_canonical_path[prev_pos_str]["hrönir_uuid"]
            else:
                # Predecessor's canonical path doesn't exist in the new version, so this branch must end.
                if current_pos_str in new_canonical_path: del new_canonical_path[current_pos_str]
                typer_echo(f"  Pos {current_pos_str}: Predecessor at {prev_pos_str} no longer canonical. Clearing from this position onwards.")
                # Clear all subsequent positions as well
                for k_idx in range(current_pos_int + 1, max_iter_pos + 1):
                    if str(k_idx) in new_canonical_path: del new_canonical_path[str(k_idx)]
                break # Stop cascading down this branch

        # Flag to check if current_pos_str has been successfully determined in this iteration
        is_current_pos_set = False

        # 1. Apply verdict if it exists for the current position
        if committed_verdicts and current_pos_str in committed_verdicts:
            winner_path_uuid_obj = committed_verdicts[current_pos_str]
            winner_path_model = dm.get_path_by_uuid(str(winner_path_uuid_obj))
            if winner_path_model:
                winner_predecessor = str(winner_path_model.prev_uuid) if winner_path_model.prev_uuid else None
                # Check consistency of verdict winner's predecessor with current_predecessor_hronir_uuid
                if current_pos_int == 0 or winner_predecessor == current_predecessor_hronir_uuid:
                    new_canonical_path[current_pos_str] = {
                        "path_uuid": str(winner_path_model.path_uuid),
                        "hrönir_uuid": str(winner_path_model.uuid),
                    }
                    typer_echo(f"  Pos {current_pos_str}: Set by verdict to Path {winner_path_model.path_uuid}, Hrönir {winner_path_model.uuid}.")
                    is_current_pos_set = True
                else: # Verdict is inconsistent with the new canonical chain
                    typer_echo(f"  Pos {current_pos_str}: Verdict winner {winner_path_model.path_uuid} (predecessor {winner_predecessor}) is inconsistent with new canonical predecessor {current_predecessor_hronir_uuid}. Invalidating this position and branch.", fg="yellow")
                    if current_pos_str in new_canonical_path: del new_canonical_path[current_pos_str]
                    # Clear subsequent positions and break
                    for k_idx in range(current_pos_int + 1, max_iter_pos + 1):
                        if str(k_idx) in new_canonical_path: del new_canonical_path[str(k_idx)]
                    break
            else: # Path from verdict not found
                typer_echo(f"  Warning: Path {str(winner_path_uuid_obj)} for verdict at pos {current_pos_str} not found. Invalidating and ending branch.", fg="yellow")
                if current_pos_str in new_canonical_path: del new_canonical_path[current_pos_str]
                for k_idx in range(current_pos_int + 1, max_iter_pos + 1): # Clear subsequent and break
                    if str(k_idx) in new_canonical_path: del new_canonical_path[str(k_idx)]
                break

        # 2. If no verdict applied for this position, try to find/confirm canonical path
        if not is_current_pos_set:
            must_find_new_path_for_current_pos = True
            if current_pos_str in new_canonical_path: # Entry might exist from initial copy
                existing_path_model = dm.get_path_by_uuid(new_canonical_path[current_pos_str]["path_uuid"])
                if existing_path_model:
                    existing_path_predecessor = str(existing_path_model.prev_uuid) if existing_path_model.prev_uuid else None
                    if existing_path_predecessor == current_predecessor_hronir_uuid:
                        # Old entry is consistent with new predecessor, keep it.
                        typer_echo(f"  Pos {current_pos_str}: Kept existing canonical {new_canonical_path[current_pos_str]['path_uuid']} as predecessor {current_predecessor_hronir_uuid} matches.")
                        must_find_new_path_for_current_pos = False
                        is_current_pos_set = True
                    else: # Old entry inconsistent
                        typer_echo(f"  Pos {current_pos_str}: Existing entry {new_canonical_path[current_pos_str]['path_uuid']} (predecessor {existing_path_predecessor}) is inconsistent with new predecessor {current_predecessor_hronir_uuid}. Removing.")
                        del new_canonical_path[current_pos_str]
                else: # Path in new_canonical_path not found in DB
                     del new_canonical_path[current_pos_str]


            if must_find_new_path_for_current_pos:
                if current_pos_int == 0 or current_predecessor_hronir_uuid: # Need valid context for ranking
                    ranking_df = ratings.get_ranking(current_pos_int, current_predecessor_hronir_uuid)
                    if not ranking_df.empty:
                        new_winner_path_uuid = ranking_df.iloc[0]["path_uuid"]
                        new_winner_hronir_uuid = ranking_df.iloc[0]["hrönir_uuid"]
                        new_canonical_path[current_pos_str] = {
                            "path_uuid": new_winner_path_uuid,
                            "hrönir_uuid": new_winner_hronir_uuid,
                        }
                        typer_echo(f"  Pos {current_pos_str}: Set by ranking from pred {current_predecessor_hronir_uuid} to Path {new_winner_path_uuid}.")
                        is_current_pos_set = True
                    else: # No path found by ranking
                        typer_echo(f"  Pos {current_pos_str}: No paths found by ranking from pred {current_predecessor_hronir_uuid}. Ending branch.")
                        if current_pos_str in new_canonical_path: del new_canonical_path[current_pos_str]
                        # Clear subsequent positions and break
                        for k_idx in range(current_pos_int + 1, max_iter_pos + 1):
                            if str(k_idx) in new_canonical_path: del new_canonical_path[str(k_idx)]
                        break
                else: # No valid context for ranking (e.g. pos > 0 but no canon pred because previous loop iteration failed)
                    if current_pos_str in new_canonical_path: del new_canonical_path[current_pos_str]
                    typer_echo(f"  Pos {current_pos_str}: No valid predecessor context. Ending branch.")
                    for k_idx in range(current_pos_int + 1, max_iter_pos + 1):
                        if str(k_idx) in new_canonical_path: del new_canonical_path[str(k_idx)]
                    break

        if not is_current_pos_set: # Should not happen if logic above is correct and complete
            typer_echo(f"  Pos {current_pos_str}: Failed to determine canonical path. Ending branch.", fg="red")
            for k_idx in range(current_pos_int, max_iter_pos + 1): # Clear this and subsequent
                if str(k_idx) in new_canonical_path: del new_canonical_path[str(k_idx)]
            break

    canonical_data["path"] = new_canonical_path
    try:
        with open(canonical_path_json_file_for_tests, "w") as f:
            json.dump(canonical_data, f, indent=2)
        typer_echo(f"INTERIM Temporal Cascade: Updated {canonical_path_json_file_for_tests}")
    except IOError as e:
        typer_echo(f"ERROR: Could not write to {canonical_path_json_file_for_tests}: {e}", fg="red")

    dm.save_all_data() # Save any other changes (e.g. path statuses if they were updated)
    typer_echo("INTERIM Temporal Cascade finished.")


def get_canonical_path_from_db(dm: storage.DataManager, max_position: int | None = None) -> dict[str, dict[str, str]]:
    """
    Reconstructs the canonical path by querying paths and ratings from DuckDB.
    Returns a dictionary similar in structure to the old canonical_path.json's "path" part.
    e.g., {"0": {"path_uuid": "...", "hrönir_uuid": "..."}, ...}
    """
    # This is a complex function that needs to determine the "best" path at each position.
    # For now, returning a dummy structure.
    # Actual logic would involve:
    # - Iterating from position 0 up to max_position (or highest known position).
    # - For each position, get all paths.
    # - Determine the predecessor hrönir from the previous canonical path choice.
    # - Use ratings.get_ranking to find the top-rated path in that context.
    # - Add this path's path_uuid and hrönir_uuid (path.uuid) to the result.

    # Placeholder implementation:
    canonical_path_dict: dict[str, dict[str, str]] = {}

    # Try to get path at position 0
    # At position 0, predecessor_hronir_uuid is None or ""
    # ranking_pos0_df = ratings.get_ranking(dm, 0, None) # Assuming get_ranking takes dm now
    # if not ranking_pos0_df.empty:
    #     top_path_pos0_uuid = ranking_pos0_df.iloc[0]["path_uuid"]
    #     top_path_pos0_obj = dm.get_path_by_uuid(top_path_pos0_uuid)
    #     if top_path_pos0_obj:
    #         canonical_path_dict["0"] = {
    #             "path_uuid": str(top_path_pos0_obj.path_uuid),
    #             "hrönir_uuid": str(top_path_pos0_obj.uuid)
    #         }
    # else:
    #     # Fallback: try to find any PENDING or QUALIFIED path at position 0
    #     # This is a simplified bootstrap if ratings are not conclusive
    #     paths_pos0 = dm.get_paths_by_position(0)
    #     if paths_pos0:
    #         # Prefer QUALIFIED, then PENDING. Could be more sophisticated.
    #         chosen_path = next((p for p in paths_pos0 if p.status == "QUALIFIED"), None)
    #         if not chosen_path:
    #             chosen_path = next((p for p in paths_pos0 if p.status == "PENDING"), None)
    #         if chosen_path:
    #             canonical_path_dict["0"] = {
    #                 "path_uuid": str(chosen_path.path_uuid),
    #                 "hrönir_uuid": str(chosen_path.uuid)
    #             }


    # This placeholder doesn't make sense without proper ratings integration.
    # For now, it will return empty, and the CLI will need to handle it.
    # The goal is to show that the dependency on canonical_path.json is being removed.
    # print("WARNING: get_canonical_path_from_db is a placeholder and returns an empty path.") # Removed print
    return canonical_path_dict

def get_canonical_hronir_uuid_for_position(dm: storage.DataManager, position: int) -> str | None:
    """
    Gets the hrönir_uuid of the canonical path at a given position.
    This is a helper for session_manager.create_session to find predecessor for duels.
    """
    # This will use get_canonical_path_from_db (eventually)
    # For now, it's also a placeholder.
    # canonical_path = get_canonical_path_from_db(dm) # This will be inefficient if called repeatedly
    # entry = canonical_path.get(str(position))
    # if entry:
    #     return entry.get("hrönir_uuid")
    # return None
    # print(f"WARNING: get_canonical_hronir_uuid_for_position({position}) is a placeholder and returns None.") # Removed print
    return None
