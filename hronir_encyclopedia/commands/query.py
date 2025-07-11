import json  # Added import
import logging
from pathlib import Path
from typing import Annotated

import typer

# Assuming these are needed based on original cli.py structure for these commands
from .. import canon, ratings, storage  # May need adjustment

logger = logging.getLogger(__name__)

query_app = typer.Typer(help="Query Hrönir data (status, rankings, duels).", no_args_is_help=True)


@query_app.command(help="Display the canonical path and optional path status counts.")
def status(
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file (legacy, for reference).")
    ] = Path("data/canonical_path.json"),  # Kept for now, but emphasize DB as source
    counts: Annotated[
        bool, typer.Option("--counts", help="Also show number of paths by status.")
    ] = False,
):
    typer.echo("Status of the Hrönir Encyclopedia:")

    # Canonical path display - Emphasize that DB should be the source of truth
    # For now, we might show both or prioritize DB if canon.get_canonical_path_from_db is robust
    # Let's assume canon.get_canonical_path_from_db is the target
    dm_for_canon = storage.DataManager()
    if not dm_for_canon._initialized:
        dm_for_canon.initialize_and_load()

    # This function in canon.py is currently a placeholder.
    # It needs to be implemented to actually query DB.
    # For now, we'll show a message and then try the JSON as fallback.
    db_canonical_path = canon.get_canonical_path_from_db(dm_for_canon)
    if db_canonical_path:
        typer.echo("\nCanonical Path (derived from Database):")
        sorted_db_path = sorted(db_canonical_path.items(), key=lambda item: int(item[0]))
        for position, details in sorted_db_path:
            typer.echo(
                f"  Pos {position}: Path {details['path_uuid']} (Hrönir: {details['hrönir_uuid']})"
            )
    else:
        typer.echo("\nCanonical Path (derived from Database): Not available or empty.")
        typer.echo(
            f"Attempting to read from legacy file: {canonical_path_file} (for reference only)"
        )
        if canonical_path_file.exists():
            try:
                with open(canonical_path_file) as f:
                    data = json.load(f)  # Define json here
                typer.echo(f"Canonical Path (from {canonical_path_file}):")
                if "path" in data and data["path"]:
                    sorted_path = sorted(data["path"].items(), key=lambda item: int(item[0]))
                    for position, details in sorted_path:
                        typer.echo(
                            f"  Pos {position}: Path {details['path_uuid']} (Hrönir: {details['hrönir_uuid']})"
                        )
                else:
                    typer.echo("  No canonical path defined in the JSON file.")
            except Exception as e:
                typer.secho(
                    f"  Error reading legacy canonical path file {canonical_path_file}: {e}",
                    fg=typer.colors.YELLOW,
                )
        else:
            typer.echo(f"  Legacy canonical path file not found at {canonical_path_file}.")
        typer.echo(
            "  Run 'hronir recover-canon' or ensure votes are processed to build DB-derived canon."
        )

    if counts:
        typer.echo("\nPath Status Counts:")
        dm_for_counts = storage.DataManager()
        if not dm_for_counts._initialized:
            dm_for_counts.initialize_and_load()

        status_counts = dm_for_counts.get_path_status_counts()
        if status_counts:
            for status_val, count_val in status_counts.items():  # renamed count to count_val
                typer.echo(f"  {status_val}: {count_val}")
        else:
            typer.echo("  No paths found to count.")


