import itertools
import math
import uuid

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


def record_vote(
    position: int,
    voter: str,
    winner: str,
    loser: str,
) -> None:
    """Record a vote using the pandas-based data manager."""
    data_manager = storage.DataManager()
    data_manager.initialize_and_load()

    vote_uuid = str(uuid.uuid4())
    vote = Vote(uuid=vote_uuid, position=position, voter=voter, winner=winner, loser=loser)

    data_manager.add_vote(vote)
    data_manager.save_all_data_to_csvs()


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
    data_manager.initialize_and_load()

    # Get eligible paths
    eligible_paths = data_manager.get_paths_by_position(position)

    if predecessor_hronir_uuid is None:
        if position == 0:
            # For position 0, include paths with no predecessor or empty predecessor
            eligible_paths = [
                p for p in eligible_paths if p.prev_uuid is None or str(p.prev_uuid) == ""
            ]
        else:
            return empty_df
    else:
        # Filter paths with the specified predecessor
        eligible_paths = [p for p in eligible_paths if str(p.prev_uuid) == predecessor_hronir_uuid]

    if not eligible_paths:
        return empty_df

    # Create path mapping
    hronir_to_path_map = {str(p.uuid): str(p.path_uuid) for p in eligible_paths}

    # Initialize ranking
    ELO_BASE = 1500.0
    ranking_data = []
    for path in eligible_paths:
        ranking_data.append(
            {
                "path_uuid": str(path.path_uuid),
                "hrönir_uuid": str(path.uuid),
                "elo_rating": ELO_BASE,
                "games_played": 0,
                "wins": 0,
                "losses": 0,
            }
        )

    current_ranking_df = pd.DataFrame(ranking_data).set_index("path_uuid")

    # Get votes for this position
    votes = data_manager.get_votes_by_position(position)

    if votes:
        # Process votes
        votes_data = [
            {
                "winner": v.winner,
                "loser": v.loser,
                "voter": v.voter,
            }
            for v in votes
        ]
        df_votes = pd.DataFrame(votes_data)

        if not df_votes.empty:
            # Map hrönir UUIDs to path UUIDs
            df_votes["winner_path_uuid"] = df_votes["winner"].map(hronir_to_path_map)
            df_votes["loser_path_uuid"] = df_votes["loser"].map(hronir_to_path_map)

            # Keep only valid votes (both winner and loser are eligible)
            valid_votes = df_votes.dropna(subset=["winner_path_uuid", "loser_path_uuid"])
            valid_votes = valid_votes[
                valid_votes["winner_path_uuid"] != valid_votes["loser_path_uuid"]
            ]

            if not valid_votes.empty:
                K_FACTOR = 32
                for _, vote_row in valid_votes.iterrows():
                    winner_path = vote_row["winner_path_uuid"]
                    loser_path = vote_row["loser_path_uuid"]

                    if (
                        winner_path not in current_ranking_df.index
                        or loser_path not in current_ranking_df.index
                    ):
                        continue

                    # Update stats
                    current_ranking_df.loc[winner_path, "wins"] += 1
                    current_ranking_df.loc[loser_path, "losses"] += 1
                    current_ranking_df.loc[winner_path, "games_played"] += 1
                    current_ranking_df.loc[loser_path, "games_played"] += 1

                    # Calculate new Elo ratings
                    r_winner = current_ranking_df.loc[winner_path, "elo_rating"]
                    r_loser = current_ranking_df.loc[loser_path, "elo_rating"]
                    expected_winner = _calculate_elo_probability(r_winner, r_loser)

                    new_r_winner = r_winner + K_FACTOR * (1 - expected_winner)
                    new_r_loser = r_loser + K_FACTOR * (0 - (1 - expected_winner))

                    current_ranking_df.loc[winner_path, "elo_rating"] = new_r_winner
                    current_ranking_df.loc[loser_path, "elo_rating"] = new_r_loser

                # Round ratings to integers
                current_ranking_df["elo_rating"] = (
                    current_ranking_df["elo_rating"].round().astype(int)
                )

    # Return sorted results
    final_df = current_ranking_df.reset_index()
    final_df = final_df.sort_values(
        by=["elo_rating", "wins", "games_played"], ascending=[False, False, True]
    )
    return final_df[output_columns]


def determine_next_duel_entropy(position: int, predecessor_hronir_uuid: str | None) -> dict | None:
    """
    Choose the pair of paths with MAX Shannon entropy of predicted outcome.
    """
    ranking_df = get_ranking(position=position, predecessor_hronir_uuid=predecessor_hronir_uuid)

    if ranking_df.empty or len(ranking_df) < 2:
        return None

    best_pair_info = {"path_A": None, "path_B": None, "entropy": -1.0}
    path_elos = ranking_df.set_index("path_uuid")["elo_rating"].to_dict()
    path_keys = list(path_elos.keys())

    possible_duels_count = 0
    low_entropy_duels_count = 0
    ENTROPY_SATURATION_THRESHOLD = 0.2

    for path_A_uuid, path_B_uuid in itertools.combinations(path_keys, 2):
        possible_duels_count += 1

        current_entropy = _calculate_duel_entropy(path_elos[path_A_uuid], path_elos[path_B_uuid])

        if current_entropy < ENTROPY_SATURATION_THRESHOLD:
            low_entropy_duels_count += 1

        if current_entropy > best_pair_info["entropy"]:
            best_pair_info["path_A"] = path_A_uuid
            best_pair_info["path_B"] = path_B_uuid
            best_pair_info["entropy"] = current_entropy

    if best_pair_info["path_A"] is None:
        return None

    if possible_duels_count > 0 and low_entropy_duels_count == possible_duels_count:
        print(
            f"INFO: Saturated league for position {position}, lineage {predecessor_hronir_uuid}. "
            f"All {possible_duels_count} possible duels have entropy < {ENTROPY_SATURATION_THRESHOLD}."
        )
        if best_pair_info["entropy"] < 0:
            return None

    return {
        "position": position,
        "strategy": "max_shannon_entropy",
        "entropy": best_pair_info["entropy"],
        "duel_pair": {
            "path_A": best_pair_info["path_A"],
            "path_B": best_pair_info["path_B"],
        },
    }


def check_path_qualification(
    path_uuid: str,
    ratings_df: pd.DataFrame,
    all_paths_in_position_df: pd.DataFrame,
) -> bool:
    """
    Check if a path meets the criteria to be marked as 'QUALIFIED'.
    """
    ELO_QUALIFICATION_THRESHOLD = 1550

    if ratings_df.empty:
        return False

    path_data = ratings_df[ratings_df["path_uuid"] == path_uuid]
    if path_data.empty:
        return False

    elo_rating = path_data.iloc[0]["elo_rating"]
    wins = path_data.iloc[0]["wins"]

    if elo_rating >= ELO_QUALIFICATION_THRESHOLD:
        return True

    if all_paths_in_position_df is None or all_paths_in_position_df.empty:
        num_competitors = 0
    else:
        num_competitors = len(all_paths_in_position_df["path_uuid"].unique())

    if num_competitors <= 0:
        min_wins_threshold = float("inf")
    elif num_competitors == 1:
        min_wins_threshold = 0
    else:
        min_wins_threshold = math.ceil(math.log2(num_competitors))

    if wins >= min_wins_threshold:
        return True

    return False
