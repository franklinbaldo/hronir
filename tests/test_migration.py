import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

# Add script directory to sys.path to allow import of migrate_to_duckdb
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.append(str(SCRIPT_DIR))

# Conditional import for testing
if SCRIPT_DIR.joinpath("migrate_to_duckdb.py").exists():
    import migrate_to_duckdb
else:
    migrate_to_duckdb = None


# --- Fixtures ---

@pytest.fixture(scope="function")
def temp_data_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create temporary data directories for a test run."""
    base_dir = tmp_path / "hronir_data_root"
    base_dir.mkdir()

    paths_dir = base_dir / "narrative_paths"
    paths_dir.mkdir()
    ratings_dir = base_dir / "ratings"
    ratings_dir.mkdir()
    transactions_dir = base_dir / "data" / "transactions"
    transactions_dir.mkdir(parents=True)
    library_dir = base_dir / "the_library"
    library_dir.mkdir()
    backup_dir = base_dir / "data" / "backup"
    # backup_dir.mkdir(parents=True) # Script will create this
    db_dir = base_dir / "data"
    db_dir.mkdir(parents=True)

    # Create dummy files
    # Paths
    pd.DataFrame({
        "path_uuid": ["path1", "path2"], "position": [0, 0],
        "prev_uuid": [None, None], "uuid": ["hronirA", "hronirB"],
        "status": ["QUALIFIED", "PENDING"], "mandate_id": [None, None],
        "created_at": [datetime.datetime.now(datetime.timezone.utc).isoformat()] * 2
    }).to_csv(paths_dir / "narrative_paths_position_0.csv", index=False)

    # Votes
    pd.DataFrame({
        "uuid": ["vote1"], "position": [0], "voter": ["path1"],
        "winner": ["hronirA"], "loser": ["hronirB"],
        "created_at": [datetime.datetime.now(datetime.timezone.utc).isoformat()]
    }).to_csv(ratings_dir / "votes.csv", index=False)

    # Transactions
    tx_content1 = {
        "session_id": "session1", "initiating_path_uuid": "path1",
        "verdicts_processed": [{"position": 0, "winner_hrönir_uuid": "hronirA", "loser_hrönir_uuid": "hronirB"}],
        "promotions_granted": []
    }
    tx1 = {"uuid": "tx1", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "prev_uuid": None, "content": tx_content1}
    with open(transactions_dir / "tx1.json", "w") as f:
        json.dump(tx1, f)

    # Library
    hronirA_dir = library_dir / "hronirA"
    hronirA_dir.mkdir()
    (hronirA_dir / "index.md").write_text("Content of Hronir A")

    hronirB_dir = library_dir / "hronirB"
    hronirB_dir.mkdir()
    (hronirB_dir / "index.md").write_text("Content of Hronir B")

    return {
        "base": base_dir,
        "paths": paths_dir,
        "ratings": ratings_dir,
        "transactions": transactions_dir,
        "library": library_dir,
        "backup_root": backup_dir.parent, # data/
        "db_path": db_dir / "test_encyclopedia.duckdb"
    }

# --- Helper Functions ---
def run_migration_script(cwd: Path, *args) -> subprocess.CompletedProcess:
    """Runs the migration script as a subprocess."""
    if not migrate_to_duckdb:
        pytest.skip("migrate_to_duckdb.py not found, skipping integration test.")

    script_path = Path(migrate_to_duckdb.__file__).resolve()
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=False)


# --- Test Cases ---

@pytest.mark.skipif(migrate_to_duckdb is None, reason="migrate_to_duckdb.py not found")
def test_migration_script_arg_parsing_defaults(temp_data_dirs):
    """Test basic argument parsing and default values (indirectly)."""
    # This test primarily ensures the script can be called.
    # More specific arg parsing tests would mock argparse.
    res = run_migration_script(
        temp_data_dirs["base"],
        "--db-path", str(temp_data_dirs["db_path"]),
        "--csv-paths-dir", str(temp_data_dirs["paths"]),
        "--csv-ratings-dir", str(temp_data_dirs["ratings"]),
        "--transactions-json-dir", str(temp_data_dirs["transactions"]),
        "--hronirs-library-dir", str(temp_data_dirs["library"]),
        "--backup-dir", str(temp_data_dirs["backup_root"]), # data/
    )
    assert res.returncode == 0, f"Script failed: {res.stderr}"
    assert "Starting data migration to DuckDB" in res.stdout
    assert "Data migration to" in res.stdout
    assert str(temp_data_dirs["db_path"].name) in res.stdout # Check if specified db name is mentioned

@pytest.mark.skipif(migrate_to_duckdb is None, reason="migrate_to_duckdb.py not found")
def test_backup_functionality(temp_data_dirs: dict[str, Path]):
    """Test the --backup flag and backup directory structure."""
    res = run_migration_script(
        temp_data_dirs["base"],
        "--backup",
        "--db-path", str(temp_data_dirs["db_path"]),
        "--csv-paths-dir", str(temp_data_dirs["paths"]),
        "--csv-ratings-dir", str(temp_data_dirs["ratings"]),
        "--transactions-json-dir", str(temp_data_dirs["transactions"]),
        "--hronirs-library-dir", str(temp_data_dirs["library"]),
        "--backup-dir", str(temp_data_dirs["backup_root"] / "backup") # Explicitly data/backup
    )
    assert res.returncode == 0, f"Script failed: {res.stderr}"
    assert "Backing up data to" in res.stdout

    backup_base = temp_data_dirs["backup_root"] / "backup" # data/backup
    assert backup_base.exists()

    # Check for a timestamped backup directory
    backup_dirs = list(backup_base.iterdir())
    assert len(backup_dirs) == 1, "Should be one timestamped backup directory"
    ts_backup_dir = backup_dirs[0]
    assert ts_backup_dir.is_dir()

    # Check for copied data
    assert (ts_backup_dir / temp_data_dirs["paths"].name / "narrative_paths_position_0.csv").exists()
    assert (ts_backup_dir / temp_data_dirs["ratings"].name / "votes.csv").exists()
    assert (ts_backup_dir / temp_data_dirs["transactions"].name / "tx1.json").exists()
    assert (ts_backup_dir / temp_data_dirs["library"].name / "hronirA" / "index.md").exists()

@pytest.mark.skipif(migrate_to_duckdb is None, reason="migrate_to_duckdb.py not found")
def test_schema_creation_and_data_migration(temp_data_dirs: dict[str, Path]):
    """Test DuckDB schema creation and data migration."""
    db_file = temp_data_dirs["db_path"]
    res = run_migration_script(
        temp_data_dirs["base"],
        "--db-path", str(db_file),
        "--csv-paths-dir", str(temp_data_dirs["paths"]),
        "--csv-ratings-dir", str(temp_data_dirs["ratings"]),
        "--transactions-json-dir", str(temp_data_dirs["transactions"]),
        "--hronirs-library-dir", str(temp_data_dirs["library"]),
    )
    assert res.returncode == 0, f"Script failed: {res.stderr}"
    assert db_file.exists(), "DuckDB file was not created"

    conn = duckdb.connect(str(db_file), read_only=True)

    # Test schema
    tables = conn.execute("SHOW TABLES;").fetchall()
    table_names = {t[0] for t in tables}
    assert "paths" in table_names
    assert "votes" in table_names
    assert "transactions" in table_names
    assert "hronirs" in table_names
    # assert "snapshots_meta" in table_names # This one is optional for migration

    # Test data migration
    paths_count = conn.execute("SELECT COUNT(*) FROM paths;").fetchone()[0]
    assert paths_count == 2, "Incorrect number of paths migrated"

    path_data = conn.execute("SELECT path_uuid, uuid FROM paths WHERE position = 0 AND path_uuid = 'path1';").fetchone()
    assert path_data is not None
    assert path_data[0] == "path1"
    assert path_data[1] == "hronirA"

    votes_count = conn.execute("SELECT COUNT(*) FROM votes;").fetchone()[0]
    assert votes_count == 1, "Incorrect number of votes migrated"
    vote_data = conn.execute("SELECT uuid, winner FROM votes WHERE uuid = 'vote1';").fetchone()
    assert vote_data is not None
    assert vote_data[1] == "hronirA"

    transactions_count = conn.execute("SELECT COUNT(*) FROM transactions;").fetchone()[0]
    assert transactions_count == 1, "Incorrect number of transactions migrated"
    tx_data_row = conn.execute("SELECT uuid, session_id FROM transactions WHERE uuid = 'tx1';").fetchone()
    assert tx_data_row is not None
    assert tx_data_row[1] == "session1" # Check session_id from content

    hronirs_count = conn.execute("SELECT COUNT(*) FROM hronirs;").fetchone()[0]
    assert hronirs_count == 2, "Incorrect number of hronirs migrated"
    hronir_content = conn.execute("SELECT content FROM hronirs WHERE uuid = 'hronirA';").fetchone()[0]
    assert hronir_content == "Content of Hronir A"

    conn.close()

@pytest.mark.skipif(migrate_to_duckdb is None, reason="migrate_to_duckdb.py not found")
def test_enable_sharding_flag(temp_data_dirs: dict[str, Path], capsys):
    """Test --enable-sharding flag (currently a placeholder in script)."""
    # This test just checks if the warning for not-implemented sharding appears.
    # It doesn't test actual sharding logic.
    res = run_migration_script(
        temp_data_dirs["base"],
        "--enable-sharding",
        "--db-path", str(temp_data_dirs["db_path"]),
        "--csv-paths-dir", str(temp_data_dirs["paths"]),
        "--csv-ratings-dir", str(temp_data_dirs["ratings"]),
        "--transactions-json-dir", str(temp_data_dirs["transactions"]),
        "--hronirs-library-dir", str(temp_data_dirs["library"]),
    )
    assert res.returncode == 0, f"Script failed: {res.stderr}"
    assert "--enable-sharding is specified, but sharding logic is not fully implemented" in res.stdout

@pytest.mark.skipif(migrate_to_duckdb is None, reason="migrate_to_duckdb.py not found")
def test_empty_or_missing_sources(temp_data_dirs: dict[str, Path]):
    """Test migration with empty or missing source directories/files."""
    # Remove some source data
    shutil.rmtree(temp_data_dirs["paths"])
    (temp_data_dirs["base"] / "narrative_paths").mkdir() # Recreate empty dir

    (temp_data_dirs["ratings"] / "votes.csv").unlink() # Remove votes file

    db_file = temp_data_dirs["db_path"]
    res = run_migration_script(
        temp_data_dirs["base"],
        "--db-path", str(db_file),
        "--csv-paths-dir", str(temp_data_dirs["paths"]), # Now empty
        "--csv-ratings-dir", str(temp_data_dirs["ratings"]), # votes.csv missing
        "--transactions-json-dir", str(temp_data_dirs["transactions"]),
        "--hronirs-library-dir", str(temp_data_dirs["library"]),
    )
    assert res.returncode == 0, f"Script failed: {res.stderr}"
    assert "No path CSV files found or processed" in res.stdout
    assert "Votes CSV file not found" in res.stdout

    conn = duckdb.connect(str(db_file), read_only=True)
    paths_count = conn.execute("SELECT COUNT(*) FROM paths;").fetchone()[0]
    assert paths_count == 0
    votes_count = conn.execute("SELECT COUNT(*) FROM votes;").fetchone()[0]
    assert votes_count == 0
    transactions_count = conn.execute("SELECT COUNT(*) FROM transactions;").fetchone()[0]
    assert transactions_count == 1 # Transactions should still load
    conn.close()

# Example of how one might test the main function directly if preferred over subprocess
# @pytest.mark.skipif(migrate_to_duckdb is None, reason="migrate_to_duckdb.py not found")
# def test_migration_main_direct(temp_data_dirs, monkeypatch, caplog):
#     """Test the main function of the migration script directly."""
#     db_file = temp_data_dirs["db_path"]

#     args_list = [
#         "--db-path", str(db_file),
#         "--csv-paths-dir", str(temp_data_dirs["paths"]),
#         "--csv-ratings-dir", str(temp_data_dirs["ratings"]),
#         "--transactions-json-dir", str(temp_data_dirs["transactions"]),
#         "--hronirs-library-dir", str(temp_data_dirs["library"]),
#         "--backup-dir", str(temp_data_dirs["backup_root"] / "backup"),
#         "--backup"
#     ]

#     # Monkeypatch sys.argv and current working directory if necessary
#     monkeypatch.setattr(sys, "argv", ["migrate_to_duckdb.py"] + args_list)
#     monkeypatch.chdir(temp_data_dirs["base"]) # Run as if CWD is the base data dir

#     with caplog.at_level(logging.INFO):
#         migrate_to_duckdb.main()

#     assert db_file.exists()
#     assert "Data migration to" in caplog.text
#     assert "Backup completed." in caplog.text

#     # Add DuckDB queries here to verify data
#     conn = duckdb.connect(str(db_file), read_only=True)
#     paths_count = conn.execute("SELECT COUNT(*) FROM paths;").fetchone()[0]
#     assert paths_count == 2
#     conn.close()

```
