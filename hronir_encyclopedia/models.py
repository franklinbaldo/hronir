import datetime
import pathlib  # Changed from "from pathlib import Path"
import uuid  # Ensure this import is present
from typing import Any  # For Hronir.metadata and ValidationIssue.details

from pydantic import UUID5, BaseModel, Field, field_validator

# --- Type Aliases ---
MandateID = uuid.UUID  # Represents the ID associated with a QUALIFIED path's mandate to judge.


# --- Pydantic Models for Data Validation and Business Logic ---
class Vote(BaseModel):
    vote_id: uuid.UUID = Field(default_factory=uuid.uuid4) # vote_id is the PK
    duel_id: uuid.UUID # Foreign key to the specific duel instance
    voting_token_path_uuid: UUID5 # The path_uuid that cast this vote
    chosen_winner_side: str # 'A' or 'B', referring to path_A_uuid or path_B_uuid in the duel
    position: int # Denormalized from duel for easier querying, or could be joined
    recorded_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    @field_validator("chosen_winner_side")
    def side_must_be_A_or_B(cls, v):
        if v not in ("A", "B"):
            raise ValueError("chosen_winner_side must be 'A' or 'B'")
        return v

class Path(BaseModel):
    path_uuid: UUID5
    position: int
    prev_uuid: UUID5 | None = None # Hrönir UUID of the predecessor content node
    uuid: UUID5 # Hrönir UUID of the current content node this path leads to
    # status field removed
    # mandate_id field removed


# --- Enhanced Transaction Models ---
class SessionVerdictRecord(BaseModel):
    position: int
    winner_hrönir_uuid: UUID5
    loser_hrönir_uuid: UUID5
    predecessor_hrönir_uuid: UUID5 | None


class TransactionContent(BaseModel):
    session_id: uuid.UUID
    initiating_path_uuid: UUID5
    verdicts_processed: list[SessionVerdictRecord] = Field(default_factory=list)
    promotions_granted: list[UUID5] = Field(default_factory=list)


class Transaction(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    prev_uuid: UUID5 | None = None
    content: TransactionContent


class SuperBlock(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    parent_a_uuid: UUID5 | None = None
    parent_b_uuid: UUID5 | None = None
    merged_tx_uuids: list[UUID5] = []

    @field_validator("parent_b_uuid")
    def check_parents(cls, v, values):
        data = values.data
        if data.get("parent_a_uuid") and not v:
            raise ValueError("A merge block must have two parents (parent_b is missing)")
        return v


# --- Session Models ---
class SessionDuel(BaseModel):
    """
    Represents a single duel within a session dossier.
    A duel consists of two competing paths at a specific position.
    path_A_uuid and path_B_uuid store the UUIDs of the paths in the duel.
    """

    path_A_uuid: UUID5
    path_B_uuid: UUID5
    entropy: float = Field(default=0.0, description="Entropy of the duel, if calculated.")

    class Config:
        extra = "forbid"


class SessionDossier(BaseModel):
    """
    Represents the dossier for a judgment session.
    It contains all the duels that need to be judged for prior positions.
    Duels are keyed by position string (e.g., "0", "1", "2").
    """

    duels: dict[str, SessionDuel] = Field(default_factory=dict)

    class Config:
        extra = "forbid"


class SessionModel(BaseModel):  # Renamed from Session to SessionModel
    """
    Represents a judgment session in the Hrönir Encyclopedia.
    """

    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    initiating_path_uuid: UUID5  # The QUALIFIED path_uuid that granted the mandate for this session
    mandate_id: MandateID  # The mandate_id from the initiating_path_uuid that was used.
    position_n: int  # The position of the initiating_path_uuid

    dossier: SessionDossier = Field(default_factory=SessionDossier)
    status: str = Field(
        default="active",
        description="Current status of the session (e.g., active, committed, aborted).",
    )

    # Store verdicts as position string to winning path UUID
    committed_verdicts: dict[str, UUID5] | None = Field(
        default=None,
        description="Verdicts committed for this session, mapping position string to winning path UUID.",
    )

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    class Config:
        extra = "forbid"
        # Pydantic v2 handles datetime and UUID serialization well by default.
        # If specific string formats are needed, json_encoders can be used.
        # Example:
        # json_encoders = {
        #     datetime.datetime: lambda dt: dt.isoformat(),
        #     uuid.UUID: lambda u: str(u),
        # }
        validate_assignment = (
            True  # Allows updated_at to be auto-updated on field change via validators if needed
        )

    # Automatically update `updated_at` when relevant fields change.
    # This is a common pattern, but for simple "touch on save" it's often handled in the manager.
    # For now, a manual `touch()` method in the manager or before saving is simpler.
    # Pydantic v2's model_on_setattr or similar could also be explored if auto-update is critical.

    def model_post_init(self, __context: Any) -> None:
        # Ensure updated_at is also set to created_at initially if factories behave unexpectedly or for older Pydantic versions
        # For Pydantic v2, default_factory should ensure they are set.
        # This is more of a safeguard or for specific initialization logic.
        if (
            self.created_at and self.updated_at and self.updated_at < self.created_at
        ):  # Should not happen with factories
            self.updated_at = self.created_at
        # Ensure UTC for datetime fields if not already handled by factory
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=datetime.timezone.utc)
        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=datetime.timezone.utc)


