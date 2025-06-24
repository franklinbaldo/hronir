import itertools
import math

import pandas as pd
from sqlalchemy.orm import Session

from . import storage  # To get DB session

# Import models used in this file
from .models import ForkDB, VoteDB  # Added TransactionDB


def _calculate_elo_probability(elo_a: float, elo_b: float) -> float:
    """Calcula a probabilidade de A vencer B."""
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def _calculate_duel_entropy(elo_a: float, elo_b: float) -> float:
    """Calcula a entropia de Shannon para um duelo Elo."""
    p_a = _calculate_elo_probability(elo_a, elo_b)
    if p_a == 0 or p_a == 1:
        return 0.0
    p_b = 1 - p_a
    # Ensure p_b is also not 0 to avoid log2(0) if p_a is very close to 1
    if p_b == 0:
        return 0.0
    return -(p_a * math.log2(p_a) + p_b * math.log2(p_b))


def record_vote(
    position: int,
    voter: str,
    winner: str,
    loser: str,
    session: Session | None = None,
) -> None:
    """Records a vote into the VoteDB in the in-memory database."""
    close_session_locally = False
    if session is None:
        session = storage.get_db_session()
        close_session_locally = True

    try:
        vote = VoteDB(position=position, voter=voter, winner=winner, loser=loser)
        session.add(vote)
        session.commit()
    except Exception:
        if session:
            session.rollback()
        raise
    finally:
        if close_session_locally and session is not None:
            session.close()


