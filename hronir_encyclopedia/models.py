import datetime
import pathlib
import uuid
from typing import Any

from pydantic import UUID5, BaseModel, Field, field_validator

# --- Type Aliases ---
# MandateID is removed as it's no longer on PathModel

# --- Pydantic Models for Data Validation and Business Logic ---
class Vote(BaseModel): # New structure
    vote_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    duel_id: uuid.UUID
    voting_token_path_uuid: UUID5
    chosen_winner_side: str
    position: int
    recorded_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    @field_validator("chosen_winner_side")
    def side_must_be_A_or_B(cls, v):
        if v not in ("A", "B"):
            raise ValueError("chosen_winner_side must be 'A' or 'B'")
        return v

class Path(BaseModel): # Schema from Step 1
    path_uuid: UUID5
    position: int
    prev_uuid: UUID5 | None = None
    uuid: UUID5

# --- Enhanced Transaction Models ---
class SessionVerdictRecord(BaseModel): # This might be obsolete or need rework if tied to old session_verdicts
    position: int
    winner_hrönir_uuid: UUID5 # These are hrönir UUIDs
    loser_hrönir_uuid: UUID5
    predecessor_hrönir_uuid: UUID5 | None

class TransactionContent(BaseModel):
    session_id: uuid.UUID # Represents the unique ID of the voting transaction event (e.g. pseudo_session_id)
    initiating_path_uuid: UUID5 # The path_uuid that cast the votes (the voting_token_path_uuid)
    # verdicts_processed might now store a list of new Vote model dumps, or just a summary
    verdicts_processed: list[SessionVerdictRecord] = Field(default_factory=list) # Keep for now, may need adjustment
    promotions_granted: list[UUID5] = Field(default_factory=list) # This is obsolete

class Transaction(BaseModel):
    uuid: UUID5 # Transaction's own UUID
    timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)) # Ensure utcnow
    prev_uuid: UUID5 | None = None # For blockchain-like ledger if implemented
    content: TransactionContent

# ... (Keep other models like SuperBlock, SessionDuel, SessionDossier, SessionModel for now, though Session* are slated for removal) ...
# ... For brevity, I'll assume they are present as before but SessionModel and its users are next to be removed ...

class SessionDuel(BaseModel):
    path_A_uuid: UUID5
    path_B_uuid: UUID5
    entropy: float = Field(default=0.0)
    class Config: extra = "forbid"

class SessionDossier(BaseModel):
    duels: dict[str, SessionDuel] = Field(default_factory=dict)
    class Config: extra = "forbid"

class SessionModel(BaseModel): # This model is for the old session system
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    initiating_path_uuid: UUID5
    mandate_id: uuid.UUID # Old system mandate_id
    position_n: int
    dossier: SessionDossier = Field(default_factory=SessionDossier)
    status: str = Field(default="active")
    committed_verdicts: dict[str, UUID5] | None = Field(default=None)
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    class Config: extra = "forbid"; validate_assignment = True
    def model_post_init(self, __context: Any) -> None:
        if self.created_at.tzinfo is None: self.created_at = self.created_at.replace(tzinfo=datetime.timezone.utc)
        if self.updated_at.tzinfo is None: self.updated_at = self.updated_at.replace(tzinfo=datetime.timezone.utc)

class Hronir(BaseModel):
    uuid: UUID5; text_content: str; author_agent_id:str|None=None; metadata:dict[str,Any]|None=None; creation_timestamp:datetime.datetime
class CanonicalEntry(BaseModel): path_uuid:UUID5; hrönir_uuid:UUID5
class CanonicalPath(BaseModel):
    title:str="The Hrönir Encyclopedia - Canonical Path"; path:dict[int,CanonicalEntry]=Field(default_factory=dict); last_updated:datetime.datetime=Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    @field_validator("path",mode="before")
    def coerce_keys(cls,v): return {int(k) if isinstance(k,str)and k.isdigit() else k:val for k,val in v.items()} if isinstance(v,dict) else v
class RankingEntry(BaseModel): path_uuid:UUID5; hrönir_uuid:UUID5; elo_rating:int; games_played:int; wins:int; losses:int
class ProposedDuelPair(BaseModel): path_A_uuid:UUID5; path_B_uuid:UUID5
class ProposedDuel(BaseModel): position:int; strategy:str; entropy:float; duel_pair:ProposedDuelPair
class QualificationRules(BaseModel): elo_threshold:int=1550
class StoragePaths(BaseModel):
    library_dir:pathlib.Path=Field(default=pathlib.Path("the_library")); narrative_paths_dir:pathlib.Path=Field(default=pathlib.Path("narrative_paths"))
    ratings_dir:pathlib.Path=Field(default=pathlib.Path("ratings")); data_dir:pathlib.Path=Field(default=pathlib.Path("data"))
    @property
    def sessions_dir(self)->pathlib.Path: return self.data_dir/"sessions"
    @property
    def transactions_dir(self)->pathlib.Path: return self.data_dir/"transactions"
    @property
    def canonical_path_file(self)->pathlib.Path: return self.data_dir/"canonical_path.json"
class SystemConfig(BaseModel): storage_paths:StoragePaths=Field(default_factory=StoragePaths); qualification_rules:QualificationRules=Field(default_factory=QualificationRules); elo_k_factor:int=32; entropy_saturation_threshold:float=0.2; max_cascade_positions:int=100
class ValidationIssue(BaseModel): severity:str; message:str; source_entity_type:str|None=None; source_entity_id:str|None=None; details:dict[str,Any]|None=None
class DataIntegrityReport(BaseModel):
    report_generated_at:datetime.datetime=Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)); issues:list[ValidationIssue]=Field(default_factory=list)
    paths_checked:int=0; hrönirs_checked:int=0; votes_checked:int=0; transactions_checked:int=0
    error_count:int=0; warning_count:int=0
    @property
    def total_issues(self)->int: return len(self.issues)

# Note: SessionModel, SessionDossier, SessionDuel are part of the old system to be removed.
# TransactionContent.verdicts_processed still uses SessionVerdictRecord, which might need to change
# to reflect new Vote model or a simplified verdict summary. promotions_granted in TransactionContent is also obsolete.
# MandateID type alias is removed.
