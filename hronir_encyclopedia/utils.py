import json
import tempfile
import uuid
from pathlib import Path

from .storage import DataManager # Might need to change this if DataManager itself moves or for DI

UUID_NAMESPACE = uuid.NAMESPACE_URL


# --- Path/Hrönir UUID Computation ---
def compute_narrative_path_uuid(
    position: int, prev_hronir_uuid: str, current_hronir_uuid: str
) -> uuid.UUID:
    """
    Computes a deterministic UUID for a narrative path (edge).
    Path UUIDs are UUIDv5 based on the concatenated string of:
    position, predecessor hrönir UUID, and current hrönir UUID.
    """
    prev_uuid_str = prev_hronir_uuid if prev_hronir_uuid else ""
    path_key = f"{position}:{prev_uuid_str}:{current_hronir_uuid}"
    return uuid.uuid5(UUID_NAMESPACE, path_key)


# --- Legacy/Compatibility Functions ---
# These functions might still use the global data_manager for now,
# or be refactored to accept a DataManager instance.
# For now, they will instantiate their own DataManager if not provided.

def store_hrönir_from_file(file_path: Path, data_manager_instance: DataManager | None = None) -> str:
    """
    Stores a hrönir's content from a file into DuckDB using the provided DataManager instance
    or a new one, and returns its UUID.
    This function is intended to replace the `store_chapter` part of the old API
    that directly interfaces with file paths.
    """
    dm = data_manager_instance if data_manager_instance else DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    # The actual reading of file and calling backend.add_hronir is now in DataManager.store_hrönir
    # This function is a wrapper that ensures DataManager is available.
    # DataManager.store_hrönir itself will use self.library_path for now if file_path is relative
    # This will be addressed in step 1.5
    return dm.store_hrönir(file_path)


def store_hrönir_from_text(text_content: str, data_manager_instance: DataManager | None = None) -> str:
    """
    Stores a hrönir's content from a string into DuckDB using the provided DataManager instance
    or a new one, and returns its UUID.
    This function is intended to replace the `store_chapter_text` part of the old API.
    """
    dm = data_manager_instance if data_manager_instance else DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    content_uuid = str(uuid.uuid5(UUID_NAMESPACE, text_content))

    if hasattr(dm.backend, "add_hronir"):
        dm.backend.add_hronir(hronir_uuid=content_uuid, content=text_content)
        dm.save_all_data() # Ensure commit
    else:
        raise NotImplementedError("Backend does not support add_hronir method.")
    return content_uuid


def get_canonical_path_info_from_json_file(position: int, canonical_path_json_file: Path) -> dict[str, str] | None:
    """
    Retrieves path_uuid and hrönir_uuid for a given position from a JSON file.
    This is a utility that might be used by other components that still rely on this file format
    for some specific purpose (e.g. session manager's dossier generation).
    It does NOT interact with the DataManager.
    """
    if not canonical_path_json_file.exists():
        return None
    try:
        with open(canonical_path_json_file) as f:
            data = json.load(f)

        path_entry = data.get("path", {}).get(str(position))
        if path_entry and "path_uuid" in path_entry and "hrönir_uuid" in path_entry:
            return {
                "path_uuid": path_entry["path_uuid"],
                "hrönir_uuid": path_entry["hrönir_uuid"],
            }
        return None
    except (OSError, json.JSONDecodeError):
        return None


# --- CLI Compatibility Wrappers (Old global DataManager behavior) ---
# These are direct carry-overs and will instantiate DataManager internally
# They should be phased out or refactored to accept DataManager instances.

def store_chapter(chapter_file: Path, base: Path | str = "the_library") -> str:
    """
    Legacy compatibility wrapper for storing a chapter from a file.
    Instantiates its own DataManager.
    'base' parameter is part of legacy and related to library_path in DataManager.
    """
    # Note: 'base' parameter is used by DataManager's library_path initialization if HRONIR_LIBRARY_DIR is not set.
    # This will be affected by step 1.5.
    data_manager = DataManager(library_dir=base) # Pass base to library_dir
    return data_manager.store_hrönir(chapter_file)


def store_chapter_text(text: str, base: Path | str = "the_library") -> str:
    """
    Legacy compatibility wrapper for storing chapter text.
    Instantiates its own DataManager.
    'base' parameter is part of legacy.
    """
    # This function now directly uses store_hrönir_from_text for clarity
    # and to avoid temporary file creation if the main store_hrönir in DataManager
    # is modified to take text directly in future.
    data_manager = DataManager(library_dir=base) # Pass base to library_dir
    # The store_hrönir_from_text utility is preferred over creating temp files here.
    return store_hrönir_from_text(text_content=text, data_manager_instance=data_manager)

# It's better if DataManager.store_hrönir is adapted to take text directly
# or if we use the new store_hrönir_from_text utility.
# For now, to keep DataManager.store_hrönir for files:
# def store_chapter_text(text: str, base: Path | str = "the_library") -> str:
#     """Store chapter text - compatibility wrapper."""
#     # data_manager = DataManager(library_dir=base) # Pass base to library_dir
#     # This creates a temporary file, which is not ideal.
#     # DataManager.store_hrönir expects a file path.
#     with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, dir=data_manager.library_path if data_manager else None) as f:
#         f.write(text)
#         temp_path = Path(f.name)
#     try:
#         # If store_hrönir uses library_path, temp_path should be relative to it or absolute
#         return data_manager.store_hrönir(temp_path)
#     finally:
#         temp_path.unlink() # Clean up temp file
