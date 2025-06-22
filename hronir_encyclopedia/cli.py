import json
import shutil
import subprocess
from pathlib import Path
from typing_extensions import Annotated # Use typing_extensions for compatibility

import typer

from . import database, gemini_util, ratings, storage

app = typer.Typer(
    help="Hrönir Encyclopedia CLI: A tool for managing and generating content for the encyclopedia.",
    add_completion=True, # Typer will handle shell completion
    no_args_is_help=True # Show help if no command is given
)

# Re-map old _cmd functions to new Typer command functions
# Original functions are kept with minimal changes to their core logic,
# only adapting their signatures to Typer's way of handling arguments.

@app.command(help="Consolidate fork rankings and update the canonical path.")
def consolidate_book(
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.", exists=True, file_okay=False, dir_okay=True, readable=True)] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Directory containing forking path CSV files.", exists=True, file_okay=False, dir_okay=True, readable=True)] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Path to the canonical path JSON file.", dir_okay=False, writable=True)] = Path("data/canonical_path.json"),
    max_positions_to_consolidate: Annotated[int, typer.Option(help="Maximum number of positions to attempt to consolidate.")] = 100 # Evita loop infinito
):
    """
    Analyzes fork rankings and updates the canonical path of forks.
    Iterates sequentially through positions, determining the canonical fork for each
    based on the winning fork of the previous position's canonical hrönir.
    """
    if not ratings_dir.is_dir():
        typer.echo(f"Ratings directory not found: {ratings_dir}", err=True)
        raise typer.Exit(code=1)
    if not forking_path_dir.is_dir():
        typer.echo(f"Forking path directory not found: {forking_path_dir}", err=True)
        raise typer.Exit(code=1)

    try:
        canonical_path_data = (
            json.loads(canonical_path_file.read_text())
            if canonical_path_file.exists()
            else {"title": "The Hrönir Encyclopedia - Canonical Path", "path": {}}
        )
    except json.JSONDecodeError:
        typer.echo(f"Error reading or parsing canonical path file: {canonical_path_file}", err=True)
        canonical_path_data = {"title": "The Hrönir Encyclopedia - Canonical Path", "path": {}}

    if "path" not in canonical_path_data or not isinstance(canonical_path_data["path"], dict):
        canonical_path_data["path"] = {}


    updated_any_position = False
    current_predecessor_hronir_uuid: str | None = None

    for position_idx in range(max_positions_to_consolidate):
        position_str = str(position_idx)

        if position_idx == 0:
            predecessor_hronir_uuid_for_ranking = None
        else:
            # Obter o hrönir_uuid sucessor do fork canônico da posição anterior
            prev_pos_canonical_info = storage.get_canonical_fork_info(position_idx - 1, canonical_path_file)
            if not prev_pos_canonical_info or "hrönir_uuid" not in prev_pos_canonical_info:
                typer.echo(f"Canonical fork for position {position_idx - 1} not found or invalid. Stopping consolidation.")
                # Se o caminho canônico quebrou, remove todas as posições subsequentes
                keys_to_remove = [k for k in canonical_path_data["path"] if int(k) >= position_idx]
                if keys_to_remove:
                    typer.echo(f"Removing subsequent canonical entries from position {position_idx} onwards due to broken path.")
                    for k in keys_to_remove:
                        del canonical_path_data["path"][k]
                    updated_any_position = True # Marcamos como atualizado porque removemos algo
                break
            predecessor_hronir_uuid_for_ranking = prev_pos_canonical_info["hrönir_uuid"]

        typer.echo(f"Consolidating position {position_idx} (predecessor hrönir: {predecessor_hronir_uuid_for_ranking or 'None'})...")

        # `ratings.get_ranking` agora retorna ranking de fork_uuids
        ranking_df = ratings.get_ranking(
            position=position_idx,
            predecessor_hronir_uuid=predecessor_hronir_uuid_for_ranking,
            forking_path_dir=forking_path_dir,
            ratings_dir=ratings_dir # Corrigido de ratings_base_dir
        )

        if ranking_df.empty:
            typer.echo(f"No ranking found for eligible forks at position {position_idx}. Path ends here.")
            # Se esta posição tinha uma entrada canônica, e agora não tem mais ranking, ela deve ser removida.
            # E todas as subsequentes.
            keys_to_remove = [k for k in canonical_path_data["path"] if int(k) >= position_idx]
            if keys_to_remove:
                typer.echo(f"Removing canonical entries from position {position_idx} onwards as path ends.")
                for k in keys_to_remove:
                    if k in canonical_path_data["path"]: # Segurança
                        del canonical_path_data["path"][k]
                        updated_any_position = True
            break # Fim do caminho canônico

        # O campeão é o fork_uuid no topo do ranking
        champion_fork_uuid = ranking_df.iloc[0]["fork_uuid"]
        champion_hronir_uuid = ranking_df.iloc[0]["hrönir_uuid"] # hrönir_uuid sucessor do fork campeão
        champion_elo = ranking_df.iloc[0]["elo_rating"]

        current_entry_in_path = canonical_path_data["path"].get(position_str)
        new_entry_for_path = {"fork_uuid": champion_fork_uuid, "hrönir_uuid": champion_hronir_uuid}

        if current_entry_in_path != new_entry_for_path:
            canonical_path_data["path"][position_str] = new_entry_for_path
            typer.echo(
                f"Position {position_idx}: Set fork {champion_fork_uuid[:8]} (hrönir: {champion_hronir_uuid[:8]}, Elo: {champion_elo}) as canonical."
            )
            updated_any_position = True
        else:
            typer.echo(f"Position {position_idx}: Canonical fork {champion_fork_uuid[:8]} remains unchanged.")

        # O hrönir_uuid sucessor do fork campeão atual se torna o predecessor para a próxima posição
        # Esta linha não é mais necessária aqui pois `predecessor_hronir_uuid_for_ranking` é determinado no início do loop
        # current_predecessor_hronir_uuid = champion_hronir_uuid

        # Se não houve atualização nesta posição e não há mais posições nos ratings, podemos parar.
        # (Esta condição de parada é heurística, o loop principal por max_positions ou quebra de caminho é mais robusto)

    if updated_any_position:
        try:
            canonical_path_file.parent.mkdir(parents=True, exist_ok=True)
            canonical_path_file.write_text(json.dumps(canonical_path_data, indent=2))
            typer.echo(f"Canonical path file updated: {canonical_path_file}")
        except Exception as e:
            typer.echo(f"Error writing canonical path file: {e}", err=True)
            raise typer.Exit(code=1)
    else:
        typer.echo("No changes to the canonical path.")

    typer.echo("Canonical path consolidation complete.")


