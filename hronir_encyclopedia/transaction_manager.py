import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

TRANSACTIONS_DIR = Path("data/transactions")
HEAD_FILE = TRANSACTIONS_DIR / "HEAD"
UUID_NAMESPACE = uuid.NAMESPACE_URL # Using the same namespace as storage.py for consistency

def _ensure_transactions_dir():
    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)

def get_previous_transaction_uuid() -> Optional[str]:
    """Reads the UUID of the last transaction from the HEAD file."""
    _ensure_transactions_dir()
    if not HEAD_FILE.exists():
        return None
    return HEAD_FILE.read_text().strip()

def _compute_transaction_uuid(content: Dict[str, Any]) -> str:
    """Computes a deterministic UUIDv5 for the transaction content."""
    # Serialize the content to a stable string format (sorted keys)
    # For the 'verdicts' dict, ensure it's also sorted for stability.
    # Making a deep copy to sort 'verdicts' if it exists and is a dict.
    content_copy = json.loads(json.dumps(content))
    if "verdicts" in content_copy and isinstance(content_copy["verdicts"], dict):
        content_copy["verdicts"] = dict(sorted(content_copy["verdicts"].items()))

    serialized_content = json.dumps(content_copy, sort_keys=True, separators=(',', ':'))
    return str(uuid.uuid5(UUID_NAMESPACE, serialized_content))


def record_transaction(
    session_id: str,
    initiating_fork_uuid: str,
    verdicts: Dict[str, str] # Position_str -> winning_fork_uuid
) -> str:
    """
    Records a transaction for a session commit.
    Returns the UUID of the newly created transaction.
    """
    _ensure_transactions_dir()

    previous_transaction_uuid = get_previous_transaction_uuid()

    timestamp = datetime.datetime.utcnow().isoformat() + "Z" # ISO 8601 format

    transaction_content = {
        "timestamp": timestamp,
        "session_id": session_id,
        "initiating_fork_uuid": initiating_fork_uuid,
        "verdicts": verdicts, # Store the actual verdicts
        "previous_transaction_uuid": previous_transaction_uuid
    }

    transaction_uuid = _compute_transaction_uuid(transaction_content)

    # Add the transaction_uuid to its own content for completeness,
    # though it's derived from the content without it.
    # This is mostly for self-documentation within the transaction file.
    transaction_to_save = {"transaction_uuid": transaction_uuid, **transaction_content}

    transaction_file = TRANSACTIONS_DIR / f"{transaction_uuid}.json"
    print(f"DEBUG_TM: transaction_uuid = {transaction_uuid}") # DEBUG
    print(f"DEBUG_TM: transaction_file path = {transaction_file.resolve()}") # DEBUG
    transaction_file.write_text(json.dumps(transaction_to_save, indent=2))
    print(f"DEBUG_TM: Wrote transaction file. Exists: {transaction_file.exists()}") # DEBUG

    # Update HEAD to point to this new transaction
    print(f"DEBUG_TM: HEAD_FILE path = {HEAD_FILE.resolve()}") # DEBUG
    HEAD_FILE.write_text(transaction_uuid)
    print(f"DEBUG_TM: Wrote HEAD file. Exists: {HEAD_FILE.exists()}") # DEBUG

    return transaction_uuid
