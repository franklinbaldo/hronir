import logging
import uuid
from pathlib import Path
from typing import Annotated

import typer

from .. import gemini_util, storage
from ..models import Path as PathModel
from ..models import Transaction, TransactionContent

logger = logging.getLogger(__name__)

# Helper function (internal)
def _create_path_for_hronir(dm: storage.DataManager, hronir_uuid: str, predecessor_uuid: str | None, position: int | None = None) -> None:
    """Helper to create a path for a stored hrönir."""

    if predecessor_uuid:
        # Validate predecessor exists as a hrönir
        if not dm.hrönir_exists(predecessor_uuid):
             typer.secho(f"Error: Predecessor hrönir {predecessor_uuid} not found.", fg=typer.colors.RED)
             raise typer.Exit(1)

        # Determine position if not provided
        if position is None:
            # Find the path that introduced the predecessor to get its position
            # We search all paths where uuid == predecessor_uuid
            parent_path = None
            for p in dm.get_all_paths():
                if str(p.uuid) == predecessor_uuid:
                    parent_path = p
                    break

            if parent_path:
                position = parent_path.position + 1
            else:
                typer.secho(f"Error: Could not determine position from predecessor {predecessor_uuid}. Please specify --position.", fg=typer.colors.RED)
                raise typer.Exit(1)
    else:
        # No predecessor -> Root?
        if position is None:
            position = 0

    # Compute path UUID
    pred_str = predecessor_uuid if predecessor_uuid else ""
    path_uuid_obj = storage.compute_narrative_path_uuid(position, pred_str, hronir_uuid)

    # Check if path exists
    existing = dm.get_path_by_uuid(str(path_uuid_obj))
    if existing:
        typer.echo(f"Path already exists: {path_uuid_obj}")
        return

    # Create Path
    new_path = PathModel(
        path_uuid=path_uuid_obj,
        position=position,
        prev_uuid=uuid.UUID(predecessor_uuid) if predecessor_uuid else None,
        uuid=uuid.UUID(hronir_uuid),
        status="PENDING"
    )

    dm.add_path(new_path)

    # Record Transaction
    tx_content = TransactionContent(
        action="create_path",
        path_uuid=path_uuid_obj,
        hrönir_uuid=uuid.UUID(hronir_uuid),
        details={"position": position, "predecessor": predecessor_uuid}
    )

    transaction = Transaction(
        uuid=uuid.uuid4(),
        prev_uuid=None, # Simplified: not strictly chaining hashes for now, or fetch last tx?
                        # Ideally we'd link to previous transaction for a proper ledger, but simpler is fine for now.
        content=tx_content
    )
    dm.add_transaction(transaction)

    dm.save_all_data()
    typer.echo(f"Created path {path_uuid_obj} at position {position} linking to predecessor {predecessor_uuid or 'None'}.")


def validate_command(chapter: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]):
    """Validate a chapter file."""
    typer.echo(f"Chapter {chapter} exists and is readable.")
    # TODO: Add more robust validation logic if needed


def store_command(
    chapter: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    predecessor: Annotated[str | None, typer.Option("--predecessor", help="UUID of the predecessor hrönir.")] = None,
    position: Annotated[int | None, typer.Option("--position", help="Explicit position (optional, inferred from predecessor).")] = None,
):
    """Store a chapter and link it to a predecessor."""
    try:
        # Store content
        hronir_uuid = storage.store_chapter(chapter)
        typer.echo(f"Stored hrönir content: {hronir_uuid}")

        # Create Path
        dm = storage.DataManager()
        _create_path_for_hronir(dm, hronir_uuid, predecessor, position)

    except Exception as e:
        logger.error(f"Error storing chapter {chapter}: {e}", exc_info=True)
        typer.secho(f"Error storing chapter: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


def synthesize_command(
    prev: Annotated[str, typer.Option("--prev", help="UUID of the predecessor hrönir.")],
    position: Annotated[int | None, typer.Option("--position", help="Explicit position (optional).")] = None,
    prompt: Annotated[str, typer.Option("--prompt", help="Custom prompt for generation.")] = None,
):
    """Generate and store a new chapter using AI."""
    try:
        typer.echo(f"Synthesizing new chapter from predecessor {prev}...")

        dm = storage.DataManager()
        if not dm.hrönir_exists(prev):
             typer.secho(f"Error: Predecessor hrönir {prev} not found.", fg=typer.colors.RED)
             raise typer.Exit(1)

        # Optional: fetch content to check context or just pass UUID to agent
        # predecessor_content = dm.get_hrönir_content(prev)

        if not prompt:
            predecessor_content = dm.get_hrönir_content(prev)
            prompt = f"Write the next chapter of a Borgesian encyclopedia, continuing from this text:\n\n{predecessor_content}\n\nMaintain the style and themes."

        hronir_uuid = gemini_util.generate_chapter(prompt, prev)
        typer.echo(f"Generated and stored hrönir: {hronir_uuid}")

        _create_path_for_hronir(dm, hronir_uuid, prev, position)

    except Exception as e:
        logger.error(f"Error synthesizing chapter: {e}", exc_info=True)
        typer.secho(f"Error synthesizing chapter: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
