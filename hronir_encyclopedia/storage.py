import os
import uuid
from pathlib import Path

from .duckdb_storage import DuckDBDataManager
from .models import Path as PathModel
from .models import Transaction
from .sharding import SnapshotManifest

UUID_NAMESPACE = uuid.NAMESPACE_URL


# --- Global Data Manager ---
class DataManager:
    """DataManager that delegates to pandas or DuckDB backends."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        path_csv_dir="narrative_paths",
        transactions_json_dir="data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        db_path = os.getenv("HRONIR_DUCKDB_PATH", "data/encyclopedia.duckdb")
        self.backend = DuckDBDataManager(
            db_path=db_path,
            path_csv_dir=path_csv_dir,
            transactions_json_dir=transactions_json_dir,
        )

        default_library_path = Path("the_library")
        library_path_str = os.getenv("HRONIR_LIBRARY_DIR")
        self.library_path = Path(library_path_str) if library_path_str else default_library_path
        self.library_path.mkdir(parents=True, exist_ok=True)

        self._initialized = False

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
        if hasattr(self.backend, "create_snapshot"):
            self.backend.initialize_if_needed()
            return self.backend.create_snapshot(
                output_dir=output_dir, network_uuid=network_uuid, git_commit=git_commit
            )
        else:
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

        if hasattr(self.backend, "add_hronir"):
            self.backend.add_hronir(hronir_uuid=content_uuid, content=content)
        else:
            raise NotImplementedError("Backend does not support add_hronir method.")

        return content_uuid

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
        self.backend.initialize_if_needed()

        paths = self.get_all_paths()
        for path in paths:
            if not self.hrönir_exists(str(path.uuid)):
                issues.append(
                    f"Path {path.path_uuid} (Pos: {path.position}, Prev: {path.prev_uuid}, Curr: {path.uuid}) "
                    f"references non-existent current hrönir {path.uuid} in the database."
                )

            if path.prev_uuid and not self.hrönir_exists(str(path.prev_uuid)):
                issues.append(
                    f"Path {path.path_uuid} (Position: {path.position}, Predecessor: {path.prev_uuid}, Current Hrönir: {path.uuid}) "
                    f"references a non-existent predecessor hrönir '{path.prev_uuid}' in the database. "
                )

            prev_uuid_for_computation = str(path.prev_uuid) if path.prev_uuid else ""
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
            cleaned.extend(issues)
        return cleaned

    def __enter__(self):
        if not self._initialized:
            self.initialize_and_load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_all_data()


# Legacy compatibility functions for CLI
def store_chapter(chapter_file: Path, base: Path | str = "the_library") -> str:
    """Store a chapter file - compatibility wrapper."""
    data_manager = DataManager()
    return data_manager.store_hrönir(chapter_file)


def store_chapter_text(text: str, base: Path | str = "the_library") -> str:
    """Store chapter text - compatibility wrapper."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(text)
        temp_path = Path(f.name)

    try:
        data_manager = DataManager()
        return data_manager.store_hrönir(temp_path)
    finally:
        temp_path.unlink()  # Clean up temp file


def compute_narrative_path_uuid(
    position: int, prev_hronir_uuid: str, current_hronir_uuid: str
) -> uuid.UUID:
    """
    Computes a deterministic UUID for a narrative path (edge).
    """
    prev_uuid_str = prev_hronir_uuid if prev_hronir_uuid else ""
    path_key = f"{position}:{prev_uuid_str}:{current_hronir_uuid}"
    return uuid.uuid5(UUID_NAMESPACE, path_key)


data_manager = DataManager()
