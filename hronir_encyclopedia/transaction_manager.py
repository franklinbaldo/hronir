import datetime
import uuid
from pathlib import Path
from typing import Any

from .models import Transaction, TransactionContent  # Import TransactionContent

TRANSACTIONS_DIR = Path("data/transactions")
HEAD_FILE = TRANSACTIONS_DIR / "HEAD"
UUID_NAMESPACE = uuid.NAMESPACE_URL


def _ensure_transactions_dir():
    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def record_transaction(
    session_id: str,
    initiating_fork_uuid: str,  # This is a path_uuid
    session_verdicts: list[dict[str, Any]],
    forking_path_dir: Path | None = None,  # These are not used by this TM
    ratings_dir: Path | None = None,  # These are not used by this TM
) -> dict[str, Any]:
    """
    Records a transaction, processes its verdicts to update ratings and path statuses,
    and saves the transaction data.
    """
    _ensure_transactions_dir()

    timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
    # prev_tx_uuid = HEAD_FILE.read_text().strip() if HEAD_FILE.exists() else None # Not used by current model
    prev_tx_uuid = None  # Simplified: prev_uuid is optional in Transaction model

    # Process verdicts to update ratings and check for qualifications
    # This part needs to align with how ratings and qualifications are actually handled.
    # The current version of this function in the codebase seems to do this *after*
    # creating the transaction_data dictionary.
    # For Pydantic validation to pass for Transaction model, 'content' must be structured correctly.

    # --- Logic for processing votes and qualifications (adapted from existing code) ---
    import pandas as pd

    from . import ratings, storage  # Local import for clarity

    dm = storage.DataManager()  # This will use paths set by fixture or defaults relative to CWD
    if not dm._initialized:  # Ensure DataManager is loaded if not already by the test fixture
        dm.initialize_and_load()

    promotions_granted_uuids = []  # Store path_uuids of promoted paths
    oldest_voted_position = float("inf")
    affected_contexts = set()

    processed_verdicts_for_tx_content = []

    for verdict in session_verdicts:
        pos = verdict["position"]
        winner_hrönir_uuid = verdict["winner_hrönir_uuid"]
        loser_hrönir_uuid = verdict["loser_hrönir_uuid"]
        predecessor_hrönir_uuid = verdict.get("predecessor_hrönir_uuid")

        ratings.record_vote(
            position=pos,
            voter=initiating_fork_uuid,
            winner=winner_hrönir_uuid,
            loser=loser_hrönir_uuid,
        )
        if pos < oldest_voted_position:
            oldest_voted_position = pos

        affected_contexts.add((pos, predecessor_hrönir_uuid))

        # For TransactionContent.verdicts_processed
        processed_verdicts_for_tx_content.append(
            {
                "position": pos,
                "winner_hrönir_uuid": winner_hrönir_uuid,
                "loser_hrönir_uuid": loser_hrönir_uuid,
                "predecessor_hrönir_uuid": predecessor_hrönir_uuid,
            }
        )

    for pos, pred_uuid_str in affected_contexts:
        current_rankings_df = ratings.get_ranking(pos, pred_uuid_str)

        all_paths_in_context_models = []
        for p_model in dm.get_all_paths():  # Use get_all_paths then filter
            if p_model.position == pos:
                p_model_prev_uuid_str = str(p_model.prev_uuid) if p_model.prev_uuid else None
                # Handle case where pred_uuid_str is None for position 0
                if pred_uuid_str is None and (
                    p_model_prev_uuid_str is None or p_model_prev_uuid_str == ""
                ):
                    all_paths_in_context_models.append(p_model)
                elif p_model_prev_uuid_str == pred_uuid_str:
                    all_paths_in_context_models.append(p_model)

        if not all_paths_in_context_models:
            continue

        all_paths_in_context_df = pd.DataFrame(
            [p.model_dump() for p in all_paths_in_context_models]
        )

        for path_model_to_check in all_paths_in_context_models:
            if path_model_to_check.status == "PENDING":
                is_qualified = ratings.check_path_qualification(
                    path_uuid=str(path_model_to_check.path_uuid),
                    ratings_df=current_rankings_df,
                    all_paths_in_position_df=all_paths_in_context_df,
                )
                if is_qualified:
                    new_mandate_id = uuid.uuid4()  # mandate_id is UUID
                    dm.update_path_status(
                        path_uuid=str(path_model_to_check.path_uuid),
                        status="QUALIFIED",
                        mandate_id=str(new_mandate_id),  # Pass as string if model expects string
                        set_mandate_explicitly=True,
                    )
                    promotions_granted_uuids.append(
                        path_model_to_check.path_uuid
                    )  # Store UUID object

    # Create transaction content for the model
    transaction_content_data = TransactionContent(
        session_id=uuid.UUID(session_id),  # Ensure session_id is UUID object
        initiating_path_uuid=uuid.UUID(initiating_fork_uuid),  # Ensure this is UUIDv5
        verdicts_processed=processed_verdicts_for_tx_content,
        promotions_granted=promotions_granted_uuids,
    )

    # Generate transaction UUID based on content to ensure determinism if needed, or just random for now
    # For now, using session_id and timestamp as in original code
    transaction_uuid_obj = uuid.uuid5(UUID_NAMESPACE, f"{session_id}-{timestamp_dt.isoformat()}")

    transaction_model_data = Transaction(
        uuid=transaction_uuid_obj,
        timestamp=timestamp_dt,
        prev_uuid=uuid.UUID(prev_tx_uuid) if prev_tx_uuid else None,
        content=transaction_content_data,
    )

    # Save transaction to file (using model_dump_json for Pydantic model)
    transaction_file = TRANSACTIONS_DIR / f"{str(transaction_uuid_obj)}.json"
    with open(transaction_file, "w") as f:
        f.write(transaction_model_data.model_dump_json(indent=2))

    # Update HEAD to point to this new transaction
    HEAD_FILE.write_text(str(transaction_uuid_obj))

    dm.save_all_data_to_csvs()

    final_oldest_voted_position = (
        int(oldest_voted_position) if oldest_voted_position != float("inf") else -1
    )

    return {
        "transaction_uuid": str(transaction_uuid_obj),
        "promotions_granted": [
            str(p_uuid) for p_uuid in promotions_granted_uuids
        ],  # Return strings
        "new_qualified_forks": [str(p_uuid) for p_uuid in promotions_granted_uuids],  # Consistency
        "status": "completed",  # This status is for the return dict, not part of Transaction model
        "oldest_voted_position": final_oldest_voted_position,
    }
