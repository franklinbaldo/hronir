import pytest

from hronir_encyclopedia import storage


@pytest.fixture(autouse=True)
def enable_duckdb(tmp_path, monkeypatch):
    db_file = tmp_path / "test.duckdb"
    monkeypatch.setenv("HRONIR_USE_DUCKDB", "1")
    monkeypatch.setenv("HRONIR_DUCKDB_PATH", str(db_file))
    # Create a DataManager instance for the test environment
    # No longer setting a global instance in storage module
    test_dm = storage.DataManager(db_path=str(db_file))
    test_dm.initialize_and_load(clear_existing_data=True) # Ensure clean state for each test
    yield test_dm # Provide the instance to tests that request this fixture

    # Cleanup: Close the connection if necessary, or let DuckDB handle it on process exit.
    # If tests modify the DB, the tmp_path fixture handles temp directory removal.
    if hasattr(test_dm.backend, 'conn') and test_dm.backend.conn:
        test_dm.backend.conn.close()
