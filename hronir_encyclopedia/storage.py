import json
import uuid
import shutil
from sqlalchemy.engine import Engine
from pathlib import Path

UUID_NAMESPACE = uuid.NAMESPACE_URL


def compute_forking_uuid(position: int, prev_uuid: str, cur_uuid: str) -> str:
    """Return deterministic UUID5 for a forking path entry."""
    data = f"{position}:{prev_uuid}:{cur_uuid}"
    return str(uuid.uuid5(UUID_NAMESPACE, data))


def compute_uuid(text: str) -> str:
    """Return deterministic UUID5 of the given text."""
    return str(uuid.uuid5(UUID_NAMESPACE, text))


def uuid_to_path(uuid_str: str, base: Path) -> Path:
    """Split UUID characters into a directory tree under base."""
    parts = list(uuid_str)
    path = base
    for c in parts:
        path /= c
    return path


def store_chapter(chapter_file: Path, previous_uuid: str | None = None, base: Path | str = "hronirs") -> str:
    """Store chapter_file content under UUID-based path and return UUID."""
    base = Path(base)
    text = chapter_file.read_text()
    chapter_uuid = compute_uuid(text)
    chapter_dir = uuid_to_path(chapter_uuid, base)
    chapter_dir.mkdir(parents=True, exist_ok=True)

    ext = chapter_file.suffix or ".md"
    (chapter_dir / f"index{ext}").write_text(text)

    meta = {"uuid": chapter_uuid}
    if previous_uuid:
        meta["previous_uuid"] = previous_uuid
    (chapter_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return chapter_uuid


def store_chapter_text(text: str, previous_uuid: str | None = None, base: Path | str = "hronirs") -> str:
    """Store raw chapter text and return its UUID."""
    base = Path(base)
    chapter_uuid = compute_uuid(text)
    chapter_dir = uuid_to_path(chapter_uuid, base)
    chapter_dir.mkdir(parents=True, exist_ok=True)
    (chapter_dir / "index.md").write_text(text)
    meta = {"uuid": chapter_uuid}
    if previous_uuid:
        meta["previous_uuid"] = previous_uuid
    (chapter_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return chapter_uuid


def is_valid_uuid_v5(value: str) -> bool:
    """Return True if value is a valid UUIDv5."""
    try:
        u = uuid.UUID(value)
        return u.version == 5
    except ValueError:
        return False


def chapter_exists(uuid_str: str, base: Path | str = "hronirs") -> bool:
    """Return True if a chapter directory exists for uuid_str."""
    base = Path(base)
    chapter_dir = uuid_to_path(uuid_str, base)
    return any(chapter_dir.glob("index.*"))


def forking_path_exists(
    fork_uuid: str,
    fork_dir: Path | str = "forking_path",
    conn: Engine | None = None,
) -> bool:
    """Return True if fork_uuid appears in any forking path table or CSV."""
    import pandas as pd

    if conn is not None:
        with conn.connect() as con:
            tables = [row[0] for row in con.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                try:
                    row = con.exec_driver_sql(
                        f"SELECT 1 FROM `{table}` WHERE fork_uuid=? LIMIT 1",
                        (fork_uuid,),
                    ).fetchone()
                except Exception:
                    continue
                if row:
                    return True
            return False

    fork_dir = Path(fork_dir)
    for csv in fork_dir.glob("*.csv"):
        try:
            df = pd.read_csv(csv)
        except Exception:
            continue
        if "fork_uuid" in df.columns and fork_uuid in df["fork_uuid"].astype(str).values:
            return True
    return False


def validate_or_move(chapter_file: Path, base: Path | str = "hronirs") -> str:
    """Ensure chapter_file resides under its UUID path. Move if necessary."""
    base = Path(base)
    text = chapter_file.read_text()
    chapter_uuid = compute_uuid(text)
    target_dir = uuid_to_path(chapter_uuid, base)
    ext = chapter_file.suffix or ".md"
    target_file = target_dir / f"index{ext}"
    if chapter_file.resolve() != target_file.resolve():
        target_dir.mkdir(parents=True, exist_ok=True)
        chapter_file.replace(target_file)
    meta_path = target_dir / "metadata.json"
    if not meta_path.exists():
        meta = {"uuid": chapter_uuid}
        meta_path.write_text(json.dumps(meta, indent=2))
    return chapter_uuid


def audit_forking_csv(csv_path: Path, base: Path | str = "hronirs") -> None:
    """Validate chapters referenced in a forking path CSV."""
    import pandas as pd

    base = Path(base)
    if csv_path.stat().st_size == 0:
        csv_path.write_text("")
        return 0
    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        csv_path.write_text("")
        return 0

    # Normalise column names
    cols = list(df.columns)
    if "position" not in cols:
        df.insert(0, "position", range(len(df)))
        cols = ["position"] + cols
    if "prev_uuid" not in cols:
        df.rename(columns={cols[1]: "prev_uuid"}, inplace=True)
    if "uuid" not in df.columns:
        df.rename(columns={df.columns[2]: "uuid"}, inplace=True)

    if "fork_uuid" not in df.columns:
        df["fork_uuid"] = ""
    if "undiscovered" not in df.columns:
        df["undiscovered"] = False

    changed = False
    for idx, row in df.iterrows():
        position = int(row["position"])
        prev_uuid = str(row["prev_uuid"])
        cur_uuid = str(row["uuid"])
        fork_uuid = compute_forking_uuid(position, prev_uuid, cur_uuid)
        if row.get("fork_uuid") != fork_uuid:
            df.at[idx, "fork_uuid"] = fork_uuid
            changed = True
        prev_ok = is_valid_uuid_v5(prev_uuid) and chapter_exists(prev_uuid, base)
        cur_ok = is_valid_uuid_v5(cur_uuid) and chapter_exists(cur_uuid, base)
        if not (prev_ok and cur_ok):
            df.at[idx, "undiscovered"] = True
            changed = True

    if changed:
        df.to_csv(csv_path, index=False)


def purge_fake_hronirs(base: Path | str = "hronirs") -> int:
    """Remove chapters whose metadata or path UUID doesn't match their text."""
    base = Path(base)
    removed = 0
    for meta in base.rglob("metadata.json"):
        chapter_dir = meta.parent
        try:
            data = json.loads(meta.read_text())
        except Exception:
            shutil.rmtree(chapter_dir, ignore_errors=True)
            removed += 1
            continue

        uuid_str = data.get("uuid")
        index_file = chapter_dir / "index.md"
        if not index_file.exists() or not is_valid_uuid_v5(uuid_str):
            shutil.rmtree(chapter_dir, ignore_errors=True)
            removed += 1
            continue

        computed = compute_uuid(index_file.read_text())
        expected_dir = uuid_to_path(uuid_str, base)
        if computed != uuid_str or chapter_dir.resolve() != expected_dir.resolve():
            shutil.rmtree(chapter_dir, ignore_errors=True)
            removed += 1
    return removed


def purge_fake_forking_csv(csv_path: Path, base: Path | str = "hronirs") -> int:
    """Remove invalid rows from a forking path CSV."""
    import pandas as pd

    base = Path(base)
    if not csv_path.exists():
        return 0

    if csv_path.stat().st_size == 0:
        csv_path.write_text("")
        return 0
    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        csv_path.write_text("")
        return 0
    keep = []
    removed = 0
    for _, row in df.iterrows():
        pos = int(row.get("position", 0))
        prev_uuid = str(row.get("prev_uuid", ""))
        cur_uuid = str(row.get("uuid", ""))
        fork_uuid = str(row.get("fork_uuid", ""))
        expected = compute_forking_uuid(pos, prev_uuid, cur_uuid)
        if fork_uuid != expected:
            removed += 1
            continue
        if not (is_valid_uuid_v5(prev_uuid) and chapter_exists(prev_uuid, base)):
            removed += 1
            continue
        if not (is_valid_uuid_v5(cur_uuid) and chapter_exists(cur_uuid, base)):
            removed += 1
            continue
        keep.append(row)

    if removed:
        pd.DataFrame(keep).to_csv(csv_path, index=False)
    return removed


def purge_fake_votes_csv(
    csv_path: Path,
    base: Path | str = "hronirs",
    fork_dir: Path | str = "forking_path",
    conn: Engine | None = None,
) -> int:
    """Remove votes referencing missing chapters or duplicate voters."""
    import pandas as pd

    base = Path(base)
    if not csv_path.exists():
        return 0

    if csv_path.stat().st_size == 0:
        csv_path.write_text("")
        return 0
    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        csv_path.write_text("")
        return 0
    keep = []
    seen = set()
    removed = 0
    for _, row in df.iterrows():
        voter = str(row.get("voter", ""))
        winner = str(row.get("winner", ""))
        loser = str(row.get("loser", ""))
        if voter in seen:
            removed += 1
            continue
        if not forking_path_exists(voter, fork_dir, conn=conn):
            removed += 1
            continue
        if not (is_valid_uuid_v5(winner) and chapter_exists(winner, base)):
            removed += 1
            continue
        if not (is_valid_uuid_v5(loser) and chapter_exists(loser, base)):
            removed += 1
            continue
        seen.add(voter)
        keep.append(row)

    if removed:
        pd.DataFrame(keep).to_csv(csv_path, index=False)
    return removed
