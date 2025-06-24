import json
import uuid
from pathlib import Path
from typing import Any

from . import ratings, storage  # Assuming storage.py has get_canonical_fork_info

SESSIONS_DIR = Path("data/sessions")
CONSUMED_FORKS_FILE = SESSIONS_DIR / "consumed_fork_uuids.json"


def _load_consumed_forks() -> dict[str, str]:
    """Loads the set of consumed fork UUIDs and the session_id they were consumed by."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONSUMED_FORKS_FILE.exists():
        return {}
    try:
        return json.loads(CONSUMED_FORKS_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_consumed_forks(consumed_forks: dict[str, str]) -> None:
    """Saves the set of consumed fork UUIDs."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    CONSUMED_FORKS_FILE.write_text(json.dumps(consumed_forks, indent=2))


def is_fork_consumed(fork_uuid: str) -> str | None:
    """Checks if a fork_uuid has been consumed, returning the session_id if so."""
    consumed_forks = _load_consumed_forks()
    return consumed_forks.get(fork_uuid)


def mark_fork_as_consumed(fork_uuid: str, session_id: str) -> None:
    """Marks a fork_uuid as consumed by a given session_id."""
    consumed_forks = _load_consumed_forks()
    consumed_forks[fork_uuid] = session_id
    _save_consumed_forks(consumed_forks)


def create_session(
    fork_n_uuid: str,
    position_n: int,
    mandate_id: str,  # Added mandate_id
    forking_path_dir: Path,
    ratings_dir: Path,
    canonical_path_file: Path,
) -> dict[str, Any]:
    """
    Creates a new session, generates a dossier, and stores session information.
    Returns the session data including session_id and dossier.
    """
    session_id = str(uuid.uuid4())
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{session_id}.json"

    dossier_duels: dict[str, dict[str, str]] = {}
    # Iterate from N-1 down to 0
    # Example: if position_n (fork's position) is 2, loop for p_idx = 1, then p_idx = 0.
    # Duels for p_idx=1 need predecessor from p_idx=0.
    # Duels for p_idx=0 need no predecessor (or predecessor is None).
    for p_idx in range(position_n - 1, -1, -1):
        predecessor_hronir_uuid_for_duel: str | None = None
        # Determine the predecessor for duels at p_idx.
        # This predecessor is the canonical hrönir from position p_idx - 1.
        if p_idx > 0:
            # storage.get_canonical_fork_info expects the position of the canonical entry itself.
            # So, for duels at p_idx, we need the canonical hrönir from p_idx - 1.
            canonical_info_for_predecessor = storage.get_canonical_fork_info(
                p_idx - 1, canonical_path_file
            )
            if (
                not canonical_info_for_predecessor
                or "hrönir_uuid" not in canonical_info_for_predecessor
            ):
                # print(f"Warning: Cannot find canonical hrönir at position {p_idx - 1} to serve as predecessor for duels at {p_idx}. Skipping duels for {p_idx}.")
                continue
            predecessor_hronir_uuid_for_duel = canonical_info_for_predecessor["hrönir_uuid"]
        # If p_idx is 0, predecessor_hronir_uuid_for_duel remains None, which is correct.

        # Acquire session for ratings.determine_next_duel_entropy
        db_session_for_duel = storage.get_db_session()
        try:
            duel_info = ratings.determine_next_duel_entropy(  # Correct function name
                position=p_idx,  # We are determining duels for this position p_idx
                predecessor_hronir_uuid=predecessor_hronir_uuid_for_duel,
                # forking_path_dir and ratings_dir are no longer needed
                session=db_session_for_duel,
            )
        finally:
            db_session_for_duel.close()

        if (
            duel_info
            and "duel_pair" in duel_info
            and duel_info["duel_pair"].get("fork_A")
            and duel_info["duel_pair"].get("fork_B")
        ):
            dossier_duels[str(p_idx)] = {
                "fork_A": duel_info["duel_pair"]["fork_A"],
                "fork_B": duel_info["duel_pair"]["fork_B"],
                "entropy": duel_info.get("entropy", 0.0),
            }

    session_data = {
        "session_id": session_id,
        "initiating_fork_uuid": fork_n_uuid,
        "mandate_id": mandate_id,  # Store the mandate_id
        "position_n": position_n,
        "dossier": {"duels": dossier_duels},
        "status": "active",
    }

    session_file.write_text(json.dumps(session_data, indent=2))
    mark_fork_as_consumed(fork_n_uuid, session_id)  # Mark the fork itself as consumed for a session

    return {
        "session_id": session_id,
        "dossier": session_data["dossier"],
        "mandate_id_used": mandate_id,
    }


def get_session(session_id: str) -> dict[str, Any] | None:
    """Loads session data from a session_id."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{session_id}.json"
    if not session_file.exists():
        return None
    try:
        return json.loads(session_file.read_text())
    except json.JSONDecodeError:
        return None


def update_session_status(session_id: str, status: str) -> bool:
    """Updates the status of a session."""
    session_data = get_session(session_id)
    if not session_data:
        return False

    session_data["status"] = status
    session_file = SESSIONS_DIR / f"{session_id}.json"
    session_file.write_text(json.dumps(session_data, indent=2))
    return True


# Placeholder for cleaning up old/expired sessions if needed in the future
# def cleanup_expired_sessions():
#     pass
