import datetime  # Added for timestamps
import json
import uuid
from pathlib import Path

from pydantic import ValidationError  # For parsing errors

from . import ratings, storage, canon # Added canon
from .models import Session, SessionDossier, SessionDuel # Import the new Pydantic models

SESSIONS_DIR = Path("data/sessions")
# CONSUMED_PATHS_FILE instead of CONSUMED_FORKS_FILE for clarity
CONSUMED_PATHS_FILE = SESSIONS_DIR / "consumed_path_uuids.json"


def _load_consumed_paths() -> dict[str, str]:
    """Loads the set of consumed path UUIDs and the session_id they were consumed by."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONSUMED_PATHS_FILE.exists():
        return {}
    try:
        return json.loads(CONSUMED_PATHS_FILE.read_text())
    except json.JSONDecodeError:
        # Consider logging this error
        print(
            f"Warning: Could not parse {CONSUMED_PATHS_FILE}, returning empty consumed paths list."
        )
        return {}


def _save_consumed_paths(consumed_paths: dict[str, str]) -> None:
    """Saves the set of consumed path UUIDs."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    CONSUMED_PATHS_FILE.write_text(json.dumps(consumed_paths, indent=2))


def is_path_consumed(path_uuid: str) -> str | None:
    """Checks if a path_uuid has been consumed, returning the session_id if so."""
    consumed_paths = _load_consumed_paths()
    return consumed_paths.get(path_uuid)


def mark_path_as_consumed(path_uuid: str, session_id: str) -> None:
    """Marks a path_uuid as consumed by a given session_id."""
    consumed_paths = _load_consumed_paths()
    consumed_paths[path_uuid] = session_id
    _save_consumed_paths(consumed_paths)


def create_session(
    path_n_uuid_str: str,
    position_n: int,
    mandate_id_str: str,
    # canonical_path_file: Path, # To be removed, use DB-derived canonical info
    dm: storage.DataManager, # Pass DataManager
) -> Session:
    """
    Creates a new session, generates a dossier using Pydantic models,
    and stores session information as a JSON representation of Session.
    Returns the created Session instance.
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # PathModel uses UUID5, SessionModel.initiating_path_uuid is UUID5
        # MandateID is uuid.UUID
        initiating_path_uuid_obj = uuid.UUID(path_n_uuid_str)
        mandate_id_obj = uuid.UUID(mandate_id_str)
    except ValueError as e:
        raise ValueError(
            f"Invalid UUID string provided for path_n_uuid ('{path_n_uuid_str}') or mandate_id ('{mandate_id_str}'): {e}"
        )

    # Dossier generation
    dossier_duels_models: dict[str, SessionDuel] = {}
    for p_idx in range(position_n - 1, -1, -1):
        predecessor_hronir_uuid_for_duel_str: str | None = None
        if p_idx > 0:
            # Use the new canon module function to get predecessor from DB
            # dm is already passed into create_session
            predecessor_hronir_uuid_for_duel_str = canon.get_canonical_hronir_uuid_for_position(
                dm, p_idx - 1
            )
            if not predecessor_hronir_uuid_for_duel_str:
                # print( # Removed print to avoid interfering with JSON output in CLI tests
                #     f"Warning: SessionManager: Cannot find canonical hrönir (via DB) at position {p_idx - 1} to serve as predecessor for duels at {p_idx}. Skipping duels for {p_idx}."
                # )
                continue
        # else: predecessor_hronir_uuid_for_duel_str remains None for p_idx == 0

        # ratings.determine_next_duel_entropy currently instantiates its own DataManager,
        # which handles its own database connections if using DuckDB. This should be refactored later
        # to accept a DataManager instance (Action 1.3). For now, the call remains.
        # Therefore, we don't need to pass a session/connection object here.
        duel_info_dict = ratings.determine_next_duel_entropy(
            position=p_idx,
            predecessor_hronir_uuid=predecessor_hronir_uuid_for_duel_str,
        )

        if (
            duel_info_dict
            and "duel_pair" in duel_info_dict
            and duel_info_dict["duel_pair"].get("path_A")
            and duel_info_dict["duel_pair"].get("path_B")
        ):
            try:
                # SessionDuel model expects path_A_uuid, path_B_uuid as UUID5
                # determine_next_duel_entropy returns path_A, path_B as strings (UUIDs)
                path_a_uuid = uuid.UUID(duel_info_dict["duel_pair"]["path_A"])
                path_b_uuid = uuid.UUID(duel_info_dict["duel_pair"]["path_B"])
                entropy = float(duel_info_dict.get("entropy", 0.0))

                dossier_duels_models[str(p_idx)] = SessionDuel(
                    path_A_uuid=path_a_uuid,
                    path_B_uuid=path_b_uuid,
                    entropy=entropy,
                )
            except (ValueError, TypeError) as e:
                print(
                    f"Warning: SessionManager: Error creating SessionDuel for position {p_idx} from duel_info {duel_info_dict}: {e}"
                )
                continue

    session_dossier_model = SessionDossier(duels=dossier_duels_models)

    session_model_instance = Session(
        # session_id is generated by default_factory
        initiating_path_uuid=initiating_path_uuid_obj,  # type: ignore
        mandate_id=mandate_id_obj,  # type: ignore
        position_n=position_n,
        dossier=session_dossier_model,
        status="active",
        # created_at and updated_at are handled by default_factory
    )

    session_file = SESSIONS_DIR / f"{session_model_instance.session_id}.json"
    session_file.write_text(session_model_instance.model_dump_json(indent=2))

    mark_path_as_consumed(path_n_uuid_str, str(session_model_instance.session_id))

    return session_model_instance


def get_session(session_id_str: str) -> Session | None:
    """Loads session data from a session_id and parses it into a Session."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Ensure session_id_str is a valid UUID format before file system access
        # This doesn't guarantee the file exists, just that the format is okay.
        uuid.UUID(session_id_str)
    except ValueError:
        print(f"Warning: SessionManager: Invalid session_id format: {session_id_str}")
        return None

    session_file = SESSIONS_DIR / f"{session_id_str}.json"
    if not session_file.exists():
        return None

    try:
        json_data = session_file.read_text()
        session_model_instance = Session.model_validate_json(json_data)
        return session_model_instance
    except json.JSONDecodeError as e:
        print(f"Error: SessionManager: Could not decode JSON from session file {session_file}: {e}")
        return None
    except ValidationError as e:
        print(
            f"Error: SessionManager: Pydantic validation failed for session file {session_file}: {e}"
        )
        return None


