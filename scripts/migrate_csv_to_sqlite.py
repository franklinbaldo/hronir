import datetime
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hronir_encyclopedia.models import Base, ForkDB, VoteDB, TransactionDB, SuperBlockDB


def migrate(db_path: str = "hronir.db") -> None:
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    ratings_dir = Path("ratings")
    for csv in ratings_dir.glob("position_*.csv"):
        if csv.stat().st_size == 0:
            continue
        pos = int(csv.stem.split("_")[1])
        df = pd.read_csv(csv)
        for _, row in df.iterrows():
            vote = VoteDB(
                position=pos,
                voter=row.get("voter"),
                winner=row.get("winner"),
                loser=row.get("loser"),
            )
            session.add(vote)

    fork_dir = Path("forking_path")
    for csv in fork_dir.glob("*.csv"):
        if csv.stat().st_size == 0:
            continue
        df = pd.read_csv(csv)
        for _, row in df.iterrows():
            fork = ForkDB(
                fork_uuid=row["fork_uuid"],
                position=int(row.get("position", 0)),
                prev_uuid=row.get("prev_uuid"),
                uuid=row.get("uuid"),
                status=row.get("status", "PENDING"),
                mandate_id=row.get("mandate_id"),
            )
            session.add(fork)

    tx_dir = Path("data/transactions")
    if tx_dir.exists():
        for json_file in tx_dir.glob("*.json"):
            data = json.loads(json_file.read_text())
            ts = datetime.datetime.fromisoformat(data["timestamp"].replace("Z", ""))
            tx = TransactionDB(
                uuid=data["transaction_uuid"],
                timestamp=ts,
                prev_uuid=data.get("previous_transaction_uuid"),
                content=data,
            )
            session.add(tx)

    session.commit()
    session.close()


if __name__ == "__main__":
    migrate()
