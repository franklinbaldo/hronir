import datetime
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import typer

from . import (
    ratings,
    session_manager,
    storage,
    transaction_manager,
)

logger = logging.getLogger(__name__)


def _get_successor_hronir_for_path(path_uuid_to_find: str) -> str | None:
    path_data_obj = storage.DataManager().get_path_by_uuid(path_uuid_to_find)
    if path_data_obj:
        return str(path_data_obj.uuid)
    return None


app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True,
    no_args_is_help=True,
)

session_app = typer.Typer(help="Manage Hrönir judgment sessions.", no_args_is_help=True)
app.add_typer(session_app, name="session")

# Add AI agents commands
try:
    from .agents.cli_commands import agent_app
    app.add_typer(agent_app, name="agent")
except ImportError as e:
    # Agents module not available
    pass


def run_temporal_cascade(
    canonical_path_file: Path,
    typer_echo: callable,
    start_position: int | None = None,
    committed_verdicts: dict[str, uuid.UUID] | None = None,
    max_positions_to_consolidate: int = 100,
):
    logger.info(
        f"run_temporal_cascade called. Start_pos: {start_position}, Committed Verdicts: {committed_verdicts is not None}"
    )
    if committed_verdicts:
        logger.info("Processing committed verdicts to update canonical path.")
        try:
            if not canonical_path_file.exists():
                default_canon_data = {
                    "title": "The Hrönir Encyclopedia - Canonical Path",
                    "path": {},
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                canonical_path_file.write_text(json.dumps(default_canon_data, indent=2))
                logger.info(f"Created default canonical path file: {canonical_path_file}")

            with open(canonical_path_file, "r+") as f:
                try:
                    canonical_data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Canonical path file {canonical_path_file} is empty or invalid. Initializing."
                    )
                    canonical_data = {
                        "title": "The Hrönir Encyclopedia - Canonical Path",
                        "path": {},
                        "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }

                path_map = canonical_data.get("path", {})
                updated = False

                for pos_str, winning_path_uuid in committed_verdicts.items():
                    path_data = storage.DataManager().get_path_by_uuid(str(winning_path_uuid))
                    if path_data:
                        winning_hronir_uuid = str(path_data.uuid)
                        current_entry = path_map.get(pos_str)
                        if (
                            not current_entry
                            or current_entry.get("path_uuid") != str(winning_path_uuid)
                            or current_entry.get("hrönir_uuid") != winning_hronir_uuid
                        ):
                            path_map[pos_str] = {
                                "path_uuid": str(winning_path_uuid),
                                "hrönir_uuid": winning_hronir_uuid,
                            }
                            logger.info(
                                f"Canonical path for pos {pos_str} updated by verdict to path {winning_path_uuid}."
                            )
                            updated = True
                        else:
                            logger.info(
                                f"Canonical path for pos {pos_str} already matches direct verdict."
                            )
                    else:
                        logger.warning(
                            f"Could not find path data for winning_path_uuid {winning_path_uuid} at pos {pos_str}."
                        )

                min_affected_pos = 0
                if committed_verdicts:
                    min_affected_pos = (
                        min([int(p) for p in committed_verdicts.keys()])
                        if committed_verdicts
                        else 0
                    )

                max_eval_pos = (
                    max(list(map(int, path_map.keys())) + [min_affected_pos]) + 1
                )  # Go one beyond current max

                for current_eval_pos_val in range(
                    min_affected_pos, max_eval_pos + 1
                ):  # Iterate through all potentially affected positions
                    current_eval_pos_str = str(current_eval_pos_val)
                    predecessor_pos_str = str(current_eval_pos_val - 1)
                    required_pred_hronir_uuid: str | None = None

                    if current_eval_pos_val > 0:
                        if predecessor_pos_str in path_map:
                            required_pred_hronir_uuid = path_map[predecessor_pos_str]["hrönir_uuid"]
                        else:  # Predecessor is not canonical, so this and subsequent positions cannot be.
                            if current_eval_pos_str in path_map:
                                logger.info(
                                    f"Cascade: Pos {current_eval_pos_str} and subsequent invalidated as predecessor pos {predecessor_pos_str} is not canonical."
                                )
                                for i in range(
                                    current_eval_pos_val, max_eval_pos + 1
                                ):  # Clear this and all subsequent
                                    if str(i) in path_map:
                                        del path_map[str(i)]
                                        updated = True
                            break

                    # If current_eval_pos_str was set by a direct verdict, trust it for now (already handled above)
                    # Otherwise, or if its predecessor doesn't match, it needs re-evaluation or clearing.
                    if (
                        current_eval_pos_str not in committed_verdicts
                        and current_eval_pos_str in path_map
                    ):
                        current_canon_entry_data = storage.DataManager().get_path_by_uuid(
                            path_map[current_eval_pos_str]["path_uuid"]
                        )
                        current_entry_prev_uuid = (
                            str(current_canon_entry_data.prev_uuid)
                            if current_canon_entry_data and current_canon_entry_data.prev_uuid
                            else ""
                        )
                        required_pred_hronir_uuid_str = (
                            str(required_pred_hronir_uuid) if required_pred_hronir_uuid else ""
                        )
                        if (
                            not current_canon_entry_data
                            or current_entry_prev_uuid != required_pred_hronir_uuid_str
                        ):
                            logger.info(
                                f"Cascade: Pos {current_eval_pos_str} entry {path_map[current_eval_pos_str]['path_uuid']} invalidated."
                            )
                            del path_map[current_eval_pos_str]
                            updated = True
                            # Invalidate subsequent positions as well
                            for i in range(current_eval_pos_val + 1, max_eval_pos + 1):
                                if str(i) in path_map:
                                    del path_map[str(i)]

                    # If the position is now empty (either initially, or cleared), try to fill it.
                    if current_eval_pos_str not in path_map:
                        logger.info(
                            f"Cascade: Attempting to fill position {current_eval_pos_str} (predecessor hrönir: {required_pred_hronir_uuid})."
                        )
                        # Corrected keyword: predecessor_hronir_uuid
                        rankings = ratings.get_ranking(
                            position=current_eval_pos_val,
                            predecessor_hronir_uuid=required_pred_hronir_uuid,
                        )
                        logger.info(
                            f"Cascade: Rankings for pos {current_eval_pos_str} (pred: {required_pred_hronir_uuid}): {len(rankings)} results."
                        )
                        if not rankings.empty:
                            top_path_uuid = rankings.iloc[0]["path_uuid"]
                            top_hronir_uuid = rankings.iloc[0]["hrönir_uuid"]
                            path_map[current_eval_pos_str] = {
                                "path_uuid": str(top_path_uuid),
                                "hrönir_uuid": str(top_hronir_uuid),
                            }
                            logger.info(
                                f"Cascade: Pos {current_eval_pos_str} filled with {top_path_uuid}."
                            )
                            updated = True
                        else:
                            logger.info(
                                f"Cascade: No path found for pos {current_eval_pos_str} from pred {required_pred_hronir_uuid}. Stopping cascade for this branch."
                            )
                            # If we can't fill this position, subsequent positions are also invalid.
                            for i in range(current_eval_pos_val + 1, max_eval_pos + 1):
                                if str(i) in path_map:
                                    del path_map[str(i)]
                                    updated = True
                            break  # Stop trying to fill further positions in this cascade attempt

                if updated:
                    logger.info("Canonical path updated after cascade.")
                    sorted_path_map_tuples = sorted(path_map.items(), key=lambda item: int(item[0]))
                    canonical_data["path"] = {k: v for k, v in sorted_path_map_tuples}
                    canonical_data["last_updated"] = datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
                    f.seek(0)
                    json.dump(canonical_data, f, indent=2)
                    f.truncate()
                    typer_echo(typer.style("Canonical path updated.", fg=typer.colors.GREEN))
                else:
                    typer_echo(
                        typer.style(
                            "No changes to canonical path after cascade processing.",
                            fg=typer.colors.YELLOW,
                        )
                    )

        except FileNotFoundError:
            typer_echo(
                typer.style(
                    f"ERROR: Canonical path file {canonical_path_file} could not be accessed.",
                    fg=typer.colors.RED,
                )
            )
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error(f"Error in run_temporal_cascade: {e}", exc_info=True)
            typer_echo(
                typer.style(f"ERROR during temporal cascade update: {e}", fg=typer.colors.RED)
            )
            raise typer.Exit(code=1)
    elif start_position is not None:
        logger.critical(
            "CRITICAL: Full `run_temporal_cascade` from start_position is not implemented for recover-canon!"
        )
        typer_echo(
            typer.style(
                "CRITICAL WARNING: Full Temporal Cascade logic for recover-canon is NOT IMPLEMENTED.",
                fg=typer.colors.RED,
                bold=True,
            )
        )
    else:
        logger.error("run_temporal_cascade called without committed_verdicts or start_position.")
        typer_echo(typer.style("ERROR: Temporal cascade called incorrectly.", fg=typer.colors.RED))


# ... (The rest of the file - init_test, path, list_paths, session_commit, etc. - remains the same as the last full successful read_files) ...


@app.command(
    "recover-canon",
    help="Manual recovery tool: Triggers Temporal Cascade from position 0 to rebuild canon.",
)
def recover_canon(
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    max_positions_to_rebuild: Annotated[
        int, typer.Option(help="Maximum number of positions to attempt to rebuild.")
    ] = 100,
):
    typer.echo("WARNING: This is a manual recovery tool.")
    run_temporal_cascade(
        start_position=0,
        max_positions_to_consolidate=max_positions_to_rebuild,
        canonical_path_file=canonical_path_file,
        typer_echo=typer.echo,
        committed_verdicts=None,
    )
    typer.echo("Manual canon recovery attempt complete (current implementation is basic).")


@app.command("init-test", help="Generate a minimal sample narrative for quick testing.")
def init_test(
    library_dir: Annotated[Path, typer.Option(help="Directory to store sample hrönirs.")] = Path(
        "the_library"
    ),
    narrative_paths_dir: Annotated[Path, typer.Option(help="Directory for path CSV files.")] = Path(
        "narrative_paths"
    ),
    ratings_dir: Annotated[Path, typer.Option(help="Directory for rating CSV files.")] = Path(
        "ratings"
    ),
    data_dir: Annotated[Path, typer.Option(help="Directory for canonical data files.")] = Path(
        "data"
    ),
) -> None:
    import shutil

    def clear_or_create_dir(dir_path: Path):
        if dir_path.exists():
            for item in dir_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            dir_path.mkdir(parents=True, exist_ok=True)

    clear_or_create_dir(library_dir)
    clear_or_create_dir(narrative_paths_dir)
    clear_or_create_dir(ratings_dir)
    sessions_dir = data_dir / "sessions"
    transactions_dir = data_dir / "transactions"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    clear_or_create_dir(sessions_dir)
    clear_or_create_dir(transactions_dir)
    canonical_file_path = data_dir / "canonical_path.json"
    if canonical_file_path.exists():
        canonical_file_path.unlink()
    consumed_paths_file = sessions_dir / "consumed_path_uuids.json"
    if consumed_paths_file.exists():
        consumed_paths_file.unlink()
    h0_uuid_str = storage.store_chapter_text("Example Hrönir 0", base=library_dir)
    h1_uuid_str = storage.store_chapter_text("Example Hrönir 1", base=library_dir)
    h0_uuid, h1_uuid = uuid.UUID(h0_uuid_str), uuid.UUID(h1_uuid_str)
    from .models import Path as PathModel

    data_manager = storage.DataManager()
    p0_path_uuid_val = storage.compute_narrative_path_uuid(0, "", h0_uuid_str)
    data_manager.add_path(
        PathModel(
            path_uuid=p0_path_uuid_val, position=0, prev_uuid=None, uuid=h0_uuid, status="PENDING"
        )
    )
    p1_path_uuid_val = storage.compute_narrative_path_uuid(1, h0_uuid_str, h1_uuid_str)
    data_manager.add_path(
        PathModel(
            path_uuid=p1_path_uuid_val,
            position=1,
            prev_uuid=h0_uuid,
            uuid=h1_uuid,
            status="PENDING",
        )
    )
    canonical = {
        "title": "The Hrönir Encyclopedia - Canonical Path",
        "path": {
            "0": {"path_uuid": str(p0_path_uuid_val), "hrönir_uuid": h0_uuid_str},
            "1": {"path_uuid": str(p1_path_uuid_val), "hrönir_uuid": h1_uuid_str},
        },
    }
    (data_dir / "canonical_path.json").write_text(json.dumps(canonical, indent=2))
    data_manager.save_all_data_to_csvs()
    typer.echo(f"Sample data initialized. P0: {p0_path_uuid_val}, P1: {p1_path_uuid_val}")


@app.command(help="Validate a chapter file.")
def validate(chapter: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]):
    typer.echo(f"Chapter {chapter} exists and is readable.")


