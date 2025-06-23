import datetime

from pydantic import UUID5, BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Camada de Persistência (SQLAlchemy) ---
Base = declarative_base()
# By default we rely on an in-memory SQLite database so that no
# persistent state is written to the repository.  Consumers are free to
# create their own Engine if they want to work with a file on disk.
DATABASE_URL = "sqlite:///:memory:"


class ForkDB(Base):
    __tablename__ = "forks"

    fork_uuid = Column(String, primary_key=True)
    position = Column(Integer, index=True)
    prev_uuid = Column(String, nullable=True)
    uuid = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    mandate_id = Column(String, nullable=True)


class TransactionDB(Base):
    __tablename__ = "transactions"

    uuid = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    prev_uuid = Column(String, nullable=True)
    content = Column(JSON, nullable=False)


class VoteDB(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position = Column(Integer, index=True)
    voter = Column(String)
    winner = Column(String)
    loser = Column(String)


class Vote(BaseModel):
    id: int | None = None
    position: int
    voter: str
    winner: str
    loser: str

    class Config:
        from_attributes = True


class SuperBlockDB(Base):
    __tablename__ = "super_blocks"

    uuid = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    parent_a_uuid = Column(String, nullable=True)
    parent_b_uuid = Column(String, nullable=True)
    merged_tx_uuids = Column(JSON, nullable=False)


# --- Camada de Validação e API (Pydantic) ---
class Fork(BaseModel):
    fork_uuid: UUID5
    position: int
    prev_uuid: UUID5 | None = None
    uuid: UUID5
    status: str = "PENDING"
    mandate_id: str | None = None

    class Config:
        from_attributes = True


class Transaction(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    prev_uuid: UUID5 | None = None
    content: dict

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_db_and_tables(target_engine=engine) -> None:
    """Create tables for the provided engine."""
    Base.metadata.create_all(bind=target_engine)
