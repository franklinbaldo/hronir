import sqlite3
from pathlib import Path
import pandas as pd
import os
import tempfile

_CONNECTION_MAP: dict[int, dict[str, Path]] = {}

class CsvDatabase:
    """Context manager loading CSV files into an SQLite database."""

    def __init__(self, ratings_dir: Path | str = "ratings", fork_dir: Path | str = "forking_path", filename: str | None = None):
        self.ratings_dir = Path(ratings_dir)
        self.fork_dir = Path(fork_dir)
        self.filename = filename or ":memory:"
        self._conn: sqlite3.Connection | None = None
        self._mapping: dict[str, Path] = {}

    def _load_csv(self, csv: Path) -> None:
        table = csv.stem
        if csv.exists() and csv.stat().st_size:
            df = pd.read_csv(csv)
        else:
            df = pd.DataFrame()
        df.to_sql(table, self._conn, index=False, if_exists="replace")
        self._mapping[table] = csv

    def _load(self) -> None:
        self.ratings_dir.mkdir(exist_ok=True)
        self.fork_dir.mkdir(exist_ok=True)
        for csv in self.ratings_dir.glob("*.csv"):
            self._load_csv(csv)
        for csv in self.fork_dir.glob("*.csv"):
            self._load_csv(csv)

    def __enter__(self) -> sqlite3.Connection:
        if self.filename == ":memory:":
            self._conn = sqlite3.connect(self.filename)
        else:
            self._conn = sqlite3.connect(self.filename)
        self._load()
        _CONNECTION_MAP[id(self._conn)] = {
            "mapping": self._mapping,
            "ratings_dir": self.ratings_dir,
            "fork_dir": self.fork_dir,
        }
        return self._conn

    def commit_to_csv(self) -> None:
        if not self._conn:
            return
        commit_to_csv(self._conn)

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.commit_to_csv()
        finally:
            if self._conn:
                conn_id = id(self._conn)
                self._conn.close()
                if conn_id in _CONNECTION_MAP:
                    del _CONNECTION_MAP[conn_id]
                if self.filename and self.filename != ":memory:" and os.path.exists(self.filename):
                    os.remove(self.filename)


def commit_to_csv(conn: sqlite3.Connection) -> None:
    """Write loaded tables back to their original CSV files."""
    info = _CONNECTION_MAP.get(id(conn))
    if not info:
        return
    mapping = info.get("mapping", {})
    ratings_dir = Path(info.get("ratings_dir", "ratings"))
    fork_dir = Path(info.get("fork_dir", "forking_path"))
    cur = conn.cursor()
    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        csv = mapping.get(table)
        if not csv:
            if table.startswith("position_"):
                csv = ratings_dir / f"{table}.csv"
            else:
                csv = fork_dir / f"{table}.csv"
        df = pd.read_sql_query(f"SELECT * FROM `{table}`", conn)
        csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv, index=False)


def open_database(temp_file: bool = False, ratings_dir: Path | str = "ratings", fork_dir: Path | str = "forking_path") -> CsvDatabase:
    """Return CsvDatabase context manager."""
    if temp_file:
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        return CsvDatabase(ratings_dir, fork_dir, filename=path)
    return CsvDatabase(ratings_dir, fork_dir, filename=":memory:")
