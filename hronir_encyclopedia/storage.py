import json
import shutil
import uuid
from pathlib import Path
import pandas as pd # Moved to top
from sqlalchemy.engine import Engine
from typing import Any # Import Any

UUID_NAMESPACE = uuid.NAMESPACE_URL


def compute_forking_uuid(position: int, prev_uuid: str, cur_uuid: str) -> str:
    """Return deterministic UUID5 for a forking path entry."""
    data = f"{position}:{prev_uuid}:{cur_uuid}"
    return str(uuid.uuid5(UUID_NAMESPACE, data))


def compute_uuid(text: str) -> str:
    """Return deterministic UUID5 of the given text."""
    return str(uuid.uuid5(UUID_NAMESPACE, text))


def uuid_to_path(uuid_str: str, base: Path) -> Path:
    """Return a direct subdirectory path for the given UUID string under base."""
    return base / uuid_str


def store_chapter(
    chapter_file: Path, previous_uuid: str | None = None, base: Path | str = "the_library"
) -> str:
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


def store_chapter_text(
    text: str, previous_uuid: str | None = None, base: Path | str = "the_library"
) -> str:
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


def chapter_exists(uuid_str: str, base: Path | str = "the_library") -> bool:
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
    # print(f"DEBUG: storage.forking_path_exists searching for fork_uuid: {fork_uuid} in dir: {fork_dir}") # DEBUG REMOVED

    if conn is not None:
        # print(f"DEBUG: storage.forking_path_exists using DB conn") # DEBUG REMOVED
        with conn.connect() as con:
            tables = [
                row[0]
                for row in con.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
            ]
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

    fork_dir_obj = Path(fork_dir)
    resolved_fork_dir = fork_dir_obj.resolve() # Resolve the path
    found_in_csv = False
    # print(f"DEBUG: storage.forking_path_exists iterating items in {resolved_fork_dir}") # DEBUG REMOVED

    if resolved_fork_dir.is_dir(): # Check if directory exists before iterating
        for item_path in resolved_fork_dir.iterdir():
            # print(f"DEBUG: storage.forking_path_exists found item: {item_path}, is_file: {item_path.is_file()}, name: {item_path.name}") # DEBUG REMOVED
            if item_path.is_file() and item_path.name.endswith(".csv"):
                csv_file_path = item_path
                # print(f"DEBUG: storage.forking_path_exists checking CSV: {csv_file_path}") # DEBUG REMOVED
                try:
                    # Read only 'fork_uuid' column if possible, for efficiency, though pandas reads all by default.
                    df = pd.read_csv(csv_file_path, usecols=["fork_uuid"], dtype={"fork_uuid": str}) # type: ignore
                    if fork_uuid in df["fork_uuid"].values: # More direct check
                        # print(f"DEBUG: storage.forking_path_exists FOUND fork_uuid {fork_uuid} in {csv_file_path}") # DEBUG REMOVED
                        found_in_csv = True
                        break
                except ValueError: # Happens if 'fork_uuid' column is not in CSV or other read issues
                    # print(f"DEBUG: storage.forking_path_exists ValueError (likely missing 'fork_uuid' col) in {csv_file_path}: {ve}") # DEBUG REMOVED
                    pass # Ignore files that don't have fork_uuid or are malformed for this check
                except Exception:
                    # print(f"DEBUG: storage.forking_path_exists error reading {csv_file_path}: {e}") # DEBUG REMOVED
                    continue # Ignore other read errors for this specific check
            if found_in_csv: # Break outer loop if found
                break

    # if not found_in_csv: # DEBUG REMOVED
        # print(f"DEBUG: storage.forking_path_exists DID NOT FIND fork_uuid {fork_uuid} in any CSV in {resolved_fork_dir}") # DEBUG REMOVED
    return found_in_csv


def validate_or_move(chapter_file: Path, base: Path | str = "the_library") -> str:
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


def audit_forking_csv(csv_path: Path, base: Path | str = "the_library") -> None:
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
    if "status" not in df.columns:
        df["status"] = "PENDING"
        changed = True

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


def purge_fake_hronirs(base: Path | str = "the_library") -> int:
    """Remove chapters whose metadata or path UUID doesn't match their text."""
    base = Path(base)
    removed = 0
    metas = list(base.rglob("metadata.json"))
    for meta in metas:
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


from typing import Optional, Dict # Add Optional and Dict for type hinting

