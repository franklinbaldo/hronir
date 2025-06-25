import shutil
import uuid
from pathlib import Path

from .models import Path as PathModel
from .models import Transaction, Vote
from .pandas_data_manager import PandasDataManager

UUID_NAMESPACE = uuid.NAMESPACE_URL


# --- Global Data Manager ---
class DataManager:
    """Simplified DataManager using pandas instead of SQLAlchemy."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        path_csv_dir="narrative_paths",
        ratings_csv_dir="ratings",
        transactions_json_dir="data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.pandas_manager = PandasDataManager(
            path_csv_dir=path_csv_dir,
            ratings_csv_dir=ratings_csv_dir,
            transactions_json_dir=transactions_json_dir,
        )
        self._initialized = False

    @property
    def fork_csv_dir(self):
        return self.pandas_manager.path_csv_dir

    @fork_csv_dir.setter
    def fork_csv_dir(self, value):
        self.pandas_manager.path_csv_dir = value

    @property
    def ratings_csv_dir(self):
        return self.pandas_manager.ratings_csv_dir

    @ratings_csv_dir.setter
    def ratings_csv_dir(self, value):
        self.pandas_manager.ratings_csv_dir = Path(value)  # Ensure it's a Path object

    @property
    def transactions_json_dir(self):
        return self.pandas_manager.transactions_json_dir

    @transactions_json_dir.setter
    def transactions_json_dir(self, value):
        self.pandas_manager.transactions_json_dir = value

    def initialize_and_load(self, clear_existing_data=False):
        """Initialize the data manager and load data from files."""
        if clear_existing_data:
            self.clear_in_memory_data()

        self.pandas_manager.load_all_data()
        self._initialized = True

    def clear_in_memory_data(self):
        """Clear all in-memory data."""
        self.pandas_manager._paths_df = None
        self.pandas_manager._votes_df = None
        self.pandas_manager._transactions = {}

    def save_all_data_to_csvs(self):
        """Save all data back to CSV files."""
        self.pandas_manager.save_all_data()

    # --- Path operations ---
    def get_all_paths(self) -> list[PathModel]:
        """Get all paths."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_all_paths()

    def get_paths_by_position(self, position: int) -> list[PathModel]:
        """Get paths at a specific position."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_paths_by_position(position)

    def add_path(self, path: PathModel):
        """Add a new path."""
        self.pandas_manager.initialize_if_needed()
        self.pandas_manager.add_path(path)

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
        self.pandas_manager.initialize_if_needed()
        self.pandas_manager.update_path_status(
            path_uuid, status, mandate_id=mandate_id, set_mandate_explicitly=set_mandate_explicitly
        )

    def get_path_by_uuid(self, path_uuid: str) -> PathModel | None:
        """Get a specific path by UUID."""
        self.pandas_manager.initialize_if_needed()
        paths = self.pandas_manager.get_all_paths()
        for path in paths:
            if str(path.path_uuid) == path_uuid:
                return path
        return None

    # --- Vote operations ---
    def get_all_votes(self) -> list[Vote]:
        """Get all votes."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_all_votes()

    def add_vote(self, vote: Vote):
        """Add a new vote."""
        self.pandas_manager.initialize_if_needed()
        self.pandas_manager.add_vote(vote)

    def get_votes_by_position(self, position: int) -> list[Vote]:
        """Get votes for a specific position."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_votes_by_position(position)

    # --- Transaction operations ---
    def get_all_transactions(self) -> list[Transaction]:
        """Get all transactions."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_all_transactions()

    def add_transaction(self, transaction: Transaction):
        """Add a new transaction."""
        self.pandas_manager.initialize_if_needed()
        self.pandas_manager.add_transaction(transaction)

    def get_transaction(self, tx_uuid: str) -> Transaction | None:
        """Get a specific transaction."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_transaction(tx_uuid)

    # --- File operations ---
    def store_hrönir(self, file_path: Path) -> str:
        """Store a hrönir file and return its UUID."""
        # Read the file content
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Generate UUID from content
        content_uuid = str(uuid.uuid5(UUID_NAMESPACE, content))

        # Create target directory and file
        target_dir = Path("the_library")
        target_dir.mkdir(exist_ok=True)
        target_file = target_dir / f"{content_uuid}.md"

        # Copy the file
        shutil.copy2(file_path, target_file)

        return content_uuid

    def get_hrönir_path(self, content_uuid: str) -> Path:
        """Get the path to a stored hrönir."""
        return Path("the_library") / f"{content_uuid}.md"

    def hrönir_exists(self, content_uuid: str) -> bool:
        """Check if a hrönir exists."""
        # Ensure content_uuid is a string and not None or empty before creating Path object
        if not content_uuid or not isinstance(content_uuid, str):
            return False  # Or raise an error, depending on desired strictness
        return self.get_hrönir_path(content_uuid).exists()

    def get_hrönir_content(self, content_uuid: str) -> str | None:
        """Get the content of a hrönir."""
        hrönir_path = self.get_hrönir_path(content_uuid)
        if hrönir_path.exists():
            with open(hrönir_path, encoding="utf-8") as f:
                return f.read()
        return None

    # --- Utility methods ---
    def validate_data_integrity(self) -> list[str]:
        """Validate data integrity and return list of issues."""
        issues = []
        self.pandas_manager.initialize_if_needed()  # Ensure data is loaded via pandas_manager

        # Check that all referenced hrönirs exist
        paths = self.get_all_paths()  # This uses self.pandas_manager to get PathModels
        for path in paths:
            # Check existence of the current hrönir (uuid)
            if not self.hrönir_exists(str(path.uuid)):  # self.hrönir_exists uses file system
                issues.append(
                    f"Path {path.path_uuid} (Pos: {path.position}, Prev: {path.prev_uuid}, Curr: {path.uuid}) "
                    f"references non-existent current hrönir {path.uuid}."
                )

            # Check existence of the predecessor hrönir (prev_uuid), if applicable
            if path.prev_uuid and not self.hrönir_exists(str(path.prev_uuid)):
                issues.append(
                    f"Path {path.path_uuid} (Position: {path.position}, Predecessor: {path.prev_uuid}, Current Hrönir: {path.uuid}) "
                    f"references a non-existent predecessor hrönir '{path.prev_uuid}'. "
                    f"This breaks the narrative chain for this path. "
                    f"Please ensure the hrönir file '{path.prev_uuid}.md' exists in 'the_library/' or verify the predecessor UUID."
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
        self.save_all_data_to_csvs()


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
    Path UUIDs are UUIDv5 based on the concatenated string of:
    position, predecessor hrönir UUID, and current hrönir UUID.
    """
    # Ensure consistent string representation for None or empty prev_uuid, especially for position 0
    # The CLI 'path' command uses "" for source at position 0.
    # The PathModel uses None for prev_uuid at position 0.
    # Let's standardize on using an empty string for hashing if prev_hronir_uuid is None or empty.
    prev_uuid_str = prev_hronir_uuid if prev_hronir_uuid else ""

    path_key = f"{position}:{prev_uuid_str}:{current_hronir_uuid}"
    return uuid.uuid5(UUID_NAMESPACE, path_key)


data_manager = DataManager()
