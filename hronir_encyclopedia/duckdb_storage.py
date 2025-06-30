import json
import logging
import datetime # Added import
from pathlib import Path
import uuid # Added import for duel_id generation

import duckdb
from pydantic import ValidationError

from .models import Path as PathModel
from .models import Transaction, Vote
from .sharding import ShardingManager, SnapshotManifest  # Added


class DuckDBDataManager:
    """DuckDB-based data manager for ACID persistence."""

    # Removed singleton pattern (_instance, __new__)

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
                uuid TEXT
            );
            """
            # status TEXT, # Removed
            # mandate_id TEXT # Removed
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes(
                vote_id TEXT PRIMARY KEY,
                duel_id TEXT,
                voting_token_path_uuid TEXT,
                chosen_winner_side TEXT,
                position INTEGER,
                recorded_at TIMESTAMP
            );
            """
            # FOREIGN KEY (duel_id) REFERENCES pending_duels(duel_id) -- Can be added if desired
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions(
                uuid TEXT PRIMARY KEY,
                data TEXT
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS consumed_voting_tokens(
                voting_token_path_uuid TEXT PRIMARY KEY,
                consumed_at TIMESTAMP
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_duels(
                duel_id TEXT PRIMARY KEY,
                position INTEGER,
                path_A_uuid TEXT,
                path_B_uuid TEXT,
                created_at TIMESTAMP,
                is_active BOOLEAN
            );
            """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_pending_duels_pos_active
            ON pending_duels (position, is_active);
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

                    # Select only relevant fields for the new PathModel schema
                    path_model_data = {
                        "path_uuid": row_dict.get("path_uuid"),
                        "position": int(row_dict.get("position")) if pd.notna(row_dict.get("position")) else None,
                        "prev_uuid": row_dict.get("prev_uuid"), # Already handles None
                        "uuid": row_dict.get("uuid"),
                    }
                    # Validate required fields before creating PathModel
                    if not all([path_model_data["path_uuid"], path_model_data["position"] is not None, path_model_data["uuid"]]):
                        logging.warning(f"Skipping CSV row due to missing required fields: {row_dict}")
                        continue
                    try:
                        self.add_path(PathModel(**path_model_data))
                    except ValidationError as e:
                        logging.warning(f"Skipping CSV row due to PathModel validation error: {e}, row: {row_dict}")
                        continue

        votes_empty = self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
        if votes_empty:
            votes_file = self.ratings_csv_dir / "votes.csv"
            if votes_file.exists() and votes_file.stat().st_size > 0:
                logging.info(f"Old format votes.csv found at {votes_file}. Skipping import due to schema change. New votes must be added via new system.")
                # df = pd.read_csv(votes_file) # Old format: uuid,position,voter,winner,loser
                # for _, row in df.iterrows():
                #     try:
                #         # Cannot directly map old vote structure to new Vote model
                #         # self.add_vote(Vote(**row.to_dict()))
                #         pass
                #     except ValidationError:
                #         continue

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
                    "prev_uuid": row[2] if row[2] else None, # Assuming column 2 is prev_uuid
                    "uuid": row[3],                          # Assuming column 3 is uuid
                    # status and mandate_id removed
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
                    # status and mandate_id removed
                }
                paths.append(PathModel(**data))
            except ValidationError:
                continue
        return paths

    def add_path(self, path: PathModel) -> None:
        # PathModel no longer has status or mandate_id
        # model_dump() will only include fields defined in PathModel
        data = path.model_dump(exclude_none=False) # Use exclude_none=False to get None for prev_uuid if it's None

        # Ensure prev_uuid is correctly transformed for SQL (None becomes SQL NULL)
        prev_uuid_for_sql = str(data["prev_uuid"]) if data["prev_uuid"] is not None else None

        self.conn.execute(
            """
            INSERT INTO paths(path_uuid, position, prev_uuid, uuid)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path_uuid) DO NOTHING
            """,
            (
                str(data["path_uuid"]),
                data["position"],
                prev_uuid_for_sql, # Correctly handles None for SQL NULL
                str(data["uuid"]),
            ),
        )

    # update_path_status method removed as path statuses are removed.

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
            # status and mandate_id removed
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
            # vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at
            try:
                data = {
                    "vote_id": row[0],
                    "duel_id": row[1],
                    "voting_token_path_uuid": row[2],
                    "chosen_winner_side": row[3],
                    "position": row[4],
                    "recorded_at": row[5],
                }
                votes.append(Vote(**data))
            except ValidationError:
                continue
        return votes

    def add_vote(self, vote: Vote) -> None:
        # Vote model now has: vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at
        data = vote.model_dump(mode='json') # mode='json' ensures UUIDs are strings for DB
        self.conn.execute(
            """
            INSERT INTO votes(vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(vote_id) DO NOTHING
            """,
            (
                data["vote_id"],
                data["duel_id"],
                data["voting_token_path_uuid"],
                data["chosen_winner_side"],
                data["position"],
                data["recorded_at"],
            ),
        )

    def get_votes_by_position(self, position: int) -> list[Vote]:
        rows = self.conn.execute(
            "SELECT * FROM votes WHERE position=?",
            (position,),
        ).fetchall()
        votes: list[Vote] = []
        for row in rows:
            # vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at
            try:
                data = {
                    "vote_id": row[0],
                    "duel_id": row[1],
                    "voting_token_path_uuid": row[2],
                    "chosen_winner_side": row[3],
                    "position": row[4], # This is already known from the WHERE clause, but good to include
                    "recorded_at": row[5],
                }
                votes.append(Vote(**data))
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

    # --- Consumed Voting Token operations ---
    def add_consumed_token(self, voting_token_path_uuid: str, consumed_at: datetime.datetime) -> None:
        self.conn.execute(
            "INSERT INTO consumed_voting_tokens (voting_token_path_uuid, consumed_at) VALUES (?, ?)",
            (voting_token_path_uuid, consumed_at)
        )

    def is_token_consumed(self, voting_token_path_uuid: str) -> bool:
        res = self.conn.execute(
            "SELECT COUNT(*) FROM consumed_voting_tokens WHERE voting_token_path_uuid = ?",
            (voting_token_path_uuid,)
        ).fetchone()
        return res[0] > 0 if res else False

    # --- Pending Duel operations ---
    def add_pending_duel(self, position: int, path_A_uuid: str, path_B_uuid: str, created_at: datetime.datetime) -> str:
        duel_id = str(uuid.uuid4()) # Generate a new unique ID for the duel
        self.conn.execute(
            """
            INSERT INTO pending_duels (duel_id, position, path_A_uuid, path_B_uuid, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
            """,
            (duel_id, position, path_A_uuid, path_B_uuid, created_at)
        )
        return duel_id

    def get_active_duel_for_position(self, position: int) -> dict | None:
        res = self.conn.execute(
            "SELECT duel_id, path_A_uuid, path_B_uuid FROM pending_duels WHERE position = ? AND is_active = TRUE",
            (position,)
        ).fetchone()
        if res:
            return {"duel_id": res[0], "path_A_uuid": res[1], "path_B_uuid": res[2]}
        return None

    def deactivate_duel(self, duel_id: str) -> None:
        self.conn.execute(
            "UPDATE pending_duels SET is_active = FALSE WHERE duel_id = ?",
            (duel_id,)
        )

    def get_duel_details(self, duel_id: str) -> dict | None:
        """Fetches details of a specific duel by its ID."""
        res = self.conn.execute(
            "SELECT position, path_A_uuid, path_B_uuid, created_at, is_active FROM pending_duels WHERE duel_id = ?",
            (duel_id,)
        ).fetchone()
        if res:
            return {
                "duel_id": duel_id,
                "position": res[0],
                "path_A_uuid": res[1],
                "path_B_uuid": res[2],
                "created_at": res[3],
                "is_active": res[4]
            }
        return None

    # --- Utility methods ---
    def initialize_if_needed(self) -> None:
        if not self._initialized:
            self.load_all_data()

    def clear_in_memory_data(self) -> None:
        self.conn.execute("DELETE FROM paths")
        self.conn.execute("DELETE FROM votes")
        self.conn.execute("DELETE FROM transactions")
        self.conn.execute("DELETE FROM consumed_voting_tokens")
        self.conn.execute("DELETE FROM pending_duels") # Added this line
        self.conn.commit()

    def __enter__(self) -> "DuckDBDataManager":
        self.initialize_if_needed()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.conn.commit()
        self.conn.close()
        self._initialized = False

    # --- Snapshotting with ShardingManager ---
    def create_snapshot(
        self, output_dir: Path, network_uuid: str, git_commit: str | None = None
    ) -> SnapshotManifest:
        """
        Creates a snapshot of the current DuckDB database, potentially sharded.
        The snapshot is saved to the specified output_dir.
        """
        if not self._initialized:
            self.load_all_data()  # Ensure data is loaded and DB is consistent

        self.conn.commit()  # Ensure all current transactions are written to the DB file.
        # Checkpoint might be good too, but commit should suffice for file consistency.
        # self.conn.execute("CHECKPOINT;") # Force write WAL to main DB file.

        logging.info(f"Creating snapshot from DB: {self.db_path} into {output_dir}")

        sharding_manager = ShardingManager()  # Uses default temp dir

        # Ensure the db_path for sharding manager is absolute, as it might run from different CWDs
        absolute_db_path = self.db_path.resolve()

        manifest = sharding_manager.create_sharded_snapshot(
            duckdb_path=absolute_db_path,
            output_dir=output_dir,
            network_uuid=network_uuid,
            git_commit=git_commit,
        )
        logging.info(f"Snapshot manifest created by DuckDBDataManager: {manifest.merkle_root}")
        return manifest