@query_app.command(help="Show Elo rankings for a chapter position.")
def ranking(position: Annotated[int, typer.Argument(help="The chapter position to rank.")]):
    # Placeholder for predecessor_hrönir_uuid, as get_ranking now requires it.
    # This command might need to be smarter or take it as an option.
    # For now, let's try with None, which implies ranking all paths at that position
    # without filtering by a specific canonical predecessor.
    # This behavior might need refinement based on how get_ranking handles None for predecessor.
    # Alternatively, we might need to fetch the current canonical predecessor for that position.

    # Attempt to get canonical predecessor for context, if position > 0
    predecessor_hrönir_uuid_for_ranking = None
    if position > 0:
        dm = storage.DataManager()
        if not dm._initialized:
            dm.initialize_and_load()
        # This is a simplified way to get a predecessor, might need more robust logic
        # or this command should require a predecessor_uuid if filtering is desired.
        # For now, this part is disabled to match previous simpler behavior of ranking command.
        # predecessor_hrönir_uuid_for_ranking = canon.get_canonical_hronir_uuid_for_position(dm, position -1)
        pass

    ranking_df = ratings.get_ranking(
        position, predecessor_hrönir_uuid=predecessor_hrönir_uuid_for_ranking
    )
    if ranking_df.empty:
        typer.echo(
            f"No rankings found for position {position} {('with predecessor ' + predecessor_hrönir_uuid_for_ranking) if predecessor_hrönir_uuid_for_ranking else ''}."
        )
        return

    typer.echo(
        f"Elo Rankings for Position {position}{(' (context: ' + predecessor_hrönir_uuid_for_ranking + ')') if predecessor_hrönir_uuid_for_ranking else ' (all contexts)'}:"
    )

    # Ensure all expected columns are present before trying to access them
    expected_cols = ["path_uuid", "hrönir_uuid", "elo_rating", "num_duels", "status"]
    cols_to_display = [col for col in expected_cols if col in ranking_df.columns]

    if not cols_to_display:
        typer.echo("Ranking data is missing expected columns for display.")
        typer.echo(f"Available columns: {ranking_df.columns.tolist()}")
        return

    display_df = ranking_df[cols_to_display].copy()

    # Rename columns for display if they exist in display_df
    rename_map = {
        "path_uuid": "Path_UUID",
        "hrönir_uuid": "Hrönir_UUID",
        "elo_rating": "Elo",
        "num_duels": "Duels",
        "status": "Status",
    }
    cols_to_rename = {k: v for k, v in rename_map.items() if k in display_df.columns}
    display_df.rename(columns=cols_to_rename, inplace=True)

    typer.echo(display_df.to_string(index=False))


@query_app.command(help="Get the maximum entropy duel between paths for a position.")
def get_duel(
    position: Annotated[
        int, typer.Option(help="The chapter position for which to get the path duel.")
    ],
    # canonical_path_file: Annotated[ # No longer primary source for canon.
    #     Path, typer.Option(help="Path to the canonical path JSON file.")
    # ] = Path("data/canonical_path.json"), # Removed this option
):
    dm = storage.DataManager()
    if not dm._initialized:
        dm.initialize_and_load()

    predecessor_hrönir_uuid = None
    if position > 0:
        # This function in canon.py is currently a placeholder.
        # It needs to be implemented to actually query DB.
        predecessor_hrönir_uuid = canon.get_canonical_hronir_uuid_for_position(dm, position - 1)
        if predecessor_hrönir_uuid is None:
            typer.secho(
                f"Could not determine canonical predecessor for position {position - 1} from DB. "
                "Will find duel among all paths at target position.",
                fg=typer.colors.YELLOW,
            )
            # Fall back to showing any duel at that position by passing None as predecessor.

    duel_info = ratings.get_max_entropy_duel(position, predecessor_hrönir_uuid)

    if duel_info:
        typer.echo(
            f"Maximum Entropy Duel for Position {position}{(' from predecessor ' + predecessor_hrönir_uuid) if predecessor_hrönir_uuid else ' (any predecessor)'}:"
        )
        typer.echo(
            f"  Path A: {duel_info['path_A_uuid']} (Hrönir: {duel_info['hrönir_A_uuid']}, Elo: {duel_info['elo_A']:.2f})"
        )
        typer.echo(
            f"  Path B: {duel_info['path_B_uuid']} (Hrönir: {duel_info['hrönir_B_uuid']}, Elo: {duel_info['elo_B']:.2f})"
        )
        typer.echo(f"  Entropy: {duel_info['entropy']:.4f}")
    else:
        typer.echo(
            f"No eligible duel found for position {position}{(' from predecessor ' + predecessor_hrönir_uuid) if predecessor_hrönir_uuid else ''}."
        )
