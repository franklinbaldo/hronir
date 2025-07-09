import datetime
import pathlib
import uuid
from typing import Any
from enum import Enum # Added Enum

from pydantic import UUID5, BaseModel, Field, field_validator

# --- Type Aliases ---
MandateID = uuid.UUID

# --- Enums ---
class PathStatus(str, Enum):
    PENDING = "PENDING"
    QUALIFIED = "QUALIFIED"
    SPENT = "SPENT"
    INVALID = "INVALID" # Added for completeness, though not used everywhere yet

# --- Base Models ---


class Vote(BaseModel):
    uuid: str
    position: int
    voter: str
    winner: str
    loser: str


class Path(BaseModel):
    path_uuid: UUID5
    position: int
    prev_uuid: UUID5 | None = None
    uuid: UUID5
    status: PathStatus = PathStatus.PENDING # Changed to PathStatus Enum
    mandate_id: MandateID | None = None


# --- Session Models ---


class SessionDuel(BaseModel):
    """A single duel between two competing hrönir at a specific position."""

    path_A_uuid: UUID5
    path_B_uuid: UUID5
    entropy: float = Field(0.0, description="Entropy of the duel.")


class SessionDossier(BaseModel):
    """A collection of duels for a judgment session, keyed by position."""

    duels: dict[str, SessionDuel] = Field(default_factory=dict)


class Session(BaseModel):
    """A judgment session."""

    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    initiating_path_uuid: UUID5
    mandate_id: MandateID
    position_n: int
    dossier: SessionDossier = Field(default_factory=SessionDossier)
    status: str = Field("active", description="Session status (active, committed, aborted).")
    committed_verdicts: dict[str, UUID5] | None = Field(None, description="Committed verdicts.")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


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


# --- Enhanced Transaction Models ---


class SessionVerdict(BaseModel):
    """A single verdict from a session."""

    position: int
    winner_hrönir_uuid: UUID5
    loser_hrönir_uuid: UUID5
    predecessor_hrönir_uuid: UUID5 | None


class TransactionContent(BaseModel):
    """The content of a transaction, detailing session results."""

    session_id: uuid.UUID
    initiating_path_uuid: UUID5
    verdicts_processed: list[SessionVerdict] = Field(default_factory=list)
    promotions_granted: list[UUID5] = Field(default_factory=list)


class Transaction(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    prev_uuid: UUID5 | None = None
    content: TransactionContent


# --- Duel/Ranking Models ---


class DuelResult(BaseModel):
    """The result of a duel for Elo calculation."""

    winner_uuid: UUID5
    loser_uuid: UUID5


class RankingEntry(BaseModel):
    """An entry in the ranking list."""

    path_uuid: UUID5
    hrönir_uuid: UUID5
    elo_rating: int
    games_played: int
    wins: int
    losses: int


# --- Mandate/Qualification Models ---


class Mandate(BaseModel):
    """A mandate for a path to initiate a judgment session."""

    mandate_id: MandateID
    path_uuid: UUID5
    status: str = "unused"  # unused, used, expired


class QualificationCriteria(BaseModel):
    """Criteria for a path to become qualified."""

    min_elo_rating: int = 1600
    min_games_played: int = 10


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
    qualification_rules: QualificationCriteria = Field(default_factory=QualificationCriteria)
    elo_k_factor: int = 32
    entropy_saturation_threshold: float = 0.2
    max_cascade_positions: int = 100


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
