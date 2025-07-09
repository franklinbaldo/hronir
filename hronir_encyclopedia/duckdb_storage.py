import datetime  # Added for Optional[datetime] type hint
import json
import logging  # Added to fix Ruff F821
from pathlib import Path

import duckdb
from pydantic import ValidationError

from .models import Path as PathModel
from .models import Session as SessionModel  # Added
from .models import Transaction, Vote
from .sharding import ShardingManager, SnapshotManifest  # Added


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
                mandate_id TEXT,
                consumed_in_session_id TEXT NULLABLE
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
        self.conn.execute(  # Add hronirs table creation
            """
            CREATE TABLE IF NOT EXISTS hronirs (
                uuid VARCHAR PRIMARY KEY,
                content TEXT,
                created_at TIMESTAMP,
                metadata TEXT -- JSON string for other attributes
            );
            """
        )
        self.conn.execute(  # Add sessions table
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                initiating_path_uuid TEXT,
                mandate_id TEXT,
                position_n INTEGER,
                dossier TEXT, -- JSON string for SessionDossier
                status TEXT,
                committed_verdicts TEXT, -- JSON string for dict[str, UUID5] or null
                created_at TIMESTAMP,
                updated_at TIMESTAMP
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
        """Commits the current transaction to the DuckDB database."""
        self.conn.commit()
        # Removed logic that writes back to CSV/JSON files.

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
                    "consumed_in_session_id": row[6] if row[6] else None,
                }
                # Ensure prev_uuid and mandate_id are correctly typed for Pydantic
                if data["prev_uuid"] == "":
                    data["prev_uuid"] = None
                if data["mandate_id"] == "":
                    data["mandate_id"] = None

                paths.append(PathModel(**data))
            except ValidationError as e:
                logging.warning(f"Validation error loading path from DB: {data}, error: {e}")
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
                    "consumed_in_session_id": row[6] if row[6] else None,
                }
                if data["prev_uuid"] == "":
                    data["prev_uuid"] = None
                if data["mandate_id"] == "":
                    data["mandate_id"] = None
                paths.append(PathModel(**data))
            except ValidationError as e:
                logging.warning(f"Validation error loading path by position from DB: {data}, error: {e}")
                continue
        return paths

    def add_path(self, path: PathModel) -> None:
        data = path.model_dump()
        self.conn.execute(
            """
            INSERT INTO paths(path_uuid, position, prev_uuid, uuid, status, mandate_id, consumed_in_session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path_uuid) DO UPDATE SET
                position = excluded.position,
                prev_uuid = excluded.prev_uuid,
                uuid = excluded.uuid,
                status = excluded.status,
                mandate_id = excluded.mandate_id,
                consumed_in_session_id = excluded.consumed_in_session_id
            """,  # Using DO UPDATE to allow upsert logic if needed, though path_uuid is primary key
            (
                str(data["path_uuid"]),
                data["position"],
                str(data.get("prev_uuid")) if data.get("prev_uuid") else None,
                str(data["uuid"]),
                data.get("status", "PENDING"),
                str(data.get("mandate_id")) if data.get("mandate_id") else None,
                str(data.get("consumed_in_session_id")) if data.get("consumed_in_session_id") else None,
            ),
        )

    def update_path_fields(self, path_uuid: str, fields_to_update: dict) -> None:
        """Dynamically update specified fields for a path."""
        if not fields_to_update:
            return

        set_clauses = []
        params = []
        for key, value in fields_to_update.items():
            # Ensure column names are valid to prevent injection; ideally, use a whitelist
            if key not in ["status", "mandate_id", "consumed_in_session_id"]: # Add other valid fields if necessary
                logging.warning(f"Attempted to update invalid or protected field: {key}")
                continue
            set_clauses.append(f"{key} = ?")
            params.append(str(value) if value is not None else None)

        if not set_clauses:
            return

        sql = f"UPDATE paths SET {', '.join(set_clauses)} WHERE path_uuid = ?"
        params.append(path_uuid)
        self.conn.execute(sql, tuple(params))


    def update_path_status(
        self,
        path_uuid: str,
        status: str,
        mandate_id: str | None = None,
        set_mandate_explicitly: bool = False,
    ) -> None:
        fields = {"status": status}
        if set_mandate_explicitly:
            fields["mandate_id"] = mandate_id
        self.update_path_fields(path_uuid, fields)

    def mark_path_consumed(self, path_uuid: str, session_id: str) -> None:
        """Marks a path as consumed by a specific session."""
        self.update_path_fields(path_uuid, {"consumed_in_session_id": session_id})

    def get_path_consumed_session_id(self, path_uuid: str) -> str | None:
        """Retrieves the session_id that consumed the path, if any."""
        path = self.get_path_by_uuid(path_uuid)
        return str(path.consumed_in_session_id) if path and path.consumed_in_session_id else None

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
            "prev_uuid": row[2] if row[2] else None, # Handle empty string from DB
            "uuid": row[3],
            "status": row[4],
            "mandate_id": row[5] if row[5] else None, # Handle empty string from DB
            "consumed_in_session_id": row[6] if row[6] else None,
        }
        if data["prev_uuid"] == "":
            data["prev_uuid"] = None
        if data["mandate_id"] == "":
            data["mandate_id"] = None
        try:
            return PathModel(**data)
        except ValidationError as e:
            logging.warning(f"Validation error loading path by UUID from DB: {data}, error: {e}")
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

    # --- Hrönir operations ---
    def add_hronir(
        self,
        hronir_uuid: str,
        content: str,
        created_at: datetime.datetime | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Adds a hrönir's content to the hronirs table."""
        if created_at is None:
            created_at = datetime.datetime.now(datetime.timezone.utc)
        metadata_json = json.dumps(metadata) if metadata else "{}"

        # Ensure the hronirs table exists (it should have been created by _create_tables via migration script)
        # For robustness, we could add a check or ensure_table_exists call here if necessary.
        # self._create_tables() # This would try to create all tables, maybe too broad.
        # A more targeted "CREATE TABLE IF NOT EXISTS hronirs ..." could be used if this method
        # could be called before the main initialization. Given current flow, it's likely fine.

        self.conn.execute(
            """
            INSERT INTO hronirs (uuid, content, created_at, metadata)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(uuid) DO UPDATE SET
                content = excluded.content,
                created_at = excluded.created_at,
                metadata = excluded.metadata;
            """,
            (hronir_uuid, content, created_at, metadata_json),
        )

    def get_hronir_content(self, hronir_uuid: str) -> str | None:
        """Retrieves a hrönir's content from the hronirs table by its UUID."""
        # Ensure the hronirs table exists.
        result = self.conn.execute(
            "SELECT content FROM hronirs WHERE uuid = ?", (hronir_uuid,)
        ).fetchone()
        return result[0] if result else None

    # --- Session operations ---
    def add_session(self, session: SessionModel) -> None:
        """Adds a new session to the sessions table."""
        session_data = session.model_dump()
        dossier_json = json.dumps(session_data["dossier"])
        committed_verdicts_json = json.dumps(session_data["committed_verdicts"]) if session_data["committed_verdicts"] is not None else None

        self.conn.execute(
            """
            INSERT INTO sessions (session_id, initiating_path_uuid, mandate_id, position_n, dossier, status, committed_verdicts, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                initiating_path_uuid = excluded.initiating_path_uuid,
                mandate_id = excluded.mandate_id,
                position_n = excluded.position_n,
                dossier = excluded.dossier,
                status = excluded.status,
                committed_verdicts = excluded.committed_verdicts,
                created_at = excluded.created_at, -- Should not change on conflict if session_id is unique
                updated_at = excluded.updated_at
            """,
            (
                str(session_data["session_id"]),
                str(session_data["initiating_path_uuid"]),
                str(session_data["mandate_id"]),
                session_data["position_n"],
                dossier_json,
                session_data["status"],
                committed_verdicts_json,
                session_data["created_at"],
                session_data["updated_at"],
            ),
        )

    def get_session(self, session_id: str) -> SessionModel | None:
        """Retrieves a session by its ID from the sessions table."""
        row = self.conn.execute(
            "SELECT session_id, initiating_path_uuid, mandate_id, position_n, dossier, status, committed_verdicts, created_at, updated_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            return None

        try:
            dossier_data = json.loads(row[4]) if row[4] else None
            committed_verdicts_data = json.loads(row[6]) if row[6] else None
            session_data = {
                "session_id": row[0],
                "initiating_path_uuid": row[1],
                "mandate_id": row[2],
                "position_n": row[3],
                "dossier": dossier_data,
                "status": row[5],
                "committed_verdicts": committed_verdicts_data,
                "created_at": row[7],
                "updated_at": row[8],
            }
            return SessionModel(**session_data)
        except (json.JSONDecodeError, ValidationError) as e:
            logging.error(f"Error decoding/validating session {session_id} from DB: {e}")
            return None

    def update_session(self, session: SessionModel) -> None:
        """Updates an existing session in the sessions table."""
        session_data = session.model_dump()
        dossier_json = json.dumps(session_data["dossier"])
        committed_verdicts_json = json.dumps(session_data["committed_verdicts"]) if session_data["committed_verdicts"] is not None else None

        self.conn.execute(
            """
            UPDATE sessions SET
                initiating_path_uuid = ?,
                mandate_id = ?,
                position_n = ?,
                dossier = ?,
                status = ?,
                committed_verdicts = ?,
                created_at = ?,
                updated_at = ?
            WHERE session_id = ?
            """,
            (
                str(session_data["initiating_path_uuid"]),
                str(session_data["mandate_id"]),
                session_data["position_n"],
                dossier_json,
                session_data["status"],
                committed_verdicts_json,
                session_data["created_at"],
                session_data["updated_at"],
                str(session_data["session_id"]),
            ),
        )

    # --- Utility methods ---
    def initialize_if_needed(self) -> None:
        if not self._initialized:
            self.load_all_data()

    def clear_in_memory_data(self) -> None:
        self.conn.execute("DELETE FROM paths")
        self.conn.execute("DELETE FROM votes")
        self.conn.execute("DELETE FROM transactions")
        self.conn.execute("DELETE FROM hronirs")
        self.conn.execute("DELETE FROM sessions")
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
