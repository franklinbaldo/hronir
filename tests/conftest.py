import pytest

from hronir_encyclopedia import storage


@pytest.fixture(autouse=True)
def enable_duckdb(tmp_path, monkeypatch):
    db_file = tmp_path / "test.duckdb"
    monkeypatch.setenv("HRONIR_USE_DUCKDB", "1")
    monkeypatch.setenv("HRONIR_DUCKDB_PATH", str(db_file))
    storage.DataManager._instance = None
    storage.data_manager = storage.DataManager()
    yield
    storage.DataManager._instance = None
