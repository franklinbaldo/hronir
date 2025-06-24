import datetime
import uuid # Ensure this import is present
import pathlib # Changed from "from pathlib import Path"
from typing import Any # For Hronir.metadata and ValidationIssue.details

from pydantic import UUID5, BaseModel, Field, field_validator

# --- Type Aliases ---
MandateID = uuid.UUID # Represents the ID associated with a QUALIFIED path's mandate to judge.

# --- Pydantic Models for Data Validation and Business Logic ---
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
    status: str = "PENDING"
    mandate_id: MandateID | None = None


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
    path_A_uuid: UUID5
    path_B_uuid: UUID5
    entropy: float

class SessionDossier(BaseModel):
    duels: dict[int, SessionDuel] = Field(default_factory=dict)

class Session(BaseModel):
    session_id: uuid.UUID
    initiating_path_uuid: UUID5
    mandate_id: MandateID
    position_n: int
    dossier: SessionDossier
    status: str
    committed_verdicts: dict[int, UUID5] | None = None

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

    @field_validator('path', mode='before')
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
    elo_threshold: int = Field(default=1550, description="ELO rating at or above which a path qualifies.")

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
    entropy_saturation_threshold: float = Field(default=0.2, description="Entropy below which a league is considered saturated.")
    max_cascade_positions: int = Field(default=100, description="Default max positions for temporal cascade.")

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