def get_canonical_fork_info(position: int, canonical_path_file: Path = Path("data/canonical_path.json")) -> Optional[Dict[str, str]]:
    """
    Consulta o arquivo de caminho canônico (ex: data/canonical_path.json) para
    revelar o fork_uuid e o hrönir_uuid (sucessor) canônicos para a posição especificada.

    Retorna um dicionário {'fork_uuid': str, 'hrönir_uuid': str} se encontrado e válido,
    caso contrário None.

    Espera que o canonical_path_file armazene uma estrutura como:
    {
      "title": "The Hrönir Encyclopedia - Canonical Path",
      "path": {
        "0": { "fork_uuid": "...", "hrönir_uuid": "..." },
        "1": { "fork_uuid": "...", "hrönir_uuid": "..." }
      }
    }
    """
    if not canonical_path_file.exists():
        return None

    try:
        with open(canonical_path_file, "r") as f:
            canonical_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    path_entries = canonical_data.get("path")
    if not isinstance(path_entries, dict):
        return None

    position_str = str(position)
    canonical_entry = path_entries.get(position_str)

    if not isinstance(canonical_entry, dict):
        return None

    fork_uuid = canonical_entry.get("fork_uuid")
    hrönir_uuid = canonical_entry.get("hrönir_uuid")

    if not fork_uuid or not hrönir_uuid:
        return None

    if not isinstance(fork_uuid, str) or not is_valid_uuid_v5(fork_uuid):
        return None

    if not isinstance(hrönir_uuid, str) or not is_valid_uuid_v5(hrönir_uuid):
        return None

    return {"fork_uuid": fork_uuid, "hrönir_uuid": hrönir_uuid}


