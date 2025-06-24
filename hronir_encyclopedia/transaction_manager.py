import datetime
import json
import sys # Moved import sys to the top
import uuid
from pathlib import Path
from typing import Any

import blake3
import pandas as pd
from sqlalchemy.orm import Session

from hronir_encyclopedia import ratings, storage

from .models import TransactionDB

TRANSACTIONS_DIR = Path("data/transactions")
HEAD_FILE = TRANSACTIONS_DIR / "HEAD"
UUID_NAMESPACE = uuid.NAMESPACE_URL  # Using the same namespace as storage.py for consistency


def _ensure_transactions_dir():
    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_previous_transaction_uuid() -> str | None:
    """Reads the UUID of the last transaction from the HEAD file."""
    _ensure_transactions_dir()
    if not HEAD_FILE.exists():
        return None
    return HEAD_FILE.read_text().strip()


def _compute_transaction_uuid(content: dict[str, Any]) -> str:
    """Computes a deterministic UUIDv5 for the transaction content."""
    # Serialize the content to a stable string format (sorted keys)
    # For the 'verdicts' dict, ensure it's also sorted for stability.
    # Making a deep copy to sort 'verdicts' if it exists and is a dict.
    content_copy = json.loads(json.dumps(content))
    if "verdicts" in content_copy and isinstance(content_copy["verdicts"], dict):
        content_copy["verdicts"] = dict(sorted(content_copy["verdicts"].items()))

    serialized_content = json.dumps(content_copy, sort_keys=True, separators=(",", ":"))
    return str(uuid.uuid5(UUID_NAMESPACE, serialized_content))


# Define default paths, these could be configurable
FORKING_PATH_DIR = Path("forking_path")
RATINGS_DIR = Path("ratings")
CHAPTER_BASE_DIR = Path("the_library")


def _get_fork_details_by_hrönir_uuid(
    hrönir_uuid_to_find: str, at_position: int, session: Session | None = None
) -> dict[str, Any] | None:
    """
    Finds the fork_uuid and other details for a given hrönir_uuid (ForkDB.uuid)
    at a specific position from the database.
    Returns a dictionary representation of the ForkDB object if found, else None.
    """
    close_session_locally = False
    if session is None:
        session = storage.get_db_session()
        close_session_locally = True

    try:
        fork_db_entry = (
            session.query(storage.ForkDB)
            .filter(
                storage.ForkDB.uuid == hrönir_uuid_to_find,
                storage.ForkDB.position == at_position,
            )
            .first()
        )

        if fork_db_entry:
            # Convert ForkDB object to dict to match expected return type by caller
            return {
                "fork_uuid": fork_db_entry.fork_uuid,
                "position": fork_db_entry.position,
                "prev_uuid": fork_db_entry.prev_uuid,
                "uuid": fork_db_entry.uuid, # This is the hrönir_uuid
                "status": fork_db_entry.status,
                "mandate_id": fork_db_entry.mandate_id,
                # 'csv_filepath' is no longer relevant as we are reading from DB
            }
        return None
    finally:
        if close_session_locally and session is not None:
            session.close()


def _get_all_forks_at_position(
    position_num: int, predecessor_uuid: str | None, session: Session | None = None
) -> pd.DataFrame:
    """
    Loads all forks from the database that are at the given position
    and optionally match the predecessor_uuid.
    Returns a Pandas DataFrame.
    """
    close_session_locally = False
    if session is None:
        session = storage.get_db_session()
        close_session_locally = True

    try:
        query = session.query(storage.ForkDB).filter(storage.ForkDB.position == position_num)

        if predecessor_uuid is None: # Position 0 case
            if position_num == 0:
                query = query.filter(
                    (storage.ForkDB.prev_uuid == None) | (storage.ForkDB.prev_uuid == "") # noqa E711
                )
            else:
                # For positions > 0, a predecessor_uuid should generally be specified.
                # If not, it implies no forks should match, or logic needs clarification.
                # For now, returning empty DataFrame if predecessor_uuid is None for pos > 0.
                return pd.DataFrame(columns=["fork_uuid", "uuid", "prev_uuid", "position", "status"])
        else: # Position > 0, predecessor_uuid is specified
            query = query.filter(storage.ForkDB.prev_uuid == predecessor_uuid)

        fork_db_entries = query.all()

        if not fork_db_entries:
            return pd.DataFrame(columns=["fork_uuid", "uuid", "prev_uuid", "position", "status"])

        # Convert list of ForkDB objects to DataFrame
        fork_data_list = [
            {
                "fork_uuid": f.fork_uuid,
                "uuid": f.uuid, # This is the hrönir_uuid
                "prev_uuid": f.prev_uuid,
                "position": f.position,
                "status": f.status,
                "mandate_id": f.mandate_id,
            }
            for f in fork_db_entries
        ]
        return pd.DataFrame(fork_data_list)
    finally:
        if close_session_locally and session is not None:
            session.close()