def get_ranking(
    position: int,
    predecessor_hronir_uuid: str | None,
    session: Session | None = None,
) -> pd.DataFrame:
    """
    Calcula o ranking Elo para fork_uuid's de uma dada 'position', considerando
    apenas os forks que descendem diretamente do 'predecessor_hronir_uuid'.
    Operates on data from the in-memory database.
    """
    output_columns = ["fork_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
    empty_df = pd.DataFrame(columns=output_columns)

    close_session_locally = False
    if session is None:
        session = storage.get_db_session()
        close_session_locally = True

    try:
        query_forks = session.query(ForkDB).filter(ForkDB.position == position)
        if predecessor_hronir_uuid is None:
            if position == 0:
                query_forks = query_forks.filter(
                    (ForkDB.prev_uuid == None) | (ForkDB.prev_uuid == "")  # noqa: E711
                )
            else:
                if close_session_locally and session is not None:
                    session.close()
                return empty_df
        else:
            query_forks = query_forks.filter(ForkDB.prev_uuid == predecessor_hronir_uuid)

        eligible_fork_db_entries = query_forks.all()

        if not eligible_fork_db_entries:
            if close_session_locally and session is not None:
                session.close()
            return empty_df

        eligible_fork_infos_list = [
            {"fork_uuid": f.fork_uuid, "hrönir_uuid": f.uuid} for f in eligible_fork_db_entries
        ]

        eligible_fork_df = pd.DataFrame(eligible_fork_infos_list).drop_duplicates(
            subset=["fork_uuid"]
        )
        if eligible_fork_df.empty:
            if close_session_locally and session is not None:
                session.close()
            return empty_df

        hronir_to_eligible_fork_map = pd.Series(
            eligible_fork_df.fork_uuid.values, index=eligible_fork_df.hrönir_uuid
        ).to_dict()

        ELO_BASE = 1500.0  # Initialize with a float
        ranking_list = [
            {
                "fork_uuid": fork_info["fork_uuid"],
                "hrönir_uuid": fork_info["hrönir_uuid"],
                "elo_rating": ELO_BASE,
                "games_played": 0,
                "wins": 0,
                "losses": 0,
            }
            for fork_info in eligible_fork_df.to_dict("records")
        ]
        current_ranking_df = pd.DataFrame(ranking_list).set_index("fork_uuid")

        votes_at_position = session.query(VoteDB).filter(VoteDB.position == position).all()

        # ---- START DEBUG PRINTS ----
        # # import sys # Moved to top
        # print(f"DEBUG Ratings: get_ranking for pos {position}, pred_hrönir {predecessor_hronir_uuid}", file=sys.stderr)
        # print(f"DEBUG Ratings: eligible_fork_df:\n{eligible_fork_df.to_string()}", file=sys.stderr)
        # print(f"DEBUG Ratings: hronir_to_eligible_fork_map:\n{hronir_to_eligible_fork_map}", file=sys.stderr)
        # print(f"DEBUG Ratings: Found {len(votes_at_position)} votes in DB for position {position}.", file=sys.stderr)
        # ---- END DEBUG PRINTS ----

        if votes_at_position:
            votes_data = [
                {
                    "winner": v.winner,
                    "loser": v.loser,
                    "voter": v.voter,
                }  # Removed "id": v.id from debug
                for v in votes_at_position
            ]
            df_votes = pd.DataFrame(votes_data)

            if not df_votes.empty:
                df_votes["winner_fork_uuid"] = df_votes["winner"].map(hronir_to_eligible_fork_map)
                df_votes["loser_fork_uuid"] = df_votes["loser"].map(hronir_to_eligible_fork_map)

                valid_duel_votes = df_votes.dropna(subset=["winner_fork_uuid", "loser_fork_uuid"])
                valid_duel_votes = valid_duel_votes[
                    valid_duel_votes["winner_fork_uuid"] != valid_duel_votes["loser_fork_uuid"]
                ]

                if not valid_duel_votes.empty:
                    K_FACTOR = 32
                    for _, vote_row in valid_duel_votes.iterrows():
                        winner_fork = vote_row["winner_fork_uuid"]
                        loser_fork = vote_row["loser_fork_uuid"]

                        if (
                            winner_fork not in current_ranking_df.index
                            or loser_fork not in current_ranking_df.index
                        ):
                            continue

                        current_ranking_df.loc[winner_fork, "wins"] += 1
                        current_ranking_df.loc[loser_fork, "losses"] += 1
                        current_ranking_df.loc[winner_fork, "games_played"] += 1
                        current_ranking_df.loc[loser_fork, "games_played"] += 1

                        r_winner_fork = current_ranking_df.loc[winner_fork, "elo_rating"]
                        r_loser_fork = current_ranking_df.loc[loser_fork, "elo_rating"]
                        expected_winner = _calculate_elo_probability(r_winner_fork, r_loser_fork)
                        new_r_winner_fork = r_winner_fork + K_FACTOR * (1 - expected_winner)
                        new_r_loser_fork = r_loser_fork + K_FACTOR * (0 - (1 - expected_winner))
                        current_ranking_df.loc[winner_fork, "elo_rating"] = new_r_winner_fork
                        current_ranking_df.loc[loser_fork, "elo_rating"] = new_r_loser_fork

                    current_ranking_df["elo_rating"] = (
                        current_ranking_df["elo_rating"].round().astype(int)
                    )

        final_df = current_ranking_df.reset_index()
        final_df = final_df.sort_values(
            by=["elo_rating", "wins", "games_played"], ascending=[False, False, True]
        )
        return final_df[output_columns]

    except Exception:
        if close_session_locally and session is not None:
            session.close()
        return empty_df
    finally:
        if close_session_locally and session is not None:
            session.close()


def determine_next_duel_entropy(
    position: int, predecessor_hronir_uuid: str | None, session: Session | None = None
) -> dict | None:
    """
    Chooses the pair of forks with MAX Shannon entropy of predicted outcome,
    ignoring pairs already dueled (once TransactionDB is structured for it).
    """
    close_session_locally = False
    if session is None:
        session = storage.get_db_session()
        close_session_locally = True

    try:
        ranking_df = get_ranking(
            position=position, predecessor_hronir_uuid=predecessor_hronir_uuid, session=session
        )
        if ranking_df.empty or len(ranking_df) < 2:
            return None  # No need to close session here, finally block will handle it.

        def p_win(rA, rB, k=400.0):
            return 1.0 / (1.0 + 10.0 ** ((rB - rA) / k))

        # TODO: Implement proper duels_done query once TransactionDB has structured columns:
        # duel_position, duel_predecessor_hronir_uuid, duel_winner_fork_uuid, duel_loser_fork_uuid.
        # This also requires transaction_manager.record_transaction to populate these new columns.
        # For now, this set remains empty, meaning duels might be repeated.
        # print(f"WARNING: determine_next_duel_entropy is NOT checking TransactionDB for prior duels effectively for position {position}.")

        best_pair_info = {"fork_A": None, "fork_B": None, "entropy": -1.0}
        fork_elos = ranking_df.set_index("fork_uuid")["elo_rating"].to_dict()
        fork_keys = list(fork_elos.keys())

        possible_duels_count = 0
        low_entropy_duels_count = 0
        ENTROPY_SATURATION_THRESHOLD = 0.2

        for fork_A_uuid, fork_B_uuid in itertools.combinations(fork_keys, 2):
            # current_duel_pair_sorted = tuple(sorted((fork_A_uuid, fork_B_uuid)))
            # if current_duel_pair_sorted in duels_done:
            #     continue

            possible_duels_count += 1
            # Using existing _calculate_duel_entropy as the Shannon entropy function
            current_entropy = _calculate_duel_entropy(
                fork_elos[fork_A_uuid], fork_elos[fork_B_uuid]
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
                f"INFO: Ratings liga saturada para posição {position}, linhagem {predecessor_hronir_uuid}. "
                f"Todos os {possible_duels_count} duelos possíveis têm entropia < {ENTROPY_SATURATION_THRESHOLD}."
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
    finally:
        if close_session_locally and session is not None:
            session.close()


def check_fork_qualification(
    fork_uuid: str,
    ratings_df: pd.DataFrame,
    all_forks_in_position_df: pd.DataFrame,
) -> bool:
    """
    Checks if a fork meets the criteria to be marked as 'QUALIFIED'.
    (Content of this function remains unchanged from original)
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
