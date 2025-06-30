import itertools
import math
import uuid
import logging # Added import

import pandas as pd

from . import storage  # To get DataManager
from .models import Vote


def _calculate_elo_probability(elo_a: float, elo_b: float) -> float:
    """Calculate the probability of A winning against B."""
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def _calculate_duel_entropy(elo_a: float, elo_b: float) -> float:
    """Calculate Shannon entropy for an Elo duel."""
    p_a = _calculate_elo_probability(elo_a, elo_b)
    if p_a == 0 or p_a == 1:
        return 0.0
    p_b = 1 - p_a
    if p_b == 0:
        return 0.0
    return -(p_a * math.log2(p_a) + p_b * math.log2(p_b))


import datetime # Add datetime for Vote model's recorded_at

def record_vote(
    duel_id: str, # Changed from position, winner, loser
    voting_token_path_uuid: str, # Changed from voter (which was also a path_uuid)
    chosen_winner_side: str, # 'A' or 'B'
    position: int # Denormalized from duel for convenience, or could be fetched from duel_id
    # winner_hrönir_uuid and loser_hrönir_uuid are no longer direct inputs here.
    # They are attributes of the duel identified by duel_id.
) -> None:
    """Records a structured vote linked to a specific duel instance."""
    logging.info(f"ratings.record_vote CALLED with: duel_id='{duel_id}', voting_token='{voting_token_path_uuid}', side='{chosen_winner_side}', pos='{position}'")
    data_manager = storage.DataManager()

    # Create the new Vote Pydantic model
    # vote_id and recorded_at have default factories
    new_vote = Vote(
        duel_id=uuid.UUID(duel_id),
        voting_token_path_uuid=uuid.UUID(voting_token_path_uuid), # This is a UUID5
        chosen_winner_side=chosen_winner_side,
        position=position
    )

    data_manager.add_vote(new_vote)
    data_manager.save_all_data_to_csvs() # This commits the change to DuckDB via backend.save_all_data()
    logging.info(f"Vote {new_vote.vote_id} recorded for duel {duel_id}.")


