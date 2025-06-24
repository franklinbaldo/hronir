import datetime
import json
import uuid
from pathlib import Path
from typing import Any

TRANSACTIONS_DIR = Path("data/transactions")
HEAD_FILE = TRANSACTIONS_DIR / "HEAD"
UUID_NAMESPACE = uuid.NAMESPACE_URL


def _ensure_transactions_dir():
    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def record_transaction(
    session_id: str,
    initiating_fork_uuid: str,
    session_verdicts: list[dict[str, Any]],
    forking_path_dir: Path | None = None,
    ratings_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Simple transaction recording for the pandas-based system.
    This is a minimal implementation that focuses on core functionality.
    """
    _ensure_transactions_dir()

    # Generate transaction UUID
    timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
    transaction_uuid = str(uuid.uuid5(UUID_NAMESPACE, f"{session_id}-{timestamp_dt.isoformat()}"))

    # Create transaction record
    transaction_data = {
        "uuid": transaction_uuid,
        "timestamp": timestamp_dt.isoformat(),
        "session_id": session_id,
        "initiating_fork_uuid": initiating_fork_uuid,
        "verdicts": session_verdicts,
        "status": "completed",
    }

    # Save transaction to file
    transaction_file = TRANSACTIONS_DIR / f"{transaction_uuid}.json"
    with open(transaction_file, "w") as f:
        json.dump(transaction_data, f, indent=2)

    # --- Enhanced logic for processing votes and qualifications ---
    import pandas as pd

    from . import ratings, storage  # Local import for type hinting and clarity

    dm = storage.DataManager()
    dm.initialize_and_load()  # Ensure data is loaded

    promotions_granted = []
    oldest_voted_position = float("inf")
    affected_contexts = set()  # Store (position, predecessor_hrönir_uuid) tuples

    # 1. Record votes and identify affected contexts
    for verdict in session_verdicts:
        pos = verdict["position"]
        winner_hrönir_uuid = verdict["winner_hrönir_uuid"]
        loser_hrönir_uuid = verdict["loser_hrönir_uuid"]

        ratings.record_vote(
            position=pos,
            voter=initiating_fork_uuid,  # This is the initiating_path_uuid
            winner=winner_hrönir_uuid,
            loser=loser_hrönir_uuid,
        )
        if pos < oldest_voted_position:
            oldest_voted_position = pos

        # The predecessor_hrönir_uuid is now directly provided in the verdict
        predecessor_for_this_vote = verdict.get("predecessor_hrönir_uuid")

        # For position 0, predecessor_for_this_vote should be None
        if pos == 0:
            predecessor_for_this_vote = None

        affected_contexts.add((pos, predecessor_for_this_vote))

    # 2. Check for qualifications in affected contexts
    for pos, pred_uuid_str in affected_contexts:
        current_rankings_df = ratings.get_ranking(pos, pred_uuid_str)

        # Get all PathModels for this specific context (position and predecessor)
        all_paths_in_context_models = []
        for p_model in dm.get_paths_by_position(pos):
            p_model_prev_uuid_str = str(p_model.prev_uuid) if p_model.prev_uuid else None
            if p_model_prev_uuid_str == pred_uuid_str:
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
                    ratings_df=current_rankings_df,  # DataFrame of paths in this context with their Elo
                    all_paths_in_position_df=all_paths_in_context_df,  # DataFrame of all paths in this context
                )
                if is_qualified:
                    new_mandate_id = str(uuid.uuid4())
                    dm.update_path_status(
                        path_uuid=str(path_model_to_check.path_uuid),
                        status="QUALIFIED",
                        mandate_id=new_mandate_id,
                        set_mandate_explicitly=True,
                    )
                    promotions_granted.append(str(path_model_to_check.path_uuid))

    dm.save_all_data_to_csvs()  # Save all changes made (votes, status updates)

    # Ensure oldest_voted_position is an int if it was updated, else keep it as something distinct if no votes
    final_oldest_voted_position = (
        int(oldest_voted_position) if oldest_voted_position != float("inf") else -1
    )  # Or None

    return {
        "transaction_uuid": transaction_uuid,
        "promotions_granted": promotions_granted,
        "new_qualified_forks": promotions_granted,  # Assuming new_qualified_forks is same as promotions_granted
        "status": "completed",
        "oldest_voted_position": final_oldest_voted_position,
    }
