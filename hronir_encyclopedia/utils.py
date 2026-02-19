import uuid
from collections.abc import Callable

import typer

from . import storage  # Assuming storage.py contains DataManager and Path models
from .models import PathStatus


def validate_path_inputs_helper(
    position: int,
    source: str,
    target: str,
    secho_func: Callable,
    echo_func: Callable,
) -> str:
    """
    Validates inputs for creating a narrative path.
    Returns normalized source UUID string.
    """
    if not target:
        secho_func("Error: Target Hrönir UUID must be provided.", fg="red")
        raise typer.Exit(code=1)
    try:
        uuid.UUID(target)
    except ValueError:
        secho_func(f"Error: Target Hrönir UUID '{target}' is not a valid UUID.", fg="red")
        raise typer.Exit(code=1)

    if position == 0:
        if source:
            echo_func(
                f"Info: Source UUID '{source}' ignored for position 0. Path starts with target Hrönir '{target}'."
            )
        return ""  # Normalized source for position 0 is an empty string
    else:
        if not source:
            secho_func(
                f"Error: Source Hrönir UUID must be provided for position {position}.",
                fg="red",
            )
            raise typer.Exit(code=1)
        try:
            uuid.UUID(source)
            return source
        except ValueError:
            secho_func(f"Error: Source Hrönir UUID '{source}' is not a valid UUID.", fg="red")
            raise typer.Exit(code=1)


def get_successor_hronir_for_path(path_uuid_str: str) -> str | None:
    """
    Retrieves the successor (current) Hrönir UUID for a given path UUID.
    """
    dm = storage.DataManager()
    # Ensure DataManager is initialized if it's not done globally or by context
    if not dm._initialized:
        dm.initialize_and_load()

    path_data = dm.get_path_by_uuid(path_uuid_str)
    if path_data:
        return str(path_data.uuid)
    return None


def dev_qualify_path_uuid(
    path_uuid_to_qualify: str,
    mandate_id_override: str | None,
    echo_func: Callable,
):
    """
    Manually qualifies a path and assigns a mandate ID.
    """
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    path_to_qualify = dm.get_path_by_uuid(path_uuid_to_qualify)

    if not path_to_qualify:
        echo_func(f"Error: Path UUID '{path_uuid_to_qualify}' not found.", fg="red")
        raise typer.Exit(code=1)

    if path_to_qualify.status == PathStatus.QUALIFIED.value:
        echo_func(
            f"Path {path_uuid_to_qualify} is already QUALIFIED. Mandate ID: {path_to_qualify.mandate_id}"
        )
        return

    new_mandate_id_str: str
    if mandate_id_override:
        try:
            uuid.UUID(mandate_id_override)
            new_mandate_id_str = mandate_id_override
            echo_func(f"Using provided mandate_id: {new_mandate_id_str}")
        except ValueError:
            echo_func(
                f"Warning: Provided mandate_id_override '{mandate_id_override}' is not a valid UUID. Generating a new one.",
                fg="yellow",
            )
            new_mandate_id_str = str(uuid.uuid4())
    else:
        new_mandate_id_str = str(uuid.uuid4())
        echo_func(f"Generated new mandate_id: {new_mandate_id_str}")

    dm.update_path_status(
        path_uuid=path_uuid_to_qualify,
        status=PathStatus.QUALIFIED.value,
        mandate_id=new_mandate_id_str,
        set_mandate_explicitly=True,
    )
    dm.save_all_data()
    echo_func(
        f"Path {path_uuid_to_qualify} has been QUALIFIED with Mandate ID: {new_mandate_id_str}."
    )


# Need to import typer for Exit and secho, or pass them in always.
# For now, assuming they are passed or handled by the caller context (like Typer).
# Re-evaluating: validate_path_inputs_helper and dev_qualify_path_uuid use Typer funcs.
# It's better if these utils don't directly depend on Typer for easier testing.
# Let's adjust them to raise exceptions and let CLI handle Typer output.


class UtilsError(Exception):
    pass


