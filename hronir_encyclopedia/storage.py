import os
import uuid
from pathlib import Path

from .duckdb_storage import DuckDBDataManager
from .models import Path as PathModel
from .models import Transaction, Vote

# Removed PandasDataManager import
from .sharding import SnapshotManifest  # Added

UUID_NAMESPACE = uuid.NAMESPACE_URL


# --- Global Data Manager ---
class DataManager:
    """
    DataManager that provides a high-level interface to the data storage backend.
    Currently, it exclusively uses DuckDBDataManager.
    """

    def __init__(
        self,
        db_path: str | None = None,
        path_csv_dir: str | Path = "narrative_paths",
        ratings_csv_dir: str | Path = "ratings",
        transactions_json_dir: str | Path = "data/transactions",
        library_dir: str | Path = "the_library", # Will be removed in a later step
    ):
        """
        Initializes the DataManager.

        Args:
            db_path: Path to the DuckDB database file. Defaults to env var or "data/encyclopedia.duckdb".
            path_csv_dir: Directory for legacy path CSV files (for initial load).
            ratings_csv_dir: Directory for legacy ratings CSV files (for initial load).
            transactions_json_dir: Directory for legacy transaction JSON files (for initial load).
            library_dir: Path to the hrönir library (will be deprecated).
        """
        actual_db_path = db_path or os.getenv("HRONIR_DUCKDB_PATH", "data/encyclopedia.duckdb")
        self.backend = DuckDBDataManager(
            db_path=actual_db_path,
            path_csv_dir=path_csv_dir,
            ratings_csv_dir=ratings_csv_dir,
            transactions_json_dir=transactions_json_dir,
        )

        # This library_path logic will be removed in step 1.5
        default_library_path = Path(library_dir)
        library_path_str = os.getenv("HRONIR_LIBRARY_DIR")
        self.library_path = Path(library_path_str) if library_path_str else default_library_path
        if not Path(actual_db_path).parent.exists(): # Ensure parent of DB exists
             Path(actual_db_path).parent.mkdir(parents=True, exist_ok=True)
        # self.library_path.mkdir(parents=True, exist_ok=True) # This specific line will be removed later

        self._initialized = False # Tracks if load_all_data has been called

    @property
    def fork_csv_dir(self):
        return getattr(self.backend, "path_csv_dir", Path(""))

    @fork_csv_dir.setter
    def fork_csv_dir(self, value):
        if hasattr(self.backend, "path_csv_dir"):
            self.backend.path_csv_dir = value

    @property
    def ratings_csv_dir(self):
        return getattr(self.backend, "ratings_csv_dir", Path(""))

    @ratings_csv_dir.setter
    def ratings_csv_dir(self, value):
        if hasattr(self.backend, "ratings_csv_dir"):
            self.backend.ratings_csv_dir = Path(value)

    @property
    def transactions_json_dir(self):
        return getattr(self.backend, "transactions_json_dir", Path(""))

    @transactions_json_dir.setter
    def transactions_json_dir(self, value):
        if hasattr(self.backend, "transactions_json_dir"):
            self.backend.transactions_json_dir = value

    def initialize_and_load(self, clear_existing_data=False):
        """Initialize the data manager and load data from files."""
        if clear_existing_data:
            self.clear_in_memory_data()

        self.backend.load_all_data()
        self._initialized = True

    def clear_in_memory_data(self):
        """Clear all in-memory data."""
        if hasattr(self.backend, "clear_in_memory_data"):
            self.backend.clear_in_memory_data()

    def save_all_data(self):
        """Saves all data to the backend (e.g., commits DB transaction)."""
        self.backend.save_all_data()

    # --- Path operations ---
    def get_all_paths(self) -> list[PathModel]:
        """Get all paths."""
        self.backend.initialize_if_needed()
        return self.backend.get_all_paths()

    def get_paths_by_position(self, position: int) -> list[PathModel]:
        """Get paths at a specific position."""
        self.backend.initialize_if_needed()
        return self.backend.get_paths_by_position(position)

    def add_path(self, path: PathModel):
        """Add a new path."""
        self.backend.initialize_if_needed()
        self.backend.add_path(path)

    def update_path_status(
        self,
        path_uuid: str,
        status: str,
        mandate_id: str | None = None,
        set_mandate_explicitly: bool = False,
    ):
        """Update path status and optionally mandate_id.

        Args:
            path_uuid: The UUID of the path to update.
            status: The new status for the path.
            mandate_id: The new mandate_id for the path. Only updated if `set_mandate_explicitly` is True.
            set_mandate_explicitly: If True, the mandate_id field will be updated to the value of `mandate_id`
                                   (which can be None to clear it). If False, `mandate_id` field is not changed.
        """
        self.backend.initialize_if_needed()
        self.backend.update_path_status(
            path_uuid, status, mandate_id=mandate_id, set_mandate_explicitly=set_mandate_explicitly
        )

    def get_path_by_uuid(self, path_uuid: str) -> PathModel | None:
        """Get a specific path by UUID."""
        self.backend.initialize_if_needed()
        paths = self.backend.get_all_paths()
        for path in paths:
            if str(path.path_uuid) == path_uuid:
                return path
        return None

    # --- Vote operations ---
    def get_all_votes(self) -> list[Vote]:
        """Get all votes."""
        self.backend.initialize_if_needed()
        return self.backend.get_all_votes()

    def add_vote(self, vote: Vote):
        """Add a new vote."""
        self.backend.initialize_if_needed()
        self.backend.add_vote(vote)

    def get_votes_by_position(self, position: int) -> list[Vote]:
        """Get votes for a specific position."""
        self.backend.initialize_if_needed()
        return self.backend.get_votes_by_position(position)

    # --- Transaction operations ---
    def get_all_transactions(self) -> list[Transaction]:
        """Get all transactions."""
        self.backend.initialize_if_needed()
        return self.backend.get_all_transactions()

    def add_transaction(self, transaction: Transaction):
        """Add a new transaction."""
        self.backend.initialize_if_needed()
        self.backend.add_transaction(transaction)

    def get_transaction(self, tx_uuid: str) -> Transaction | None:
        """Get a specific transaction."""
        self.backend.initialize_if_needed()
        return self.backend.get_transaction(tx_uuid)

    # --- Snapshot operations ---
    def create_snapshot(
        self, output_dir: Path, network_uuid: str, git_commit: str | None = None
    ) -> SnapshotManifest | None:
        """
        Creates a snapshot of the current database, potentially sharded.
        Delegates to the backend if the method exists.
        Returns SnapshotManifest if successful, None otherwise.
        """
        if hasattr(self.backend, "create_snapshot"):
            self.backend.initialize_if_needed()  # Ensure backend is ready
            return self.backend.create_snapshot(
                output_dir=output_dir, network_uuid=network_uuid, git_commit=git_commit
            )
        else:
            # Fallback or error for backends that don't support snapshotting (e.g., PandasDataManager)
            print(
                f"Warning: Backend {type(self.backend).__name__} does not support create_snapshot method."
            )
            return None

    # --- Hrönir operations (now interacting with DuckDB) ---
    def store_hrönir(self, file_path: Path) -> str:
        """Store a hrönir's content from a file into DuckDB and return its UUID."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        content_uuid = str(uuid.uuid5(UUID_NAMESPACE, content))

        # Delegate to backend to store hrönir content
        if hasattr(self.backend, "add_hronir"):
            # metadata and created_at can be extended here if needed
            self.backend.add_hronir(hronir_uuid=content_uuid, content=content)
        else:
            raise NotImplementedError("Backend does not support add_hronir method.")

        return content_uuid

    def get_hrönir_path(self, content_uuid: str) -> Path | None:
        """Returns None as hrönirs are stored in DB, not as files. Path is no longer relevant."""
        # This method might need to be deprecated or re-evaluated based on usage.
        # For now, it signals that paths are not how hrönirs are accessed.
        print(
            f"Warning: get_hrönir_path for {content_uuid} called. Hrönirs are stored in DB, file paths are not directly applicable."
        )
        return None

    def hrönir_exists(self, content_uuid: str) -> bool:
        """Check if a hrönir exists in DuckDB."""
        if not content_uuid or not isinstance(content_uuid, str):
            return False
        if hasattr(self.backend, "get_hronir_content"):
            return self.backend.get_hronir_content(content_uuid) is not None
        raise NotImplementedError("Backend does not support get_hronir_content method.")

    def get_hrönir_content(self, content_uuid: str) -> str | None:
        """Get the content of a hrönir from DuckDB."""
        if hasattr(self.backend, "get_hronir_content"):
            return self.backend.get_hronir_content(content_uuid)
        raise NotImplementedError("Backend does not support get_hronir_content method.")

    # --- Utility methods ---
    def validate_data_integrity(self) -> list[str]:
        """Validate data integrity and return list of issues."""
        issues = []
        self.backend.initialize_if_needed()  # Ensure data is loaded via backend

        # Check that all referenced hrönirs exist
        paths = self.get_all_paths()
        for path in paths:
            # Check existence of the current hrönir (uuid)
            if not self.hrönir_exists(str(path.uuid)):
                issues.append(
                    f"Path {path.path_uuid} (Pos: {path.position}, Prev: {path.prev_uuid}, Curr: {path.uuid}) "
                    f"references non-existent current hrönir {path.uuid} in the database."
                )

            # Check existence of the predecessor hrönir (prev_uuid), if applicable
            if path.prev_uuid and not self.hrönir_exists(str(path.prev_uuid)):
                issues.append(
                    f"Path {path.path_uuid} (Position: {path.position}, Predecessor: {path.prev_uuid}, Current Hrönir: {path.uuid}) "
                    f"references a non-existent predecessor hrönir '{path.prev_uuid}' in the database. "
                    f"This breaks the narrative chain for this path. "
                    f"Please ensure the hrönir with UUID '{path.prev_uuid}' exists in the database or verify the predecessor UUID."
                )

            # Validate deterministic path_uuid
            # Ensure prev_uuid is handled as empty string if None for computation, matching compute_narrative_path_uuid
            prev_uuid_for_computation = str(path.prev_uuid) if path.prev_uuid else ""

            # Ensure path.position is an int and path.uuid is a str for computation
            # path.position is already int from Pydantic model, path.uuid is UUID object
            current_hrönir_uuid_str = str(path.uuid)

            expected_path_uuid = compute_narrative_path_uuid(
                path.position, prev_uuid_for_computation, current_hrönir_uuid_str
            )
            if str(path.path_uuid) != str(expected_path_uuid):
                issues.append(
                    f"Path {path.path_uuid} (Pos: {path.position}, Prev: {path.prev_uuid}, Curr: {path.uuid}) "
                    f"has mismatched path_uuid. Expected: {expected_path_uuid}, Actual: {path.path_uuid}."
                )

        return issues

    def clean_invalid_data(self) -> list[str]:
        """Remove invalid data and return list of cleaned items."""
        cleaned = []
        issues = self.validate_data_integrity()

        if issues:
            # For now, just report issues - actual cleaning would need more sophisticated logic
            cleaned.extend(issues)

        return cleaned

    # --- Context manager support ---
    def __enter__(self):
        """Context manager entry."""
        if not self._initialized:
            self.initialize_and_load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save data."""
        self.save_all_data()

# Global data_manager instance removed.
# Utility functions (store_chapter, get_canonical_path_info, store_chapter_text, compute_narrative_path_uuid)
# have been moved to hronir_encyclopedia/utils.py