def record_transaction(
    session_id: str,
    initiating_fork_uuid: str,  # Fork whose mandate is being used
    session_verdicts: list[
        dict[str, Any]
    ],  # [{"position": int, "winner_hrönir_uuid": str, "loser_hrönir_uuid": str}]
    forking_path_dir: Path | None = None,
    ratings_dir: Path | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """
    Orchestrates the processing of a judgment session's commit.

    This function is the central point for handling the consequences of a `session commit`.
    Its responsibilities include:
    1.  Recording all votes cast in the session via `ratings.record_vote`.
    2.  Checking if any of the hrönirs involved in the voted-upon duels
        have corresponding forks that now meet the criteria for `QUALIFIED` status.
        This involves using `ratings.check_fork_qualification`.
    3.  If a fork becomes `QUALIFIED`, its status is updated in its respective
        `forking_path/*.csv` file via `storage.update_fork_status`, and a unique
        `mandate_id` (derived from the fork_uuid and the hash of the *previous*
        transaction block) is generated and stored with it.
    4.  Preparing all necessary data for a new transaction block, including
        timestamp, session details, processed verdicts, any promotions granted,
        and the hash of the previous transaction block.
    5.  Computing a deterministic UUIDv5 for this new transaction block based on its content.
    6.  Saving the transaction block as a JSON file in `data/transactions/`.
    7.  Updating the `data/transactions/HEAD` file to point to this new transaction_uuid.
    8.  Returning key information about the transaction, including its UUID and the
        oldest position number that received a vote (critical for triggering the
        Temporal Cascade).

    Args:
        session_id (str): The unique identifier of the judgment session being committed.
        initiating_fork_uuid (str): The `fork_uuid` of the fork that was used to
            initiate this session (i.e., the fork whose mandate is being exercised).
            This fork_uuid acts as the "voter" for all votes cast in this session.
        session_verdicts (List[Dict[str, Any]]): A list of verdict dictionaries.
            Each dictionary represents a single judgment made in the session and
            must conform to the structure:
            `{"position": int, "winner_hrönir_uuid": str, "loser_hrönir_uuid": str}`.
            - "position": The numerical position of the duel being judged.
            - "winner_hrönir_uuid": The `hrönir_uuid` of the chapter chosen as the winner.
            - "loser_hrönir_uuid": The `hrönir_uuid` of the chapter chosen as the loser.

    Returns:
        Dict[str, Any]: A dictionary containing key results of the transaction processing:
        - "transaction_uuid" (str): The UUID of the newly created transaction block.
        - "promotions_granted" (List[Dict[str, str]]): A list of forks that were
          promoted to `QUALIFIED` status during this transaction. Each item is a dict:
          `{"fork_uuid": str, "mandate_id": str, "qualified_in_tx_with_prev_hash": str}`.
        - "oldest_voted_position" (int): The lowest numerical position for which a
          verdict was processed in this session. Returns -1 if no votes processed.
          This value is used by the CLI to determine the starting point for the
          Temporal Cascade.
    """
    _ensure_transactions_dir()

    # This is the hash of the transaction *before* this one.
    # Crucial for mandate_id generation if a fork qualifies in *this* transaction.
    last_tx_hash = get_previous_transaction_uuid() or ""  # Use empty string if no prev tx

    base_dir = TRANSACTIONS_DIR.parent.parent
    if forking_path_dir is None:
        forking_path_dir = base_dir / "forking_path"
    if ratings_dir is None:
        ratings_dir = base_dir / "ratings"

    promotions_granted: list[dict[str, str]] = []
    oldest_voted_position = -1
    processed_verdicts_for_log = []
    hrönirs_to_check_for_qualification = set() # Collect (hrönir_uuid, position) tuples

    # Loop 1: Record all votes
    for vote_action in session_verdicts:
        position = vote_action["position"]
        winner_hrönir_uuid = vote_action["winner_hrönir_uuid"]
        loser_hrönir_uuid = vote_action["loser_hrönir_uuid"]

        ratings.record_vote(
            position,
            voter=initiating_fork_uuid,
            winner=winner_hrönir_uuid,
            loser=loser_hrönir_uuid,
            session=session,
        )
        processed_verdicts_for_log.append(vote_action)

        if oldest_voted_position == -1 or position < oldest_voted_position:
            oldest_voted_position = position

        # Add involved hrönirs to a set for later qualification check
        hrönirs_to_check_for_qualification.add((winner_hrönir_uuid, position))
        hrönirs_to_check_for_qualification.add((loser_hrönir_uuid, position))

    # Loop 2: Check qualifications for all uniquely involved hrönirs
    # This loop executes *after* all votes from the current session_verdicts are recorded.
    for hrönir_involved_uuid, position in hrönirs_to_check_for_qualification:
        # Use the refactored helper, passing the session
        fork_details = _get_fork_details_by_hrönir_uuid(
            hrönir_uuid_to_find=hrönir_involved_uuid,
            at_position=position,
            session=session, # Pass the session
        )

        if not fork_details:
            print(f"DEBUG TM: (Loop 2) Warning: Could not find fork details for hrönir {hrönir_involved_uuid} at pos {position}", file=sys.stderr)
            continue

        fork_to_check_uuid = fork_details["fork_uuid"]
        # Fetch current status from DB again, as it might have been updated by a previous iteration
        # if a hrönir was part of multiple duels (though less likely with current set logic, good practice).
        # More importantly, this ensures we get the status *after all votes are in*.
        current_fork_obj = storage.get_fork_data(fork_to_check_uuid, session=session)
        if not current_fork_obj:
            print(f"DEBUG TM: (Loop 2) Warning: Could not refetch fork data for {fork_to_check_uuid}. Skipping.", file=sys.stderr)
            continue
        current_fork_status = current_fork_obj.status

        # ---- START DEBUG PRINTS (Loop 2) ----
        # print(f"DEBUG TM: (Loop 2) Checking fork {fork_to_check_uuid} at pos {position} (hrönir {hrönir_involved_uuid})", file=sys.stderr)
        # print(f"DEBUG TM: (Loop 2) Current status from DB: {current_fork_status}", file=sys.stderr)
        # ---- END DEBUG PRINTS (Loop 2) ----

        if current_fork_status == "PENDING":
            # ---- START DEBUG PRINTS (Loop 2) ----
            # print(f"DEBUG TM: (Loop 2) Fork {fork_to_check_uuid} is PENDING, proceeding to check qualification.", file=sys.stderr)
            # ---- END DEBUG PRINTS (Loop 2) ----

            predecessor_for_ranking = fork_details.get("prev_uuid") # prev_uuid from initial fetch of this fork's details
            if pd.isna(predecessor_for_ranking) or predecessor_for_ranking == "nan":
                predecessor_for_ranking = None

            # ratings.get_ranking will now see all votes committed from Loop 1.
            current_pos_ratings_df = ratings.get_ranking(
                position=position,
                predecessor_hronir_uuid=predecessor_for_ranking,
                session=session,
            )

            all_forks_in_same_segment_df = _get_all_forks_at_position(
                position_num=position,
                predecessor_uuid=predecessor_for_ranking,
                session=session,
            )

            is_qualified = ratings.check_fork_qualification(
                fork_uuid=fork_to_check_uuid,
                ratings_df=current_pos_ratings_df,
                all_forks_in_position_df=all_forks_in_same_segment_df,
            )

            # ---- START DEBUG PRINTS (Loop 2) ----
            # print(f"DEBUG TM: (Loop 2) Fork {fork_to_check_uuid} - predecessor_for_ranking: {predecessor_for_ranking}", file=sys.stderr)
            # print(f"DEBUG TM: (Loop 2) Fork {fork_to_check_uuid} - current_pos_ratings_df (empty: {current_pos_ratings_df.empty}):\n{current_pos_ratings_df.to_string()}", file=sys.stderr)
            # print(f"DEBUG TM: (Loop 2) Fork {fork_to_check_uuid} - all_forks_in_same_segment_df (empty: {all_forks_in_same_segment_df.empty}):\n{all_forks_in_same_segment_df.to_string()}", file=sys.stderr)
            # print(f"DEBUG TM: (Loop 2) Fork {fork_to_check_uuid} - is_qualified: {is_qualified}", file=sys.stderr)
            # ---- END DEBUG PRINTS (Loop 2) ----

            if is_qualified:
                # ---- START DEBUG PRINTS (Loop 2) ----
                # print(f"DEBUG TM: (Loop 2) Fork {fork_to_check_uuid} IS NOW QUALIFIED. Attempting to update status.", file=sys.stderr)
                # ---- END DEBUG PRINTS (Loop 2) ----
                mandate_id_str = blake3.blake3(
                    (fork_to_check_uuid + last_tx_hash).encode("utf-8")
                ).hexdigest()[:16]

                update_success = storage.update_fork_status(
                    fork_uuid_to_update=fork_to_check_uuid,
                    new_status="QUALIFIED",
                    mandate_id=mandate_id_str,
                    session=session,
                )
                if update_success:
                    promotions_granted.append(
                        {
                            "fork_uuid": fork_to_check_uuid,
                            "mandate_id": mandate_id_str,
                            "qualified_in_tx_with_prev_hash": last_tx_hash,
                        }
                    )
                else: # Should not happen if DB update is robust
                    # print(f"DEBUG TM: (Loop 2) Warning: Failed to update status for qualified fork {fork_to_check_uuid}", file=sys.stderr)
                    pass # Silently continue if update failed, or add more robust error handling

    # --- Prepare data for the transaction block ---
    timestamp_dt = datetime.datetime.utcnow()
    timestamp = timestamp_dt.isoformat() + "Z"

    # Content for computing this transaction's UUID
    # Note: 'promotions_granted' is part of the content that determines the tx_uuid
    current_transaction_content_for_uuid = {
        "timestamp": timestamp,
        "session_id": session_id,
        "initiating_fork_uuid": initiating_fork_uuid,  # The one that started the session
        "verdicts": processed_verdicts_for_log,  # Actual votes cast
        "promotions_granted": sorted(
            promotions_granted, key=lambda x: x["fork_uuid"]
        ),  # Sort for deterministic UUID
        "previous_transaction_uuid": last_tx_hash,  # This is the get_previous_transaction_uuid() result
    }

    current_transaction_uuid = _compute_transaction_uuid(current_transaction_content_for_uuid)

    # This is the data that will be written to the transaction file.
    # It includes its own UUID for self-reference within the file.
    # The content used for UUID generation (`current_transaction_content_for_uuid`)
    # does not include the `transaction_uuid` itself or `oldest_voted_position`.
    transaction_block_to_save = {
        "transaction_uuid": current_transaction_uuid,  # Self-reference
        "timestamp": timestamp,
        "session_id": session_id,
        "initiating_fork_uuid": initiating_fork_uuid,  # This is the "voter_fork_uuid" for the session
        "verdicts": processed_verdicts_for_log,  # Renaming for clarity in the block
        "promotions_granted": promotions_granted,
        "previous_transaction_uuid": last_tx_hash,
    }

    # Save the transaction block to a file
    transaction_file = TRANSACTIONS_DIR / f"{current_transaction_uuid}.json"
    try:
        transaction_file.write_text(json.dumps(transaction_block_to_save, indent=2))
    except OSError:
        # print(f"Error writing transaction file {transaction_file}: {e}") # Optional logging
        # Consider how to handle this error; e.g., raise an exception
        # For now, if writing fails, we probably shouldn't update HEAD.
        # This part of the function might need to become more robust to errors.
        raise  # Re-raise the exception for now

    # Update HEAD to point to this new transaction
    try:
        HEAD_FILE.write_text(current_transaction_uuid)
    except OSError:
        # print(f"Error writing HEAD file {HEAD_FILE}: {e}") # Optional logging
        # This is problematic: transaction is saved, but HEAD is not updated.
        # May require a rollback or recovery mechanism in a production system.
        raise  # Re-raise

    if session is not None:
        tx_obj = TransactionDB(
            uuid=current_transaction_uuid,
            timestamp=timestamp_dt,
            prev_uuid=last_tx_hash or None,
            content=transaction_block_to_save,
        )
        session.add(tx_obj)
        session.commit()

    # Return data that might be useful to the caller, including the new transaction_uuid
    # and the oldest_voted_position for triggering the temporal cascade.
    return {
        "transaction_uuid": current_transaction_uuid,
        "promotions_granted": promotions_granted,  # Could be useful for immediate feedback
        "oldest_voted_position": oldest_voted_position,
        # Other fields from transaction_block_to_save could be included if needed by CLI
    }


# Removed the previous note as saving is now integrated.
