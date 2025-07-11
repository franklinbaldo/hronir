import datetime
import logging
import uuid
from typing import Any

from .models import SessionVerdict, Transaction, TransactionContent  # Added SessionVerdict

logger = logging.getLogger(__name__)

# TRANSACTIONS_DIR = Path("data/transactions") # Removed
# HEAD_FILE = TRANSACTIONS_DIR / "HEAD" # Removed
UUID_NAMESPACE = uuid.NAMESPACE_URL  # Still used for generating transaction UUID

# PGP, IA upload, ConflictDetection, Merkle Tree, and Trust Check Sampling removed.
# Comments about Pivot Plan, ShardingManager, ConflictDetection also removed as they are outdated.

# def _ensure_transactions_dir(): # Removed
#     TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True) # Removed


def record_transaction(
    initiating_path_uuid: str,  # Made non-optional
    submitted_votes: list[dict[str, Any]],  # Renamed from session_verdicts, made non-optional
    # forking_path_dir and ratings_dir were unused and removed.
    # **kwargs was only for handling deprecated initiating_fork_uuid, now removed.
) -> dict[str, Any]:
    """
    Records a transaction based on submitted votes, processes votes to update ratings
    and path statuses, and saves the transaction data.
    The transaction is initiated by a path that has a qualified mandate.
    """
    # Deprecated initiating_fork_uuid logic removed.
    # Kwargs removed as no longer needed.

    # _ensure_transactions_dir() # Removed as transactions are now DB based

    timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
    prev_tx_uuid = None  # Simplified: prev_uuid is optional in Transaction model

    # Process votes to update ratings and check for qualifications

    # --- Logic for processing votes and qualifications (adapted from existing code) ---
    import pandas as pd

    from . import ratings, storage  # Local import for clarity

    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    promotions_granted_uuids = []
    oldest_voted_position = float("inf")
    affected_contexts = set()

    processed_votes_for_tx_content = []  # Renamed from processed_verdicts_for_tx_content

    for vote_data in submitted_votes:  # Changed from session_verdicts
        pos = vote_data["position"]
        winner_hrönir_uuid = vote_data["winner_hrönir_uuid"]
        loser_hrönir_uuid = vote_data["loser_hrönir_uuid"]
        predecessor_hrönir_uuid = vote_data.get("predecessor_hrönir_uuid")

        ratings.record_vote(
            position=pos,
            voter=initiating_path_uuid,  # This is the mandate path UUID
            winner=winner_hrönir_uuid,
            loser=loser_hrönir_uuid,
        )
        if pos < oldest_voted_position:
            oldest_voted_position = pos

        affected_contexts.add((pos, predecessor_hrönir_uuid))

        # For TransactionContent.votes_processed
        processed_votes_for_tx_content.append(
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
        for p_model in dm.get_all_paths():
            if p_model.position == pos:
                p_model_prev_uuid_str = str(p_model.prev_uuid) if p_model.prev_uuid else None
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
            if (
                path_model_to_check.status == "PENDING"
            ):  # Assuming PathStatus enum is used or direct string comparison
                is_qualified = ratings.check_path_qualification(
                    path_uuid=str(path_model_to_check.path_uuid),
                    ratings_df=current_rankings_df,
                    all_paths_in_position_df=all_paths_in_context_df,
                )
                if is_qualified:
                    new_mandate_id = uuid.uuid4()
                    dm.update_path_status(
                        path_uuid=str(path_model_to_check.path_uuid),
                        status="QUALIFIED",  # Assuming PathStatus enum is used or direct string comparison
                        mandate_id=str(new_mandate_id),
                        set_mandate_explicitly=True,
                    )
                    promotions_granted_uuids.append(path_model_to_check.path_uuid)

    # Create transaction content for the model
    transaction_content_data = TransactionContent(
        initiating_path_uuid=uuid.UUID(initiating_path_uuid),  # Ensure this is UUID object
        votes_processed=[
            SessionVerdict(**v) for v in processed_votes_for_tx_content
        ],  # Corrected to SessionVerdict
        promotions_granted=promotions_granted_uuids,
    )

    # Generate transaction UUID deterministically based on initiating path and timestamp
    transaction_uuid_obj = uuid.uuid5(
        UUID_NAMESPACE, f"{initiating_path_uuid}-{timestamp_dt.isoformat()}"
    )

    transaction_model_data = Transaction(
        uuid=transaction_uuid_obj,
        timestamp=timestamp_dt,
        prev_uuid=uuid.UUID(prev_tx_uuid)
        if prev_tx_uuid
        else None,  # prev_tx_uuid is currently always None
        content=transaction_content_data,
    )

    # Save transaction to DuckDB via DataManager
    dm.add_transaction(transaction_model_data)  # Assumes DataManager will have this method

    # dm.save_all_data() # This should be called by DataManager.add_transaction or at a higher level if needed
    # The individual file and HEAD logic is now removed.

    final_oldest_voted_position = (
        int(oldest_voted_position) if oldest_voted_position != float("inf") else -1
    )

    return {
        "transaction_uuid": str(transaction_uuid_obj),
        "promotions_granted": [str(p_uuid) for p_uuid in promotions_granted_uuids],
        "new_qualified_forks": [
            str(p_uuid) for p_uuid in promotions_granted_uuids
        ],  # For consistency if used elsewhere
        "status": "completed",
        "oldest_voted_position": final_oldest_voted_position,
    }
