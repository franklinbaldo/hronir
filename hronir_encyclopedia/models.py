import datetime
from typing import List, Optional, Dict

from pydantic import BaseModel, Field, UUID5, field_validator
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Camada de Persistência (SQLAlchemy) ---
Base = declarative_base()
DATABASE_URL = "sqlite:///hronir.db"


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
    prev_uuid: Optional[UUID5] = None
    uuid: UUID5
    status: str = "PENDING"
    mandate_id: Optional[str] = None

    class Config:
        from_attributes = True


class Transaction(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    prev_uuid: Optional[UUID5] = None
    content: Dict

    class Config:
        from_attributes = True


class SuperBlock(BaseModel):
    uuid: UUID5
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    parent_a_uuid: Optional[UUID5] = None
    parent_b_uuid: Optional[UUID5] = None
    merged_tx_uuids: List[UUID5] = []

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


def create_db_and_tables() -> None:
    """Inicializa o banco de dados criando tabelas se necessário."""
    Base.metadata.create_all(bind=engine)

# Execute a criação das tabelas na importação inicial
create_db_and_tables()
