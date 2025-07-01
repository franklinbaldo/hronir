import datetime
import json
import math

import logging # Keep for other modules that might use root logger
import os
import subprocess
import uuid
import zipfile
from pathlib import Path
from typing import (
    Annotated,
    Any,
)

import pandas as pd
import typer
from pydantic import ValidationError

from . import (
    database,
    gemini_util,
    ratings,
    storage,
    transaction_manager,
)
from .models import Path as PathModel
from .models import Vote
from .transaction_manager import ConflictDetection

# logger for this module - will use root config from main_callback
logger = logging.getLogger(__name__)


app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True,
    no_args_is_help=True,
)

# --- Helper Functions ---
def _get_successor_hronir_for_path(path_uuid_to_find: str) -> str | None:
    dm = storage.DataManager()
    path_data_obj = dm.get_path_by_uuid(path_uuid_to_find)
    if path_data_obj: return str(path_data_obj.uuid)
    return None

def _validate_and_normalize_path_inputs(
    position: int, source: str, target: str, secho: callable, echo: callable
) -> str:
    dm = storage.DataManager()
    library_path = dm.library_path
    library_path.mkdir(parents=True, exist_ok=True)
    if position < 0: secho(f"ERR: Pos must be >=0", fg=typer.colors.RED, err=True); raise typer.Exit(code=1)
    if position > 0 and not source: secho("ERR: Source UUID required for pos > 0.", fg=typer.colors.RED, err=True); raise typer.Exit(code=1)
    if position == 0 and source: echo("Warn: Source UUID ignored for pos 0."); source = ""
    if not target: secho("ERR: Target hrönir UUID required.", fg=typer.colors.RED, err=True); raise typer.Exit(code=1)
    if not dm.hrönir_exists(target): secho(f"ERR: Target hrönir '{target}' not in lib.", fg=typer.colors.RED, err=True); raise typer.Exit(code=1)
    if source and not dm.hrönir_exists(source): secho(f"ERR: Source hrönir '{source}' not in lib.", fg=typer.colors.RED, err=True); raise typer.Exit(code=1)
    return source

# --- CLI Commands ---
@app.command("recover-canon")
def recover_canon(
    canonical_path_file: Annotated[Path | None, typer.Option(help="Path to the canonical path JSON file.")] = None,
    max_positions_to_rebuild: Annotated[int, typer.Option()] = 100):
    dm = storage.DataManager() # Get data manager to resolve default path if needed
    resolved_canonical_path_file = canonical_path_file if canonical_path_file else Path(os.getenv("HRONIR_DATA_DIR", "data")) / "canonical_path.json"

    typer.echo("Triggering Temporal Cascade from position 0.")
    run_temporal_cascade(0, max_positions_to_rebuild, resolved_canonical_path_file, typer.echo)
    typer.echo("Manual canon recovery complete.")

