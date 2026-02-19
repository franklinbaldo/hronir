import datetime
import pathlib
import uuid
from enum import Enum
from typing import Any

from pydantic import UUID5, BaseModel, Field, field_validator

# --- Type Aliases ---
MandateID = uuid.UUID


# --- Enums ---
class PathStatus(str, Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    INVALID = "INVALID"
    # Legacy statuses kept for compatibility if needed, but not used in new protocol
    QUALIFIED = "QUALIFIED"
    SPENT = "SPENT"


# --- Base Models ---


class Path(BaseModel):
    path_uuid: UUID5
    position: int
    prev_uuid: UUID5 | None = None
    uuid: UUID5
    status: PathStatus = PathStatus.PENDING
    mandate_id: MandateID | None = None  # Deprecated but kept for schema compatibility


# --- Hrönir Content Model ---


class Hronir(BaseModel):
    """Represents the content of a hrönir with metadata."""

    uuid: UUID5
    text_content: str
    author_agent_id: str | None = None
    metadata: dict[str, Any] | None = None
    creation_timestamp: datetime.datetime


# --- Canonical Path Models ---


class CanonicalEntry(BaseModel):
    """An entry in the canonical path, linking a path to a hrönir."""

    path_uuid: UUID5
    hrönir_uuid: UUID5


class CanonicalPath(BaseModel):
    """The canonical state of the encyclopedia."""

    title: str = "The Hrönir Encyclopedia - Canonical Path"
    path: dict[int, CanonicalEntry] = Field(default_factory=dict)
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    @field_validator("path", mode="before")
    def coerce_str_keys_to_int(cls, value):
        if isinstance(value, dict):
            return {
                int(k) if isinstance(k, str) and k.isdigit() else k: v for k, v in value.items()
            }
        return value


# --- Transaction Models (Simplified) ---


class TransactionContent(BaseModel):
    """
    The content of a transaction.
    In the simplified protocol, this primarily records the creation of a hrönir/path.
    Legacy session verdicts are removed from new transactions.
    """

    action: str = "create_path"
    path_uuid: UUID5 | None = None
    hrönir_uuid: UUID5 | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Transaction(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    prev_uuid: UUID5 | None = None
    content: TransactionContent


# --- Configuration Models ---


class StoragePaths(BaseModel):
    """Defines the storage paths for various data components."""

    library_dir: pathlib.Path = pathlib.Path("the_library")
    narrative_paths_dir: pathlib.Path = pathlib.Path("narrative_paths")
    ratings_dir: pathlib.Path = pathlib.Path("ratings")
    data_dir: pathlib.Path = pathlib.Path("data")

    @property
    def sessions_dir(self) -> pathlib.Path:
        return self.data_dir / "sessions"

    @property
    def transactions_dir(self) -> pathlib.Path:
        return self.data_dir / "transactions"

    @property
    def canonical_path_file(self) -> pathlib.Path:
        return self.data_dir / "canonical_path.json"


class SystemConfig(BaseModel):
    """System-wide configuration."""

    storage_paths: StoragePaths = Field(default_factory=StoragePaths)
    # Qualification and Elo settings are deprecated/removed


# --- Validation Models ---


class ValidationIssue(BaseModel):
    """An issue found during data validation."""

    severity: str  # e.g., 'error', 'warning'
    message: str
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    details: dict[str, Any] | None = None


class DataIntegrityReport(BaseModel):
    """A report summarizing data integrity validation results."""

    report_generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    issues: list[ValidationIssue] = Field(default_factory=list)
    paths_checked: int = 0
    hrönirs_checked: int = 0
    votes_checked: int = 0
    transactions_checked: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def total_issues(self) -> int:
        return len(self.issues)