# Command `export` and `tree` removed as they depended on the old book structure.

@app.command(help="Validate a chapter file (basic check).")
def validate(
    chapter: Annotated[Path, typer.Argument(help="Path to chapter markdown file.", exists=True, dir_okay=False, readable=True)],
):
    """
    Performs a basic validation check on a chapter file.
    Currently, just checks for existence.
    """
    # The original logic was just a print, keeping it simple.
    # More complex validation would go into storage.validate_or_move
    typer.echo(f"Chapter file {chapter} exists and is readable. Basic validation passed.")
    # For a more meaningful validation, one might call storage.validate_or_move or parts of it.


@app.command(help="Store a chapter by UUID in the library.")
def store(
    chapter: Annotated[Path, typer.Argument(help="Path to chapter markdown file.", exists=True, dir_okay=False, readable=True)],
    prev: Annotated[str, typer.Option(help="UUID of the previous chapter.")] = None, # Made optional as in original
):
    """
    Stores a given chapter file into the hrönir library, associating it with a predecessor UUID if provided.
    """
    uuid_str = storage.store_chapter(chapter, prev_uuid=prev)
    typer.echo(uuid_str)


# Helper function to find successor hrönir_uuid for a given fork_uuid
# This could also live in storage.py if it's deemed generally useful
def _get_successor_hronir_for_fork(fork_uuid_to_find: str, forking_path_dir: Path) -> str | None:
    if not forking_path_dir.is_dir():
        return None
    for csv_file in forking_path_dir.glob("*.csv"):
        if csv_file.stat().st_size > 0:
            try:
                df_forks = pd.read_csv(csv_file, dtype=str) # Ler tudo como string
                # Ensure required columns are present
                if not all(col in df_forks.columns for col in ["fork_uuid", "uuid"]):
                    continue
                # Search for the fork_uuid
                # Using .astype(str) again for fork_uuid just in case, though dtype=str should handle it.
                match = df_forks[df_forks["fork_uuid"].astype(str) == fork_uuid_to_find]
                if not match.empty:
                    return match.iloc[0]["uuid"] # 'uuid' is the successor hrönir_uuid
            except pd.errors.EmptyDataError:
                continue
            except Exception: # Broad exception for other parsing errors
                # Consider logging this error
                continue
    return None