class PathInputError(UtilsError):
    pass


class PathNotFoundError(UtilsError):
    pass


def validate_path_inputs_helper_v2(
    position: int,
    source: str,
    target: str,
) -> str:
    """
    Validates inputs for creating a narrative path.
    Returns normalized source UUID string.
    Raises PathInputError on validation failure.
    """
    if not target:
        raise PathInputError("Target Hrönir UUID must be provided.")
    try:
        uuid.UUID(target)
    except ValueError:
        raise PathInputError(f"Target Hrönir UUID '{target}' is not a valid UUID.")

    if position < 0:
        raise PathInputError("Position cannot be negative.")

    if position == 0:
        # Source might be provided but will be ignored.
        # For consistency, we can enforce it to be empty or just normalize.
        if source:
            # Optionally, log a warning that source is ignored for position 0
            pass
        return ""
    else:  # position > 0
        if not source:
            raise PathInputError(f"Source Hrönir UUID must be provided for position {position}.")
        try:
            uuid.UUID(source)
            return source
        except ValueError:
            raise PathInputError(f"Source Hrönir UUID '{source}' is not a valid UUID.")


def dev_qualify_path_uuid_v2(
    dm: storage.DataManager,  # Pass DataManager instance
    path_uuid_to_qualify: str,
    mandate_id_override: str | None,
) -> tuple[str, str]:
    """
    Manually qualifies a path and assigns a mandate ID.
    Returns the qualified path_uuid and its mandate_id.
    Raises PathNotFoundError or PathInputError.
    """
    path_to_qualify = dm.get_path_by_uuid(path_uuid_to_qualify)

    if not path_to_qualify:
        raise PathNotFoundError(f"Path UUID '{path_uuid_to_qualify}' not found.")

    if path_to_qualify.status == PathStatus.QUALIFIED.value:
        # Path is already qualified, return existing info
        return str(path_to_qualify.path_uuid), str(path_to_qualify.mandate_id)

    new_mandate_id_str: str
    if mandate_id_override:
        try:
            uuid.UUID(mandate_id_override)
            new_mandate_id_str = mandate_id_override
        except ValueError:
            # Allow generating new one if override is invalid, or raise error?
            # For a dev tool, maybe flexibility is better. Let's raise for now.
            raise PathInputError(
                f"Provided mandate_id_override '{mandate_id_override}' is not a valid UUID."
            )
    else:
        new_mandate_id_str = str(uuid.uuid4())

    dm.update_path_status(
        path_uuid=str(path_to_qualify.path_uuid),  # Ensure string
        status=PathStatus.QUALIFIED.value,
        mandate_id=new_mandate_id_str,
        set_mandate_explicitly=True,
    )
    # dm.save_all_data() # Caller should handle saving

    return str(path_to_qualify.path_uuid), new_mandate_id_str


def git_remove_deleted_files(deleted_paths: list[str], echo_func: Callable):
    """
    Placeholder for staging deleted files in Git.
    """
    if deleted_paths:
        echo_func(
            f"Placeholder: {len(deleted_paths)} files would be staged for deletion with git rm."
        )
        for p_str in deleted_paths:
            echo_func(
                f"  - Would run: git rm --cached {p_str}"
            )  # --cached if only removing from index
    else:
        echo_func("Placeholder: No files to git rm.")
    # Actual implementation would use subprocess to call git.
    # import subprocess
    # for p_str in deleted_paths:
    #     try:
    #         # Use --ignore-unmatch to avoid error if file is already deleted or not in git
    #         subprocess.run(["git", "rm", "--cached", p_str], check=True, capture_output=True)
    #         echo_func(f"Staged {p_str} for deletion.")
    #     except subprocess.CalledProcessError as e:
    #         echo_func(f"Failed to stage {p_str} for deletion: {e.stderr.decode()}", fg="yellow")
    #     except FileNotFoundError:
    #         echo_func("Error: git command not found. Is Git installed and in PATH?", fg="red")
    #         break