def update_session_status(session_id_str: str, new_status: str) -> bool:
    """Updates the status of a session and its updated_at timestamp."""
    session_model_instance = get_session(session_id_str)
    if not session_model_instance:
        return False  # get_session already printed a warning/error

    session_model_instance.status = new_status
    session_model_instance.updated_at = datetime.datetime.now(datetime.timezone.utc)

    session_file = SESSIONS_DIR / f"{session_model_instance.session_id}.json"
    try:
        session_file.write_text(session_model_instance.model_dump_json(indent=2))
        return True
    except Exception as e:
        print(f"Error: SessionManager: Could not write updated session file {session_file}: {e}")
        return False


# Note: The old is_fork_consumed and mark_fork_as_consumed were already aliased
# to is_path_consumed and mark_path_as_consumed in the previous step's plan.
# If they are still present with "fork" names, they should be removed or fully replaced.
# The provided file only had the "fork" versions, so this refactor effectively renames them
# by defining the "path" versions and how they use _load_consumed_paths and _save_consumed_paths.
# The global constants CONSUMED_FORKS_FILE should also be CONSUMED_PATHS_FILE.
# The current overwrite will handle this renaming.


# --- Anti-Sybil Discovery Placeholder ---
def discover_trusted_entities_for_session_context(
    context_description: str, required_count: int, current_data_manager: storage.DataManager
) -> list[uuid.UUID]:
    """
    Placeholder for an anti-Sybil discovery mechanism.

    This function would be responsible for discovering entities (e.g., paths, hrönirs, voters)
    that are considered trustworthy or non-Sybil for a given session context.
    The actual anti-Sybil mechanisms (e.g., reputation, proof-of-work, web-of-trust)
    are not implemented here.

    Args:
        context_description: A string describing the context for which trusted entities are needed
                             (e.g., "duel_candidates_for_position_X", "voters_for_genre_Y").
        required_count: The number of trusted entities desired.
        current_data_manager: The DataManager instance to access existing data.

    Returns:
        A list of UUIDs of discovered trusted entities. Returns an empty list if none found or on error.
    """
    # import logging # Would be good to add proper logging
    # logger = logging.getLogger(__name__)
    print(
        f"Placeholder: Discovering {required_count} trusted entities for context '{context_description}'."
    )
    print("  Actual anti-Sybil logic (reputation, PoW, Web of Trust) needs implementation.")

    # Example placeholder logic:
    # - Could query DataManager for entities matching some criteria.
    # - Could consult a (hypothetical) reputation service.
    # - Could traverse a (hypothetical) trust graph.

    # For now, this function does not implement any real discovery or anti-Sybil checks.
    # It serves as a hook for future development.
    # Depending on the context, it might return paths that are highly rated,
    # or hrönirs from authors with a good track record, etc.

    # If this were for network peer discovery (which is less likely for session_manager.py):
    # print("  If this were for P2P peer discovery, it might involve DHT lookups with trust metrics.")
    # print("  Such logic might be better placed in transaction_manager.py or a dedicated p2p module.")

    # Returning an empty list as a default placeholder action.
    return []
