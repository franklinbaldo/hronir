import datetime
import json
import logging
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer

from .. import utils, canon, storage as storage_module # Relative import, aliased storage
from .. import session_manager, transaction_manager # Relative imports
from ..models import PathStatus # Import PathStatus

logger = logging.getLogger(__name__)

session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True)


@session_app.command(
    "commit", help="Submit verdicts, record transaction, trigger Temporal Cascade."
)
def session_commit(
    session_id: Annotated[
        str, typer.Option("--session-id", "-s", help="ID of active session to commit.")
    ],
    verdicts_input: Annotated[
        str,
        typer.Option(
            "--verdicts",
            "-v",
            help='JSON string or path to JSON file of verdicts. Format: \'{"pos": "winning_path_uuid"}\'.',
        ),
    ],
    canonical_path_file: Annotated[Path, typer.Option(help="Path to canonical path JSON.")] = Path(
        "data/canonical_path.json" # TODO: Consider making this configurable via env or a central config
    ),
    max_cascade_positions: Annotated[
        int, typer.Option(help="Max positions for temporal cascade.")
    ] = 100,
):
    session_model = session_manager.get_session(session_id)
    if not session_model:
        typer.secho(f"Error: Session ID '{session_id}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if session_model.status != "active":
        typer.secho(
            f"Error: Session '{session_id}' not active (status: '{session_model.status}').",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    verdicts: dict[str, str] = {}
    verdicts_path = Path(verdicts_input)
    if verdicts_path.is_file():
        try:
            verdicts = json.loads(verdicts_path.read_text())
        except Exception as e:
            typer.secho(f"Error parsing verdicts file {verdicts_input}: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    else:
        try:
            verdicts = json.loads(verdicts_input)
        except Exception as e:
            typer.secho(f"Error parsing verdicts JSON string: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    if not isinstance(verdicts, dict):
        typer.secho("Error: Verdicts must be JSON object.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    initiating_path_uuid_str = str(session_model.initiating_path_uuid)
    dossier_duels_models = session_model.dossier.duels
    valid_votes_for_tm: list[dict[str, Any]] = []
    processed_verdicts_for_session_model: dict[str, uuid.UUID] = {}
    oldest_voted_position = float("inf")

    for pos_str, winning_path_uuid_verdict_str in verdicts.items():
        if not isinstance(winning_path_uuid_verdict_str, str):
            typer.echo(f"Warning: Verdict for pos {pos_str} not string. Skipping.")
            continue
        try:
            position_idx = int(pos_str)
            assert position_idx >= 0
        except (ValueError, AssertionError):
            typer.echo(f"Warning: Invalid pos key '{pos_str}'. Skipping.")
            continue
        duel_model_for_pos = dossier_duels_models.get(pos_str)
        if not duel_model_for_pos:
            typer.echo(f"Warning: No duel for pos {pos_str} in dossier. Skipping.")
            continue
        path_a_uuid_obj, path_b_uuid_obj = (
            duel_model_for_pos.path_A_uuid,
            duel_model_for_pos.path_B_uuid,
        )
        try:
            winning_path_uuid_verdict_obj = uuid.UUID(winning_path_uuid_verdict_str)
        except ValueError:
            typer.echo(
                f"Warning: Verdict for pos {pos_str}: winner '{winning_path_uuid_verdict_str}' invalid UUID. Skipping."
            )
            continue
        if winning_path_uuid_verdict_obj not in [path_a_uuid_obj, path_b_uuid_obj]:
            typer.echo(
                f"Warning: Verdict for pos {pos_str}: winner {winning_path_uuid_verdict_str[:8]} not in duel. Skipping."
            )
            continue
        loser_path_uuid_obj = (
            path_a_uuid_obj if winning_path_uuid_verdict_obj == path_b_uuid_obj else path_b_uuid_obj
        )
        winner_hronir, loser_hronir = (
            utils.get_successor_hronir_for_path(str(winning_path_uuid_verdict_obj)),
            utils.get_successor_hronir_for_path(str(loser_path_uuid_obj)),
        )
        if not winner_hronir or not loser_hronir:
            typer.secho(
                f"Error: Can't map duel paths for pos {pos_str} to hrönirs. Aborting.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        path_data_winner = storage_module.DataManager().get_path_by_uuid( # Changed to storage_module
            str(winning_path_uuid_verdict_obj)
        )
        if not path_data_winner:
            typer.secho(
                f"Error: Path data for winner {winning_path_uuid_verdict_str} not found. Aborting.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        pred_hronir_uuid = str(path_data_winner.prev_uuid) if path_data_winner.prev_uuid else None
        if position_idx == 0: # Position 0 has no predecessor
            pred_hronir_uuid = None
        valid_votes_for_tm.append(
            {
                "position": position_idx,
                "winner_hrönir_uuid": winner_hronir,
                "loser_hrönir_uuid": loser_hronir,
                "predecessor_hrönir_uuid": pred_hronir_uuid,
            }
        )
        processed_verdicts_for_session_model[pos_str] = winning_path_uuid_verdict_obj
        if position_idx < oldest_voted_position:
            oldest_voted_position = position_idx

    transaction_result: dict[str, Any]
    if valid_votes_for_tm:
        typer.echo(f"{len(valid_votes_for_tm)} valid verdicts prepared for transaction processing.")
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
            logger.error(f"Error: Failed to process transaction: {e}. Aborting commit.", exc_info=True)
            session_manager.update_session_status(
                str(session_model.session_id), "commit_failed_tx_processing"
            )
            raise typer.Exit(code=1)
    else:
        typer.echo(
            "No valid verdicts to process for transaction. Session will still be closed and path marked SPENT."
        )
        transaction_result = { # Ensure this structure is consistent for later access
            "oldest_voted_position": float("inf"),
            "transaction_uuid": None, # Explicitly None
            "promotions_granted": [], # Explicitly empty list
        }


    try:
        mandate_id_for_update = str(session_model.mandate_id) if session_model.mandate_id else None
        dm_instance = storage_module.DataManager() # Changed to storage_module
        if not dm_instance._initialized: # Ensure initialized
            dm_instance.initialize_and_load()
        dm_instance.update_path_status(
            path_uuid=initiating_path_uuid_str,
            status=PathStatus.SPENT.value, # Use Enum
            mandate_id=mandate_id_for_update, # Use the stored mandate_id from the session
            set_mandate_explicitly=True, # Ensure mandate is set/updated
        )
        dm_instance.save_all_data() # Persist path status change
        typer.echo(f"Path {initiating_path_uuid_str} status updated to SPENT.")
    except Exception as e:
        logger.warning(
            f"Warning: Error updating status for path {initiating_path_uuid_str} to SPENT: {e}."
        )

    session_model.committed_verdicts = processed_verdicts_for_session_model
    # Use oldest_voted_position from transaction_result if available, else from local calculation
    tm_oldest_voted_position = transaction_result.get("oldest_voted_position", float('inf'))

    # Ensure we use the actual oldest position where a vote occurred.
    # If transaction processing occurred, its 'oldest_voted_position' is authoritative.
    # If no transaction (no valid votes), then local 'oldest_voted_position' (still inf) is fine.
    effective_oldest_voted_pos = tm_oldest_voted_position if tm_oldest_voted_position != float('inf') else oldest_voted_position


    if effective_oldest_voted_pos != float("inf") and effective_oldest_voted_pos >= 0:
        typer.echo(
            f"Oldest voted position: {effective_oldest_voted_pos}. Triggering Temporal Cascade."
        )
        try:
            # Pass the actual committed verdicts to the cascade function
            dm = storage_module.DataManager() # Get DataManager instance
            if not dm._initialized:
                dm.initialize_and_load()

            canon.run_temporal_cascade(
                dm=dm,
                committed_verdicts=session_model.committed_verdicts, # These are UUID objects
                canonical_path_json_file_for_tests=canonical_path_file, # Pass the json file path
                typer_echo=typer.echo,
                start_position=int(effective_oldest_voted_pos), # Ensure it's int
                max_positions_to_consolidate=max_cascade_positions,
            )
            typer.echo("Temporal Cascade completed.")
        except Exception as e:
            logger.error(f"Error: Temporal Cascade failed: {e}.", exc_info=True)
            session_manager.update_session_status(
                str(session_model.session_id), "commit_failed_cascade"
            )
            session_model.status = "commit_failed_cascade" # Update local model status
            # Save updated session model to reflect failure state
            (session_manager.SESSIONS_DIR / f"{session_model.session_id}.json").write_text(
                session_model.model_dump_json(indent=2)
            )
            raise typer.Exit(code=1)
    else:
        typer.echo(
            "No valid votes cast or oldest position undetermined; Temporal Cascade not triggered."
        )

    # Finalize session status to committed
    if session_manager.update_session_status(str(session_model.session_id), "committed"):
        session_model.status = "committed" # Update local model
        session_model.updated_at = datetime.datetime.now(datetime.timezone.utc)
        # Save the final state of the session, including committed_verdicts
        (session_manager.SESSIONS_DIR / f"{session_model.session_id}.json").write_text(
            session_model.model_dump_json(indent=2)
        )
        typer.echo(f"Session {session_id} committed successfully. Committed verdicts saved.")
    else:
        # This case should ideally not be reached if previous error handling is correct
        typer.secho(
            f"Error: Failed to update session {session_id} status to committed. Check logs.",
            fg=typer.colors.RED,
        )


@session_app.command("start", help="Initiate a Judgment Session using a QUALIFIED path's mandate.")
def session_start(
    path_uuid_str: Annotated[
        str, typer.Option("--path-uuid", "-p", help="QUALIFIED path_uuid granting mandate.")
    ],
    canonical_path_file: Annotated[Path, typer.Option(help="Path to canonical path JSON.")] = Path(
        "data/canonical_path.json" # TODO: Consider making this configurable
    ),
):
    path_data_obj = storage_module.DataManager().get_path_by_uuid(path_uuid_str) # Corrected indentation
    if not path_data_obj:
        typer.secho(f"Error: Path UUID '{path_uuid_str}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    # This 'if' was incorrectly indented due to the above line in the previous read.
    # It should be at the same level as the 'if not path_data_obj:'
    if path_data_obj.status != PathStatus.QUALIFIED: # Use Enum
        typer.secho(
            f"Error: Path '{path_uuid_str}' not QUALIFIED (status: '{path_data_obj.status}').",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    if not path_data_obj.mandate_id: # Mandate ID is crucial for QUALIFIED paths
        typer.secho(
            f"Error: Path '{path_uuid_str}' QUALIFIED but no mandate_id. This indicates an inconsistency.", fg=typer.colors.RED
        )
        # This might be a state where `dev-qualify` was used without providing one, or a bug.
        # Forcing an exit as this is a prerequisite for a valid session.
        raise typer.Exit(code=1)

    if csid := session_manager.is_path_consumed(path_uuid_str):
        typer.secho(
            f"Error: Path '{path_uuid_str}' already used for session '{csid}'. Cannot start new session.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    try:
        dm = storage_module.DataManager() # Get DataManager instance
        if not dm._initialized:
            dm.initialize_and_load()
        session_model = session_manager.create_session(
            path_n_uuid_str=path_uuid_str,
            position_n=path_data_obj.position,
            mandate_id_str=str(path_data_obj.mandate_id), # Ensure mandate_id is string
            # canonical_path_file=canonical_path_file, # Removed
            dm=dm, # Pass DataManager
        )
        # Prepare dossier for output, ensuring UUIDs are strings
        dossier_out = {
            p_str: { # p_str is position as string
                "path_A": str(d.path_A_uuid),
                "path_B": str(d.path_B_uuid),
                "entropy": round(d.entropy, 4),
            }
            for p_str, d in (session_model.dossier.duels or {}).items() # Handle if duels is None
        }
        out = {
            "message": "Judgment session started.",
            "session_id": str(session_model.session_id),
            "initiating_path_uuid": str(session_model.initiating_path_uuid),
            "mandate_id_used": str(session_model.mandate_id), # Ensure string
            "position_n": session_model.position_n,
            "status": session_model.status,
            "created_at": session_model.created_at.isoformat(),
            "dossier": {"duels": dossier_out},
        }
        typer.echo(json.dumps(out, indent=2))
    except ValueError as ve: # Catch specific session creation errors (e.g., no duels)
        typer.secho(f"Error creating session: {ve}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"Unexpected error creating session: {e}", exc_info=True)
        typer.secho(f"Unexpected error creating session: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
