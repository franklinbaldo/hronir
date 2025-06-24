import datetime

from pydantic import UUID5, BaseModel, Field, field_validator


# --- Pydantic Models for Data Validation and Business Logic ---
class Vote(BaseModel):
    uuid: str
    position: int
    voter: str
    winner: str
    loser: str


class Fork(BaseModel):
    fork_uuid: UUID5
    position: int
    prev_uuid: UUID5 | None = None
    uuid: UUID5
    status: str = "PENDING"
    mandate_id: str | None = None


class Transaction(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    prev_uuid: UUID5 | None = None
    content: dict


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
        if not data.get("parent_a_uuid") and v:
            raise ValueError("A merge block must have two parents (parent_a is missing)")
        return v
