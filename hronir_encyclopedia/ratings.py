import uuid
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy.engine import Engine


def record_vote(
    position: int,
    voter: str,
    winner: str,
    loser: str,
    base: Path | str = "ratings",
    conn: Optional[Engine] = None,
) -> None:
    """Append a vote to the ratings table."""
    if conn is not None:
        table = f"position_{position:03d}"
        with conn.begin() as con:
            con.exec_driver_sql(
                f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    uuid TEXT,
                    voter TEXT,
                    winner TEXT,
                    loser TEXT
                )
                """
            )
            con.exec_driver_sql(
                f"INSERT INTO `{table}` (uuid, voter, winner, loser) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), voter, winner, loser),
            )
        return

    base = Path(base)
    base.mkdir(exist_ok=True)
    csv_path = base / f"position_{position:03d}.csv"

    row = {
        "uuid": str(uuid.uuid4()),
        "voter": voter,
        "winner": winner,
        "loser": loser,
    }
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_csv(csv_path, index=False)