# --- Hrönir Content Model ---
class Hronir(BaseModel):
    uuid: UUID5
    text_content: str
    author_agent_id: str | None = None
    metadata: dict[str, Any] | None = None
    creation_timestamp: datetime.datetime


# --- Canonical Path Models ---
class CanonicalEntry(BaseModel):
    path_uuid: UUID5
    hrönir_uuid: UUID5


class CanonicalPath(BaseModel):
    title: str = "The Hrönir Encyclopedia - Canonical Path"
    path: dict[int, CanonicalEntry] = Field(default_factory=dict)
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    @field_validator("path", mode="before")
    def coerce_str_keys_to_int(cls, value):
        if isinstance(value, dict):
            new_dict = {}
            for k, v in value.items():
                if isinstance(k, str) and k.isdigit():
                    new_dict[int(k)] = v
                else:
                    new_dict[k] = v
            return new_dict
        return value


# --- Duel/Ranking Models ---
class RankingEntry(BaseModel):
    path_uuid: UUID5
    hrönir_uuid: UUID5
    elo_rating: int
    games_played: int
    wins: int
    losses: int


class ProposedDuelPair(BaseModel):
    path_A_uuid: UUID5
    path_B_uuid: UUID5


class ProposedDuel(BaseModel):
    position: int
    strategy: str
    entropy: float
    duel_pair: ProposedDuelPair


# --- Mandate/Qualification Models ---
class QualificationRules(BaseModel):
    elo_threshold: int = Field(
        default=1550, description="ELO rating at or above which a path qualifies."
    )


# --- Configuration Models ---
class StoragePaths(BaseModel):
    library_dir: pathlib.Path = Field(default=pathlib.Path("the_library"))
    narrative_paths_dir: pathlib.Path = Field(default=pathlib.Path("narrative_paths"))
    ratings_dir: pathlib.Path = Field(default=pathlib.Path("ratings"))
    data_dir: pathlib.Path = Field(default=pathlib.Path("data"))

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
    storage_paths: StoragePaths = Field(default_factory=StoragePaths)
    qualification_rules: QualificationRules = Field(default_factory=QualificationRules)
    elo_k_factor: int = Field(default=32, description="K-factor for ELO calculations.")
    entropy_saturation_threshold: float = Field(
        default=0.2, description="Entropy below which a league is considered saturated."
    )
    max_cascade_positions: int = Field(
        default=100, description="Default max positions for temporal cascade."
    )


# --- Validation Models ---
class ValidationIssue(BaseModel):
    severity: str
    message: str
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    details: dict[str, Any] | None = None


class DataIntegrityReport(BaseModel):
    report_generated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    issues: list[ValidationIssue] = Field(default_factory=list)

    paths_checked: int = 0
    hrönirs_checked: int = 0
    votes_checked: int = 0
    transactions_checked: int = 0

    error_count: int = 0
    warning_count: int = 0

    @property
    def total_issues(self) -> int:
        return len(self.issues)
