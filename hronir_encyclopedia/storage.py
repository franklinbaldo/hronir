import shutil
import uuid
from pathlib import Path

from .models import Fork, Transaction, Vote
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
        fork_csv_dir="the_garden",
        ratings_csv_dir="ratings",
        transactions_json_dir="data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.pandas_manager = PandasDataManager(
            fork_csv_dir=fork_csv_dir,
            ratings_csv_dir=ratings_csv_dir,
            transactions_json_dir=transactions_json_dir
        )
        self._initialized = False

    def initialize_and_load(self, clear_existing_data=False):
        """Initialize the data manager and load data from files."""
        if clear_existing_data:
            self.clear_in_memory_data()

        self.pandas_manager.load_all_data()
        self._initialized = True

    def clear_in_memory_data(self):
        """Clear all in-memory data."""
        self.pandas_manager._forks_df = None
        self.pandas_manager._votes_df = None
        self.pandas_manager._transactions = {}

    def save_all_data_to_csvs(self):
        """Save all data back to CSV files."""
        self.pandas_manager.save_all_data()

    # --- Fork operations ---
    def get_all_forks(self) -> list[Fork]:
        """Get all forks."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_all_forks()

    def get_forks_by_position(self, position: int) -> list[Fork]:
        """Get forks at a specific position."""
        self.pandas_manager.initialize_if_needed()
        return self.pandas_manager.get_forks_by_position(position)

    def add_fork(self, fork: Fork):
        """Add a new fork."""
        self.pandas_manager.initialize_if_needed()
        self.pandas_manager.add_fork(fork)

    def update_fork_status(self, fork_uuid: str, status: str):
        """Update fork status."""
        self.pandas_manager.initialize_if_needed()
        self.pandas_manager.update_fork_status(fork_uuid, status)

    def get_fork_by_uuid(self, fork_uuid: str) -> Fork | None:
        """Get a specific fork by UUID."""
        self.pandas_manager.initialize_if_needed()
        forks = self.pandas_manager.get_all_forks()
        for fork in forks:
            if str(fork.fork_uuid) == fork_uuid:
                return fork
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

        # Check that all referenced hrönirs exist
        forks = self.get_all_forks()
        for fork in forks:
            if not self.hrönir_exists(str(fork.uuid)):
                issues.append(f"Fork {fork.fork_uuid} references non-existent hrönir {fork.uuid}")

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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(text)
        temp_path = Path(f.name)

    try:
        data_manager = DataManager()
        return data_manager.store_hrönir(temp_path)
    finally:
        temp_path.unlink()  # Clean up temp file
