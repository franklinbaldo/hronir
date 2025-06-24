from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_CONNECTION_MAP: dict[int, dict] = {}


def _mk_engine(filename: str | Path) -> Engine:
    """Return a SQLAlchemy Engine for the given SQLite file."""
    return create_engine(f"sqlite:///{filename}", future=True, echo=False)


def _load_csv_into(engine: Engine, csv: Path) -> None:
    """Load a CSV file into a table named after the file stem."""
    tbl_name = csv.stem
    df = pd.read_csv(csv) if csv.stat().st_size else pd.DataFrame()
    df.to_sql(tbl_name, engine, if_exists="replace", index=False)


class CsvDatabase:
    """Context manager loading CSV files into a temporary SQLite DB."""

    def __init__(
        self,
        ratings_dir: Path | str = "ratings",
        path_dir: Path | str = "narrative_paths", # Changed from fork_dir
        filename: str | None = None,
    ) -> None:
        self.ratings_dir = Path(ratings_dir)
        self.path_dir = Path(path_dir) # Changed from fork_dir
        self.filename = filename or ":memory:"
        self._engine: Engine | None = None
        self._mapping: dict[str, Path] = {}

    def _load(self) -> None:
        eng = self._engine
        assert eng is not None
        self.ratings_dir.mkdir(exist_ok=True)
        self.path_dir.mkdir(exist_ok=True) # Changed from fork_dir
        for csv in list(self.ratings_dir.glob("*.csv")) + list(self.path_dir.glob("*.csv")): # Changed from fork_dir
            _load_csv_into(eng, csv)
            self._mapping[csv.stem] = csv

    # -- context-manager protocol --
    def __enter__(self) -> Engine:
        if self.filename == ":memory:":
            self._engine = _mk_engine(self.filename)
        else:
            self._engine = _mk_engine(str(self.filename))
        self._load()
        _CONNECTION_MAP[id(self._engine)] = {
            "mapping": self._mapping,
            "ratings_dir": self.ratings_dir,
            "path_dir": self.path_dir, # Changed from fork_dir
        }
        return self._engine

    def commit_to_csv(self) -> None:
        if not self._engine:
            return
        commit_to_csv(self._engine)

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.commit_to_csv()
        finally:
            if self._engine:
                eid = id(self._engine)
                self._engine.dispose()
                _CONNECTION_MAP.pop(eid, None)
                if self.filename not in (":memory:", None) and os.path.exists(self.filename):
                    os.remove(self.filename)


# Helper ------------------------------------------------------------


def commit_to_csv(engine: Engine) -> None:
    """Write loaded tables back to their original CSV files."""
    info = _CONNECTION_MAP.get(id(engine))
    if not info:
        return
    mapping = info["mapping"]
    with engine.connect() as con:
        for tbl_name in con.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).scalars():
            df = pd.read_sql_table(tbl_name, con)
            csv = mapping.get(tbl_name)
            if not csv:
                base = info["ratings_dir"] if tbl_name.startswith("position_") else info["path_dir"] # Changed from fork_dir
                csv = Path(base) / f"{tbl_name}.csv"
            csv.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(csv, index=False)


# Convenience shortcut ---------------------------------------------


def open_database(
    *,
    temp_file: bool = False,
    ratings_dir: Path | str = "ratings",
    path_dir: Path | str = "narrative_paths", # Changed from fork_dir
) -> CsvDatabase:
    """Return CsvDatabase context manager."""
    if temp_file:
        fd, p = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        return CsvDatabase(ratings_dir, path_dir, filename=p) # Changed from fork_dir
    return CsvDatabase(ratings_dir, path_dir, filename=":memory:") # Changed from fork_dir