def get_ranking(
    position: int,
    predecessor_hronir_uuid: str | None,
) -> pd.DataFrame:
    """
    Calculate Elo ranking for path_uuids at a given position,
    considering only paths that descend directly from predecessor_hronir_uuid.
    """
    output_columns = ["path_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
    empty_df = pd.DataFrame(columns=output_columns)

    data_manager = storage.DataManager()
    # DataManager methods (like get_paths_by_position) call backend.initialize_if_needed() internally.

    # Get eligible paths
    eligible_paths_models = data_manager.get_paths_by_position(position)

    if predecessor_hronir_uuid is None:
        if position == 0:
            # For position 0, include paths with no predecessor or empty predecessor string
            eligible_paths_models = [
                p for p in eligible_paths_models if p.prev_uuid is None or str(p.prev_uuid) == ""
            ]
        else:
            # Non-zero position must have a predecessor to be ranked in a specific lineage
            return empty_df
    else:
        # Filter paths with the specified predecessor
        eligible_paths_models = [p for p in eligible_paths_models if str(p.prev_uuid) == predecessor_hronir_uuid]

    if not eligible_paths_models:
        return empty_df

    # Create path mapping: hrönir_uuid (content) to path_uuid (edge)
    # Both p.uuid (hrönir content) and p.path_uuid are UUID objects from PathModel
    hronir_to_path_map = {str(p.uuid): str(p.path_uuid) for p in eligible_paths_models}

    # Initialize ranking
    ELO_BASE = 1500.0
    ranking_data = []
    for path_model in eligible_paths_models:
        ranking_data.append(
            {
                "path_uuid": str(path_model.path_uuid), # path_uuid of the edge
                "hrönir_uuid": str(path_model.uuid),   # hrönir_uuid of the content node this path leads to
                "elo_rating": ELO_BASE,
                "games_played": 0,
                "wins": 0,
                "losses": 0,
            }
        )

    current_ranking_df = pd.DataFrame(ranking_data)
    if not ranking_data: # No eligible paths, return empty
        return empty_df

    current_ranking_df = current_ranking_df.set_index("path_uuid")


    # Get votes for this position using the new Vote model structure
    vote_models_for_position = data_manager.get_votes_by_position(position)

    if vote_models_for_position:
        K_FACTOR = 32
        for vote_model in vote_models_for_position:
            duel_details = data_manager.get_duel_details(str(vote_model.duel_id))
            if not duel_details:
                logging.warning(f"ratings.get_ranking: Could not find duel details for duel_id {vote_model.duel_id} from vote {vote_model.vote_id}. Skipping vote.")
                continue

            # Determine winner and loser path_uuids from the duel details and chosen_winner_side
            actual_winner_path_uuid: str | None = None
            actual_loser_path_uuid: str | None = None

            if vote_model.chosen_winner_side == 'A':
                actual_winner_path_uuid = duel_details["path_A_uuid"]
                actual_loser_path_uuid = duel_details["path_B_uuid"]
            elif vote_model.chosen_winner_side == 'B':
                actual_winner_path_uuid = duel_details["path_B_uuid"]
                actual_loser_path_uuid = duel_details["path_A_uuid"]

            if not actual_winner_path_uuid or not actual_loser_path_uuid:
                logging.warning(f"ratings.get_ranking: Could not determine winner/loser paths for vote {vote_model.vote_id} on duel {vote_model.duel_id}. Skipping.")
                continue

            # Check if these paths are part of the current ranking context
            # (i.e., among the eligible_paths for this specific get_ranking call based on position and predecessor)
            if (
                actual_winner_path_uuid not in current_ranking_df.index
                or actual_loser_path_uuid not in current_ranking_df.index
            ):
                if position == 0 and predecessor_hronir_uuid is None: # Extra logging for debug
                    logging.info(f"ratings.get_ranking (pos 0): Vote for duel {vote_model.duel_id} (winner: {actual_winner_path_uuid}, loser: {actual_loser_path_uuid}) involves paths not in current ranking context. Skipping. Index: {current_ranking_df.index.to_list()}")
                continue

            # Update stats
            current_ranking_df.loc[actual_winner_path_uuid, "games_played"] += 1
            current_ranking_df.loc[actual_loser_path_uuid, "games_played"] += 1
            current_ranking_df.loc[actual_winner_path_uuid, "wins"] += 1
            current_ranking_df.loc[actual_loser_path_uuid, "losses"] += 1

            r_winner = current_ranking_df.loc[actual_winner_path_uuid, "elo_rating"]
            r_loser = current_ranking_df.loc[actual_loser_path_uuid, "elo_rating"]

            expected_winner_prob = _calculate_elo_probability(r_winner, r_loser)

            new_r_winner = r_winner + K_FACTOR * (1 - expected_winner_prob)
            new_r_loser = r_loser + K_FACTOR * (0 - (1 - expected_winner_prob))

            current_ranking_df.loc[actual_winner_path_uuid, "elo_rating"] = new_r_winner
            current_ranking_df.loc[actual_loser_path_uuid, "elo_rating"] = new_r_loser

        # Round ratings to integers after all votes for the position are processed
        current_ranking_df["elo_rating"] = current_ranking_df["elo_rating"].round().astype(int)

    final_df = current_ranking_df.reset_index()
    final_df = final_df.sort_values(
        by=["elo_rating", "wins", "games_played"], ascending=[False, False, True]
    )

    # Conditional logging for easier debugging
    if position == 0 and predecessor_hronir_uuid is None:
        logging.info(f"ratings.get_ranking for pos 0 (root) final_df just before return:\n{final_df[output_columns].to_string(index=False)}")
        # Log the Vote models again to confirm what was used by this point
        logged_votes_for_pos_0 = data_manager.get_votes_by_position(0)
        logging.info(f"ratings.get_ranking for pos 0 (root) VOTE MODELS processed by end of func: {[v.model_dump(mode='json') for v in logged_votes_for_pos_0]}")

    return final_df[output_columns]


def determine_next_duel_entropy(position: int, predecessor_hronir_uuid: str | None) -> dict | None:
    """
    Choose the pair of paths with MAX Shannon entropy of predicted outcome.
    """
    ranking_df = get_ranking(position=position, predecessor_hronir_uuid=predecessor_hronir_uuid)

    if ranking_df.empty or len(ranking_df) < 2:
        return None

    best_pair_info = {"path_A": None, "path_B": None, "entropy": -1.0}
    # Ensure path_uuid is string for dict keys if coming from DataFrame index
    path_elos = ranking_df.set_index("path_uuid")["elo_rating"].to_dict()
    path_keys = list(path_elos.keys()) # These are path_uuids as strings

    possible_duels_count = 0
    low_entropy_duels_count = 0
    ENTROPY_SATURATION_THRESHOLD = 0.2

    for path_A_uuid, path_B_uuid in itertools.combinations(path_keys, 2):
        possible_duels_count += 1
        current_entropy = _calculate_duel_entropy(path_elos[str(path_A_uuid)], path_elos[str(path_B_uuid)])

        if current_entropy < ENTROPY_SATURATION_THRESHOLD:
            low_entropy_duels_count += 1

        if current_entropy > best_pair_info["entropy"]:
            best_pair_info["path_A"] = str(path_A_uuid)
            best_pair_info["path_B"] = str(path_B_uuid)
            best_pair_info["entropy"] = current_entropy

    if best_pair_info["path_A"] is None: # No valid duels found that improve entropy
        return None

    if possible_duels_count > 0 and low_entropy_duels_count == possible_duels_count:
        logging.info( # Changed print to logging.info
            f"INFO: Saturated league for position {position}, lineage {predecessor_hronir_uuid}. "
            f"All {possible_duels_count} possible duels have entropy < {ENTROPY_SATURATION_THRESHOLD}."
        )
        # If all duels are low entropy, still return the best one found if its entropy is non-negative.
        # The original check 'if best_pair_info["entropy"] < 0: return None' might be too strict if 0 entropy is acceptable.
        # For now, keeping original logic: if max entropy is < 0 (e.g. -1 initial), means no pair found.

    return {
        "position": position,
        "strategy": "max_shannon_entropy",
        "entropy": best_pair_info["entropy"],
        "duel_pair": { # Ensure these are strings
            "path_A": str(best_pair_info["path_A"]),
            "path_B": str(best_pair_info["path_B"]),
        },
    }


def check_path_qualification(
    path_uuid: str,
    ratings_df: pd.DataFrame, # This is the result of get_ranking for the context
    all_paths_in_position_df: pd.DataFrame, # This is a df of all PathModels at the position
) -> bool:
    """
    Check if a path meets the criteria to be marked as 'QUALIFIED'.
    """
    ELO_QUALIFICATION_THRESHOLD = 1550

    if ratings_df.empty:
        return False

    # path_uuid is string, ensure comparison with string column
    path_data_series = ratings_df[ratings_df["path_uuid"].astype(str) == str(path_uuid)]
    if path_data_series.empty:
        return False

    elo_rating = path_data_series.iloc[0]["elo_rating"]
    wins = path_data_series.iloc[0]["wins"]

    if elo_rating >= ELO_QUALIFICATION_THRESHOLD:
        return True

    # Qualification by wins based on number of competitors
    if all_paths_in_position_df is None or all_paths_in_position_df.empty:
        num_competitors = 0
    else:
        # Ensure 'path_uuid' column exists before calling unique()
        if "path_uuid" in all_paths_in_position_df.columns:
            num_competitors = len(all_paths_in_position_df["path_uuid"].unique())
        else: # Should not happen if all_paths_in_position_df is correctly populated
            num_competitors = 0


    min_wins_threshold = float("inf") # Default to needing infinite wins if no competitors
    if num_competitors == 1: # Only one path, qualifies by default if ELO not met by wins=0
        min_wins_threshold = 0
    elif num_competitors > 1:
        min_wins_threshold = math.ceil(math.log2(num_competitors))

    # If elo is not met, path can still qualify if it has enough wins for the number of competitors
    if wins >= min_wins_threshold:
        return True

    return False
