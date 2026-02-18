import datetime
import json
import logging
from pathlib import Path

import duckdb
from pydantic import ValidationError

from .models import Path as PathModel
from .models import Transaction
from .sharding import ShardingManager, SnapshotManifest


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
        transactions_json_dir: str | Path = "data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.db_path = Path(db_path)
        self.path_csv_dir = Path(path_csv_dir)
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
        # votes table removed from creation in new installations
        # transactions table persists
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
            CREATE TABLE IF NOT EXISTS hronirs (
                uuid VARCHAR PRIMARY KEY,
                content TEXT,
                created_at TIMESTAMP,
                metadata TEXT -- JSON string for other attributes
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

        # Vote loading removed

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

    # --- Vote operations removed ---

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
        result = self.conn.execute(
            "SELECT content FROM hronirs WHERE uuid = ?", (hronir_uuid,)
        ).fetchone()
        return result[0] if result else None

    # --- Utility methods ---
    def initialize_if_needed(self) -> None:
        if not self._initialized:
            self.load_all_data()

    def clear_in_memory_data(self) -> None:
        self.conn.execute("DELETE FROM paths")
        # votes delete removed
        self.conn.execute("DELETE FROM transactions")
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
