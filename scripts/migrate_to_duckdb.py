import argparse
import datetime
import json
import logging
import os
import shutil
from pathlib import Path

import duckdb
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define default paths (can be overridden by config or arguments if needed)
DEFAULT_DUCKDB_PATH = Path("data/encyclopedia.duckdb")
DEFAULT_CSV_NARRATIVE_PATHS_DIR = Path("narrative_paths/")
DEFAULT_CSV_RATINGS_DIR = Path("ratings/")
DEFAULT_TRANSACTIONS_JSON_DIR = Path("data/transactions/")
DEFAULT_BACKUP_DIR = Path("data/backup/")

# Schema based on docs/pivot_plan_v2.md and existing models
DUCKDB_SCHEMA = {
    "paths": """
        CREATE TABLE IF NOT EXISTS paths (
            path_uuid VARCHAR PRIMARY KEY,
            position INTEGER NOT NULL,
            prev_uuid VARCHAR,
            uuid VARCHAR NOT NULL, -- This is hrönir_uuid
            status VARCHAR DEFAULT 'PENDING',
            mandate_id VARCHAR,
            created_at TIMESTAMP -- Need to extract or generate this
        );
    """,
    "votes": """
        CREATE TABLE IF NOT EXISTS votes (
            uuid VARCHAR PRIMARY KEY, -- Vote UUID
            position INTEGER NOT NULL,
            voter TEXT, -- voter_path_uuid
            winner TEXT, -- winner_hrönir_uuid
            loser TEXT, -- loser_hrönir_uuid
            created_at TIMESTAMP -- Need to extract or generate this
        );
    """,
    "transactions": """
        CREATE TABLE IF NOT EXISTS transactions (
            uuid VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL,
            prev_uuid VARCHAR,
            session_id VARCHAR,
            initiating_path_uuid VARCHAR,
            verdicts_processed TEXT, -- JSON string of list of dicts
            promotions_granted TEXT  -- JSON string of list of UUIDs
        );
    """,
    "hronirs": """
        CREATE TABLE IF NOT EXISTS hronirs (
            uuid VARCHAR PRIMARY KEY,
            content TEXT,
            created_at TIMESTAMP,
            metadata TEXT -- JSON string for other attributes
        );
    """,
    # Snapshot table from pivot_plan_v2.md - might be managed differently,
    # but including for completeness of data that could be in DuckDB.
    # This script primarily focuses on migrating current data.
    "snapshots_meta": """
        CREATE TABLE IF NOT EXISTS snapshots_meta (
            sequence INTEGER PRIMARY KEY,
            prev_sequence INTEGER,
            network_uuid VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            git_commit VARCHAR,
            merkle_root VARCHAR NOT NULL,
            pgp_signature TEXT NOT NULL,
            upload_id VARCHAR -- IA identifier
        );
    """,
}


