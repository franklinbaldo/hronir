import itertools
import math
import uuid

import pandas as pd

from . import storage  # To get DataManager
from .models import Fork, Vote


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
    vote = Vote(
        uuid=vote_uuid,
        position=position,
        voter=voter,
        winner=winner,
        loser=loser
    )
    
    data_manager.add_vote(vote)
    data_manager.save_all_data_to_csvs()


def get_ranking(
    position: int,
    predecessor_hronir_uuid: str | None,
) -> pd.DataFrame:
    """
    Calculate Elo ranking for fork_uuids at a given position,
    considering only forks that descend directly from predecessor_hronir_uuid.
    """
    output_columns = ["fork_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
    empty_df = pd.DataFrame(columns=output_columns)

    data_manager = storage.DataManager()
    data_manager.initialize_and_load()
    
    # Get eligible forks
    eligible_forks = data_manager.get_forks_by_position(position)
    
    if predecessor_hronir_uuid is None:
        if position == 0:
            # For position 0, include forks with no predecessor or empty predecessor
            eligible_forks = [f for f in eligible_forks if f.prev_uuid is None or str(f.prev_uuid) == ""]
        else:
            return empty_df
    else:
        # Filter forks with the specified predecessor
        eligible_forks = [f for f in eligible_forks if str(f.prev_uuid) == predecessor_hronir_uuid]

    if not eligible_forks:
        return empty_df

    # Create fork mapping
    hronir_to_fork_map = {str(f.uuid): str(f.fork_uuid) for f in eligible_forks}
    
    # Initialize ranking
    ELO_BASE = 1500.0
    ranking_data = []
    for fork in eligible_forks:
        ranking_data.append({
            "fork_uuid": str(fork.fork_uuid),
            "hrönir_uuid": str(fork.uuid),
            "elo_rating": ELO_BASE,
            "games_played": 0,
            "wins": 0,
            "losses": 0,
        })
    
    current_ranking_df = pd.DataFrame(ranking_data).set_index("fork_uuid")
    
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
            # Map hrönir UUIDs to fork UUIDs
            df_votes["winner_fork_uuid"] = df_votes["winner"].map(hronir_to_fork_map)
            df_votes["loser_fork_uuid"] = df_votes["loser"].map(hronir_to_fork_map)
            
            # Keep only valid votes (both winner and loser are eligible)
            valid_votes = df_votes.dropna(subset=["winner_fork_uuid", "loser_fork_uuid"])
            valid_votes = valid_votes[valid_votes["winner_fork_uuid"] != valid_votes["loser_fork_uuid"]]
            
            if not valid_votes.empty:
                K_FACTOR = 32
                for _, vote_row in valid_votes.iterrows():
                    winner_fork = vote_row["winner_fork_uuid"]
                    loser_fork = vote_row["loser_fork_uuid"]
                    
                    if winner_fork not in current_ranking_df.index or loser_fork not in current_ranking_df.index:
                        continue
                    
                    # Update stats
                    current_ranking_df.loc[winner_fork, "wins"] += 1
                    current_ranking_df.loc[loser_fork, "losses"] += 1
                    current_ranking_df.loc[winner_fork, "games_played"] += 1
                    current_ranking_df.loc[loser_fork, "games_played"] += 1
                    
                    # Calculate new Elo ratings
                    r_winner = current_ranking_df.loc[winner_fork, "elo_rating"]
                    r_loser = current_ranking_df.loc[loser_fork, "elo_rating"]
                    expected_winner = _calculate_elo_probability(r_winner, r_loser)
                    
                    new_r_winner = r_winner + K_FACTOR * (1 - expected_winner)
                    new_r_loser = r_loser + K_FACTOR * (0 - (1 - expected_winner))
                    
                    current_ranking_df.loc[winner_fork, "elo_rating"] = new_r_winner
                    current_ranking_df.loc[loser_fork, "elo_rating"] = new_r_loser
                
                # Round ratings to integers
                current_ranking_df["elo_rating"] = current_ranking_df["elo_rating"].round().astype(int)
    
    # Return sorted results
    final_df = current_ranking_df.reset_index()
    final_df = final_df.sort_values(
        by=["elo_rating", "wins", "games_played"], 
        ascending=[False, False, True]
    )
    return final_df[output_columns]


def determine_next_duel_entropy(
    position: int, 
    predecessor_hronir_uuid: str | None
) -> dict | None:
    """
    Choose the pair of forks with MAX Shannon entropy of predicted outcome.
    """
    ranking_df = get_ranking(position=position, predecessor_hronir_uuid=predecessor_hronir_uuid)
    
    if ranking_df.empty or len(ranking_df) < 2:
        return None
    
    best_pair_info = {"fork_A": None, "fork_B": None, "entropy": -1.0}
    fork_elos = ranking_df.set_index("fork_uuid")["elo_rating"].to_dict()
    fork_keys = list(fork_elos.keys())
    
    possible_duels_count = 0
    low_entropy_duels_count = 0
    ENTROPY_SATURATION_THRESHOLD = 0.2
    
    for fork_A_uuid, fork_B_uuid in itertools.combinations(fork_keys, 2):
        possible_duels_count += 1
        
        current_entropy = _calculate_duel_entropy(
            fork_elos[fork_A_uuid], 
            fork_elos[fork_B_uuid]
        )
        
        if current_entropy < ENTROPY_SATURATION_THRESHOLD:
            low_entropy_duels_count += 1
        
        if current_entropy > best_pair_info["entropy"]:
            best_pair_info["fork_A"] = fork_A_uuid
            best_pair_info["fork_B"] = fork_B_uuid
            best_pair_info["entropy"] = current_entropy
    
    if best_pair_info["fork_A"] is None:
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
            "fork_A": best_pair_info["fork_A"],
            "fork_B": best_pair_info["fork_B"],
        },
    }


def check_fork_qualification(
    fork_uuid: str,
    ratings_df: pd.DataFrame,
    all_forks_in_position_df: pd.DataFrame,
) -> bool:
    """
    Check if a fork meets the criteria to be marked as 'QUALIFIED'.
    """
    ELO_QUALIFICATION_THRESHOLD = 1550
    
    if ratings_df.empty:
        return False
    
    fork_data = ratings_df[ratings_df["fork_uuid"] == fork_uuid]
    if fork_data.empty:
        return False
    
    elo_rating = fork_data.iloc[0]["elo_rating"]
    wins = fork_data.iloc[0]["wins"]
    
    if elo_rating >= ELO_QUALIFICATION_THRESHOLD:
        return True
    
    if all_forks_in_position_df is None or all_forks_in_position_df.empty:
        num_competitors = 0
    else:
        num_competitors = len(all_forks_in_position_df["fork_uuid"].unique())
    
    if num_competitors <= 0:
        min_wins_threshold = float("inf")
    elif num_competitors == 1:
        min_wins_threshold = 0
    else:
        min_wins_threshold = math.ceil(math.log2(num_competitors))
    
    if wins >= min_wins_threshold:
        return True
    
    return False