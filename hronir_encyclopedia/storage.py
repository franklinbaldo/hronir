import json
import shutil
import uuid
from pathlib import Path
from typing import Any
import fcntl # For file locking
import datetime # For TransactionDB

import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SQLAlchemySession # Renamed to avoid conflict

from .models import (
    ForkDB,
    VoteDB,
    TransactionDB,
    SuperBlockDB, # Assuming SuperBlock might also be needed later
    engine as in_memory_engine, # Import the global engine
    SessionLocal as InMemorySessionLocal, # Import the global SessionLocal
    create_db_and_tables
)

UUID_NAMESPACE = uuid.NAMESPACE_URL


# --- Global Data Manager ---
class DataManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DataManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, fork_csv_dir="forking_path", ratings_csv_dir="ratings", transactions_json_dir="data/transactions"):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.engine = in_memory_engine
        create_db_and_tables(self.engine) # Create tables in the in-memory DB
        self.SessionLocal = InMemorySessionLocal
        self._initialized = False # Will be set to True after initial load
        self.fork_csv_dir = Path(fork_csv_dir)
        self.ratings_csv_dir = Path(ratings_csv_dir)
        self.transactions_json_dir = Path(transactions_json_dir)

        # Automatic initial load when the first instance is created
        # self.load_all_data_from_csvs() # Defer this call to an explicit init

    def get_session(self) -> SQLAlchemySession:
        return self.SessionLocal()

    def initialize_and_load(self):
        if not self._initialized:
            self.load_all_data_from_csvs()
            self._initialized = True
            print("DataManager: In-memory database initialized and loaded from CSVs.") # For debug
        else:
            print("DataManager: Already initialized.")


    def _load_with_lock(self, file_path: Path, load_func):
        """Acquires a shared lock and calls load_func."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            # print(f"File {file_path} is empty or does not exist. Skipping.") # Debug
            return
        try:
            with open(file_path, 'rb') as f: # Open in binary for fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_SH) # Shared lock for reading
                # print(f"Acquired lock for {file_path}") # Debug
                try:
                    load_func(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN) # Release lock
                    # print(f"Released lock for {file_path}") # Debug
        except FileNotFoundError:
            # print(f"File not found during locking: {file_path}. Skipping.") # Debug
            pass # File might have been deleted between exists check and open
        except Exception as e:
            print(f"Error during locked read of {file_path}: {e}")


    def load_all_data_from_csvs(self):
        """Loads all data from CSVs into the in-memory SQLite database."""
        session = self.get_session()
        try:
            # Load Forks
            for csv_file in self.fork_csv_dir.glob("*.csv"):
                def load_forks(file_handle): # file_handle is already open
                    # Use file_handle.name to get path for pandas
                    df = pd.read_csv(file_handle.name)
                    for _, row in df.iterrows():
                        # Ensure all fields are present, providing defaults if necessary
                        fork = ForkDB(
                            fork_uuid=row["fork_uuid"],
                            position=int(row.get("position", 0)),
                            prev_uuid=row.get("prev_uuid"),
                            uuid=row.get("uuid"),
                            status=row.get("status", "PENDING"),
                            mandate_id=row.get("mandate_id"),
                        )
                        session.merge(fork) # Use merge to avoid duplicates if re-loading
                self._load_with_lock(csv_file, load_forks)

            # Load Ratings
            for csv_file in self.ratings_csv_dir.glob("position_*.csv"):
                def load_ratings(file_handle):
                    pos_str = csv_file.stem.split("_")[-1]
                    if not pos_str.isdigit():
                        # print(f"Skipping ratings file with invalid position: {csv_file}") # Debug
                        return
                    pos = int(pos_str)
                    df = pd.read_csv(file_handle.name)
                    for _, row in df.iterrows():
                        vote = VoteDB(
                            position=pos,
                            voter=row.get("voter"),
                            winner=row.get("winner"),
                            loser=row.get("loser"),
                        )
                        session.add(vote) # Votes might have auto-increment ID, so add
                self._load_with_lock(csv_file, load_ratings)

            # Load Transactions (from JSON files)
            if self.transactions_json_dir.exists():
                for json_file in self.transactions_json_dir.glob("*.json"):
                    def load_transactions(file_handle):
                        data = json.load(file_handle) # Read from file handle
                        ts_str = data.get("timestamp", "")
                        # Ensure timestamp is valid ISO format, handling potential 'Z'
                        if ts_str.endswith("Z"):
                            ts_str = ts_str[:-1] + "+00:00"
                        try:
                            ts = datetime.datetime.fromisoformat(ts_str)
                        except ValueError:
                            # print(f"Invalid timestamp format in {json_file}: {ts_str}. Using current time.") # Debug
                            ts = datetime.datetime.utcnow()

                        tx = TransactionDB(
                            uuid=data["transaction_uuid"], # Assuming this key from migrate script
                            timestamp=ts,
                            prev_uuid=data.get("previous_transaction_uuid"), # Assuming this key
                            content=data, # Store the whole JSON content
                        )
                        session.merge(tx)
                    # JSON files are also text, can use similar locking if desired,
                    # but typically are written atomically. For consistency:
                    self._load_with_lock(json_file, load_transactions)

            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error loading data from CSVs/JSON: {e}") # Critical error
            raise
        finally:
            session.close()

    def _write_with_lock(self, file_path: Path, write_func):
        """Acquires an exclusive lock and calls write_func."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(file_path, 'wb') as f: # Open in binary write for fcntl, also creates/truncates
                fcntl.flock(f.fileno(), fcntl.LOCK_EX) # Exclusive lock for writing
                # print(f"Acquired EX lock for {file_path}") # Debug
                try:
                    # write_func needs to handle writing to this open file handle 'f'
                    # or, more simply, just use the file_path and pandas will reopen/write.
                    # For simplicity with pandas, we'll pass the path and let pandas handle file opening.
                    # The lock is on the descriptor 'f', which points to file_path.
                    # Re-opening by pandas should respect the lock if on the same descriptor,
                    # but it's safer if pandas writes to the already open 'f'.
                    # However, pandas to_csv doesn't directly take a binary file handle well for text.
                    # So, we lock, then pandas writes to path, then unlock.
                    # This means the lock acquisition and release are critical.
                    write_func(file_path) # Pass path to the write function
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN) # Release lock
                    # print(f"Released EX lock for {file_path}") # Debug
        except Exception as e:
            print(f"Error during locked write to {file_path}: {e}")


    def serialize_db_to_files(self):
        """Serializes the in-memory database content back to CSV/JSON files."""
        if not self._initialized:
            print("DataManager not initialized. Skipping serialization.")
            return

        session = self.get_session()
        try:
            # Serialize Forks to a single CSV
            all_forks_db = session.query(ForkDB).all()
            if all_forks_db:
                forks_df = pd.DataFrame([f.__dict__ for f in all_forks_db])
                # Remove SQLAlchemy internal state column if present
                if '_sa_instance_state' in forks_df.columns:
                    forks_df = forks_df.drop(columns=['_sa_instance_state'])

                # Define target CSV file for all forks
                # Using a new name to avoid conflicts with potentially existing varied CSVs
                target_fork_csv = self.fork_csv_dir / "all_db_forks.csv"

                def write_forks_df(path):
                    forks_df.to_csv(path, index=False)

                self._write_with_lock(target_fork_csv, write_forks_df)
                # print(f"Serialized {len(all_forks_db)} forks to {target_fork_csv}") # Debug

            # Serialize Votes to multiple CSVs (grouped by position)
            all_votes_db = session.query(VoteDB).all()
            if all_votes_db:
                votes_df = pd.DataFrame([v.__dict__ for v in all_votes_db])
                if '_sa_instance_state' in votes_df.columns:
                    votes_df = votes_df.drop(columns=['_sa_instance_state'])

                for position, group in votes_df.groupby('position'):
                    pos_csv_file = self.ratings_csv_dir / f"position_{int(position):03d}.csv"
                    # Select only relevant columns for vote CSVs (usually voter, winner, loser)
                    # The VoteDB model has id, position, voter, winner, loser.
                    # Original CSVs might only have voter, winner, loser per position file.
                    # For now, writing all columns from DB.
                    columns_to_write = ['voter', 'winner', 'loser'] # Or all: group.columns
                    if 'id' in group.columns: # Keep id if present from DB model
                        columns_to_write = ['id'] + columns_to_write

                    # Filter group to only existing columns to avoid errors
                    group_filtered = group[[col for col in columns_to_write if col in group.columns]]

                    def write_ratings_df(path):
                        group_filtered.to_csv(path, index=False)

                    self._write_with_lock(pos_csv_file, write_ratings_df)
                    # print(f"Serialized votes for position {position} to {pos_csv_file}") # Debug

            # Serialize Transactions to individual JSON files
            all_transactions_db = session.query(TransactionDB).all()
            if all_transactions_db:
                self.transactions_json_dir.mkdir(parents=True, exist_ok=True) # Ensure dir exists
                for tx_db in all_transactions_db:
                    tx_uuid = tx_db.uuid
                    tx_data_to_serialize = tx_db.content # Content is already the JSON data

                    # Reconstruct original timestamp format if needed, or save as ISO
                    # tx_data_to_serialize['timestamp'] = tx_db.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                    target_tx_json = self.transactions_json_dir / f"{tx_uuid}.json"

                    def write_tx_json(path):
                        with open(path, 'w') as json_f:
                            json.dump(tx_data_to_serialize, json_f, indent=2)

                    # Using a text-based lock for JSON, fcntl still works on the descriptor
                    self._write_with_lock(target_tx_json, write_tx_json)
                    # print(f"Serialized transaction {tx_uuid} to {target_tx_json}") # Debug

            # print("DB serialization to files complete.") # Debug

        except Exception as e:
            # print(f"Error during DB serialization: {e}") # Debug
            # No rollback needed for reads, but important to log error
            raise
        finally:
            session.close()


