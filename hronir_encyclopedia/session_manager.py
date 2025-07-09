import datetime
import uuid
from pathlib import Path
import logging # Added for logging

# Removed pydantic.ValidationError as Session.model_validate_json is robust
# from pydantic import ValidationError

from . import ratings # Removed storage import
from .models import Session, SessionDossier, SessionDuel
from .storage import DataManager # Import DataManager itself for type hinting / instantiation
from .utils import get_canonical_path_info_from_json_file # Import moved utility

logger = logging.getLogger(__name__)

# The global data_manager instance is removed. Functions will now expect a DataManager instance.

def is_path_consumed(dm: DataManager, path_uuid: str) -> str | None:
    """Checks if a path_uuid has been consumed by querying the database via the provided DataManager."""
    if not dm._initialized: # Ensure DataManager is initialized before use
        dm.initialize_and_load()
    return dm.backend.get_path_consumed_session_id(path_uuid)


# mark_path_as_consumed is effectively replaced by logic within create_session
# which calls data_manager.backend.mark_path_consumed


def create_session( # Added dm parameter
    dm: DataManager,
    path_n_uuid_str: str,
    position_n: int,
    mandate_id_str: str,
    canonical_path_file: Path, # This dependency might need to be re-evaluated
) -> Session | None:
    """
    Creates a new session (using the provided DataManager), generates a dossier, stores it in DuckDB,
    and marks the initiating path as consumed.
    Returns the created Session instance or None on error.
    """
    try:
        # PathModel uses UUID5, SessionModel.initiating_path_uuid is UUID5
        # SessionModel.mandate_id is uuid.UUID
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
            # Use the imported utility function
            canonical_info_for_predecessor = get_canonical_path_info_from_json_file(
                p_idx - 1, canonical_path_file
            )
            if (
                not canonical_info_for_predecessor
                or "hrönir_uuid" not in canonical_info_for_predecessor
            ):
                print(
                    f"Warning: SessionManager: Cannot find canonical hrönir at position {p_idx - 1} to serve as predecessor for duels at {p_idx}. Skipping duels for {p_idx}."
                )
                continue
            predecessor_hronir_uuid_for_duel_str = canonical_info_for_predecessor["hrönir_uuid"]

        # ratings.determine_next_duel_entropy currently instantiates its own DataManager,
        # which handles its own database connections if using DuckDB.
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
        initiating_path_uuid=initiating_path_uuid_obj, # type: ignore
        mandate_id=mandate_id_obj, # type: ignore
        position_n=position_n,
        dossier=session_dossier_model,
        status="active",
    )
    if not dm._initialized: # Ensure DataManager is initialized before use
        dm.initialize_and_load()

    try:
        dm.backend.add_session(session_model_instance)
        # Mark the initiating path as consumed by this new session
        dm.backend.mark_path_consumed(
            path_uuid=str(session_model_instance.initiating_path_uuid), # Ensure string for DB
            session_id=str(session_model_instance.session_id) # Ensure string for DB
        )
        dm.save_all_data() # Commit transaction
        logger.info(f"Session {session_model_instance.session_id} created and initiating path marked consumed.")
        return session_model_instance
    except Exception as e:
        logger.error(f"Database error creating session or marking path consumed: {e}")
        # Optionally rollback or handle partial failure, though DuckDB operations are typically atomic for single commands
        return None


def get_session(dm: DataManager, session_id_str: str) -> Session | None: # Added dm parameter
    """Loads session data from DuckDB by session_id using the provided DataManager."""
    if not dm._initialized: # Ensure DataManager is initialized before use
        dm.initialize_and_load()
    try:
        # Validate session_id_str format before DB query
        uuid.UUID(session_id_str)
    except ValueError:
        logger.warning(f"Invalid session_id format: {session_id_str}")
        return None

    session_model_instance = dm.backend.get_session(session_id_str)
    if not session_model_instance:
        logger.warning(f"Session not found in DB: {session_id_str}")
        return None
    return session_model_instance


def update_session_status(dm: DataManager, session_id_str: str, new_status: str) -> bool: # Added dm parameter
    """Updates the status of a session in DuckDB and its updated_at timestamp using the provided DataManager."""
    # get_session now also needs dm
    session_model_instance = get_session(dm, session_id_str)
    if not session_model_instance:
        return False  # get_session logs warning

    session_model_instance.status = new_status
    session_model_instance.updated_at = datetime.datetime.now(datetime.timezone.utc)

    if not dm._initialized: # Ensure DataManager is initialized before use (though get_session would have done it)
        dm.initialize_and_load()
    try:
        dm.backend.update_session(session_model_instance)
        dm.save_all_data() # Commit transaction
        logger.info(f"Session {session_id_str} status updated to {new_status}.")
        return True
    except Exception as e:
        logger.error(f"Database error updating session {session_id_str}: {e}")
        return False

# Note: The old file-based consumed path logic (_load_consumed_paths, _save_consumed_paths, etc.)
# and SESSIONS_DIR, CONSUMED_PATHS_FILE constants have been removed.
# is_path_consumed now directly queries the DB via data_manager.
# mark_path_as_consumed is now handled within create_session.
# The old is_fork_consumed and mark_fork_as_consumed were already aliased
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
