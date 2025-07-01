import json
import logging
import datetime
import uuid
from pathlib import Path

import duckdb
from pydantic import ValidationError

from .models import Path as PathModel
from .models import Transaction, Vote # Ensure this is the new Vote model
from .sharding import ShardingManager, SnapshotManifest


class DuckDBDataManager:
    def __init__(
        self,
        db_path: str = "data/encyclopedia.duckdb",
        path_csv_dir: str | Path = "narrative_paths", # Kept for potential initial import
        ratings_csv_dir: str | Path = "ratings",     # Kept for potential initial import
        transactions_json_dir: str | Path = "data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.db_path = Path(db_path)
        self.path_csv_dir = Path(path_csv_dir); self.path_csv_dir.mkdir(parents=True, exist_ok=True)
        self.ratings_csv_dir = Path(ratings_csv_dir); self.ratings_csv_dir.mkdir(parents=True, exist_ok=True)
        self.transactions_json_dir = Path(transactions_json_dir); self.transactions_json_dir.mkdir(parents=True, exist_ok=True)

        self.conn = duckdb.connect(str(self.db_path))
        self._create_tables()
        self._initialized = False

    def _create_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paths(
                path_uuid TEXT PRIMARY KEY, position INTEGER, prev_uuid TEXT, uuid TEXT
            );"""
        )
        self.conn.execute( # New schema for votes
            """
            CREATE TABLE IF NOT EXISTS votes(
                vote_id TEXT PRIMARY KEY,
                duel_id TEXT,
                voting_token_path_uuid TEXT,
                chosen_winner_side TEXT,
                position INTEGER,
                recorded_at TIMESTAMP
            );"""
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS transactions(uuid TEXT PRIMARY KEY, data TEXT);"
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS consumed_voting_tokens(
                voting_token_path_uuid TEXT PRIMARY KEY, consumed_at TIMESTAMP
            );"""
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_duels(
                duel_id TEXT PRIMARY KEY, position INTEGER, path_A_uuid TEXT,
                path_B_uuid TEXT, created_at TIMESTAMP, is_active BOOLEAN,
                CHECK (position > 0) -- Position 0 is immutable and cannot have duels
            );"""
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_duels_pos_active ON pending_duels (position, is_active);"
        )

    def load_all_data(self) -> None: # For initial CSV import if DB is empty
        import pandas as pd # Local import
        paths_empty = self.conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0] == 0
        if paths_empty:
            for csv_file in self.path_csv_dir.glob("*.csv"):
                if not csv_file.exists() or csv_file.stat().st_size == 0: continue
                try:
                    df = pd.read_csv(csv_file, dtype=str)
                    for _, row in df.iterrows():
                        path_model_data = {
                            "path_uuid": row.get("path_uuid") or row.get("fork_uuid"), # Handle old fork_uuid column
                            "position": int(row.get("position")) if pd.notna(row.get("position")) else None,
                            "prev_uuid": row.get("prev_uuid") if pd.notna(row.get("prev_uuid")) else None,
                            "uuid": row.get("uuid"),
                        }
                        if not all([path_model_data["path_uuid"], path_model_data["position"] is not None, path_model_data["uuid"]]):
                            logging.warning(f"Skipping CSV path row due to missing fields: {row.to_dict()}")
                            continue
                        self.add_path(PathModel(**path_model_data))
                except Exception as e: logging.warning(f"Error loading paths from {csv_file}: {e}")

        votes_empty = self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
        if votes_empty: # Old votes.csv is incompatible with new Vote model and duel system. Skip.
            logging.info("Votes table is empty. Old votes.csv import skipped due to schema incompatibility.")

        tx_empty = self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
        if tx_empty and self.transactions_json_dir.exists():
            for jf in self.transactions_json_dir.glob("*.json"):
                if jf.name == "HEAD": continue
                try: self.add_transaction(Transaction(**json.loads(jf.read_text())))
                except Exception as e: logging.warning(f"Error loading transaction {jf}: {e}")
        self._initialized = True

    def save_all_data(self) -> None: # Primarily commits DB changes. CSV export is being phased out.
        self.conn.commit()
        logging.info("DuckDB changes committed. CSV export from save_all_data is being phased out.")
        # TODO: Remove CSV export logic entirely in a later step.
        # For now, keeping it disabled to avoid writing partial/old format data.
        # self._export_paths_to_csv()
        # self._export_votes_to_csv()
        # self._export_transactions_to_json()

    # --- Path operations ---
    def get_all_paths(self) -> list[PathModel]:
        rows = self.conn.execute("SELECT path_uuid, position, prev_uuid, uuid FROM paths").fetchall()
        return [PathModel(path_uuid=r[0],position=r[1],prev_uuid=r[2],uuid=r[3]) for r in rows]

    def get_paths_by_position(self, position: int) -> list[PathModel]:
        rows = self.conn.execute("SELECT path_uuid, position, prev_uuid, uuid FROM paths WHERE position=?",(position,)).fetchall()
        return [PathModel(path_uuid=r[0],position=r[1],prev_uuid=r[2],uuid=r[3]) for r in rows]

    def add_path(self, path: PathModel) -> None:
        data = path.model_dump(exclude_none=False)
        prev_uuid_sql = str(data["prev_uuid"]) if data["prev_uuid"] is not None else None
        self.conn.execute(
            "INSERT INTO paths(path_uuid, position, prev_uuid, uuid) VALUES (?, ?, ?, ?) ON CONFLICT(path_uuid) DO NOTHING",
            (str(data["path_uuid"]), data["position"], prev_uuid_sql, str(data["uuid"])))

    def get_path_by_uuid(self, path_uuid_str: str) -> PathModel | None:
        row = self.conn.execute("SELECT path_uuid, position, prev_uuid, uuid FROM paths WHERE path_uuid=?", (path_uuid_str,)).fetchone()
        return PathModel(path_uuid=row[0],position=row[1],prev_uuid=row[2],uuid=row[3]) if row else None

    # --- Vote operations (New Schema) ---
    def get_all_votes(self) -> list[Vote]:
        rows = self.conn.execute("SELECT vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at FROM votes").fetchall()
        return [Vote(vote_id=r[0],duel_id=r[1],voting_token_path_uuid=r[2],chosen_winner_side=r[3],position=r[4],recorded_at=r[5]) for r in rows]

    def add_vote(self, vote: Vote) -> None:
        data = vote.model_dump(mode='json')
        self.conn.execute(
            "INSERT INTO votes(vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(vote_id) DO NOTHING",
            (data["vote_id"],data["duel_id"],data["voting_token_path_uuid"],data["chosen_winner_side"],data["position"],data["recorded_at"]))

    def get_votes_by_position(self, position: int) -> list[Vote]:
        rows = self.conn.execute("SELECT vote_id, duel_id, voting_token_path_uuid, chosen_winner_side, position, recorded_at FROM votes WHERE position=?",(position,)).fetchall()
        return [Vote(vote_id=r[0],duel_id=r[1],voting_token_path_uuid=r[2],chosen_winner_side=r[3],position=r[4],recorded_at=r[5]) for r in rows]

    # --- Transaction operations ---
    def get_all_transactions(self) -> list[Transaction]:
        rows = self.conn.execute("SELECT data FROM transactions").fetchall() # Data is JSON string
        txs: list[Transaction] = []
        for row_tuple in rows: # rows is list of tuples
            if row_tuple and row_tuple[0]:
                try: txs.append(Transaction(**json.loads(row_tuple[0])))
                except Exception as e: logging.warning(f"Failed to parse transaction data: {row_tuple[0][:100]}... Error: {e}")
        return txs

    def add_transaction(self, transaction: Transaction) -> None:
        data = transaction.model_dump(mode='json') # Get dict with UUIDs as strings
        self.conn.execute("INSERT INTO transactions(uuid, data) VALUES (?, ?) ON CONFLICT(uuid) DO NOTHING",
                          (data["uuid"], json.dumps(data))) # Store full model dump as JSON string

    def get_transaction(self, tx_uuid: str) -> Transaction | None:
        row = self.conn.execute("SELECT data FROM transactions WHERE uuid=?", (tx_uuid,)).fetchone()
        if row and row[0]:
            try: return Transaction(**json.loads(row[0]))
            except Exception as e: logging.warning(f"Failed to parse transaction {tx_uuid}: {e}"); return None
        return None

    # --- Consumed Voting Token operations ---
    def add_consumed_token(self, voting_token_path_uuid: str, consumed_at: datetime.datetime) -> None:
        self.conn.execute("INSERT INTO consumed_voting_tokens (voting_token_path_uuid, consumed_at) VALUES (?, ?)", (voting_token_path_uuid, consumed_at))

    def is_token_consumed(self, voting_token_path_uuid: str) -> bool:
        res = self.conn.execute("SELECT COUNT(*) FROM consumed_voting_tokens WHERE voting_token_path_uuid = ?", (voting_token_path_uuid,)).fetchone()
        return res[0] > 0 if res else False

    # --- Pending Duel operations ---
    def add_pending_duel(
        self,
        position: int,
        path_A_uuid: str,
        path_B_uuid: str,
        created_at: datetime.datetime,
        duel_id_override: str | None = None # Optional override for testing
    ) -> str:
        if position == 0:
            raise ValueError("Duels cannot be created for position 0.")

        duel_id = duel_id_override if duel_id_override else str(uuid.uuid4())

        self.conn.execute(
            "INSERT INTO pending_duels (duel_id, position, path_A_uuid, path_B_uuid, created_at, is_active) VALUES (?, ?, ?, ?, ?, TRUE) ON CONFLICT(duel_id) DO NOTHING",
            (duel_id, position, path_A_uuid, path_B_uuid, created_at)
        )
        # If ON CONFLICT DO NOTHING occurs, this will still return the duel_id, assuming the caller expects it.
        # If strict "did I insert it now?" is needed, further checks might be required (e.g. check affected_rows if driver supports).
        return duel_id

    # Test support method - not for general use, bypasses some checks like position 0
    def add_pending_duel_direct(self, duel_id: str, position: int, path_A_uuid: str, path_B_uuid: str, is_active: bool, created_at: datetime.datetime | None = None) -> None:
        """Allows inserting a duel with a specific ID and active status, primarily for test setup."""
        if created_at is None:
            created_at = datetime.datetime.now(datetime.timezone.utc)
        self.conn.execute(
            "INSERT INTO pending_duels (duel_id, position, path_A_uuid, path_B_uuid, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (duel_id, position, path_A_uuid, path_B_uuid, created_at, is_active))


    def get_active_duel_for_position(self, position: int) -> dict | None:
        res = self.conn.execute("SELECT duel_id, path_A_uuid, path_B_uuid FROM pending_duels WHERE position = ? AND is_active = TRUE", (position,)).fetchone()
        if res: return {"duel_id": res[0], "path_A_uuid": res[1], "path_B_uuid": res[2]}
        return None

    def deactivate_duel(self, duel_id: str) -> None:
        self.conn.execute("UPDATE pending_duels SET is_active = FALSE WHERE duel_id = ?", (duel_id,))

    def get_duel_details(self, duel_id: str) -> dict | None:
        res = self.conn.execute("SELECT position, path_A_uuid, path_B_uuid, created_at, is_active FROM pending_duels WHERE duel_id = ?", (duel_id,)).fetchone()
        if res: return {"duel_id": duel_id, "position": res[0], "path_A_uuid": res[1], "path_B_uuid": res[2], "created_at": res[3], "is_active": res[4]}
        return None

    # --- Utility methods ---
    def initialize_if_needed(self) -> None: # Called by DataManager wrapper
        if not self._initialized: self.load_all_data()

    def clear_in_memory_data(self) -> None: # Actually clears DB tables
        self.conn.execute("DELETE FROM paths")
        self.conn.execute("DELETE FROM votes")
        self.conn.execute("DELETE FROM transactions")
        self.conn.execute("DELETE FROM consumed_voting_tokens")
        self.conn.execute("DELETE FROM pending_duels")
        self.conn.commit()

    def __enter__(self) -> "DuckDBDataManager": self.initialize_if_needed(); return self
    def __exit__(self,et,ev,tb) -> None: self.conn.commit(); self.conn.close(); self._initialized=False

    def create_snapshot(self, output_dir: Path, network_uuid: str, git_commit: str | None = None) -> SnapshotManifest:
        if not self._initialized: self.load_all_data()
        self.conn.commit()
        absolute_db_path = self.db_path.resolve()
        manifest = ShardingManager().create_sharded_snapshot(absolute_db_path, output_dir, network_uuid, git_commit)
        logging.info(f"Snapshot manifest created: {manifest.merkle_root}"); return manifest

# Ensure storage.py DataManager methods for votes are updated if their signature or backend call changes.
# Ensure TransactionContent model in models.py is updated if verdicts_processed stores new Vote model structure.
# Ensure ratings.py get_ranking is updated to use new Vote model structure and duel_id logic.
# Ensure cli.py cast_votes calls new ratings.record_vote correctly.
# Ensure cli.py init-test populates initial pending_duels.
# Ensure tests are updated for all these schema and logic changes.
# The _export_paths_to_csv, _export_votes_to_csv, _export_transactions_to_json methods could be added if CSV export is still desired from DuckDB for inspection.
# For now, save_all_data only commits, and load_all_data only imports from CSV if DB is empty.