def append_fork(
    csv_file: Path,
    position: int,
    prev_uuid: str,
    uuid_str: str, # Renamed 'uuid' to 'uuid_str' to avoid conflict with uuid module
    conn: Engine | None = None,
) -> str:
    """
    Appends a new fork entry to a CSV file or a database table.
    Calculates a deterministic fork_uuid for the entry.
    """
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    # compute_forking_uuid is already in storage.py
    fork_uuid = compute_forking_uuid(position, prev_uuid, uuid_str)

    if conn is not None:
        table_name = csv_file.stem # Use stem for table name consistency
        with conn.begin() as con:
            # Ensure table exists
            # TODO: Add robust schema migration if table exists with different schema
            con.exec_driver_sql(
                f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    position INTEGER,
                    prev_uuid TEXT,
                    uuid TEXT,
                    fork_uuid TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'PENDING'
                )
                """
            )
            # Insert data, handle potential conflicts if fork_uuid is primary key
            # Using ON CONFLICT IGNORE to avoid error if the exact same fork is appended again.
            # Note: This assumes 'status' column exists or has a default.
            # A more robust solution might involve checking schema or using ALTER TABLE.
            try:
                con.exec_driver_sql(
                    f"""
                    INSERT INTO `{table_name}` (position, prev_uuid, uuid, fork_uuid, status)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(fork_uuid) DO NOTHING
                    """,
                    (position, prev_uuid, uuid_str, fork_uuid, "PENDING"),
                )
            except Exception as e: # Broad exception to catch cases where schema might be old
                # This is a fallback, ideally schema migration should be handled.
                # For now, try inserting without status if the above fails,
                # assuming an older table schema. This is not ideal.
                # print(f"Warning: Failed to insert with status, attempting without: {e}")
                con.exec_driver_sql(
                    f"""
                    INSERT INTO `{table_name}` (position, prev_uuid, uuid, fork_uuid)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(fork_uuid) DO NOTHING
                    """,
                    (position, prev_uuid, uuid_str, fork_uuid),
                )
        return fork_uuid

    # CSV handling
    new_row_df = pd.DataFrame(
        [
            {
                "position": position,
                "prev_uuid": prev_uuid,
                "uuid": uuid_str,
                "fork_uuid": fork_uuid,
                "status": "PENDING",
            }
        ]
    )
    if csv_file.exists() and csv_file.stat().st_size > 0:
        try:
            df = pd.read_csv(csv_file)
            # Check if fork_uuid already exists to prevent duplicates
            if not df[df["fork_uuid"] == fork_uuid].empty:
                # print(f"Fork {fork_uuid} already exists in {csv_file}. Skipping append.")
                return fork_uuid
            df = pd.concat([df, new_row_df], ignore_index=True)
        except pd.errors.EmptyDataError:
            # File exists but is empty, treat as new file
            df = new_row_df
    else:
        df = new_row_df

    df.to_csv(csv_file, index=False)
    return fork_uuid


def purge_fake_forking_csv(csv_path: Path, base: Path | str = "the_library") -> int:
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
        # Ensure 'status' column is preserved if it exists, otherwise it might be dropped
        # if 'keep' is reconstructed from rows that don't explicitly include it and then
        # pd.DataFrame infers columns.
        # However, if 'row' is a Series from the original df and includes 'status',
        # it will be included in 'keep'.
        # For safety, if we were creating dicts for 'keep', we'd add 'status': row.get('status', "PENDING")
        keep.append(row)

    if removed:
        if keep: # Ensure 'keep' is not empty before creating DataFrame
            # Define columns to ensure 'status' is included, even if all rows
            # had it as NaN initially (though audit_forking_csv should prevent this for new files)
            final_cols = ["position", "prev_uuid", "uuid", "fork_uuid", "undiscovered", "status"]
            # Filter df_keep to only include columns that actually exist in it, plus 'status'
            df_kept = pd.DataFrame(keep)
            cols_to_use = [col for col in final_cols if col in df_kept.columns]
            if "status" not in df_kept.columns and "status" in final_cols: # if status was somehow lost
                 # This case should ideally not happen if audit_forking_csv ran correctly
                 df_kept["status"] = "PENDING" # Add with default if missing
                 if "status" not in cols_to_use: # Should not be needed but defensive
                     cols_to_use.append("status")


            pd.DataFrame(df_kept, columns=cols_to_use).to_csv(csv_path, index=False)
        else: # All rows were removed
            csv_path.write_text("position,prev_uuid,uuid,fork_uuid,undiscovered,status\n") # Write header for empty file
    return removed


def purge_fake_votes_csv(
    csv_path: Path,
    base: Path | str = "the_library",
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


def get_fork_file_and_data(fork_uuid_to_find: str, fork_dir_base: Path = Path("forking_path")) -> Optional[Dict[str, Any]]:
    """
    Scans all forking_path/*.csv files to find a specific fork_uuid.

    Returns:
        A dictionary containing the fork's data row (as a dict) and 'csv_filepath' (Path object)
        if found, otherwise None.
    """
    if not fork_dir_base.is_dir():
        return None

    for csv_filepath in fork_dir_base.glob("*.csv"):
        if csv_filepath.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(csv_filepath, dtype=str) # Read all as string to be safe
            fork_row_df = df[df["fork_uuid"] == fork_uuid_to_find]
            if not fork_row_df.empty:
                # Convert row to dict, ensure all expected columns are present or defaulted
                fork_data = fork_row_df.iloc[0].to_dict()
                fork_data['csv_filepath'] = csv_filepath
                # Ensure numeric types if necessary for consumer, but for now keep as read
                if 'position' in fork_data and fork_data['position'] is not None:
                    try:
                        fork_data['position'] = int(fork_data['position'])
                    except ValueError:
                        # Handle or log error if position is not a valid int
                        pass # Keep as string if conversion fails
                return fork_data
        except pd.errors.EmptyDataError:
            continue
        except Exception:
            # Log error ideally
            continue
    return None


def update_fork_status(
    fork_uuid_to_update: str,
    new_status: str,
    mandate_id: Optional[str] = None,
    fork_dir_base: Path = Path("forking_path"),
    conn: Engine | None = None,
) -> bool:
    """
    Updates the status and optionally the mandate_id of a specific fork_uuid
    in its corresponding forking_path CSV file or database table.

    Args:
        fork_uuid_to_update: The UUID of the fork to update.
        new_status: The new status string (e.g., "QUALIFIED", "SPENT").
        mandate_id: Optional mandate_id to set. If provided, a 'mandate_id' column
                    will be added to the CSV if it doesn't exist.
        fork_dir_base: The base directory where forking_path CSVs are stored.
        conn: Optional database engine. If provided, updates the DB table instead.

    Returns:
        True if the fork was found and updated, False otherwise.
    """
    if conn is not None:
        # Database logic:
        # This is more complex as we need to know which table the fork_uuid belongs to.
        # Assuming fork_uuid is globally unique and we'd have to scan tables or have a master table.
        # For now, this part is a placeholder for a more robust DB strategy.
        # A simplified approach might be to try updating common table names if known.
        # This example assumes a single table 'forks_master' for simplicity of illustration,
        # which is NOT how the current CSV structure works (CSVs are per-creator/path).
        # A real DB implementation would need a way to map fork_uuid to its table.
        # Or, if all forks are in one table, then:
        # with conn.begin() as c:
        #     # Ensure mandate_id column exists (this is DB specific, e.g., SQLite)
        #     # c.execute(text(f"ALTER TABLE your_forks_table ADD COLUMN mandate_id TEXT")) # One-time or check
        #     result = c.execute(
        #         text(f"UPDATE your_forks_table SET status = :status, mandate_id = :mandate_id WHERE fork_uuid = :fork_uuid"),
        #         {"status": new_status, "mandate_id": mandate_id, "fork_uuid": fork_uuid_to_update}
        #     )
        #     return result.rowcount > 0
        # print(f"DB update for fork status not fully implemented yet.") # Placeholder
        return False # DB part needs more specific design based on schema

    # CSV file logic:
    fork_info = get_fork_file_and_data(fork_uuid_to_update, fork_dir_base)
    if not fork_info or 'csv_filepath' not in fork_info:
        return False

    csv_filepath = fork_info['csv_filepath']
    try:
        df = pd.read_csv(csv_filepath)
        fork_index = df[df["fork_uuid"] == fork_uuid_to_update].index

        if not fork_index.empty:
            idx = fork_index[0]
            df.loc[idx, "status"] = new_status
            if mandate_id is not None:
                if "mandate_id" not in df.columns:
                    df["mandate_id"] = pd.NA # Initialize column if it doesn't exist
                df.loc[idx, "mandate_id"] = mandate_id

            df.to_csv(csv_filepath, index=False)
            return True
    except Exception:
        # Log error
        return False
    return False