# A primeira definição de 'vote' será sobrescrita por esta, que é a desejada.
@app.command(help="Record a voted duel result between two forks.")
def vote(
    position: Annotated[int, typer.Option(help="Chapter position being voted on.")],
    voter_fork_uuid: Annotated[str, typer.Option(help="Fork UUID of the voter (their PoW).")],
    winner_fork_uuid: Annotated[str, typer.Option(help="Winning Fork UUID of the duel.")],
    loser_fork_uuid: Annotated[str, typer.Option(help="Losing Fork UUID of the duel.")],
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Directory containing forking path CSV files.")] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Path to the canonical path JSON file.")] = Path("data/canonical_path.json"),
):
    """
    Records a vote for a winner_fork_uuid against a loser_fork_uuid for a given chapter position,
    only if the vote corresponds to the officially curated duel for that position's lineage.
    The vote itself is recorded in terms of the successor hrönir_uuids of these forks.
    """
    if winner_fork_uuid == loser_fork_uuid:
        typer.echo(json.dumps({"error": "Winner fork and loser fork cannot be the same.", "submitted_winner_fork": winner_fork_uuid, "submitted_loser_fork": loser_fork_uuid}, indent=2))
        raise typer.Exit(code=1)

    # 1. Get the canonical predecessor hrönir_uuid for the current position
    predecessor_hronir_uuid: str | None = None
    if position > 0:
        canonical_fork_info_prev_pos = storage.get_canonical_fork_info(position - 1, canonical_path_file)
        if not canonical_fork_info_prev_pos or "hrönir_uuid" not in canonical_fork_info_prev_pos:
            typer.echo(json.dumps({
                "error": f"Could not determine canonical predecessor hrönir from position {position - 1} using {canonical_path_file}.",
                "position_requested": position
            }, indent=2))
            raise typer.Exit(code=1)
        predecessor_hronir_uuid = canonical_fork_info_prev_pos["hrönir_uuid"]
    elif position < 0:
         typer.echo(json.dumps({"error": "Invalid position. Must be >= 0.", "position_requested": position}, indent=2))
         raise typer.Exit(code=1)

    # 2. Determine the official duel of forks for the position
    official_duel_info = ratings.determine_next_duel(
        position=position,
        predecessor_hronir_uuid=predecessor_hronir_uuid,
        forking_path_dir=forking_path_dir,
        ratings_dir=ratings_dir
    )

    if not official_duel_info or "duel_pair" not in official_duel_info:
        typer.echo(json.dumps({
            "error": "Could not determine an official duel for this position and lineage. Vote cannot be validated.",
            "position": position,
            "predecessor_hronir_uuid_used": predecessor_hronir_uuid
        }, indent=2))
        raise typer.Exit(code=1)

    official_fork_A = official_duel_info["duel_pair"].get("fork_A")
    official_fork_B = official_duel_info["duel_pair"].get("fork_B")

    if not official_fork_A or not official_fork_B:
        typer.echo(json.dumps({
            "error": "Official duel data is incomplete. Cannot validate vote.",
            "official_duel_info": official_duel_info
        }, indent=2))
        raise typer.Exit(code=1)

    # 3. Validate submitted vote against the official duel
    submitted_fork_pair = set([winner_fork_uuid, loser_fork_uuid])
    official_fork_pair = set([official_fork_A, official_fork_B])

    if submitted_fork_pair != official_fork_pair:
        typer.echo(json.dumps({
            "error": "Vote rejected. The submitted fork pair does not match the officially curated duel.",
            "submitted_duel_forks": {"winner": winner_fork_uuid, "loser": loser_fork_uuid},
            "expected_duel_forks": {"fork_A": official_fork_A, "fork_B": official_fork_B},
            "position": position,
            "predecessor_hronir_uuid_used": predecessor_hronir_uuid
        }, indent=2))
        raise typer.Exit(code=1)

    # 4. Map validated winner/loser fork_uuids to their successor hrönir_uuids
    winner_hronir_uuid = _get_successor_hronir_for_fork(winner_fork_uuid, forking_path_dir)
    loser_hronir_uuid = _get_successor_hronir_for_fork(loser_fork_uuid, forking_path_dir)

    if not winner_hronir_uuid or not loser_hronir_uuid:
        typer.echo(json.dumps({
            "error": "Could not map one or both duel forks to their successor hrönir_uuids. Check forking_path data.",
            "winner_fork_uuid": winner_fork_uuid, "mapped_hronir": winner_hronir_uuid,
            "loser_fork_uuid": loser_fork_uuid, "mapped_hronir": loser_hronir_uuid
        }, indent=2))
        raise typer.Exit(code=1)

    # 5. Record the vote (using hrönir_uuids for the actual record, voter is a fork_uuid)
    try:
        with database.open_database() as conn:
            ratings.record_vote(
                position=position,
                voter=voter_fork_uuid, # Voter is a fork_uuid
                winner=winner_hronir_uuid, # Winner is a hrönir_uuid (successor of winner_fork)
                loser=loser_hronir_uuid,   # Loser is a hrönir_uuid (successor of loser_fork)
                conn=conn
            )
    except Exception as e: # Catch potential DB errors or other issues from record_vote
        typer.echo(json.dumps({
            "error": f"Failed to record vote in the database: {e}",
            "position": position, "voter": voter_fork_uuid,
            "winner_hronir": winner_hronir_uuid, "loser_hronir": loser_hronir_uuid
        }, indent=2))
        raise typer.Exit(code=1)

    typer.echo(json.dumps({
        "message": "Vote for forks successfully validated and recorded (as hrönir duel). System uncertainty reduced.",
        "position": position,
        "voter_fork_uuid": voter_fork_uuid,
        "winner_fork_uuid": winner_fork_uuid,
        "loser_fork_uuid": loser_fork_uuid,
        "recorded_duel_hrönirs": {"winner": winner_hronir_uuid, "loser": loser_hronir_uuid},
        "duel_strategy": official_duel_info.get("strategy")
    }, indent=2))