# --- Initialize the global DataManager instance ---
# It's better to initialize it explicitly when the application starts.
# For now, it will be initialized on first import/use.
# A dedicated app setup function should call data_manager.initialize_and_load()
data_manager = DataManager()

# Helper function to get a session, ensures data_manager is initialized
def get_db_session() -> SQLAlchemySession:
    if not data_manager._initialized:
        # This automatic initialization might be too implicit.
        # Consider requiring an explicit setup call in the application's entry point.
        print("DataManager not initialized. Initializing and loading data now...")
        data_manager.initialize_and_load()
    return data_manager.get_session()


UUID_NAMESPACE = uuid.NAMESPACE_URL


def compute_forking_uuid(position: int, prev_uuid: str, cur_uuid: str) -> str:
    """Return deterministic UUID5 for a forking path entry."""
    data = f"{position}:{prev_uuid}:{cur_uuid}"
    return str(uuid.uuid5(UUID_NAMESPACE, data))


def compute_uuid(text: str) -> str:
    """Return deterministic UUID5 of the given text."""
    return str(uuid.uuid5(UUID_NAMESPACE, text))


def uuid_to_path(uuid_str: str, base: Path) -> Path:
    """Return a direct subdirectory path for the given UUID string under base."""
    return base / uuid_str


def store_chapter(chapter_file: Path, base: Path | str = "the_library") -> str:
    """Store chapter_file content under UUID-based path and return UUID.

    This function creates pure content nodes. Narrative connections between
    hrönirs are managed separately via forking_path CSV files.
    """
    base = Path(base)
    text = chapter_file.read_text()
    chapter_uuid = compute_uuid(text)
    chapter_dir = uuid_to_path(chapter_uuid, base)
    chapter_dir.mkdir(parents=True, exist_ok=True)

    ext = chapter_file.suffix or ".md"
    (chapter_dir / f"index{ext}").write_text(text)

    meta = {"uuid": chapter_uuid}
    (chapter_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return chapter_uuid


def store_chapter_text(text: str, base: Path | str = "the_library") -> str:
    """Store raw chapter text and return its UUID.

    This function creates pure content nodes. Narrative connections between
    hrönirs are managed separately via forking_path CSV files.
    """
    base = Path(base)
    chapter_uuid = compute_uuid(text)
    chapter_dir = uuid_to_path(chapter_uuid, base)
    chapter_dir.mkdir(parents=True, exist_ok=True)
    (chapter_dir / "index.md").write_text(text)
    meta = {"uuid": chapter_uuid}
    (chapter_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return chapter_uuid


def is_valid_uuid_v5(value: str) -> bool:
    """Return True if value is a valid UUIDv5."""
    try:
        u = uuid.UUID(value)
        return u.version == 5
    except ValueError:
        return False


def chapter_exists(uuid_str: str, base: Path | str = "the_library") -> bool:
    """Return True if a chapter directory exists for uuid_str."""
    base = Path(base)
    chapter_dir = uuid_to_path(uuid_str, base)
    return any(chapter_dir.glob("index.*"))


def forking_path_exists(
    fork_uuid: str,
    # fork_dir, conn are no longer primary ways to check. Session is key.
    session: SQLAlchemySession | None = None,
) -> bool:
    """Return True if fork_uuid appears in the in-memory database."""

    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    try:
        # The primary check is now against the ForkDB in the in-memory database
        exists = session.get(ForkDB, fork_uuid) is not None
        return exists
    finally:
        if close_session_locally and session is not None:
            session.close()


def validate_or_move(chapter_file: Path, base: Path | str = "the_library") -> str:
    """Ensure chapter_file resides under its UUID path. Move if necessary."""
    base = Path(base)
    text = chapter_file.read_text()
    chapter_uuid = compute_uuid(text)
    target_dir = uuid_to_path(chapter_uuid, base)
    ext = chapter_file.suffix or ".md"
    target_file = target_dir / f"index{ext}"
    if chapter_file.resolve() != target_file.resolve():
        target_dir.mkdir(parents=True, exist_ok=True)
        chapter_file.replace(target_file)
    meta_path = target_dir / "metadata.json"
    if not meta_path.exists():
        meta = {"uuid": chapter_uuid}
        meta_path.write_text(json.dumps(meta, indent=2))
    return chapter_uuid


def audit_forking_data_in_db(base_library_path: Path | str = "the_library", session: SQLAlchemySession | None = None) -> int:
    """
    Validates all forking path entries in the in-memory database.
    - Ensures fork_uuid is correct based on position, prev_uuid, and uuid.
    - Checks if referenced hrönir (chapters) exist. Sets 'undiscovered' if not.
    - Ensures 'status' field exists (though ForkDB model defines a default).
    Returns the number of fork entries modified.
    """
    base_library_path = Path(base_library_path)
    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    modified_count = 0
    try:
        all_forks = session.query(ForkDB).all()
        for fork_entry in all_forks:
            changed_in_entry = False

            # Ensure status exists (model should handle default, but good for robustness)
            if not fork_entry.status:
                fork_entry.status = "PENDING"
                changed_in_entry = True

            # Validate fork_uuid
            # Need to handle potential None for prev_uuid if it's the root
            expected_fork_uuid = compute_forking_uuid(
                fork_entry.position,
                fork_entry.prev_uuid if fork_entry.prev_uuid else "None", # compute_forking_uuid expects strings
                fork_entry.uuid
            )
            if fork_entry.fork_uuid != expected_fork_uuid:
                # This is serious, indicates potential corruption or miscalculation earlier.
                # For an audit, we might just log this. Forcing a change could be risky
                # if the existing fork_uuid is referenced elsewhere.
                # For now, let's assume we correct it if it's wrong.
                # print(f"Correcting fork_uuid for {fork_entry.fork_uuid} to {expected_fork_uuid}") # Debug
                fork_entry.fork_uuid = expected_fork_uuid # This could be problematic if PK constraint
                changed_in_entry = True


            # Validate chapter existence
            # The ForkDB model stores prev_uuid as String, can be nullable.
            # chapter_exists expects a valid UUID string.
            prev_chapter_valid = True # Assume valid if no prev_uuid (e.g. root)
            if fork_entry.prev_uuid:
                 prev_chapter_valid = is_valid_uuid_v5(str(fork_entry.prev_uuid)) and \
                                      chapter_exists(str(fork_entry.prev_uuid), base_library_path)

            current_chapter_valid = is_valid_uuid_v5(str(fork_entry.uuid)) and \
                                    chapter_exists(str(fork_entry.uuid), base_library_path)

            # The 'undiscovered' field is not in ForkDB model.
            # This logic would require adding it to models.py:
            #   undiscovered = Column(Boolean, default=False)
            # For now, we can't set it. This part of audit needs model change or different handling.
            # if not (prev_chapter_valid and current_chapter_valid):
            #     if not fork_entry.undiscovered: # Assuming 'undiscovered' field exists
            #         # fork_entry.undiscovered = True
            #         # changed_in_entry = True
            #         print(f"Fork {fork_entry.fork_uuid} references non-existent chapters. (undiscovered not implemented)") # Debug
            # else:
            #     if fork_entry.undiscovered: # Assuming 'undiscovered' field exists
            #         # fork_entry.undiscovered = False
            #         # changed_in_entry = True
            #         pass # Mark as discovered if it was previously undiscovered

            if changed_in_entry:
                session.add(fork_entry)
                modified_count += 1

        if modified_count > 0:
            session.commit()
            # print(f"Audit: Committed {modified_count} changes to ForkDB.") # Debug
    except Exception as e:
        if session:
            session.rollback()
        # print(f"Error during DB fork audit: {e}") # Debug
        raise
    finally:
        if close_session_locally and session is not None:
            session.close()
    return modified_count


def purge_invalid_forks_from_db(base_library_path: Path | str = "the_library", session: SQLAlchemySession | None = None) -> int:
    """
    Removes invalid forking path entries from the in-memory database.
    An entry is invalid if:
    - Its fork_uuid is incorrect.
    - It references non-existent or invalid hrönir (chapters) for prev_uuid or uuid.
    Returns the number of fork entries deleted.
    """
    base_library_path = Path(base_library_path)
    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    deleted_count = 0
    try:
        all_forks = session.query(ForkDB).all()
        forks_to_delete = []

        for fork_entry in all_forks:
            is_invalid = False

            # Check fork_uuid correctness
            expected_fork_uuid = compute_forking_uuid(
                fork_entry.position,
                fork_entry.prev_uuid if fork_entry.prev_uuid else "None",
                fork_entry.uuid
            )
            if fork_entry.fork_uuid != expected_fork_uuid:
                is_invalid = True

            # Check chapter existence and validity
            if not is_invalid and fork_entry.prev_uuid: # Only check if not already invalid
                if not (is_valid_uuid_v5(str(fork_entry.prev_uuid)) and \
                        chapter_exists(str(fork_entry.prev_uuid), base_library_path)):
                    is_invalid = True

            if not is_invalid: # Only check if not already invalid
                if not (is_valid_uuid_v5(str(fork_entry.uuid)) and \
                        chapter_exists(str(fork_entry.uuid), base_library_path)):
                    is_invalid = True

            if is_invalid:
                forks_to_delete.append(fork_entry)

        if forks_to_delete:
            for fork_to_delete in forks_to_delete:
                session.delete(fork_to_delete)
            session.commit()
            deleted_count = len(forks_to_delete)
            # print(f"Purge: Committed deletion of {deleted_count} invalid forks from ForkDB.") # Debug

    except Exception as e:
        if session:
            session.rollback()
        # print(f"Error during DB fork purge: {e}") # Debug
        raise
    finally:
        if close_session_locally and session is not None:
            session.close()
    return deleted_count


def purge_invalid_votes_from_db(
    base_library_path: Path | str = "the_library",
    session: SQLAlchemySession | None = None
) -> int:
    """
    Removes invalid vote entries from the in-memory database (VoteDB).
    A vote is invalid if:
    - It references a non-existent voter (fork_uuid).
    - It references non-existent winner or loser hrönir (chapters).
    - Duplicate (voter, position) entries are found (keeps first encountered).
    Returns the number of vote entries deleted.
    """
    base_library_path = Path(base_library_path)
    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    deleted_count = 0
    try:
        all_votes = session.query(VoteDB).order_by(VoteDB.id).all() # Process in consistent order

        votes_to_delete = []
        # For duplicate checking: (voter_fork_uuid, position)
        # This assumes a voter can only vote once per position.
        seen_voter_at_position = set()

        for vote_entry in all_votes:
            is_invalid = False

            # Check for duplicate voter at the same position
            voter_pos_tuple = (vote_entry.voter, vote_entry.position)
            if voter_pos_tuple in seen_voter_at_position:
                is_invalid = True
            else:
                seen_voter_at_position.add(voter_pos_tuple)

            # Check if voter (fork_uuid) exists
            if not is_invalid:
                # Use the already refactored forking_path_exists
                if not forking_path_exists(vote_entry.voter, session=session):
                    is_invalid = True

            # Check winner chapter existence
            if not is_invalid:
                if not (is_valid_uuid_v5(str(vote_entry.winner)) and \
                        chapter_exists(str(vote_entry.winner), base_library_path)):
                    is_invalid = True

            # Check loser chapter existence
            if not is_invalid:
                if not (is_valid_uuid_v5(str(vote_entry.loser)) and \
                        chapter_exists(str(vote_entry.loser), base_library_path)):
                    is_invalid = True

            if is_invalid:
                votes_to_delete.append(vote_entry)

        if votes_to_delete:
            for vote_to_delete in votes_to_delete:
                session.delete(vote_to_delete)
            session.commit()
            deleted_count = len(votes_to_delete)
            # print(f"Purge: Committed deletion of {deleted_count} invalid votes from VoteDB.") # Debug

    except Exception as e:
        if session:
            session.rollback()
        # print(f"Error during DB vote purge: {e}") # Debug
        raise
    finally:
        if close_session_locally and session is not None:
            session.close()
    return deleted_count


def purge_fake_hronirs(base: Path | str = "the_library") -> int:
    """Remove chapters whose metadata or path UUID doesn't match their text."""
    base = Path(base)
    removed = 0
    metas = list(base.rglob("metadata.json"))
    for meta in metas:
        chapter_dir = meta.parent
        try:
            data = json.loads(meta.read_text())
        except Exception:
            shutil.rmtree(chapter_dir, ignore_errors=True)
            removed += 1
            continue

        uuid_str = data.get("uuid")
        index_file = chapter_dir / "index.md"
        if not index_file.exists() or not is_valid_uuid_v5(uuid_str):
            shutil.rmtree(chapter_dir, ignore_errors=True)
            removed += 1
            continue

        computed = compute_uuid(index_file.read_text())
        expected_dir = uuid_to_path(uuid_str, base)
        if computed != uuid_str or chapter_dir.resolve() != expected_dir.resolve():
            shutil.rmtree(chapter_dir, ignore_errors=True)
            removed += 1
    return removed


def get_canonical_fork_info(
    position: int, canonical_path_file: Path = Path("data/canonical_path.json")
) -> dict[str, str] | None:
    """
    Consulta o arquivo de caminho canônico (ex: data/canonical_path.json) para
    revelar o fork_uuid e o hrönir_uuid (sucessor) canônicos para a posição especificada.

    Retorna um dicionário {'fork_uuid': str, 'hrönir_uuid': str} se encontrado e válido,
    caso contrário None.

    Espera que o canonical_path_file armazene uma estrutura como:
    {
      "title": "The Hrönir Encyclopedia - Canonical Path",
      "path": {
        "0": { "fork_uuid": "...", "hrönir_uuid": "..." },
        "1": { "fork_uuid": "...", "hrönir_uuid": "..." }
      }
    }
    """
    if not canonical_path_file.exists():
        return None

    try:
        with open(canonical_path_file) as f:
            canonical_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    path_entries = canonical_data.get("path")
    if not isinstance(path_entries, dict):
        return None

    position_str = str(position)
    canonical_entry = path_entries.get(position_str)

    if not isinstance(canonical_entry, dict):
        return None

    fork_uuid = canonical_entry.get("fork_uuid")
    hrönir_uuid = canonical_entry.get("hrönir_uuid")

    if not fork_uuid or not hrönir_uuid:
        return None

    if not isinstance(fork_uuid, str) or not is_valid_uuid_v5(fork_uuid):
        return None

    if not isinstance(hrönir_uuid, str) or not is_valid_uuid_v5(hrönir_uuid):
        return None

    return {"fork_uuid": fork_uuid, "hrönir_uuid": hrönir_uuid}


def append_fork(
    position: int,
    prev_uuid: str,
    uuid_str: str,  # Renamed 'uuid' to 'uuid_str' to avoid conflict with uuid module
    # csv_file parameter is removed as it's not directly used for DB op.
    # conn parameter is removed.
    session: SQLAlchemySession | None = None,
    status: str = "PENDING", # Allow status to be set
) -> str:
    """
    Appends a new fork entry to the in-memory database.
    Calculates a deterministic fork_uuid for the entry.
    Returns the fork_uuid.
    """
    fork_uuid = compute_forking_uuid(position, prev_uuid, uuid_str)

    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    try:
        existing_fork = session.get(ForkDB, fork_uuid)
        if existing_fork:
            # Fork already exists, decide on behavior: update or do nothing.
            # For now, let's assume if it exists, we don't need to re-add or update via append.
            # print(f"Fork {fork_uuid} already exists. Skipping append.")
            return fork_uuid

        fork = ForkDB(
            fork_uuid=fork_uuid,
            position=position,
            prev_uuid=prev_uuid or None, # Ensure None if prev_uuid is empty string
            uuid=uuid_str,
            status=status,
            # mandate_id is not set during initial append by default
        )
        session.add(fork)
        session.commit()
        return fork_uuid
    except Exception as e:
        if session: # Check if session was successfully obtained
            session.rollback()
        # print(f"Error appending fork {fork_uuid}: {e}") # Debug
        raise # Re-raise the exception to allow higher-level handling
    finally:
        if close_session_locally and session is not None:
            session.close()


def purge_fake_forking_csv(csv_path: Path, base: Path | str = "the_library") -> int:
    """Remove invalid rows from a forking path CSV."""
    import pandas as pd

    base = Path(base)
    if not csv_path.exists():
        return 0

    if csv_path.stat().st_size == 0:
        csv_path.write_text("")
        return 0
    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        csv_path.write_text("")
        return 0
    keep = []
    removed = 0
    for _, row in df.iterrows():
        pos = int(row.get("position", 0))
        prev_uuid = str(row.get("prev_uuid", ""))
        cur_uuid = str(row.get("uuid", ""))
        fork_uuid = str(row.get("fork_uuid", ""))
        expected = compute_forking_uuid(pos, prev_uuid, cur_uuid)
        if fork_uuid != expected:
            removed += 1
            continue
        if not (is_valid_uuid_v5(prev_uuid) and chapter_exists(prev_uuid, base)):
            removed += 1
            continue
        if not (is_valid_uuid_v5(cur_uuid) and chapter_exists(cur_uuid, base)):
            removed += 1
            continue
        # Ensure 'status' column is preserved if it exists, otherwise it might be dropped
        # if 'keep' is reconstructed from rows that don't explicitly include it and then
        # pd.DataFrame infers columns.
        # However, if 'row' is a Series from the original df and includes 'status',
        # it will be included in 'keep'.
        # For safety, if we were creating dicts for 'keep', we'd add 'status': row.get('status', "PENDING")
        keep.append(row)

    if removed:
        if keep:  # Ensure 'keep' is not empty before creating DataFrame
            # Define columns to ensure 'status' is included, even if all rows
            # had it as NaN initially (though audit_forking_csv should prevent this for new files)
            final_cols = ["position", "prev_uuid", "uuid", "fork_uuid", "undiscovered", "status"]
            # Filter df_keep to only include columns that actually exist in it, plus 'status'
            df_kept = pd.DataFrame(keep)
            cols_to_use = [col for col in final_cols if col in df_kept.columns]
            if (
                "status" not in df_kept.columns and "status" in final_cols
            ):  # if status was somehow lost
                # This case should ideally not happen if audit_forking_csv ran correctly
                df_kept["status"] = "PENDING"  # Add with default if missing
                if "status" not in cols_to_use:  # Should not be needed but defensive
                    cols_to_use.append("status")

            pd.DataFrame(df_kept, columns=cols_to_use).to_csv(csv_path, index=False)
        else:  # All rows were removed
            csv_path.write_text(
                "position,prev_uuid,uuid,fork_uuid,undiscovered,status\n"
            )  # Write header for empty file
    return removed


def purge_fake_votes_csv(
    csv_path: Path,
    base: Path | str = "the_library",
    fork_dir: Path | str = "forking_path",
    conn: Engine | None = None,
) -> int:
    """Remove votes referencing missing chapters or duplicate voters."""
    import pandas as pd

    base = Path(base)
    if not csv_path.exists():
        return 0

    if csv_path.stat().st_size == 0:
        csv_path.write_text("")
        return 0
    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        csv_path.write_text("")
        return 0
    keep = []
    seen = set()
    removed = 0
    for _, row in df.iterrows():
        voter = str(row.get("voter", ""))
        winner = str(row.get("winner", ""))
        loser = str(row.get("loser", ""))
        if voter in seen:
            removed += 1
            continue
        if not forking_path_exists(voter, fork_dir, conn=conn):
            removed += 1
            continue
        if not (is_valid_uuid_v5(winner) and chapter_exists(winner, base)):
            removed += 1
            continue
        if not (is_valid_uuid_v5(loser) and chapter_exists(loser, base)):
            removed += 1
            continue
        seen.add(voter)
        keep.append(row)

    if removed:
        pd.DataFrame(keep).to_csv(csv_path, index=False)
    return removed


def get_fork_data(fork_uuid_to_find: str, session: SQLAlchemySession | None = None) -> ForkDB | None:
    """
    Retrieves a fork by its fork_uuid from the in-memory database.

    Returns:
        A ForkDB object if found, otherwise None.
    """
    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    try:
        fork = session.get(ForkDB, fork_uuid_to_find)
        return fork
    finally:
        if close_session_locally and session is not None:
            session.close()


def update_fork_status(
    fork_uuid_to_update: str,
    new_status: str,
    mandate_id: str | None = None,
    # fork_dir_base and conn parameters are removed.
    session: SQLAlchemySession | None = None,
) -> bool:
    """
    Updates the status and optionally the mandate_id of a specific fork_uuid
    in the in-memory database.

    Args:
        fork_uuid_to_update: The UUID of the fork to update.
        new_status: The new status string (e.g., "QUALIFIED", "SPENT").
        mandate_id: Optional mandate_id to set.
        session: Optional SQLAlchemy session.

    Returns:
        True if the fork was found and updated, False otherwise.
    """
    close_session_locally = False
    if session is None:
        session = get_db_session()
        close_session_locally = True

    try:
        fork = session.get(ForkDB, fork_uuid_to_update)
        if not fork:
            return False  # Fork not found

        fork.status = new_status
        if mandate_id is not None:
            # This assumes ForkDB model has a mandate_id attribute.
            # If mandate_id is an optional part of the schema handled by a JSON field,
            # this might need adjustment. For now, direct attribute assignment.
            fork.mandate_id = mandate_id

        session.add(fork) # Add to session before commit, good practice even for updates
        session.commit()
        return True
    except Exception as e:
        if session:
            session.rollback()
        # print(f"Error updating fork status for {fork_uuid_to_update}: {e}") # Debug
        # Depending on desired error handling, you might want to log 'e' or raise it
        return False # Indicate update failure
    finally:
        if close_session_locally and session is not None:
            session.close()
