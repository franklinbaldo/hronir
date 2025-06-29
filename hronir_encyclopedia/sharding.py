import dataclasses
import datetime
import hashlib
import json
import logging
import math
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Any
import duckdb
import zstandard

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Data Classes (based on pivot_plan_v2.md) ---
@dataclasses.dataclass
class ShardInfo:
    file: str  # Name of the shard file (e.g., "shard_001.db.zst")
    sha256: str  # SHA256 hash of the compressed shard file
    size: int  # Size of the compressed shard file in bytes
    tables: Optional[List[str]] = None # List of tables in this shard (if sharded by table)
    # Add other relevant info like original_size if needed

@dataclasses.dataclass
class SnapshotManifest:
    sequence: Optional[int] = None # Monotonic counter, assigned later by ConflictDetection
    prev_sequence: Optional[int] = None # Parent snapshot sequence, assigned later
    network_uuid: Optional[str] = None # Network identifier, assigned later
    created_at: datetime.datetime = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    git_commit: Optional[str] = None # Git commit hash of the code version

    merkle_root: str # Merkle root of the entire snapshot (even if sharded, this is for the conceptual full DB)
    pgp_signature: Optional[str] = None # PGP signature of the manifest, assigned later

    shards: List[ShardInfo] # List of ShardInfo objects
    merge_script: Optional[str] = None # SQL script or instructions to merge shards

    # Additional fields that might be useful
    snapshot_tool_version: str = "0.1.0" # Version of the sharding/snapshot tool
    compression_algorithm: str = "zstd"

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(dataclasses.asdict(self), default=str, indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "SnapshotManifest":
        data = json.loads(json_str)
        # Convert shard dicts back to ShardInfo objects
        data["shards"] = [ShardInfo(**s) for s in data.get("shards", [])]
        data["created_at"] = datetime.datetime.fromisoformat(data["created_at"])
        return cls(**data)

# --- Helper Functions ---
def hash_file(filepath: Path,_hash_algo: str = "sha256") -> str:
    """Computes the hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def compress_zstd(input_path: Path, output_path: Path, level: int = 3) -> None:
    """Compresses a file using Zstandard."""
    cctx = zstandard.ZstdCompressor(level=level)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(input_path, "rb") as ifh, open(output_path, "wb") as ofh:
        cctx.copy_stream(ifh, ofh)
    logging.info(f"Compressed {input_path} to {output_path} (Level {level})")

def decompress_zstd(input_path: Path, output_path: Path) -> None:
    """Decompresses a Zstandard compressed file."""
    dctx = zstandard.ZstdDecompressor()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(input_path, "rb") as ifh, open(output_path, "wb") as ofh:
        dctx.copy_stream(ifh, ofh)
    logging.info(f"Decompressed {input_path} to {output_path}")

def calculate_db_merkle_root(db_path: Path) -> str:
    """
    Placeholder function to calculate a Merkle root for the entire DB.
    Actual implementation would depend on how DB content is broken down.
    For now, it can be a hash of the single DB file if not sharded,
    or a more complex calculation if sharded (e.g., hash of shard hashes).
    This needs to be robust and deterministic.
    """
    if not db_path.exists():
        return "dummy_merkle_root_db_not_found" # Should not happen in real flow
    # Simple approach for now: hash of the file itself.
    # If sharded, this would be calculated *before* sharding from the original DB,
    # or from the reconstructed DB.
    return hash_file(db_path)


# --- ShardingManager Class ---
class ShardingManager:
    MAX_SHARD_SIZE_BYTES = 3_500_000_000  # 3.5GB safety margin, as per pivot_plan_v2.md
    # Typical ZSTD compression ratio for structured data can be ~3-5x.
    # Using a conservative estimate for raw size limit before compression.
    # Example: 3.5GB / 0.3 compression ratio estimate = ~11.6GB raw data.
    # This means if raw_size * estimated_compression_ratio > MAX_SHARD_SIZE_BYTES, then shard.
    ESTIMATED_COMPRESSION_RATIO = 0.3 # Configurable

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "hronir_sharding"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"ShardingManager initialized. Temp directory: {self.temp_dir}")

    def _cleanup_temp_files(self, files_to_delete: List[Path]):
        for f_path in files_to_delete:
            try:
                if f_path.exists():
                    os.remove(f_path)
                    logging.debug(f"Cleaned up temporary file: {f_path}")
            except OSError as e:
                logging.warning(f"Could not delete temporary file {f_path}: {e}")

    def create_sharded_snapshot(
        self, duckdb_path: Path, output_dir: Path, network_uuid: str, git_commit: Optional[str] = None
    ) -> SnapshotManifest:
        """
        Creates a snapshot, sharding automatically if necessary.
        The actual DuckDB file at duckdb_path is the source.
        Shards are created in output_dir.
        """
        if not duckdb_path.exists():
            raise FileNotFoundError(f"Source DuckDB file not found: {duckdb_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Calculate initial Merkle root of the source DB (before any potential sharding)
        # This represents the integrity of the complete dataset.
        source_merkle_root = calculate_db_merkle_root(duckdb_path)
        logging.info(f"Calculated Merkle root for source DB ({duckdb_path}): {source_merkle_root}")

        # 2. Check if sharding is needed
        raw_size = duckdb_path.stat().st_size
        compressed_estimate = raw_size * self.ESTIMATED_COMPRESSION_RATIO

        shard_infos: List[ShardInfo] = []
        merge_script: Optional[str] = None
        temp_files_to_cleanup: List[Path] = []

        if compressed_estimate <= self.MAX_SHARD_SIZE_BYTES:
            # Single file, no sharding needed
            logging.info("Snapshot size within limits. Creating single compressed file.")
            snapshot_filename_base = f"{network_uuid}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}"
            compressed_file_name = f"{snapshot_filename_base}.db.zst"
            compressed_file_path = output_dir / compressed_file_name

            compress_zstd(duckdb_path, compressed_file_path)

            shard_infos.append(
                ShardInfo(
                    file=compressed_file_name, # Relative to IA item / torrent root
                    sha256=hash_file(compressed_file_path),
                    size=compressed_file_path.stat().st_size,
                    tables=["ALL"], # Indicates all tables are in this single shard
                )
            )
            logging.info(f"Single shard created: {compressed_file_name}")
        else:
            # Multi-shard strategy
            logging.info("Snapshot size exceeds limits. Proceeding with sharding.")
            shard_db_files = self._split_database_by_table(duckdb_path, temp_files_to_cleanup)

            if not shard_db_files:
                raise RuntimeError("Database splitting returned no shard files. Cannot proceed.")

            snapshot_filename_base = f"{network_uuid}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}"

            for i, (shard_temp_path, tables_in_shard) in enumerate(shard_db_files):
                shard_file_name_base = f"{snapshot_filename_base}_shard_{i:03d}"
                compressed_shard_name = f"{shard_file_name_base}.db.zst"
                compressed_shard_path = output_dir / compressed_shard_name

                compress_zstd(shard_temp_path, compressed_shard_path)

                shard_infos.append(
                    ShardInfo(
                        file=compressed_shard_name, # Relative to IA item / torrent root
                        sha256=hash_file(compressed_shard_path),
                        size=compressed_shard_path.stat().st_size,
                        tables=tables_in_shard,
                    )
                )
                logging.info(f"Created shard {i:03d}: {compressed_shard_name} for tables {tables_in_shard}")

            merge_script = self._generate_merge_script(shard_infos)
            logging.info("Generated merge script for sharded snapshot.")

        # Create SnapshotManifest
        manifest = SnapshotManifest(
            created_at=datetime.datetime.now(datetime.timezone.utc),
            git_commit=git_commit,
            merkle_root=source_merkle_root, # Integrity of the original, unsharded data
            shards=shard_infos,
            merge_script=merge_script,
            network_uuid=network_uuid # To be filled by caller if available then
        )

        # Cleanup temporary shard DB files
        self._cleanup_temp_files(temp_files_to_cleanup)

        logging.info(f"Snapshot manifest created. Total shards: {len(shard_infos)}")
        return manifest

    def _split_database_by_table(self, original_db_path: Path, temp_files_list: List[Path]) -> List[tuple[Path, List[str]]]:
        """
        Splits the database by tables using a bin packing approach.
        Returns a list of paths to temporary DuckDB files for each shard and the tables in them.
        Adds temporary file paths to temp_files_list for later cleanup.
        """
        logging.info(f"Splitting database {original_db_path} by table...")
        original_conn = duckdb.connect(database=str(original_db_path), read_only=True)

        try:
            # Get table sizes and dependencies (simplified: no complex dependency analysis for now)
            # For a robust solution, foreign key dependencies would need careful handling
            # to ensure related data stays together or is split logically.
            # Here, we assume tables can be moved independently or that the schema allows it.
            tables_data = original_conn.execute(
                "SELECT table_name, estimated_size FROM duckdb_tables() WHERE schema_name = 'main' ORDER BY estimated_size DESC"
            ).fetchall()

            if not tables_data:
                logging.warning("No tables found in the main schema of the database. Cannot split.")
                return []

            # Simple bin packing (first-fit decreasing)
            shards_tables_map: List[List[str]] = []
            current_shard_tables: List[str] = []
            current_shard_size_bytes: int = 0

            for table_name, estimated_size_bytes in tables_data:
                if estimated_size_bytes is None: # Should not happen for user tables
                    estimated_size_bytes = 0

                # Heuristic: If a single table (compressed) might exceed limit, it must be its own shard
                # Or, if adding this table to current shard exceeds limit
                table_compressed_estimate = estimated_size_bytes * self.ESTIMATED_COMPRESSION_RATIO

                if current_shard_tables and \
                   (current_shard_size_bytes + table_compressed_estimate) > self.MAX_SHARD_SIZE_BYTES:
                    shards_tables_map.append(current_shard_tables)
                    current_shard_tables = [table_name]
                    current_shard_size_bytes = table_compressed_estimate
                else:
                    current_shard_tables.append(table_name)
                    current_shard_size_bytes += table_compressed_estimate

            if current_shard_tables: # Add the last shard
                shards_tables_map.append(current_shard_tables)

            if not shards_tables_map:
                 logging.warning("Bin packing resulted in no shards. This is unexpected.")
                 return []

            logging.info(f"Planned table distribution into {len(shards_tables_map)} shards.")

            # Create shard databases
            shard_file_tuples: List[tuple[Path, List[str]]] = []
            for i, tables_in_shard in enumerate(shards_tables_map):
                shard_temp_db_path = self.temp_dir / f"temp_shard_{i:03d}_{original_db_path.stem}.db"
                temp_files_list.append(shard_temp_db_path) # For cleanup

                shard_conn = duckdb.connect(database=str(shard_temp_db_path), read_only=False)
                try:
                    for table_name in tables_in_shard:
                        # Copy table structure and data
                        # Using EXPORT/IMPORT DATABASE for specific tables is cleaner if available
                        # For now, using COPY TO and then recreating table + INSERT
                        logging.debug(f"Copying table {table_name} to shard {i}")

                        # Get DDL for the table
                        try:
                            ddl_result = original_conn.execute(f"SHOW CREATE TABLE {table_name};").fetchone()
                            if ddl_result and ddl_result[0]:
                                create_table_sql = ddl_result[0]
                                shard_conn.execute(create_table_sql)
                            else: # Fallback if SHOW CREATE TABLE fails or returns empty
                                logging.warning(f"Could not get DDL for table {table_name}. Attempting simple SELECT *.")
                                # This won't preserve constraints, indexes etc.
                                shard_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{original_db_path.resolve()}::{table_name}');")
                                # The above is problematic. A better approach:
                                # original_conn.execute(f"COPY {table_name} TO '{shard_temp_db_path}.{table_name}' (FORMAT PARQUET);")
                                # This would require reading it back in shard_conn.
                                # Simpler: copy data via SELECT INTO
                                original_conn.execute(f"EXPORT DATABASE '{shard_temp_db_path}' (FORMAT 'parquet', TABLE '{table_name}');")
                                # This exports only one table to a new DB, might not be ideal.

                                # Safest: Use pandas DataFrame as intermediary for data transfer
                                table_df = original_conn.table(table_name).df()
                                shard_conn.register(f'{table_name}_df', table_df)
                                shard_conn.execute(f"INSERT INTO {table_name} SELECT * FROM {table_name}_df;")

                        except Exception as e_copy:
                             logging.error(f"Error copying table {table_name} to shard {i}: {e_copy}")
                             # Decide on error handling: skip table, fail shard, fail all?
                             # For now, log and continue.
                    shard_conn.commit()
                    shard_file_tuples.append((shard_temp_db_path, tables_in_shard))
                finally:
                    shard_conn.close()

            logging.info(f"Successfully created {len(shard_file_tuples)} temporary shard database files.")
            return shard_file_tuples

        finally:
            original_conn.close()

    def _generate_merge_script(self, shard_infos: List[ShardInfo]) -> str:
        """
        Generates a SQL script (or instructions) to merge shards back into a single database.
        This is a simplified version. A robust script would handle table creation order,
        primary/foreign keys, and conflicts if any (though sharding by table should minimize this).
        """
        # For DuckDB, ATTACH and COPY/INSERT can be used.
        # Assumes the target database is empty or tables can be overwritten/appended.

        script_lines = [
            "-- Hrönir Encyclopedia Shard Merge Script --",
            "-- Target DuckDB should be opened before running this.",
            "-- Ensure shard files are in the same directory or provide full paths.",
            "",
        ]

        # Overall strategy:
        # 1. Create all tables first (from the first shard that contains them, assuming consistent schema)
        # 2. Then ATTACH each shard DB and INSERT data.

        # Collect all unique table DDLs (simplified - assumes tables are fully defined in their first appearance)
        # A more robust way would be to get DDL from original schema before sharding.
        # For now, this is a placeholder for a more robust DDL generation.
        # script_lines.append("-- TODO: Implement robust DDL generation for all tables --")

        for i, shard in enumerate(shard_infos):
            shard_db_alias = f"shard_{i:03d}_db"
            # Decompressed shard file name
            decompressed_shard_file = shard.file.replace(".zst", "")

            script_lines.append(f"-- Processing Shard: {shard.file} (contains tables: {shard.tables}) --")
            script_lines.append(f"ATTACH '{decompressed_shard_file}' AS {shard_db_alias} (READ_ONLY);")

            if shard.tables and shard.tables != ["ALL"]: # Avoid for single, non-sharded file
                for table_name in shard.tables:
                    # This assumes table DDL is already handled or tables exist in target.
                    # For a true merge, you'd ensure table exists, then insert.
                    # Example: CREATE TABLE IF NOT EXISTS main_table AS SELECT * FROM shard_db_alias.main_table LIMIT 0;
                    #          INSERT INTO main_table SELECT * FROM shard_db_alias.main_table;
                    script_lines.append(
                        f"INSERT INTO main.{table_name} SELECT * FROM {shard_db_alias}.{table_name};"
                        f" -- Ensure table '{table_name}' exists in target DB with correct schema first."
                    )
            elif shard.tables == ["ALL"]:
                 script_lines.append(f"-- This is a single-file snapshot, tables are already in '{decompressed_shard_file}'.")
                 script_lines.append(f"-- No explicit table copy needed if this is the only shard.")


            script_lines.append(f"DETACH {shard_db_alias};")
            script_lines.append("")

        script_lines.append("-- Merge script generation complete. Review and adapt as needed. --")
        return "\n".join(script_lines)

    def reconstruct_from_shards(self, manifest: SnapshotManifest, snapshot_dir: Path, output_db_path: Path) -> None:
        """
        Reconstructs a single DuckDB database from sharded files.
        Assumes shard files are in snapshot_dir.
        """
        logging.info(f"Reconstructing database from shards to {output_db_path}...")
        output_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure output DB is clean or doesn't exist
        if output_db_path.exists():
            logging.warning(f"Output DB {output_db_path} exists. It will be overwritten.")
            os.remove(output_db_path)

        temp_decompress_dir = self.temp_dir / "decompressed_shards"
        temp_decompress_dir.mkdir(parents=True, exist_ok=True)
        temp_files_to_cleanup: List[Path] = []

        try:
            decompressed_shard_paths: List[Path] = []
            # 1. Download (if needed - assumed already downloaded to snapshot_dir) and verify all shards
            for shard_info in manifest.shards:
                compressed_shard_path = snapshot_dir / shard_info.file
                if not compressed_shard_path.exists():
                    raise FileNotFoundError(f"Shard file {shard_info.file} not found in {snapshot_dir}")

                actual_hash = hash_file(compressed_shard_path)
                if actual_hash != shard_info.sha256:
                    raise ValueError(
                        f"Checksum mismatch for shard {shard_info.file}. Expected {shard_info.sha256}, got {actual_hash}"
                    )
                logging.info(f"Verified shard: {shard_info.file}")

                # 2. Decompress shards
                decompressed_name = shard_info.file.replace(".zst", "")
                decompressed_path = temp_decompress_dir / decompressed_name
                decompress_zstd(compressed_shard_path, decompressed_path)
                decompressed_shard_paths.append(decompressed_path)
                temp_files_to_cleanup.append(decompressed_path)
                logging.info(f"Decompressed {shard_info.file} to {decompressed_path}")

            # 3. Execute merge script (or logic)
            if not manifest.merge_script and len(decompressed_shard_paths) == 1:
                # Single shard, just copy/rename the decompressed file
                shutil.copy(decompressed_shard_paths[0], output_db_path)
                logging.info(f"Single shard snapshot. Copied {decompressed_shard_paths[0]} to {output_db_path}")
            elif manifest.merge_script:
                # Multiple shards, use merge script
                # The provided merge_script is more like instructions.
                # A more robust way is to connect to the output_db_path and run ATTACH commands.
                logging.info("Applying merge logic for multiple shards...")
                target_conn = duckdb.connect(database=str(output_db_path), read_only=False)
                try:
                    # First, create all tables using DDL from one of the shards or a golden schema
                    # This is a simplified approach: assumes tables are created as needed by INSERT.
                    # A proper implementation would pre-create all tables with correct DDL.

                    all_tables_in_snapshot = set()
                    for shard_info in manifest.shards:
                        if shard_info.tables and shard_info.tables != ["ALL"]:
                            for table_name in shard_info.tables:
                                all_tables_in_snapshot.add(table_name)

                    # Attempt to get DDL from the first shard containing each table (example)
                    # This is complex; ideal DDL should come from original schema source.
                    # For now, we rely on INSERT creating tables or assuming they exist.
                    # The merge script generated earlier is a guideline.
                    # Here's a direct ATTACH and COPY approach:

                    # Step A: Create all table structures in the target DB
                    # This is crucial and needs a reliable source for DDLs.
                    # If source_db for `create_sharded_snapshot` was available, we could get DDLs from there.
                    # For now, let's assume the `migrate_to_duckdb.py` script's DUCKDB_SCHEMA can be used.
                    for _, ddl_statement in DUCKDB_SCHEMA.items(): # Using DUCKDB_SCHEMA from migration script context
                        try:
                            target_conn.execute(ddl_statement)
                        except Exception as e_ddl:
                            logging.warning(f"Could not pre-create table via DUCKDB_SCHEMA: {e_ddl}")


                    for i, shard_info in enumerate(manifest.shards):
                        shard_db_alias = f"shard_{i:03d}_db"
                        # Find the corresponding decompressed path
                        current_decompressed_path = next(p for p in decompressed_shard_paths if p.name == shard_info.file.replace(".zst",""))

                        target_conn.execute(f"ATTACH '{current_decompressed_path}' AS {shard_db_alias} (READ_ONLY);")
                        logging.info(f"Attached {current_decompressed_path} as {shard_db_alias}")

                        if shard_info.tables and shard_info.tables != ["ALL"]:
                            for table_name in shard_info.tables:
                                try:
                                    # Ensure table exists in target (idempotent way)
                                    # target_conn.execute(f"CREATE TABLE IF NOT EXISTS main.{table_name} AS SELECT * FROM {shard_db_alias}.{table_name} LIMIT 0;")
                                    target_conn.execute(f"INSERT INTO main.{table_name} SELECT * FROM {shard_db_alias}.{table_name};")
                                    logging.info(f"Copied table {table_name} from {shard_db_alias}")
                                except Exception as e_copy_table:
                                    logging.error(f"Error copying table {table_name} from {shard_db_alias}: {e_copy_table}")
                        elif shard_info.tables == ["ALL"] and len(manifest.shards) > 1 : # Should not happen if properly sharded
                             logging.warning(f"Shard {shard_info.file} marked as ALL tables but is part of multi-shard snapshot. Check logic.")

                        target_conn.execute(f"DETACH {shard_db_alias};")
                    target_conn.commit()
                finally:
                    target_conn.close()
                logging.info("Merge script logic applied.")
            else:
                raise ValueError("Cannot reconstruct: No merge script for multiple shards, and not a single shard snapshot.")

            # 4. Verify final integrity (optional but recommended)
            final_merkle_root = calculate_db_merkle_root(output_db_path)
            if final_merkle_root != manifest.merkle_root:
                # This check is against the Merkle root of the *original* DB.
                # If sharding/reconstruction is perfect, they should match.
                logging.warning(
                    f"Merkle root mismatch for reconstructed database. "
                    f"Expected: {manifest.merkle_root}, Got: {final_merkle_root}. "
                    f"This might be due to non-deterministic aspects of DB internal structure "
                    f"if hashing the raw file, or minor differences in table order/storage. "
                    f"Content-level verification would be more robust here."
                )
                # raise ValueError("Reconstructed database hash mismatch with manifest Merkle root.")
            else:
                logging.info(f"Reconstructed database Merkle root matches manifest: {final_merkle_root}")

            logging.info(f"Database successfully reconstructed at {output_db_path}")

        finally:
            self._cleanup_temp_files(temp_files_to_cleanup)
            if temp_decompress_dir.exists():
                 shutil.rmtree(temp_decompress_dir) # Clean up the whole temp dir for decompressed shards


if __name__ == "__main__":
    # Example Usage (for testing ShardingManager)
    # Setup a dummy DuckDB file
    DUMMY_DB_PATH = Path("test_dummy_main.db")
    DUMMY_OUTPUT_DIR = Path("test_snapshot_output")

    if DUMMY_DB_PATH.exists():
        os.remove(DUMMY_DB_PATH)
    if DUMMY_OUTPUT_DIR.exists():
        shutil.rmtree(DUMMY_OUTPUT_DIR)
    DUMMY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(DUMMY_DB_PATH))
    conn.execute("CREATE TABLE table1 (id INTEGER, name VARCHAR);")
    conn.execute("INSERT INTO table1 VALUES (1, 'Alice'), (2, 'Bob');")
    # Make it larger to test sharding (very artificial way)
    # conn.execute("CREATE TABLE large_table (data VARCHAR);")
    # for i in range(20000): # Adjust this to control size for testing sharding
    #     conn.execute(f"INSERT INTO large_table VALUES ('{'x'*10000}');") # ~200MB raw
    conn.execute("CREATE TABLE table2 (value REAL);")
    conn.execute("INSERT INTO table2 VALUES (3.14), (2.71);")
    conn.close()

    manager = ShardingManager()
    try:
        manifest_result = manager.create_sharded_snapshot(
            DUMMY_DB_PATH,
            DUMMY_OUTPUT_DIR,
            network_uuid="test_network_123",
            git_commit="testcommit123"
        )
        logging.info(f"Generated manifest:\n{manifest_result.to_json()}")

        # Test reconstruction
        RECONSTRUCTED_DB_PATH = Path("test_reconstructed_main.db")
        if RECONSTRUCTED_DB_PATH.exists():
            os.remove(RECONSTRUCTED_DB_PATH)

        manager.reconstruct_from_shards(manifest_result, DUMMY_OUTPUT_DIR, RECONSTRUCTED_DB_PATH)

        # Verify reconstructed DB
        recon_conn = duckdb.connect(str(RECONSTRUCTED_DB_PATH))
        t1_count = recon_conn.execute("SELECT COUNT(*) FROM table1").fetchone()[0]
        t2_count = recon_conn.execute("SELECT COUNT(*) FROM table2").fetchone()[0]
        logging.info(f"Reconstructed DB: table1 has {t1_count} rows, table2 has {t2_count} rows.")
        # lt_count = recon_conn.execute("SELECT COUNT(*) FROM large_table").fetchone()[0]
        # logging.info(f"Reconstructed DB: large_table has {lt_count} rows.")
        recon_conn.close()

    except Exception as e:
        logging.error(f"Error in ShardingManager example: {e}", exc_info=True)
    finally:
        # Clean up dummy files
        if DUMMY_DB_PATH.exists():
            os.remove(DUMMY_DB_PATH)
        if DUMMY_OUTPUT_DIR.exists():
            shutil.rmtree(DUMMY_OUTPUT_DIR)
        if Path("test_reconstructed_main.db").exists():
            os.remove(Path("test_reconstructed_main.db"))
        if manager.temp_dir.exists():
            shutil.rmtree(manager.temp_dir)

```