@app.command(help="Validate and repair storage, audit forking CSVs.")
def audit():
    """
    Performs audit operations: validates chapters in the library,
    and audits forking path CSV files.
    """
    library_dir = Path("the_library")
    typer.echo(f"Auditing library directory: {library_dir}...")
    # This part needs to be adjusted. `validate_or_move` expects a specific file.
    # We should iterate through hrönirs in a way that's compatible with `purge_fake_hronirs` logic,
    # or rely on `purge_fake_hronirs` called by `clean` command.
    # For now, let's simplify the audit's scope for this command, focusing on forking paths.
    # A more thorough audit of `the_library` is implicitly handled by `storage.chapter_exists`
    # when other commands use it, and explicitly by `clean`.
    # Consider enhancing `audit` in the future if a standalone deep library audit is needed here.
    typer.echo(f"Auditing hrönirs in {library_dir} (basic check via purge_fake_hronirs in 'clean' command)...")
    # No direct action on library_dir here, purge_fake_hronirs in 'clean' is more comprehensive.

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Auditing forking path directory: {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"):
            storage.audit_forking_csv(csv_file)
    else:
        typer.echo(f"Forking path directory {fork_dir} not found. Skipping audit.")
    typer.echo("Audit complete (Note: hrönir validation primarily via 'clean' command).")


@app.command(help="Generate competing chapters from a predecessor and record an initial vote.")
def synthesize(
    position: Annotated[int, typer.Option(help="Chapter position for the new hrönirs.")],
    prev: Annotated[str, typer.Option(help="UUID of the predecessor chapter to fork from.")],
):
    """
    Synthesizes two new hrönirs from a predecessor for a given position
    and records an initial 'vote' or assessment by the generating agent.
    """
    typer.echo(
        f"Synthesizing two new hrönirs from predecessor '{prev}' "
        f"at position {position}..."
    )
    with database.open_database() as conn:
        voter_uuid = "00000000-agent-0000-0000-000000000000" # Example agent UUID
        winner_uuid = gemini_util.auto_vote(position, prev, voter_uuid, conn=conn)
    typer.echo(f"Synthesis complete. New canonical candidate: {winner_uuid}")


@app.command(help="Show Elo rankings for a chapter position.")
def ranking(
    position: Annotated[int, typer.Argument(help="The chapter position to rank.")],
    ratings_dir: Annotated[Path, typer.Option(help="Directory containing rating CSV files.")] = Path("ratings"),
):
    """
    Displays the Elo rankings for hrönirs at a specific chapter position.
    """
    # The 'base' argument for get_ranking was Path(base), so passing ratings_dir directly.
    ranking_data = ratings.get_ranking(position, base=ratings_dir)
    if ranking_data.empty:
        typer.echo(f"No ranking data found for position {position}.")
    else:
        typer.echo(f"Ranking for Position {position}:")
        # Typer automatically handles printing DataFrames nicely with rich if available,
        # otherwise, it falls back to standard print. For explicit control, use to_string().
        typer.echo(ranking_data.to_string(index=False))

@app.command(help="Obtém o duelo de máxima entropia entre forks para uma posição.")
def get_duel(
    position: Annotated[int, typer.Option(help="A posição do capítulo para a qual obter o duelo de forks.")],
    ratings_dir: Annotated[Path, typer.Option(help="Diretório contendo arquivos CSV de classificação.")] = Path("ratings"),
    forking_path_dir: Annotated[Path, typer.Option(help="Diretório contendo arquivos CSV de caminhos de bifurcação.")] = Path("forking_path"),
    canonical_path_file: Annotated[Path, typer.Option(help="Caminho para o arquivo JSON do caminho canônico.")] = Path("data/canonical_path.json"),
):
    """
    Obtém o duelo de forks de máxima entropia para uma determinada posição,
    considerando a linhagem canônica.
    """
    predecessor_hronir_uuid: str | None = None
    if position > 0:
        canonical_fork_info_prev_pos = storage.get_canonical_fork_info(position - 1, canonical_path_file)
        if not canonical_fork_info_prev_pos or "hrönir_uuid" not in canonical_fork_info_prev_pos:
            typer.echo(json.dumps({
                "error": f"Não foi possível determinar o hrönir predecessor canônico da posição {position - 1}. "
                         f"Execute 'consolidate-book' ou verifique o arquivo {canonical_path_file}.",
                "position_requested": position
            }, indent=2))
            raise typer.Exit(code=1)
        predecessor_hronir_uuid = canonical_fork_info_prev_pos["hrönir_uuid"]
    elif position < 0:
        typer.echo(json.dumps({"error": "Posição inválida. Deve ser >= 0.", "position_requested": position}, indent=2))
        raise typer.Exit(code=1)

    # `determine_next_duel` agora lida com forks
    duel_info = ratings.determine_next_duel(
        position=position,
        predecessor_hronir_uuid=predecessor_hronir_uuid,
        forking_path_dir=forking_path_dir,
        ratings_dir=ratings_dir
    )

    if duel_info:
        # O formato de duel_info já é:
        # {
        #   "position": position,
        #   "strategy": "max_entropy_duel",
        #   "entropy": max_entropy,
        #   "duel_pair": {
        #       "fork_A": duel_fork_A_uuid,
        #       "fork_B": duel_fork_B_uuid,
        #   }
        # }
        typer.echo(json.dumps(duel_info, indent=2))
    else:
        typer.echo(json.dumps({
            "error": "Não foi possível determinar um duelo de forks. "
                     "Verifique se existem forks elegíveis suficientes (pelo menos 2) para a linhagem e posição.",
            "position": position,
            "predecessor_hronir_uuid_used": predecessor_hronir_uuid
            }, indent=2))


def _git_remove_deleted_files(): # Renamed to avoid conflict and be more descriptive
    """Stage deleted files in git if git is available and files were deleted."""
    try:
        # Check if we are in a git repository and git is installed
        subprocess.check_call(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        output = subprocess.check_output(["git", "ls-files", "--deleted"], text=True, stderr=subprocess.PIPE)
        if not output.strip():
            typer.echo("No deleted files to stage in Git.")
            return

        for path_str in output.splitlines():
            if path_str:
                typer.echo(f"Staging deleted file for removal in Git: {path_str}")
                subprocess.run(["git", "rm", "--ignore-unmatch", path_str], check=True)
        typer.echo("Staged deleted files in Git.")

    except FileNotFoundError:
        typer.echo("Git command not found. Skipping Git operations.", err=True)
    except subprocess.CalledProcessError as e:
        if "not a git repository" in e.stderr.lower():
             typer.echo("Not inside a Git repository. Skipping Git operations for deleted files.")
        else:
            typer.echo(f"Git ls-files or rm command failed: {e.stderr}", err=True)
    except Exception as e:
        typer.echo(f"An unexpected error occurred with Git operations: {e}", err=True)


@app.command(help="Remove invalid entries (fake hrönirs, votes, etc.) from storage.")
def clean(
    git_stage_deleted: Annotated[bool, typer.Option("--git", help="Also stage deleted files for removal in the Git index.")] = False,
):
    """
    Cleans up storage by removing entries identified as 'fake' or invalid.
    Optionally, stages these deletions in Git.
    """
    typer.echo("Starting cleanup process...")
    storage.purge_fake_hronirs() # Assumes this function prints its actions

    fork_dir = Path("forking_path")
    if fork_dir.exists():
        typer.echo(f"Cleaning fake forking CSVs in {fork_dir}...")
        for csv_file in fork_dir.glob("*.csv"):
            storage.purge_fake_forking_csv(csv_file) # Assumes this function prints its actions
    else:
        typer.echo(f"Forking path directory {fork_dir} not found. Skipping.")

    rating_dir = Path("ratings")
    if rating_dir.exists():
        typer.echo(f"Cleaning fake votes CSVs in {rating_dir}...")
        for csv_file in rating_dir.glob("*.csv"):
            storage.purge_fake_votes_csv(csv_file) # Assumes this function prints its actions
    else:
        typer.echo(f"Ratings directory {rating_dir} not found. Skipping.")

    if git_stage_deleted:
        typer.echo("Attempting to stage deleted files in Git...")
        _git_remove_deleted_files()

    typer.echo("Cleanup complete.")


# Placeholder for 'submit' command if it was meant to be kept.
# If not, it can be removed. For now, it's commented out as per original structure.
# @app.command(help="Submit changes (placeholder).")
# def submit_cmd():
#     typer.echo("Submit command is in development.")


def main(argv: list[str] | None = None):
    # If argv is None, Typer's app() will use sys.argv by default (which is what we want for CLI execution).
    # If argv is provided (e.g., from a test), app() will use that specific list of arguments.
    app(args=argv)

if __name__ == "__main__":
    main() # Called with no arguments, so app() will use sys.argv
