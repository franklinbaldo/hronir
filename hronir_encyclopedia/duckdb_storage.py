import datetime  # Added for Optional[datetime] type hint
import json
import logging
from pathlib import Path

import duckdb
from pydantic import ValidationError  # Moved up

from .models import Path as PathModel
from .models import PathStatus, Transaction, TransactionContent, Vote  # Added PathStatus
from .sharding import ShardingManager, SnapshotManifest  # Added

logger = logging.getLogger(__name__)  # Ensure logger is defined here


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
                is_canonical BOOLEAN DEFAULT FALSE
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
                timestamp TIMESTAMPTZ,
                prev_transaction_uuid TEXT,
                initiating_path_uuid TEXT,
                votes_processed JSON,
                promotions_granted JSON
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

        # tx_empty = self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0 # Legacy load from JSON removed
        # if tx_empty and self.transactions_json_dir.exists():
        #     for jf in self.transactions_json_dir.glob("*.json"):
        #         try:
        #             data = json.loads(jf.read_text())
        #             self.add_transaction(Transaction(**data)) # This would call the new add_transaction
        #         except (json.JSONDecodeError, ValidationError):
        #             continue

        self._initialized = True

    def save_all_data(self) -> None:
        """Commits the current transaction to the DuckDB database."""
        self.conn.commit()
        # Removed logic that writes back to CSV/JSON files.

    # --- Path operations ---
    def get_all_paths(self) -> list[PathModel]:
        rows = self.conn.execute(
            "SELECT path_uuid, position, prev_uuid, uuid, status, mandate_id, is_canonical FROM paths"
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
                    "is_canonical": row[6] if row[6] is not None else False,
                }
                paths.append(PathModel(**data))
            except ValidationError:  # pragma: no cover
                logger.warning(f"Failed to validate path data from DB: {row}", exc_info=True)
                continue
        return paths

    def get_paths_by_position(self, position: int) -> list[PathModel]:
        rows = self.conn.execute(
            "SELECT path_uuid, position, prev_uuid, uuid, status, mandate_id, is_canonical FROM paths WHERE position=?",
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
                    "is_canonical": row[6] if row[6] is not None else False,
                }
                paths.append(PathModel(**data))
            except ValidationError:  # pragma: no cover
                logger.warning(
                    f"Failed to validate path data from DB for position {position}: {row}",
                    exc_info=True,
                )
                continue
        return paths

    def add_path(self, path: PathModel) -> None:
        data = path.model_dump()
        self.conn.execute(
            """
            INSERT INTO paths(path_uuid, position, prev_uuid, uuid, status, mandate_id, is_canonical)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path_uuid) DO UPDATE SET
                position = excluded.position,
                prev_uuid = excluded.prev_uuid,
                uuid = excluded.uuid,
                status = excluded.status,
                mandate_id = excluded.mandate_id,
                is_canonical = excluded.is_canonical
            """,  # Using ON CONFLICT DO UPDATE to handle potential re-additions or updates
            (
                str(data["path_uuid"]),
                data["position"],
                str(data["prev_uuid"])
                if data["prev_uuid"]
                else None,  # Store NULL for None prev_uuid
                str(data["uuid"]),
                data.get("status", PathStatus.PENDING.value),  # Use enum value
                str(data["mandate_id"])
                if data["mandate_id"]
                else None,  # Store NULL for None mandate_id
                data.get("is_canonical", False),
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
            "SELECT path_uuid, position, prev_uuid, uuid, status, mandate_id, is_canonical FROM paths WHERE path_uuid=?",
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
            "is_canonical": row[6] if row[6] is not None else False,
        }
        try:
            return PathModel(**data)
        except ValidationError:  # pragma: no cover
            logger.warning(
                f"Failed to validate path data from DB for path_uuid {path_uuid}: {row}",
                exc_info=True,
            )
            return None

    def set_path_canonical_status(self, path_uuid: str, is_canonical: bool) -> None:
        """Sets the is_canonical status for a specific path."""
        self.conn.execute(
            "UPDATE paths SET is_canonical=? WHERE path_uuid=?",
            (is_canonical, path_uuid),
        )

    def clear_canonical_statuses_from_position(self, position: int) -> None:
        """Sets is_canonical to FALSE for all paths at or after a given position."""
        self.conn.execute(
            "UPDATE paths SET is_canonical=? WHERE position >= ?",
            (False, position),
        )

    def get_max_path_position(self) -> int | None:
        """Gets the maximum position value from the paths table."""
        result = self.conn.execute("SELECT MAX(position) FROM paths").fetchone()
        if result and result[0] is not None:
            return int(result[0])
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
        rows = self.conn.execute(
            "SELECT uuid, timestamp, prev_transaction_uuid, initiating_path_uuid, votes_processed, promotions_granted FROM transactions"
        ).fetchall()
        txs: list[Transaction] = []
        for row_data in rows:
            try:
                content = TransactionContent(
                    initiating_path_uuid=row_data[3],
                    votes_processed=json.loads(row_data[4])
                    if isinstance(row_data[4], str)
                    else row_data[4],  # Handle if already list/dict
                    promotions_granted=json.loads(row_data[5])
                    if isinstance(row_data[5], str)
                    else row_data[5],
                )
                tx = Transaction(
                    uuid=row_data[0],
                    timestamp=row_data[1],
                    prev_uuid=row_data[2] if row_data[2] else None,
                    content=content,
                )
                txs.append(tx)
            except (json.JSONDecodeError, ValidationError, TypeError) as e:
                logger.error(f"Error reconstructing transaction {row_data[0]} from DB: {e}")
                continue
        return txs

    def add_transaction(self, transaction: Transaction) -> None:
        # Convert lists of Pydantic models (like SessionVerdict in votes_processed)
        # or lists of UUIDs (promotions_granted) to JSON strings for storage.
        votes_processed_json = json.dumps(
            [vote.model_dump() for vote in transaction.content.votes_processed], default=str
        )
        promotions_granted_json = json.dumps(
            [str(uuid_val) for uuid_val in transaction.content.promotions_granted], default=str
        )

        self.conn.execute(
            """
            INSERT INTO transactions(uuid, timestamp, prev_transaction_uuid, initiating_path_uuid, votes_processed, promotions_granted)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(uuid) DO NOTHING
            """,
            (
                str(transaction.uuid),
                transaction.timestamp,
                str(transaction.prev_uuid) if transaction.prev_uuid else None,
                str(transaction.content.initiating_path_uuid),
                votes_processed_json,
                promotions_granted_json,
            ),
        )

    def get_transaction(self, tx_uuid: str) -> Transaction | None:
        row_data = self.conn.execute(
            "SELECT uuid, timestamp, prev_transaction_uuid, initiating_path_uuid, votes_processed, promotions_granted FROM transactions WHERE uuid=?",
            (tx_uuid,),
        ).fetchone()
        if not row_data:
            return None
        try:
            content = TransactionContent(
                initiating_path_uuid=row_data[3],
                votes_processed=json.loads(row_data[4])
                if isinstance(row_data[4], str)
                else row_data[4],
                promotions_granted=json.loads(row_data[5])
                if isinstance(row_data[5], str)
                else row_data[5],
            )
            return Transaction(
                uuid=row_data[0],
                timestamp=row_data[1],
                prev_uuid=row_data[2] if row_data[2] else None,
                content=content,
            )
        except (json.JSONDecodeError, ValidationError, TypeError) as e:
            logger.error(f"Error reconstructing transaction {tx_uuid} from DB: {e}")
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