def backup_existing_data(
    csv_paths_dir: Path, csv_ratings_dir: Path, transactions_json_dir: Path, backup_base_dir: Path
):
    """Backs up existing CSV and JSON data to a timestamped directory."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_target_dir = backup_base_dir / f"backup_{timestamp}"
    backup_target_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Backing up data to {backup_target_dir}")

    if csv_paths_dir.exists():
        shutil.copytree(csv_paths_dir, backup_target_dir / csv_paths_dir.name, dirs_exist_ok=True)
        logging.info(f"Backed up {csv_paths_dir.name}")

    if csv_ratings_dir.exists():
        shutil.copytree(
            csv_ratings_dir, backup_target_dir / csv_ratings_dir.name, dirs_exist_ok=True
        )
        logging.info(f"Backed up {csv_ratings_dir.name}")

    if transactions_json_dir.exists():
        shutil.copytree(
            transactions_json_dir,
            backup_target_dir / transactions_json_dir.name,
            dirs_exist_ok=True,
        )
        logging.info(f"Backed up {transactions_json_dir.name}")

    # Potentially backup the_library too if it's considered part of the data state
    the_library_dir = Path("the_library/")
    if the_library_dir.exists():
        shutil.copytree(
            the_library_dir, backup_target_dir / the_library_dir.name, dirs_exist_ok=True
        )
        logging.info(f"Backed up {the_library_dir.name}")

    logging.info("Backup completed.")


def create_duckdb_schema(conn: duckdb.DuckDBPyConnection):
    """Creates tables in DuckDB based on the defined schema."""
    logging.info("Creating DuckDB schema...")
    for table_name, ddl_statement in DUCKDB_SCHEMA.items():
        try:
            conn.execute(ddl_statement)
            logging.info(f"Table '{table_name}' created or already exists.")
        except Exception as e:
            logging.error(f"Error creating table {table_name}: {e}")
    conn.commit()
    logging.info("DuckDB schema creation complete.")


def migrate_paths_to_duckdb(conn: duckdb.DuckDBPyConnection, csv_paths_dir: Path):
    """Migrates path data from CSV files to DuckDB."""
    logging.info(f"Migrating paths from {csv_paths_dir}...")
    files_processed = 0
    for csv_file in csv_paths_dir.glob("narrative_paths_position_*.csv"):
        try:
            df = pd.read_csv(csv_file, dtype=str)  # Read all as string initially
            df["position"] = pd.to_numeric(df["position"], errors="coerce")

            # Add created_at if missing - estimate from file mod time or use a default
            # For real migration, a better source for created_at would be ideal
            if "created_at" not in df.columns:
                df["created_at"] = pd.to_datetime(os.path.getmtime(csv_file), unit="s")
            else:
                df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

            df = df.where(pd.notnull(df), None)  # Convert NaNs to None for DB

            # Ensure all necessary columns exist, fill with None if not
            expected_cols = [
                "path_uuid",
                "position",
                "prev_uuid",
                "uuid",
                "status",
                "mandate_id",
                "created_at",
            ]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None

            df = df[expected_cols]  # Reorder and select

            conn.register("paths_df", df)
            conn.execute("""
                INSERT INTO paths (path_uuid, position, prev_uuid, uuid, status, mandate_id, created_at)
                SELECT path_uuid, position, prev_uuid, uuid, status, mandate_id, created_at FROM paths_df
                ON CONFLICT(path_uuid) DO NOTHING;
            """)
            logging.info(f"Migrated data from {csv_file.name}")
            files_processed += 1
        except Exception as e:
            logging.error(f"Error migrating {csv_file.name}: {e}")
    if files_processed == 0:
        logging.warning(f"No path CSV files found or processed in {csv_paths_dir}.")
    conn.commit()
    logging.info("Path data migration complete.")


def migrate_votes_to_duckdb(conn: duckdb.DuckDBPyConnection, csv_ratings_dir: Path):
    """Migrates vote data from CSV files to DuckDB."""
    logging.info(f"Migrating votes from {csv_ratings_dir}...")
    votes_csv = csv_ratings_dir / "votes.csv"  # Assuming a single votes.csv
    if votes_csv.exists():
        try:
            df = pd.read_csv(votes_csv, dtype=str)
            df["position"] = pd.to_numeric(df["position"], errors="coerce")

            if "created_at" not in df.columns:
                # Estimate from file mod time or use a default
                df["created_at"] = pd.to_datetime(os.path.getmtime(votes_csv), unit="s")
            else:
                df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

            df = df.where(pd.notnull(df), None)

            expected_cols = ["uuid", "position", "voter", "winner", "loser", "created_at"]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = None
            df = df[expected_cols]

            conn.register("votes_df", df)
            conn.execute("""
                INSERT INTO votes (uuid, position, voter, winner, loser, created_at)
                SELECT uuid, position, voter, winner, loser, created_at FROM votes_df
                ON CONFLICT(uuid) DO NOTHING;
            """)
            logging.info(f"Migrated data from {votes_csv.name}")
        except Exception as e:
            logging.error(f"Error migrating {votes_csv.name}: {e}")
    else:
        logging.warning(f"Votes CSV file not found at {votes_csv}.")
    conn.commit()
    logging.info("Vote data migration complete.")


def migrate_transactions_to_duckdb(conn: duckdb.DuckDBPyConnection, transactions_json_dir: Path):
    """Migrates transaction data from JSON files to DuckDB."""
    logging.info(f"Migrating transactions from {transactions_json_dir}...")
    files_processed = 0
    if transactions_json_dir.exists():
        for json_file in transactions_json_dir.glob("*.json"):
            if json_file.name.lower() == "head":  # Skip HEAD file
                continue
            try:
                with open(json_file) as f:
                    data = json.load(f)

                # Extract relevant fields for the 'transactions' table
                # The TransactionContent model has nested data.
                # We'll store verdicts_processed and promotions_granted as JSON strings for simplicity here.
                content = data.get("content", {})
                verdicts_processed_json = json.dumps(content.get("verdicts_processed"))
                promotions_granted_json = json.dumps(content.get("promotions_granted"))

                conn.execute(
                    """
                    INSERT INTO transactions (uuid, timestamp, prev_uuid, session_id, initiating_path_uuid, verdicts_processed, promotions_granted)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(uuid) DO NOTHING;
                    """,
                    (
                        data.get("uuid"),
                        pd.to_datetime(data.get("timestamp"), errors="coerce"),
                        data.get("prev_uuid"),
                        content.get("session_id"),
                        content.get("initiating_path_uuid"),
                        verdicts_processed_json,
                        promotions_granted_json,
                    ),
                )
                logging.info(f"Migrated transaction {json_file.name}")
                files_processed += 1
            except Exception as e:
                logging.error(f"Error migrating transaction {json_file.name}: {e}")
    if files_processed == 0:
        logging.warning(f"No transaction JSON files found or processed in {transactions_json_dir}.")
    conn.commit()
    logging.info("Transaction data migration complete.")


def migrate_hronirs_to_duckdb(conn: duckdb.DuckDBPyConnection, library_dir: Path):
    """Migrates hrönir content from the_library to DuckDB."""
    logging.info(f"Migrating hrönirs from {library_dir}...")
    files_processed = 0
    if library_dir.exists():
        for hronir_uuid_dir in library_dir.iterdir():
            if hronir_uuid_dir.is_dir():
                hronir_file = hronir_uuid_dir / "index.md"
                if hronir_file.exists():
                    try:
                        content = hronir_file.read_text(encoding="utf-8")
                        hronir_uuid = hronir_uuid_dir.name
                        # created_at and metadata are not readily available from current structure
                        # For now, use file modification time for created_at
                        created_at = pd.to_datetime(os.path.getmtime(hronir_file), unit="s")
                        metadata_json = json.dumps({})  # Placeholder

                        conn.execute(
                            """
                            INSERT INTO hronirs (uuid, content, created_at, metadata)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(uuid) DO NOTHING;
                            """,
                            (hronir_uuid, content, created_at, metadata_json),
                        )
                        logging.info(f"Migrated hrönir {hronir_uuid}")
                        files_processed += 1
                    except Exception as e:
                        logging.error(f"Error migrating hrönir {hronir_uuid_dir.name}: {e}")
    if files_processed == 0:
        logging.warning(f"No hrönirs found or processed in {library_dir}.")
    conn.commit()
    logging.info("Hrönir data migration complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Hrönir Encyclopedia data from CSV/JSON to DuckDB."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DUCKDB_PATH,
        help=f"Path to the DuckDB database file (default: {DEFAULT_DUCKDB_PATH})",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup existing CSV/JSON data before migration.",
    )
    parser.add_argument(
        "--enable-sharding",  # Placeholder for now
        action="store_true",
        help="Enable sharding logic during/after migration (feature not fully implemented in this script).",
    )
    parser.add_argument(
        "--csv-paths-dir",
        type=Path,
        default=DEFAULT_CSV_NARRATIVE_PATHS_DIR,
        help=f"Directory containing narrative path CSVs (default: {DEFAULT_CSV_NARRATIVE_PATHS_DIR})",
    )
    parser.add_argument(
        "--csv-ratings-dir",
        type=Path,
        default=DEFAULT_CSV_RATINGS_DIR,
        help=f"Directory containing ratings/votes CSVs (default: {DEFAULT_CSV_RATINGS_DIR})",
    )
    parser.add_argument(
        "--transactions-json-dir",
        type=Path,
        default=DEFAULT_TRANSACTIONS_JSON_DIR,
        help=f"Directory containing transaction JSON files (default: {DEFAULT_TRANSACTIONS_JSON_DIR})",
    )
    parser.add_argument(
        "--hronirs-library-dir",
        type=Path,
        default=Path("the_library/"),
        help="Directory containing hrönir content (default: the_library/)",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=DEFAULT_BACKUP_DIR,
        help=f"Base directory for backups (default: {DEFAULT_BACKUP_DIR})",
    )

    args = parser.parse_args()

    logging.info("Starting data migration to DuckDB...")

    if args.backup:
        args.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_existing_data(
            args.csv_paths_dir, args.csv_ratings_dir, args.transactions_json_dir, args.backup_dir
        )

    # Ensure data directory for DuckDB file exists
    args.db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = duckdb.connect(database=str(args.db_path), read_only=False)

        create_duckdb_schema(conn)
        migrate_paths_to_duckdb(conn, args.csv_paths_dir)
        migrate_votes_to_duckdb(conn, args.csv_ratings_dir)
        migrate_transactions_to_duckdb(conn, args.transactions_json_dir)
        migrate_hronirs_to_duckdb(conn, args.hronirs_library_dir)

        if args.enable_sharding:
            logging.warning(
                "--enable-sharding is specified, but sharding logic is not fully implemented in this script."
            )
            # Placeholder:
            # from hronir_encyclopedia.sharding import ShardingManager
            # manager = ShardingManager()
            # manifest = manager.create_sharded_snapshot(args.db_path)
            # logging.info(f"Sharding prepared. Manifest (details): {manifest}")

        logging.info(f"Data migration to {args.db_path} complete.")

        # Verification (optional)
        logging.info("Sample data counts from DuckDB:")
        for table in ["paths", "votes", "transactions", "hronirs"]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logging.info(f"- {table}: {count} rows")

    except Exception as e:
        logging.error(f"An error occurred during migration: {e}", exc_info=True)
    finally:
        if "conn" in locals() and conn:
            conn.close()


if __name__ == "__main__":
    main()