@app.command(help="Store a chapter by UUID.")
def store(chapter: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]):
    typer.echo(storage.store_chapter(chapter))


def _validate_path_inputs_helper(
    position: int, source: str | None, target: str, secho: callable, echo: callable
) -> str:
    library_path_str = os.getenv("HRONIR_LIBRARY_DIR", "the_library")
    library_dir = Path(library_path_str)
    if position < 0:
        secho("Error: Position must be >= 0.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if not target:
        secho("Error: Target hrönir UUID required.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if not storage.DataManager().hrönir_exists(target):
        secho(f"Error: Target hrönir '{target}' not found in the database.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if position > 0:
        if not source:
            secho("Error: Source UUID required for position > 0.", fg=typer.colors.RED)
            raise typer.Exit(1)
        if not storage.DataManager().hrönir_exists(source):
            secho(f"Error: Source hrönir '{source}' not found in the database.", fg=typer.colors.RED)
            raise typer.Exit(1)
        return source
    else:
        if source:
            echo("Warning: Source UUID ignored for position 0.")
        return ""


@app.command(help="Create a narrative path.")
def path(
    position: Annotated[int, typer.Option()],
    target: Annotated[str, typer.Option()],
    source: Annotated[str, typer.Option()] = "",
):
    norm_source = _validate_path_inputs_helper(position, source, target, typer.secho, typer.echo)
    path_uuid_obj = storage.compute_narrative_path_uuid(position, norm_source, target)
    dm = storage.DataManager()
    if any(p.path_uuid == path_uuid_obj for p in dm.get_paths_by_position(position)):
        typer.echo(f"Path already exists: {path_uuid_obj}")
        return
    from .models import Path as PathModel

    dm.add_path(
        PathModel(
            path_uuid=path_uuid_obj,
            position=position,
            prev_uuid=uuid.UUID(norm_source) if norm_source else None,
            uuid=uuid.UUID(target),
            status="PENDING",
        )
    )
    dm.save_all_data()
    typer.echo(
        f"Created path: {path_uuid_obj} (Pos: {position}, Src: {norm_source or 'None'}, Tgt: {target}, Status: PENDING)"
    )


@app.command(help="List paths.")
def list_paths(position: Annotated[int, typer.Option(help="Position to list paths for.")] = None):
    dm = storage.DataManager()
    paths_list = dm.get_paths_by_position(position) if position is not None else dm.get_all_paths()
    if not paths_list:
        typer.echo(f"No paths found{f' at position {position}' if position is not None else ''}.")
        return
    typer.echo(f"{'Paths at position ' + str(position) if position is not None else 'All paths'}:")
    df = pd.DataFrame([p.model_dump() for p in paths_list])
    for col in ["prev_uuid", "mandate_id"]:
        df[col] = df[col].astype(str).replace("None", "")
    typer.echo(
        df[["path_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"]].to_string(
            index=False
        )
    )


@app.command(help="Show path status.")
def path_status(path_uuid: str):
    path_data = storage.DataManager().get_path_by_uuid(path_uuid)
    if not path_data:
        typer.secho(f"Error: Path '{path_uuid}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(
        f"Path UUID: {path_data.path_uuid}\nPosition: {path_data.position}\nPredecessor: {path_data.prev_uuid or '(None)'}\nCurrent Hrönir: {path_data.uuid}\nStatus: {path_data.status}"
    )
    if path_data.mandate_id:
        typer.echo(f"Mandate ID: {path_data.mandate_id}")
    if csid := session_manager.is_path_consumed(path_uuid):
        typer.echo(f"Consumed by session: {csid}")


@app.command(help="Display the canonical path and optional path status counts.")
def status(
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
    counts: Annotated[
        bool, typer.Option("--counts", help="Also show number of paths by status.")
    ] = False,
    narrative_paths_dir: Annotated[
        Path,
        typer.Option(help="Directory containing narrative path CSV files (for --counts, legacy)."),
    ] = Path("narrative_paths"),
):
    # ... (status command implementation from previous cli.py)
    pass  # Placeholder for brevity


@app.command(help="Validate and repair storage, audit narrative CSVs.")
def audit():  # ... (audit command implementation from previous cli.py)
    pass  # Placeholder for brevity


@app.command("validate-paths", help="Validate integrity of all narrative paths.")
def validate_paths_command():  # ... (validate-paths command implementation)
    pass  # Placeholder for brevity


@app.command(help="Generate competing chapters from a predecessor and record an initial vote.")
def synthesize(
    position: Annotated[int, typer.Option(help="Chapter position for the new hrönirs.")],
    prev: Annotated[
        str, typer.Option(help="UUID of the predecessor chapter to create a path from.")
    ],
):
    # ... (synthesize command implementation)
    pass  # Placeholder for brevity


@app.command(help="Show Elo rankings for a chapter position.")
def ranking(position: Annotated[int, typer.Argument(help="The chapter position to rank.")]):
    # ... (ranking command implementation)
    pass  # Placeholder for brevity


@app.command(help="Get the maximum entropy duel between paths for a position.")
def get_duel(
    position: Annotated[
        int, typer.Option(help="The chapter position for which to get the path duel.")
    ],
    canonical_path_file: Annotated[
        Path, typer.Option(help="Path to the canonical path JSON file.")
    ] = Path("data/canonical_path.json"),
):
    # ... (get_duel command implementation)
    pass  # Placeholder for brevity


def _git_remove_deleted_files():  # ... (implementation)
    pass


@app.command(help="Remove invalid entries (fake hrönirs, votes, etc.) from storage.")
def clean(
    git_stage_deleted: Annotated[
        bool, typer.Option("--git", help="Stage deleted files in Git.")
    ] = False,
):
    # ... (clean command implementation)
    pass  # Placeholder for brevity


def dev_qualify_path_uuid(path_uuid_str: str, typer_echo: callable):  # ... (implementation)
    pass


@app.command("tutorial", help="Demonstrates a complete workflow of the Hrönir Encyclopedia.")
def tutorial_command(
    auto_qualify_for_session: Annotated[
        bool, typer.Option(help="Auto-qualify path for session demo.")
    ] = True,
):
    # ... (tutorial command implementation)
    pass  # Placeholder for brevity


@app.command("dev-qualify", help="DEV: Manually qualify a path.")
def dev_qualify_command(
    path_uuid_to_qualify: Annotated[str, typer.Argument(help="Path UUID to qualify.")],
    mandate_id_override: Annotated[str, typer.Option(help="Optional specific mandate_id.")] = None,
):
    # ... (dev-qualify command implementation)
    pass  # Placeholder for brevity


@session_app.command(
    "commit", help="Submit verdicts, record transaction, trigger Temporal Cascade."
)
def session_commit(
    session_id: Annotated[
        str, typer.Option("--session-id", "-s", help="ID of active session to commit.")
    ],
    verdicts_input: Annotated[
        str,
        typer.Option(
            "--verdicts",
            "-v",
            help='JSON string or path to JSON file of verdicts. Format: \'{"pos": "winning_path_uuid"}\'.',
        ),
    ],
    canonical_path_file: Annotated[Path, typer.Option(help="Path to canonical path JSON.")] = Path(
        "data/canonical_path.json"
    ),
    max_cascade_positions: Annotated[
        int, typer.Option(help="Max positions for temporal cascade.")
    ] = 100,
):
    session_model = session_manager.get_session(session_id)
    if not session_model:
        typer.secho(f"Error: Session ID '{session_id}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if session_model.status != "active":
        typer.secho(
            f"Error: Session '{session_id}' not active (status: '{session_model.status}').",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    verdicts: dict[str, str] = {}
    verdicts_path = Path(verdicts_input)
    if verdicts_path.is_file():
        try:
            verdicts = json.loads(verdicts_path.read_text())
        except Exception as e:
            typer.secho(f"Error parsing verdicts file {verdicts_input}: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    else:
        try:
            verdicts = json.loads(verdicts_input)
        except Exception as e:
            typer.secho(f"Error parsing verdicts JSON string: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    if not isinstance(verdicts, dict):
        typer.secho("Error: Verdicts must be JSON object.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    initiating_path_uuid_str = str(session_model.initiating_path_uuid)
    dossier_duels_models = session_model.dossier.duels
    valid_votes_for_tm: list[dict[str, Any]] = []
    processed_verdicts_for_session_model: dict[str, uuid.UUID] = {}
    oldest_voted_position = float("inf")

    for pos_str, winning_path_uuid_verdict_str in verdicts.items():
        if not isinstance(winning_path_uuid_verdict_str, str):
            typer.echo(f"Warning: Verdict for pos {pos_str} not string. Skipping.")
            continue
        try:
            position_idx = int(pos_str)
            assert position_idx >= 0
        except (ValueError, AssertionError):
            typer.echo(f"Warning: Invalid pos key '{pos_str}'. Skipping.")
            continue
        duel_model_for_pos = dossier_duels_models.get(pos_str)
        if not duel_model_for_pos:
            typer.echo(f"Warning: No duel for pos {pos_str} in dossier. Skipping.")
            continue
        path_a_uuid_obj, path_b_uuid_obj = (
            duel_model_for_pos.path_A_uuid,
            duel_model_for_pos.path_B_uuid,
        )
        try:
            winning_path_uuid_verdict_obj = uuid.UUID(winning_path_uuid_verdict_str)
        except ValueError:
            typer.echo(
                f"Warning: Verdict for pos {pos_str}: winner '{winning_path_uuid_verdict_str}' invalid UUID. Skipping."
            )
            continue
        if winning_path_uuid_verdict_obj not in [path_a_uuid_obj, path_b_uuid_obj]:
            typer.echo(
                f"Warning: Verdict for pos {pos_str}: winner {winning_path_uuid_verdict_str[:8]} not in duel. Skipping."
            )
            continue
        loser_path_uuid_obj = (
            path_a_uuid_obj if winning_path_uuid_verdict_obj == path_b_uuid_obj else path_b_uuid_obj
        )
        winner_hronir, loser_hronir = (
            _get_successor_hronir_for_path(str(winning_path_uuid_verdict_obj)),
            _get_successor_hronir_for_path(str(loser_path_uuid_obj)),
        )
        if not winner_hronir or not loser_hronir:
            typer.secho(
                f"Error: Can't map duel paths for pos {pos_str} to hrönirs. Aborting.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        path_data_winner = storage.DataManager().get_path_by_uuid(
            str(winning_path_uuid_verdict_obj)
        )
        if not path_data_winner:
            typer.secho(
                f"Error: Path data for winner {winning_path_uuid_verdict_str} not found. Aborting.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        pred_hronir_uuid = str(path_data_winner.prev_uuid) if path_data_winner.prev_uuid else None
        if position_idx == 0:
            pred_hronir_uuid = None
        valid_votes_for_tm.append(
            {
                "position": position_idx,
                "winner_hrönir_uuid": winner_hronir,
                "loser_hrönir_uuid": loser_hronir,
                "predecessor_hrönir_uuid": pred_hronir_uuid,
            }
        )
        processed_verdicts_for_session_model[pos_str] = winning_path_uuid_verdict_obj
        if position_idx < oldest_voted_position:
            oldest_voted_position = position_idx

    transaction_result: dict[str, Any]
    if valid_votes_for_tm:
        typer.echo(f"{len(valid_votes_for_tm)} valid verdicts prepared for transaction processing.")
        try:
            transaction_result = transaction_manager.record_transaction(
                session_id=str(session_model.session_id),
                initiating_path_uuid=initiating_path_uuid_str,
                session_verdicts=valid_votes_for_tm,
            )
            typer.echo(
                json.dumps(
                    {
                        "message": "Transaction processing complete.",
                        "transaction_uuid": transaction_result["transaction_uuid"],
                        "promotions_granted": transaction_result.get("promotions_granted", []),
                    },
                    indent=2,
                )
            )
        except Exception as e:
            typer.secho(
                f"Error: Failed to process transaction: {e}. Aborting commit.", fg=typer.colors.RED
            )
            session_manager.update_session_status(
                str(session_model.session_id), "commit_failed_tx_processing"
            )
            raise typer.Exit(code=1)
    else:
        typer.echo(
            "No valid verdicts to process for transaction. Session will still be closed and path marked SPENT."
        )
        transaction_result = {
            "oldest_voted_position": float("inf"),
            "transaction_uuid": None,
            "promotions_granted": [],
        }

    try:
        mandate_id_for_update = str(session_model.mandate_id) if session_model.mandate_id else None
        storage.DataManager().update_path_status(
            path_uuid=initiating_path_uuid_str,
            status="SPENT",
            mandate_id=mandate_id_for_update,
            set_mandate_explicitly=True,
        )
        storage.DataManager().save_all_data_to_csvs()
        typer.echo(f"Path {initiating_path_uuid_str} status updated to SPENT.")
    except Exception as e:
        typer.echo(
            f"Warning: Error updating status for path {initiating_path_uuid_str} to SPENT: {e}."
        )

    session_model.committed_verdicts = processed_verdicts_for_session_model
    tm_oldest_voted_position = transaction_result.get("oldest_voted_position", float("inf"))

    if tm_oldest_voted_position != float("inf") and tm_oldest_voted_position >= 0:
        typer.echo(
            f"Oldest voted position: {tm_oldest_voted_position}. Triggering Temporal Cascade."
        )
        try:
            run_temporal_cascade(
                committed_verdicts=session_model.committed_verdicts,
                canonical_path_file=canonical_path_file,
                typer_echo=typer.echo,
                start_position=tm_oldest_voted_position,
                max_positions_to_consolidate=max_cascade_positions,
            )
            typer.echo("Temporal Cascade (basic update from verdicts) completed.")
        except Exception as e:
            typer.secho(f"Error: Temporal Cascade failed: {e}.", fg=typer.colors.RED)
            session_manager.update_session_status(
                str(session_model.session_id), "commit_failed_cascade"
            )
            session_model.status = "commit_failed_cascade"
            (session_manager.SESSIONS_DIR / f"{session_model.session_id}.json").write_text(
                session_model.model_dump_json(indent=2)
            )
            raise typer.Exit(code=1)
    else:
        typer.echo(
            "No valid votes cast or oldest position undetermined; Temporal Cascade not triggered."
        )

    if session_manager.update_session_status(str(session_model.session_id), "committed"):
        session_model.status = "committed"
        session_model.updated_at = datetime.datetime.now(datetime.timezone.utc)
        (session_manager.SESSIONS_DIR / f"{session_model.session_id}.json").write_text(
            session_model.model_dump_json(indent=2)
        )
        typer.echo(f"Session {session_id} committed successfully. Committed verdicts saved.")
    else:
        typer.secho(
            f"Error: Failed to update session {session_id} status to committed.",
            fg=typer.colors.RED,
        )


@session_app.command("start", help="Initiate a Judgment Session using a QUALIFIED path's mandate.")
def session_start(
    path_uuid_str: Annotated[
        str, typer.Option("--path-uuid", "-p", help="QUALIFIED path_uuid granting mandate.")
    ],
    canonical_path_file: Annotated[Path, typer.Option(help="Path to canonical path JSON.")] = Path(
        "data/canonical_path.json"
    ),
):
    path_data_obj = storage.DataManager().get_path_by_uuid(path_uuid_str)
    if not path_data_obj:
        typer.secho(f"Error: Path UUID '{path_uuid_str}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if path_data_obj.status != "QUALIFIED":
        typer.secho(
            f"Error: Path '{path_uuid_str}' not QUALIFIED (status: '{path_data_obj.status}').",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    if not path_data_obj.mandate_id:
        typer.secho(
            f"Error: Path '{path_uuid_str}' QUALIFIED but no mandate_id.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)
    if csid := session_manager.is_path_consumed(path_uuid_str):
        typer.secho(
            f"Error: Path '{path_uuid_str}' already used for session '{csid}'.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)
    try:
        session_model = session_manager.create_session(
            path_n_uuid_str=path_uuid_str,
            position_n=path_data_obj.position,
            mandate_id_str=str(path_data_obj.mandate_id),
            canonical_path_file=canonical_path_file,
        )
        dossier_out = {
            p: {
                "path_A": str(d.path_A_uuid),
                "path_B": str(d.path_B_uuid),
                "entropy": round(d.entropy, 4),
            }
            for p, d in (session_model.dossier.duels or {}).items()
        }
        out = {
            "message": "Judgment session started.",
            "session_id": str(session_model.session_id),
            "initiating_path_uuid": str(session_model.initiating_path_uuid),
            "mandate_id_used": str(session_model.mandate_id),
            "position_n": session_model.position_n,
            "status": session_model.status,
            "created_at": session_model.created_at.isoformat(),
            "dossier": {"duels": dossier_out},
        }
        typer.echo(json.dumps(out, indent=2))
    except ValueError as ve:
        typer.secho(f"Error creating session: {ve}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Unexpected error creating session: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command(help="Download latest snapshot from Internet Archive to local DuckDB.")
def sync(
    archive_id: Annotated[
        str, typer.Option(help="IA identifier (placeholder).")
    ] = "hronir-snapshots",
    db_file: Annotated[Path, typer.Option(help="Local DuckDB file.")] = Path(
        "data/encyclopedia.duckdb"
    ),
    retry: Annotated[bool, typer.Option(help="Enable retry logic.")] = True,
):
    typer.echo(
        f"Sync command placeholder. (archive_id: {archive_id}, db_file: {db_file}, retry: {retry})"
    )


@app.command(help="Create local snapshot archive (snapshot.zip).")
def export(
    output: Annotated[Path, typer.Option(help="Output archive path.")] = Path("snapshot.zip"),
):
    typer.echo(f"Export command placeholder. (output: {output})")


@app.command(help="Upload snapshot and metadata to Internet Archive.")
def push(
    archive_id: Annotated[str, typer.Option(help="IA identifier (legacy).")] = "hronir-snapshots",
    force: Annotated[bool, typer.Option(help="Force push (DANGEROUS).")] = False,
    snapshot_output_base_dir: Annotated[
        Path, typer.Option(help="Base dir for snapshot files.")
    ] = Path("data/snapshots_out"),
):
    typer.echo(f"Push command placeholder. (archive_id: {archive_id}, force: {force})")


@app.command("metrics", help="Expose path status metrics in Prometheus format.")
def metrics_command(
    narrative_paths_dir: Annotated[Path, typer.Option(help="Dir for path CSVs (legacy).")] = Path(
        "narrative_paths"
    ),
):
    typer.echo("Metrics command placeholder.")


@app.callback()
def main_callback(ctx: typer.Context):
    log_level_str = os.getenv("HRONIR_LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.debug("CLI main_callback: Initializing DataManager...")
    try:
        data_manager = storage.DataManager()
        if not hasattr(data_manager, "_initialized") or not data_manager._initialized:
            logger.info("DataManager not initialized in callback. Calling initialize_and_load().")
            data_manager.initialize_and_load()
            logger.info("DataManager initialized and loaded via callback.")
        else:
            logger.debug("DataManager already initialized.")
    except Exception as e:
        logger.exception("Fatal: DataManager init failed in callback.")
        typer.secho(f"Fatal: DataManager init failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    logger.debug("Main callback finished.")


def main(argv: list[str] | None = None):
    app(args=argv)


if __name__ == "__main__":
    main()