@app.command("init-test")
def init_test(
    library_dir: Annotated[Path | None, typer.Option(help="Path to the library directory.")] = None,
    data_dir: Annotated[Path | None, typer.Option(help="Path to the data directory.")] = None
) -> None:
    import shutil
    dm = storage.DataManager() # Changed from storage.data_manager

    # Resolve paths using DataManager's configured paths if CLI options are None
    resolved_library_dir = library_dir if library_dir else dm.library_path
    # For data_dir, if HRONIR_DATA_DIR is set, DataManager doesn't directly expose it as a property.
    # We rely on os.getenv or use a conventional subdirectory of a base data path if one existed on dm.
    # For now, let's assume default structure relative to where HRONIR_DATA_DIR might point or a default.
    base_data_path = Path(os.getenv("HRONIR_DATA_DIR", "data"))
    resolved_data_dir = data_dir if data_dir else base_data_path
    resolved_data_dir.mkdir(parents=True, exist_ok=True) # Ensure it exists

    typer.echo("Clearing DB tables..."); dm.clear_in_memory_data()
    def _clear_dir(dp: Path):
        if dp.exists(): [shutil.rmtree(i) if i.is_dir() else i.unlink() for i in dp.iterdir()]
        dp.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Clearing lib: {resolved_library_dir}"); _clear_dir(resolved_library_dir)
    tx_dir = resolved_data_dir/"transactions"; typer.echo(f"Clearing tx dir: {tx_dir}"); _clear_dir(tx_dir)
    if not (tx_dir/"HEAD").exists(): (tx_dir/"HEAD").write_text("")
    canon_fp = resolved_data_dir/"canonical_path.json";
    if canon_fp.exists(): typer.echo(f"Deleting: {canon_fp}"); canon_fp.unlink()
    h0_s=storage.store_chapter_text("Ex H0",base=resolved_library_dir); h1_s=storage.store_chapter_text("Ex H1",base=resolved_library_dir)
    h0_u,h1_u = uuid.UUID(h0_s),uuid.UUID(h1_s)
    p0_pu=storage.compute_narrative_path_uuid(0,"",h0_s); dm.add_path(PathModel(path_uuid=p0_pu,position=0,prev_uuid=None,uuid=h0_u))
    p1_pu=storage.compute_narrative_path_uuid(1,h0_s,h1_s); dm.add_path(PathModel(path_uuid=p1_pu,position=1,prev_uuid=h0_u,uuid=h1_u))
    from .ratings import generate_and_store_new_pending_duel
    # Position 0 is immutable and does not have duels.
    # generate_and_store_new_pending_duel(0,None,dm); # Removed call for position 0
    generate_and_store_new_pending_duel(1,h0_s,dm) # Generate duel for position 1
    canon_c = {"title":"Canon","path":{"0":{"path_uuid":str(p0_pu),"hrönir_uuid":h0_s},"1":{"path_uuid":str(p1_pu),"hrönir_uuid":h1_s}},"last_updated":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    resolved_data_dir.mkdir(parents=True,exist_ok=True); canon_fp.write_text(json.dumps(canon_c,indent=2)) # Used resolved_data_dir
    dm.save_all_data_to_csvs(); typer.echo("Init test done.")

@app.command()
def store(chapter: Annotated[Path, typer.Argument(exists=True,dir_okay=False,readable=True)]): typer.echo(storage.store_chapter(chapter))

@app.command()
def path(pos: Annotated[int, typer.Option(help="Position")], target_hr: Annotated[str, typer.Option(help="Target hrönir UUID")], source_hr: Annotated[str, typer.Option(help="Source hrönir UUID (empty for pos 0)")] = ""):
    dm=storage.DataManager(); src_hr_s=_validate_and_normalize_path_inputs(pos,source_hr,target_hr,typer.secho,typer.echo); path_uuid_o=storage.compute_narrative_path_uuid(pos,src_hr_s,target_hr) # _validate_and_normalize_path_inputs also calls DataManager()
    if dm.get_path_by_uuid(str(path_uuid_o)): typer.echo(f"Path exists: {path_uuid_o}"); return
    try:
        dm.add_path(PathModel(path_uuid=path_uuid_o,position=pos,prev_uuid=uuid.UUID(src_hr_s) if src_hr_s else None,uuid=uuid.UUID(target_hr)))
        dm.save_all_data_to_csvs(); typer.echo(f"Created path: {path_uuid_o}")
    except Exception as e: typer.secho(f"Error creating path: {e}",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)

@app.command("list-paths")
def list_paths_cmd(position: Annotated[int, typer.Option(help="Filter by position (optional)")] = None): # Renamed func
    dm=storage.DataManager(); paths_l = dm.get_paths_by_position(position) if position is not None else dm.get_all_paths()
    if not paths_l: typer.echo("No paths found."); return
    typer.echo(f"Paths{f' at pos {position}' if position is not None else ' (all)'}:")
    df=pd.DataFrame([p.model_dump(mode='json') for p in paths_l]); df["prev_uuid"]=df["prev_uuid"].astype(str).replace("None","")
    typer.echo(df[["path_uuid","position","prev_uuid","uuid"]].to_string(index=False))

@app.command("path-info")
def path_info_cmd(path_uuid: str): # Renamed func
    dm=storage.DataManager(); pd=dm.get_path_by_uuid(path_uuid)
    if not pd: typer.secho(f"Path {path_uuid} not found.",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    typer.echo(f"Path UUID: {pd.path_uuid}\nPos: {pd.position}\nPrev Hrönir: {pd.prev_uuid or '(N/A)'}\nCurr Hrönir: {pd.uuid}")
    typer.echo(f"Token Status: {'CONSUMED' if dm.is_token_consumed(path_uuid) else 'AVAILABLE'}")

def _calc_path_counts(): return {"TOTAL_PATHS":len(storage.DataManager().get_all_paths())} # Renamed

@app.command("hrönir-status")
def hronir_status_cmd(
    canon_fp: Annotated[Path | None, typer.Option(help="Path to the canonical path JSON file.")] = None,
    counts:Annotated[bool,typer.Option("--counts")]=False
): # Renamed
    resolved_canon_fp = canon_fp if canon_fp else Path(os.getenv("HRONIR_DATA_DIR", "data")) / "canonical_path.json"
    try:
        cd=json.loads(resolved_canon_fp.read_text())
    except Exception: typer.secho(f"Error reading {resolved_canon_fp}",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    pe=cd.get("path",{}); typer.echo("Canon Path:"); [typer.echo(f"  Pos {k}: path: {v.get('path_uuid','N/A')}, hrönir: {v.get('hrönir_uuid','N/A')}") for k,v in sorted(pe.items(),key=lambda i:int(i[0]))]
    if counts: typer.echo("\nPath Counts:"); [typer.echo(f"  {k}: {v}") for k,v in _calc_path_counts().items()]

@app.command("dev-qualify", help="OBSOLETE")
def dev_qualify_cmd(path_uuid_to_qualify:str, mandate_id_override:str|None=None): typer.secho("`dev-qualify` obsolete.",fg=typer.colors.YELLOW)
@app.command("tutorial", help="OBSOLETE")
def tutorial_cmd(auto_qualify_for_session:bool=True): typer.secho("`tutorial` obsolete.",fg=typer.colors.YELLOW)
@app.command("metrics")
def metrics_cmd_new(): counts=_calc_path_counts(); typer.echo(f"# HELP hronir_paths_total Total paths\n# TYPE hronir_paths_total gauge\nhronir_paths_total {counts.get('TOTAL_PATHS',0)}") # Renamed

@app.callback()
def main_callback(ctx:typer.Context):
    lvl=os.getenv("HRONIR_LOG_LEVEL","DEBUG").upper() # Changed to DEBUG for more verbosity
    # Force basicConfig to ensure console handler for CliRunner and ensure level.
    logging.basicConfig(level=lvl,format="%(asctime)s-%(name)s-%(levelname)s-%(message)s",datefmt="%Y-%m-%d %H:%M:%S",force=True)
    logger.setLevel(lvl) # Ensure this module's logger is also set.
    logging.getLogger("hronir_encyclopedia").setLevel(lvl) # Ensure parent logger is also set.

    # Ensure a fresh DataManager instance is used, configured by current env vars.
    # This is crucial for test isolation where env vars are set per test.
    logger.debug("DM init in callback.");

    # Explicitly reset the global instance if it exists, then create a new one.
    # This ensures that the DataManager picks up env vars set by tests.
    if storage.data_manager._instance is not None:
        if hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
            try:
                storage.data_manager.backend.conn.close() # Close DB connection if open
            except Exception as e:
                logger.warning(f"Error closing DB connection during DM reset in CLI callback: {e}")
        storage.data_manager._instance = None
        logger.debug("Global DataManager instance reset in CLI callback.")

    dm = storage.DataManager() # This will now create a new instance if _instance was None
                               # or re-use one if it was already appropriately set by a test.
                               # The key is that __init__ will use current os.getenv values.

    try:
        # The initialize_and_load() call will use the paths configured in the new/reset dm instance.
        if not dm._initialized: # Check the _initialized flag on the instance we just got/created
            logger.info("DM load in callback."); dm.initialize_and_load(); logger.info("DM loaded.")
        else:
            logger.debug("DM already initialized (possibly by test setup).")
    except Exception as e: logger.exception("Fatal: DM init fail."); typer.secho(f"Fatal: DM init fail: {e}",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)

def run_temporal_cascade(start_pos:int,max_pos:int,canon_fp:Path,echo:callable): # Renamed params
    echo(f"Running Temporal Cascade from pos {start_pos}..."); dm=storage.DataManager()
    old_c={}; old_p={};
    if canon_fp.exists():
        try: old_c=json.loads(canon_fp.read_text()); old_p=old_c.get("path",{})
        except json.JSONDecodeError: echo(typer.style(f"Warn: Corrupt {canon_fp}.",fg=typer.colors.YELLOW))
    new_p={}; cur_pred_hr_uuid:str|None=None; all_paths=dm.get_all_paths()
    h_pos = max(p.position for p in all_paths) if all_paths else -1
    eff_max = min(max_pos-1,h_pos); logger.info(f"Cascade: Max:{eff_max},Start:{start_pos}")

    # Handle Position 0 (Immutable Root)
    # Position 0 is always taken from the old canon if it exists and start_pos allows.
    # It's not subject to ranking-based changes.
    if "0" in old_p:
        new_p["0"] = old_p["0"]
        cur_pred_hr_uuid = old_p["0"].get("hrönir_uuid")
        echo(f"  Pos 0: Preserved from old canon. Hrönir: {cur_pred_hr_uuid[:8] if cur_pred_hr_uuid else 'N/A'}")
    elif dm.get_paths_by_position(0): # If no old canon for pos 0, but paths exist (e.g. init)
        # This case implies we need an initial canonical path for pos 0 if one isn't loaded.
        # For simplicity, we'll assume init-test or manual setup creates a valid canon_fp with pos 0.
        # If canon_fp is truly empty or pos 0 is missing, this cascade won't invent it.
        # It relies on pos 0 being established.
        # If pos 0 is missing from old_p, and start_pos is 0, the loop below will try to rank it,
        # which is what we want to avoid for pos 0's immutability.
        # The most robust way is to ensure '0' is in old_p if canon_fp exists.
        pass # Let the loop handle it IF start_pos is 0, but it will only use get_ranking

    # Iterate for positions >= effective_start_pos
    # If start_pos is 0, we still need to ensure new_p["0"] is set (above)
    # and then proceed from 1 for rank-based changes.
    # However, if start_pos > 0, we need to copy from old_p up to start_pos-1.

    effective_loop_start_idx = 0 # Process all positions from 0 up to eff_max

    for idx in range(effective_loop_start_idx, eff_max + 1):
        k=str(idx)

        # If idx < start_pos, it means these positions are before the change that triggered the cascade.
        # They should be copied from the old canon.
        if idx < start_pos:
            if k in old_p:
                new_p[k] = old_p[k]
                cur_pred_hr_uuid = old_p[k].get("hrönir_uuid")
                echo(f"  Pos {idx}: Preserved (before start_pos). NextP: {cur_pred_hr_uuid[:8] if cur_pred_hr_uuid else 'N'}")
                continue
            else: # Should not happen if old_p is consistent up to start_pos
                echo(typer.style(f"    P{idx}: Missing in old canon before start_pos. End.",fg=typer.colors.YELLOW)); break

        # Handle Position 0 specifically: It's immutable based on voting/ranking.
        # It should already be in new_p if it was in old_p.
        # If it's not (e.g. fresh init, start_pos=0, no canon file yet), it needs one selected path.
        # ratings.get_ranking(0, None) will list paths at pos 0. We take the top one.
        if idx == 0:
            if k in new_p: # Already handled by pre-loop logic or preserved from idx < start_pos
                cur_pred_hr_uuid = new_p[k].get("hrönir_uuid") # Update predecessor for next iteration
                echo(f"  Pos 0: Confirmed from pre-cascade/preserved. Hrönir: {cur_pred_hr_uuid[:8] if cur_pred_hr_uuid else 'N/A'}")
                continue
            else: # Position 0 needs to be set, was not in old_p or not < start_pos
                echo(f"  Pos 0: Determining initial canonical entry (not from votes).")
                # For pos 0, predecessor is always None.
                rdf_pos0 = ratings.get_ranking(0, None)
                if not rdf_pos0.empty:
                    winner_pos0 = rdf_pos0.iloc[0]
                    new_p[k] = {"path_uuid": str(winner_pos0["path_uuid"]), "hrönir_uuid": str(winner_pos0["hrönir_uuid"])}
                    cur_pred_hr_uuid = str(winner_pos0["hrönir_uuid"])
                    echo(f"    Pos 0: Selected initial canon Path {winner_pos0['path_uuid'][:8]} (Hrönir {cur_pred_hr_uuid[:8]})")
                else:
                    echo(typer.style(f"    Pos 0: No paths found for initial canon. End.",fg=typer.colors.YELLOW)); break
                continue # Move to next position

        # For positions > 0
        # Determine predecessor hrönir UUID from the NEWLY established canonical path for idx-1
        pred_k = str(idx-1)
        if pred_k in new_p:
            cur_pred_hr_uuid = new_p[pred_k].get("hrönir_uuid")
        else:
            # This implies a break in the chain, should not happen if loop proceeds correctly.
            echo(typer.style(f"    P{idx}: Predecessor {pred_k} not found in new canon. End.",fg=typer.colors.RED)); break

        logger.info(f"  Pos {idx}: Calc rank. Pred: {cur_pred_hr_uuid[:8] if cur_pred_hr_uuid else 'N'}")
        rdf=ratings.get_ranking(idx, cur_pred_hr_uuid) # cur_pred_hr_uuid is from new_p

        if not rdf.empty:
            winner = rdf.iloc[0]
            new_p[k]={"path_uuid":str(winner["path_uuid"]),"hrönir_uuid":str(winner["hrönir_uuid"])}
            # cur_pred_hr_uuid is already set for the *next* iteration by this winner's hrönir_uuid
            echo(f"    Pos {idx}: Win Path {winner['path_uuid'][:8]} (Hrönir {winner['hrönir_uuid'][:8]}, Elo {winner['elo_rating']})")
        else:
            # If no ranking/paths found for a position > 0 with a valid predecessor from new_p,
            # the canonical chain stops here for new entries.
            echo(typer.style(f"    P{idx}: No paths/ranks for this lineage. End.",fg=typer.colors.YELLOW)); break

    final_data={"title":old_c.get("title","Canon"),"path":new_p,"last_updated":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try: canon_fp.parent.mkdir(parents=True,exist_ok=True); canon_fp.write_text(json.dumps(final_data,indent=2)); echo(typer.style(f"Cascade done: {canon_fp}",fg=typer.colors.GREEN))
    except IOError as e: echo(typer.style(f"Err write {canon_fp}: {e}",fg=typer.colors.RED,err=True)); logger.error(f"Err write {canon_fp}: {e}")

@app.command("cast-votes")
def cast_votes(
    voting_path_uuid_str: Annotated[str, typer.Option("--voting-path-uuid", "-p", help="The path_uuid whose voting power is being used.")],
    verdicts_input: Annotated[str, typer.Option("--verdicts", "-v", help='JSON: {"pos_str": "winning_path_uuid_str"}')],
    canonical_path_file: Annotated[Path | None, typer.Option(help="Path to canonical path JSON file.")] = None,
    max_cascade_positions: Annotated[int, typer.Option(help="Max positions for cascade.")] = 100):
    typer.secho("DEBUG cast_votes: Entered command function VERY START.", fg=typer.colors.CYAN, err=True) # Raw print to stderr
    dm = storage.DataManager()
    resolved_canonical_path_file = canonical_path_file if canonical_path_file else Path(os.getenv("HRONIR_DATA_DIR", "data")) / "canonical_path.json"
    typer.secho("DEBUG cast_votes: DataManager obtained.", fg=typer.colors.CYAN, err=True)
    # dm.initialize_if_needed() # Not a public method on DataManager
    try: voting_token_path_uuid = uuid.UUID(voting_path_uuid_str)
    except ValueError: typer.secho(f"ERR: Invalid token UUID: {voting_path_uuid_str}",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    typer.secho(f"DEBUG cast_votes: Parsed token='{voting_token_path_uuid}'.", fg=typer.colors.CYAN, err=True)
    voting_path_model = dm.get_path_by_uuid(str(voting_token_path_uuid)) # Calls backend.initialize_if_needed
    typer.secho(f"DEBUG cast_votes: Fetched voting path: {voting_path_model.model_dump(mode='json') if voting_path_model else 'None'}.", fg=typer.colors.CYAN, err=True)
    if not voting_path_model: typer.secho(f"ERR: Token path {voting_token_path_uuid} not found.",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    if dm.is_token_consumed(str(voting_token_path_uuid)): typer.secho(f"ERR: Token {voting_token_path_uuid} already used.",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    pos_token = voting_path_model.position
    max_votes = 1 if pos_token < 1 else (math.floor(math.sqrt(pos_token)) if math.floor(math.sqrt(pos_token)) > 0 else 1)
    typer.secho(f"DEBUG cast_votes: Token {voting_token_path_uuid} (pos {pos_token}) allows {max_votes} votes.", fg=typer.colors.CYAN, err=True)
    if max_votes==0: typer.secho(f"ERR: Token {voting_token_path_uuid} has no power.",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    verdicts_d={}; verdicts_p=Path(verdicts_input)
    try: verdicts_d = json.loads(verdicts_p.read_text() if verdicts_p.is_file() else verdicts_input)
    except Exception as e: typer.secho(f"ERR: Verdict parse: {e}",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    if not isinstance(verdicts_d,dict): typer.secho("ERR: Verdicts not dict.",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    typer.secho(f"DEBUG cast_votes: Parsed verdicts: {verdicts_d}.", fg=typer.colors.CYAN, err=True)

    # --- BEGIN Position 0 IMMUTABILITY CHECK ---
    if "0" in verdicts_d: # Check if "0" (string key) is in the dictionary
        typer.secho("ERR: Voting on position 0 is not allowed.", fg=typer.colors.RED, err=True)
        # Optionally consume token here if that's the desired behavior for invalid vote attempts
        # dm.add_consumed_token(str(voting_token_path_uuid),datetime.datetime.now(datetime.timezone.utc))
        # dm.save_all_data_to_csvs()
        raise typer.Exit(code=1)
    # --- END Position 0 IMMUTABILITY CHECK ---

    num_v=len(verdicts_d)
    if num_v==0: typer.echo("No verdicts. Token consumed."); dm.add_consumed_token(str(voting_token_path_uuid),datetime.datetime.now(datetime.timezone.utc)); dm.save_all_data_to_csvs(); raise typer.Exit(code=0)
    if num_v > max_votes: typer.secho(f"ERR: Too many verdicts ({num_v}) for power ({max_votes}).",fg=typer.colors.RED,err=True); dm.add_consumed_token(str(voting_token_path_uuid),datetime.datetime.now(datetime.timezone.utc)); dm.save_all_data_to_csvs(); raise typer.Exit(code=1)
    if len(verdicts_d) != len(set(verdicts_d.keys())): typer.secho("ERR: Verdict positions not unique.",fg=typer.colors.RED,err=True); dm.add_consumed_token(str(voting_token_path_uuid),datetime.datetime.now(datetime.timezone.utc)); dm.save_all_data_to_csvs(); raise typer.Exit(code=1)

    valid_tm_log:list[dict[str,Any]]=[]; valid_vote_models:list[Vote]=[]; proc_duels:set[str]=set(); oldest_pos=float("inf") # Changed proc_duels to set()
    cur_canon=json.loads(resolved_canonical_path_file.read_text()).get("path",{}) if resolved_canonical_path_file.exists() else {}
    for pos_s, winner_s in verdicts_d.items():
        typer.secho(f"  Processing pos '{pos_s}', winner='{winner_s}'", fg=typer.colors.BLUE, err=True)
        try:
            pos_i=int(pos_s) # Already checked that pos_s cannot be "0"
            winner_obj=uuid.UUID(winner_s)
        except ValueError: typer.secho(f"Warn: Invalid verdict format pos '{pos_s}'. Skip.",fg=typer.colors.YELLOW,err=True); continue

        # Position 0 check already performed before this loop for the entire verdict set.
        # Individual check for pos_i == 0 here would be redundant but harmless.
        # if pos_i == 0:
        #     typer.secho(f"ERR: Internal - Position 0 verdict slipped through initial check. Pos: {pos_s}", fg=typer.colors.RED, err=True)
        #     continue # Should not happen if the above check works

        pred_hr=cur_canon.get(str(pos_i-1),{}).get("hrönir_uuid") if pos_i > 0 else None # This is fine, as pos_i > 0
        active=dm.get_active_duel_for_position(pos_i) # This should not be called with pos_i = 0
        typer.secho(f"  DEBUG (pos {pos_i}): Pred for duel: {pred_hr}, Active Duel: {active}", fg=typer.colors.BLUE, err=True)
        if not active: typer.secho(f"Warn: No active duel for pos {pos_i}. Skip.",fg=typer.colors.YELLOW,err=True); continue
        d_id=active["duel_id"]; pA=uuid.UUID(active["path_A_uuid"]); pB=uuid.UUID(active["path_B_uuid"])
        typer.secho(f"  DEBUG (pos {pos_i}): Duel {d_id} paths: A='{pA}', B='{pB}'", fg=typer.colors.BLUE, err=True)
        if winner_obj not in [pA,pB]: typer.secho(f"Warn: Voted winner {winner_s} not in duel for pos {pos_i}. Skip.",fg=typer.colors.YELLOW,err=True); continue
        side='A' if winner_obj==pA else 'B'; loser_obj=pB if side=='A' else pA
        win_hr=_get_successor_hronir_for_path(str(winner_obj)); lose_hr=_get_successor_hronir_for_path(str(loser_obj))
        if not win_hr or not lose_hr: typer.secho(f"Err: Cannot map paths in duel {d_id} to hrönirs. Skip.",fg=typer.colors.RED,err=True); continue
        win_p_model=dm.get_path_by_uuid(str(winner_obj)); duel_pred_hr=str(win_p_model.prev_uuid) if win_p_model and win_p_model.prev_uuid else None
        valid_tm_log.append({"position":pos_i,"winner_hrönir_uuid":win_hr,"loser_hrönir_uuid":lose_hr,"predecessor_hrönir_uuid":duel_pred_hr})
        valid_vote_models.append(Vote(duel_id=uuid.UUID(d_id),voting_token_path_uuid=voting_token_path_uuid,chosen_winner_side=side,position=pos_i))
        proc_duels.add(d_id);
        if pos_i < oldest_pos: oldest_pos=pos_i

    dm.add_consumed_token(str(voting_token_path_uuid),datetime.datetime.now(datetime.timezone.utc))
    if not valid_vote_models: typer.echo("No valid verdicts. Token consumed."); dm.save_all_data_to_csvs(); raise typer.Exit(code=0)
    typer.secho(f"DEBUG cast_votes: Valid votes for TM: {valid_tm_log}", fg=typer.colors.GREEN, err=True)
    try:
        tx_id=str(uuid.uuid5(voting_token_path_uuid,datetime.datetime.now(datetime.timezone.utc).isoformat()))
        tx_res=transaction_manager.record_transaction(session_id=tx_id,initiating_path_uuid=str(voting_token_path_uuid),session_verdicts=valid_tm_log)
        for vo in valid_vote_models: dm.add_vote(vo)
        for duel_id_res in proc_duels:
            d_details=dm.get_duel_details(duel_id_res)
            if d_details:
                dm.deactivate_duel(duel_id_res)
                pred_hr_new=cur_canon.get(str(d_details["position"]-1),{}).get("hrönir_uuid") if d_details["position"]>0 else None
                ratings.generate_and_store_new_pending_duel(d_details["position"],pred_hr_new,dm)
        dm.save_all_data_to_csvs()
        typer.echo(json.dumps({"message":"Votes recorded","tx_uuid":tx_res["transaction_uuid"]},indent=2)) # Normal output
    except Exception as e: logger.error(f"Vote recording phase error: {e}",exc_info=True); typer.secho(f"Vote recording error: {e}",fg=typer.colors.RED,err=True); raise typer.Exit(code=1)
    if oldest_pos != float("inf"):
        typer.echo(f"Oldest voted pos: {oldest_pos}. Triggering Cascade.")
        try: run_temporal_cascade(int(oldest_pos),max_cascade_positions,resolved_canonical_path_file,typer.echo)
        except Exception as e: logger.error(f"Cascade error: {e}",exc_info=True); typer.secho(f"Cascade error: {e}",fg=typer.colors.RED,err=True)
    else: typer.echo("No valid votes processed; Cascade not triggered.")
    typer.secho("Vote casting process complete.",fg=typer.colors.GREEN)

if __name__ == "__main__":
    main()
