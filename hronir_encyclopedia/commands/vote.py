import json  # For parsing votes_json
import logging
import math  # For sqrt
import uuid  # For UUID validation
from pathlib import Path  # Added Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError  # For validating vote structure if needed

from .. import canon, storage, transaction_manager  # Added canon
from ..models import PathStatus, SessionVerdict  # Reusing SessionVerdict for vote structure

logger = logging.getLogger(__name__)

vote_app = typer.Typer(help="Submit votes using a qualified mandate.", no_args_is_help=True)


@vote_app.command("submit", help="Submit votes for specified duels using a mandate.")
def submit_votes(
    mandate_path_uuid_str: Annotated[
        str, typer.Option(help="The UUID of the QUALIFIED path providing the mandate.")
    ],
    votes_json: Annotated[
        str,
        typer.Option(
            help='JSON string representing a list of votes. Each vote: {"position": int, "winner_hrönir_uuid": str, "loser_hrönir_uuid": str, "predecessor_hrönir_uuid": Optional[str]}'
        ),
    ],
    # TODO: Add --canonical-path-file for run_temporal_cascade if it's still needed by the interim version
):
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    try:
        mandate_path_uuid = uuid.UUID(mandate_path_uuid_str)
    except ValueError:
        typer.secho(
            f"Error: Invalid mandate_path_uuid format: {mandate_path_uuid_str}", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    mandate_path = dm.get_path_by_uuid(str(mandate_path_uuid))

    if not mandate_path:
        typer.secho(f"Error: Mandate path {mandate_path_uuid} not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if mandate_path.status != PathStatus.QUALIFIED:
        typer.secho(
            f"Error: Mandate path {mandate_path_uuid} is not QUALIFIED. Status: {mandate_path.status}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    try:
        submitted_votes_data: list[dict[str, Any]] = json.loads(votes_json)
        if not isinstance(submitted_votes_data, list):
            raise ValueError("Votes JSON must be a list.")
    except json.JSONDecodeError:
        typer.secho("Error: Invalid JSON format for votes.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except ValueError as e:
        typer.secho(f"Error: Votes JSON structure is invalid: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Validate number of votes based on sqrt(N) rule
    # N is the position of the mandate_path
    n = mandate_path.position
    if n < 0:  # Should not happen with valid path data
        typer.secho(
            f"Error: Mandate path {mandate_path_uuid} has an invalid position {n}.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    allowed_votes = math.isqrt(n) if n > 0 else 0
    # For position 0, sqrt(0) = 0. This means a path at pos 0 cannot vote.
    # If a path at pos 1 (N=1), sqrt(1)=1 vote.
    # If a path at pos 4 (N=4), sqrt(4)=2 votes.

    if len(submitted_votes_data) > allowed_votes:
        typer.secho(
            f"Error: Too many votes submitted. Path at position {n} allows {allowed_votes} votes, but {len(submitted_votes_data)} were provided.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Validate structure of each vote
    validated_votes_for_tx = []
    for vote_dict in submitted_votes_data:
        try:
            # Use SessionVerdict for validation, ensuring all required fields are present
            # Pydantic will convert UUID strings to UUID objects here
            sv = SessionVerdict(**vote_dict)
            validated_votes_for_tx.append(sv.model_dump())  # Pass dicts to record_transaction
        except ValidationError as e:
            typer.secho(
                f"Error: Invalid vote structure: {vote_dict}. Details: {e}", fg=typer.colors.RED
            )
            raise typer.Exit(code=1)
        except Exception as e:  # Catch any other error during validation
            typer.secho(f"Error validating vote {vote_dict}: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    if not validated_votes_for_tx:
        typer.secho("No valid votes to submit.", fg=typer.colors.YELLOW)
        return

    typer.echo(
        f"Submitting {len(validated_votes_for_tx)} votes using mandate from path {mandate_path_uuid}..."
    )

    try:
        tx_result = transaction_manager.record_transaction(
            initiating_path_uuid=str(mandate_path_uuid),  # Pass as string
            submitted_votes=validated_votes_for_tx,
        )
        typer.secho(f"Transaction recorded: {tx_result['transaction_uuid']}", fg=typer.colors.GREEN)
        if tx_result.get("promotions_granted"):
            typer.echo(f"Promotions granted: {', '.join(tx_result['promotions_granted'])}")

        # Update mandate path status to SPENT
        dm.update_path_status(
            str(mandate_path_uuid), PathStatus.SPENT.value, set_mandate_explicitly=False
        )  # mandate_id is not changed here
        dm.save_all_data()
        typer.echo(f"Mandate path {mandate_path_uuid} status updated to SPENT.")

        # Trigger Temporal Cascade
        # The canon.run_temporal_cascade currently takes canonical_path_json_file_for_tests
        # This needs to be refactored to not rely on it, or we pass it for now.
        # For now, I'll assume the CLI might still pass it.
        # The oldest_voted_position from tx_result should be used.
        oldest_pos = tx_result.get("oldest_voted_position", 0)
        if oldest_pos == -1 and validated_votes_for_tx:  # if no votes, oldest_pos is -1
            oldest_pos = min(v["position"] for v in validated_votes_for_tx)

        # Placeholder for canonical_path_file, this needs to be resolved.
        # Perhaps run_temporal_cascade should not write to file anymore if DB is source of truth.
        # For now, we might need to provide the default path if the function still expects it.
        legacy_canonical_path_file = Path("data/canonical_path.json")

        if validated_votes_for_tx:  # Only run cascade if votes were actually processed
            typer.echo(f"Triggering temporal cascade from position {oldest_pos}...")
            canon.run_temporal_cascade(
                dm=dm,
                committed_verdicts=None,  # The new record_transaction handles votes, cascade re-evaluates based on new ratings
                # Or, pass submitted votes if canon needs them directly.
                # For now, assuming it re-evaluates from DB based on new ratings.
                canonical_path_json_file_for_tests=legacy_canonical_path_file,  # Needs to be resolved
                typer_echo=typer.echo,
                start_position=oldest_pos,
                max_positions_to_consolidate=100,  # Default from old recover-canon
            )
            typer.echo("Temporal cascade finished.")
        else:
            typer.echo("No votes processed, skipping temporal cascade.")

    except Exception as e:
        typer.secho(f"Error during vote submission or cascade: {e}", fg=typer.colors.RED)
        logger.error("Error in submit_votes", exc_info=True)
        raise typer.Exit(code=1)


# Further work:
# - Refine how canon.run_temporal_cascade is called (especially canonical_path_json_file_for_tests and committed_verdicts).
# - Mandate Management: How to track sqrt(N) votes if they are not all submitted at once?
#   The current implementation assumes all allowed votes are submitted in one go.
#   If partial voting is allowed, PathStatus.QUALIFIED might not be enough.
#   A vote_count or remaining_votes attribute on the Path model might be needed.
#   For now, QUALIFIED -> SPENT after one call to submit_votes.
# - Add tests for this new command.
