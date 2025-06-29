import json
from pathlib import Path

import duckdb
from pydantic import ValidationError

from .models import Path as PathModel
from .models import Transaction, Vote


class DuckDBDataManager:
    """DuckDB-based data manager for ACID persistence."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        db_path: str = "data/encyclopedia.duckdb",
        path_csv_dir: str | Path = "narrative_paths",
        ratings_csv_dir: str | Path = "ratings",
        transactions_json_dir: str | Path = "data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.db_path = Path(db_path)
        self.path_csv_dir = Path(path_csv_dir)
        self.ratings_csv_dir = Path(ratings_csv_dir)
        self.transactions_json_dir = Path(transactions_json_dir)

        self.conn = duckdb.connect(str(self.db_path))
        self._create_tables()
        self._initialized = False

    def _create_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paths(
                path_uuid TEXT PRIMARY KEY,
                position INTEGER,
                prev_uuid TEXT,
                uuid TEXT,
                status TEXT,
                mandate_id TEXT
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes(
                uuid TEXT PRIMARY KEY,
                position INTEGER,
                voter TEXT,
                winner TEXT,
                loser TEXT
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions(
                uuid TEXT PRIMARY KEY,
                data TEXT
            );
            """
        )

    def load_all_data(self) -> None:
        import pandas as pd

        # Only load if tables are empty
        paths_empty = self.conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0] == 0
        if paths_empty:
            for csv_file in self.path_csv_dir.glob("*.csv"):
                if csv_file.stat().st_size == 0:
                    continue
                df = pd.read_csv(csv_file)
                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    if "prev_uuid" in row_dict and pd.isna(row_dict["prev_uuid"]):
                        row_dict["prev_uuid"] = None
                    try:
                        self.add_path(PathModel(**row_dict))
                    except ValidationError:
                        continue

        votes_empty = self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
        if votes_empty:
            votes_file = self.ratings_csv_dir / "votes.csv"
            if votes_file.exists() and votes_file.stat().st_size > 0:
                df = pd.read_csv(votes_file)
                for _, row in df.iterrows():
                    try:
                        self.add_vote(Vote(**row.to_dict()))
                    except ValidationError:
                        continue

        tx_empty = self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
        if tx_empty and self.transactions_json_dir.exists():
            for jf in self.transactions_json_dir.glob("*.json"):
                try:
                    data = json.loads(jf.read_text())
                    self.add_transaction(Transaction(**data))
                except (json.JSONDecodeError, ValidationError):
                    continue

        self._initialized = True

    def save_all_data(self) -> None:
        self.conn.commit()

        self.path_csv_dir.mkdir(exist_ok=True)
        df_paths = self.conn.execute("SELECT * FROM paths").df()
        if not df_paths.empty:
            for position, group in df_paths.groupby("position"):
                file_path = self.path_csv_dir / f"narrative_paths_position_{position}.csv"
                group.to_csv(file_path, index=False)

        self.ratings_csv_dir.mkdir(exist_ok=True)
        df_votes = self.conn.execute("SELECT * FROM votes").df()
        if not df_votes.empty:
            (self.ratings_csv_dir / "votes.csv").write_text("")  # clear file
            df_votes.to_csv(self.ratings_csv_dir / "votes.csv", index=False)

        self.transactions_json_dir.mkdir(parents=True, exist_ok=True)
        tx_rows = self.conn.execute("SELECT * FROM transactions").fetchall()
        for tx_uuid, data in tx_rows:
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            (self.transactions_json_dir / f"{tx_uuid}.json").write_text(json.dumps(obj, indent=2))

    # --- Path operations ---
    def get_all_paths(self) -> list[PathModel]:
        rows = self.conn.execute("SELECT * FROM paths").fetchall()
        paths: list[PathModel] = []
        for row in rows:
            try:
                data = {
                    "path_uuid": row[0],
                    "position": row[1],
                    "prev_uuid": row[2] if row[2] else None,
                    "uuid": row[3],
                    "status": row[4],
                    "mandate_id": row[5] if row[5] else None,
                }
                paths.append(PathModel(**data))
            except ValidationError:
                continue
        return paths

    def get_paths_by_position(self, position: int) -> list[PathModel]:
        rows = self.conn.execute(
            "SELECT * FROM paths WHERE position=?",
            (position,),
        ).fetchall()
        paths: list[PathModel] = []
        for row in rows:
            try:
                data = {
                    "path_uuid": row[0],
                    "position": row[1],
                    "prev_uuid": row[2] if row[2] else None,
                    "uuid": row[3],
                    "status": row[4],
                    "mandate_id": row[5] if row[5] else None,
                }
                paths.append(PathModel(**data))
            except ValidationError:
                continue
        return paths

    def add_path(self, path: PathModel) -> None:
        data = path.model_dump()
        self.conn.execute(
            """
            INSERT INTO paths(path_uuid, position, prev_uuid, uuid, status, mandate_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path_uuid) DO NOTHING
            """,
            (
                str(data["path_uuid"]),
                data["position"],
                str(data["prev_uuid"] or ""),
                str(data["uuid"]),
                data.get("status", "PENDING"),
                str(data["mandate_id"] or ""),
            ),
        )

    def update_path_status(
        self,
        path_uuid: str,
        status: str,
        mandate_id: str | None = None,
        set_mandate_explicitly: bool = False,
    ) -> None:
        if set_mandate_explicitly:
            self.conn.execute(
                "UPDATE paths SET status=?, mandate_id=? WHERE path_uuid=?",
                (status, mandate_id, path_uuid),
            )
        else:
            self.conn.execute(
                "UPDATE paths SET status=? WHERE path_uuid=?",
                (status, path_uuid),
            )

    def get_path_by_uuid(self, path_uuid: str) -> PathModel | None:
        row = self.conn.execute(
            "SELECT * FROM paths WHERE path_uuid=?",
            (path_uuid,),
        ).fetchone()
        if not row:
            return None
        data = {
            "path_uuid": row[0],
            "position": row[1],
            "prev_uuid": row[2] if row[2] else None,
            "uuid": row[3],
            "status": row[4],
            "mandate_id": row[5] if row[5] else None,
        }
        try:
            return PathModel(**data)
        except ValidationError:
            return None

    # --- Vote operations ---
    def get_all_votes(self) -> list[Vote]:
        rows = self.conn.execute("SELECT * FROM votes").fetchall()
        votes: list[Vote] = []
        for row in rows:
            try:
                votes.append(
                    Vote(
                        uuid=row[0],
                        position=row[1],
                        voter=row[2],
                        winner=row[3],
                        loser=row[4],
                    )
                )
            except ValidationError:
                continue
        return votes

    def add_vote(self, vote: Vote) -> None:
        data = vote.model_dump()
        self.conn.execute(
            """
            INSERT INTO votes(uuid, position, voter, winner, loser)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(uuid) DO NOTHING
            """,
            (
                data["uuid"],
                data["position"],
                data["voter"],
                data["winner"],
                data["loser"],
            ),
        )

    def get_votes_by_position(self, position: int) -> list[Vote]:
        rows = self.conn.execute(
            "SELECT * FROM votes WHERE position=?",
            (position,),
        ).fetchall()
        votes: list[Vote] = []
        for row in rows:
            try:
                votes.append(
                    Vote(
                        uuid=row[0],
                        position=row[1],
                        voter=row[2],
                        winner=row[3],
                        loser=row[4],
                    )
                )
            except ValidationError:
                continue
        return votes

    # --- Transaction operations ---
    def get_all_transactions(self) -> list[Transaction]:
        rows = self.conn.execute("SELECT * FROM transactions").fetchall()
        txs: list[Transaction] = []
        for row in rows:
            try:
                data = json.loads(row[1])
                txs.append(Transaction(**data))
            except (json.JSONDecodeError, ValidationError):
                continue
        return txs

    def add_transaction(self, transaction: Transaction) -> None:
        data = transaction.model_dump()
        self.conn.execute(
            """
            INSERT INTO transactions(uuid, data)
            VALUES (?, ?)
            ON CONFLICT(uuid) DO NOTHING
            """,
            (str(data["uuid"]), json.dumps(data, default=str)),
        )

    def get_transaction(self, tx_uuid: str) -> Transaction | None:
        row = self.conn.execute(
            "SELECT data FROM transactions WHERE uuid=?",
            (tx_uuid,),
        ).fetchone()
        if not row:
            return None
        try:
            return Transaction(**json.loads(row[0]))
        except (json.JSONDecodeError, ValidationError):
            return None

    # --- Utility methods ---
    def initialize_if_needed(self) -> None:
        if not self._initialized:
            self.load_all_data()

    def clear_in_memory_data(self) -> None:
        self.conn.execute("DELETE FROM paths")
        self.conn.execute("DELETE FROM votes")
        self.conn.execute("DELETE FROM transactions")
        self.conn.commit()

    def __enter__(self) -> "DuckDBDataManager":
        self.initialize_if_needed()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.conn.commit()
        self.conn.close()
        self._initialized = False
