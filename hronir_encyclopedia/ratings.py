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


def get_ranking(position: int, base: Path | str = "ratings") -> pd.DataFrame:
    csv_path = Path(base) / f"position_{position:03d}.csv"
    if not csv_path.exists():
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses"])  # Elo a ser implementado

    df = pd.read_csv(csv_path)
    # Ensure DataFrame is not empty to prevent errors with value_counts
    if df.empty:
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    wins = df["winner"].value_counts().reset_index()
    wins.columns = ["uuid", "wins"]

    losses = df["loser"].value_counts().reset_index()
    losses.columns = ["uuid", "losses"]

    ranking_df = pd.merge(wins, losses, on="uuid", how="outer").fillna(0)
    ranking_df["wins"] = ranking_df["wins"].astype(int)
    ranking_df["losses"] = ranking_df["losses"].astype(int)
    ranking_df["total_duels"] = ranking_df["wins"] + ranking_df["losses"]
    # Placeholder for Elo calculation if it were to be implemented
    ranking_df["elo"] = 0
    ranking_df = ranking_df.sort_values(by="wins", ascending=False)
    # Ensure all specified columns are present, even if Elo is just a placeholder
    return ranking_df[["uuid", "elo", "wins", "losses", "total_duels"]]
