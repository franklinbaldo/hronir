import json
from pathlib import Path

import duckdb
import pandas as pd


def migrate(db_path: str = "hronir.duckdb") -> None:
    conn = duckdb.connect(db_path)

    ratings_dir = Path("ratings")
    for csv_file in ratings_dir.glob("position_*.csv"):
        if csv_file.stat().st_size == 0:
            continue
        pos = int(csv_file.stem.split("_")[1])
        df = pd.read_csv(csv_file)
        df["position"] = pos
        conn.execute(
            "CREATE TABLE IF NOT EXISTS votes (position INTEGER, voter TEXT, winner TEXT, loser TEXT)"
        )
        conn.execute("INSERT INTO votes SELECT * FROM df")

    fork_dir = Path("narrative_paths")
    for csv_file in fork_dir.glob("*.csv"):
        if csv_file.stat().st_size == 0:
            continue
        df = pd.read_csv(csv_file)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS paths (path_uuid TEXT, position INTEGER, prev_uuid TEXT, uuid TEXT, status TEXT, mandate_id TEXT)"
        )
        conn.execute("INSERT INTO paths SELECT * FROM df")

    tx_dir = Path("data/transactions")
    if tx_dir.exists():
        for json_file in tx_dir.glob("*.json"):
            data = json.loads(json_file.read_text())
            conn.execute("CREATE TABLE IF NOT EXISTS transactions (uuid TEXT, content JSON)")
            conn.execute(
                "INSERT INTO transactions VALUES (?, ?)",
                (data.get("transaction_uuid"), json.dumps(data)),
            )

    conn.close()


if __name__ == "__main__":
    migrate()
