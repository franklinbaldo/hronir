import json
import logging
import uuid
from pathlib import Path

from hronir_encyclopedia.storage import DataManager # Import DataManager
from hronir_encyclopedia.models import Session
from pydantic import ValidationError

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Constants for old session storage
OLD_SESSIONS_DIR = Path("data/sessions")
OLD_CONSUMED_PATHS_FILE = OLD_SESSIONS_DIR / "consumed_path_uuids.json"


def migrate_sessions_and_consumed_paths():
    """
    Migrates session data from JSON files and consumed_path_uuids.json
    into the DuckDB database.
    - Reads session files from `data/sessions/*.json`.
    - Adds each session to the `sessions` table in DuckDB.
    - Marks the initiating_path_uuid of each session as consumed in the `paths` table.
    - Reads `data/sessions/consumed_path_uuids.json` and ensures any paths listed
      there are also marked as consumed in the `paths` table.
    This script is designed to be idempotent.
    """
    # Instantiate DataManager for this script's execution.
    # It will use default DB path or environment variable.
    data_manager = DataManager()
    if not data_manager._initialized:
        data_manager.initialize_and_load()

    logging.info("Starting migration of sessions and consumed paths to DuckDB...")

    migrated_sessions_count = 0
    failed_sessions_count = 0
    already_migrated_sessions_count = 0
    paths_marked_consumed_count = 0
    paths_already_marked_count = 0
    paths_failed_to_mark_count = 0

    # 1. Migrate session files
    if OLD_SESSIONS_DIR.exists() and OLD_SESSIONS_DIR.is_dir():
        logging.info(f"Scanning for session files in {OLD_SESSIONS_DIR}...")
        for session_file in OLD_SESSIONS_DIR.glob("*.json"):
            if session_file.name == OLD_CONSUMED_PATHS_FILE.name:
                continue  # Skip the consumed_paths.json file itself

            logging.info(f"Processing session file: {session_file.name}")
            try:
                session_id_str = session_file.stem
                # Validate if session_id_str is a valid UUID
                try:
                    uuid.UUID(session_id_str)
                except ValueError:
                    logging.warning(f"Skipping file {session_file.name}: Name is not a valid UUID.")
                    failed_sessions_count +=1
                    continue

                # Check if session already exists in DB
                if data_manager.backend.get_session(session_id_str):
                    logging.info(f"Session {session_id_str} already exists in DB. Skipping.")
                    already_migrated_sessions_count += 1
                    # Ensure its initiating path is marked as consumed if not already
                    # This covers cases where session was migrated but path marking failed/was missed
                    try:
                        session_json_data = json.loads(session_file.read_text())
                        initiating_path_uuid = session_json_data.get("initiating_path_uuid")
                        if initiating_path_uuid:
                            if not data_manager.backend.get_path_consumed_session_id(str(initiating_path_uuid)):
                                data_manager.backend.mark_path_consumed(str(initiating_path_uuid), session_id_str)
                                logging.info(f"Marked initiating_path_uuid {initiating_path_uuid} from already migrated session {session_id_str} as consumed.")
                                paths_marked_consumed_count +=1
                            else:
                                paths_already_marked_count +=1
                        else:
                            logging.warning(f"No initiating_path_uuid found in {session_file.name} for already migrated session.")
                    except Exception as e:
                        logging.error(f"Error ensuring path consumed for already migrated session {session_id_str}: {e}")
                    continue

                json_data = session_file.read_text()
                session_model_instance = Session.model_validate_json(json_data)

                data_manager.backend.add_session(session_model_instance)
                logging.info(f"Successfully migrated session {session_model_instance.session_id} to DB.")
                migrated_sessions_count += 1

                # Mark its initiating_path_uuid as consumed
                if session_model_instance.initiating_path_uuid:
                    path_uuid_str = str(session_model_instance.initiating_path_uuid)
                    session_id_for_path = str(session_model_instance.session_id)
                    if not data_manager.backend.get_path_consumed_session_id(path_uuid_str):
                        data_manager.backend.mark_path_consumed(path_uuid_str, session_id_for_path)
                        logging.info(f"Marked initiating_path_uuid {path_uuid_str} as consumed by session {session_id_for_path}.")
                        paths_marked_consumed_count += 1
                    else:
                        # This case might indicate the path was consumed by another session listed in consumed_paths.json
                        # Or data inconsistency. Log it.
                        logging.warning(f"Path {path_uuid_str} was already marked as consumed. Current session: {session_id_for_path}.")
                        paths_already_marked_count +=1

            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON from {session_file.name}: {e}")
                failed_sessions_count += 1
            except ValidationError as e:
                logging.error(f"Pydantic validation failed for {session_file.name}: {e}")
                failed_sessions_count += 1
            except Exception as e:
                logging.error(f"Unexpected error processing {session_file.name}: {e}")
                failed_sessions_count += 1
    else:
        logging.info(f"{OLD_SESSIONS_DIR} does not exist or is not a directory. No session files to migrate.")

    # 2. Migrate consumed_path_uuids.json
    if OLD_CONSUMED_PATHS_FILE.exists():
        logging.info(f"Processing {OLD_CONSUMED_PATHS_FILE}...")
        try:
            consumed_paths_data = json.loads(OLD_CONSUMED_PATHS_FILE.read_text())
            if not isinstance(consumed_paths_data, dict):
                raise ValueError("consumed_path_uuids.json is not a dictionary.")

            for path_uuid, session_id in consumed_paths_data.items():
                try:
                    # Validate UUIDs
                    str_path_uuid = str(uuid.UUID(path_uuid))
                    str_session_id = str(uuid.UUID(session_id))

                    if data_manager.backend.get_path_by_uuid(str_path_uuid):
                        existing_consumer_session_id = data_manager.backend.get_path_consumed_session_id(str_path_uuid)
                        if not existing_consumer_session_id:
                            data_manager.backend.mark_path_consumed(str_path_uuid, str_session_id)
                            logging.info(f"Marked path {str_path_uuid} from {OLD_CONSUMED_PATHS_FILE.name} as consumed by session {str_session_id}.")
                            paths_marked_consumed_count += 1
                        elif existing_consumer_session_id == str_session_id:
                            logging.info(f"Path {str_path_uuid} from {OLD_CONSUMED_PATHS_FILE.name} already marked as consumed by session {str_session_id}.")
                            paths_already_marked_count +=1
                        else:
                            logging.warning(f"Path {str_path_uuid} from {OLD_CONSUMED_PATHS_FILE.name} was already marked consumed by a different session ({existing_consumer_session_id}) than specified ({str_session_id}). Not changing.")
                            paths_already_marked_count +=1 # or a different counter for conflicts
                    else:
                        logging.warning(f"Path {str_path_uuid} from {OLD_CONSUMED_PATHS_FILE.name} not found in DB. Cannot mark as consumed.")
                        paths_failed_to_mark_count +=1
                except ValueError as e: # UUID validation error
                    logging.warning(f"Invalid UUID string in {OLD_CONSUMED_PATHS_FILE.name} for entry '{path_uuid}': '{session_id}'. Error: {e}. Skipping entry.")
                    paths_failed_to_mark_count +=1
                except Exception as e:
                    logging.error(f"Error processing entry '{path_uuid}': '{session_id}' from {OLD_CONSUMED_PATHS_FILE.name}: {e}")
                    paths_failed_to_mark_count +=1

        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {OLD_CONSUMED_PATHS_FILE.name}: {e}")
        except ValueError as e: # For the isinstance check
            logging.error(f"Format error in {OLD_CONSUMED_PATHS_FILE.name}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error processing {OLD_CONSUMED_PATHS_FILE.name}: {e}")
    else:
        logging.info(f"{OLD_CONSUMED_PATHS_FILE} does not exist. No legacy consumed paths to migrate.")

    # Commit all changes to DB
    try:
        data_manager.save_all_data()
        logging.info("Successfully committed all changes to the database.")
    except Exception as e:
        logging.error(f"Failed to commit changes to the database: {e}")

    logging.info("--- Migration Summary ---")
    logging.info(f"Sessions migrated: {migrated_sessions_count}")
    logging.info(f"Sessions already in DB: {already_migrated_sessions_count}")
    logging.info(f"Sessions failed to migrate: {failed_sessions_count}")
    logging.info(f"Paths newly marked as consumed: {paths_marked_consumed_count}")
    logging.info(f"Paths already marked as consumed: {paths_already_marked_count}")
    logging.info(f"Paths failed to be marked as consumed: {paths_failed_to_mark_count}")
    logging.info("Migration process finished.")
    logging.info("Please verify the data in DuckDB.")
    if OLD_SESSIONS_DIR.exists():
        logging.info(f"After verification, you may manually delete the {OLD_SESSIONS_DIR} directory and {OLD_CONSUMED_PATHS_FILE} file.")

if __name__ == "__main__":
    migrate_sessions_and_consumed_paths()
