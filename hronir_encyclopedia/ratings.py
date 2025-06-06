import pandas as pd
from pathlib import Path

DEFAULT_ELO = 1500
K_FACTOR = 32


def _expected(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def record_vote(position: int, winner: str, loser: str, base: Path | str = "ratings") -> None:
    """Record a literary duel result and update Elo ratings."""
    base = Path(base)
    base.mkdir(exist_ok=True)
    csv_path = base / f"position_{position:03d}.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(columns=["chapter", "elo", "wins", "losses"])

    for chapter in (winner, loser):
        if chapter not in df["chapter"].values:
            df = pd.concat([
                df,
                pd.DataFrame({
                    "chapter": [chapter],
                    "elo": [DEFAULT_ELO],
                    "wins": [0],
                    "losses": [0],
                })
            ], ignore_index=True)

    w_idx = df.index[df["chapter"] == winner][0]
    l_idx = df.index[df["chapter"] == loser][0]
    w_rating = df.at[w_idx, "elo"]
    l_rating = df.at[l_idx, "elo"]

    expected_w = _expected(w_rating, l_rating)
    expected_l = _expected(l_rating, w_rating)

    df.at[w_idx, "elo"] = w_rating + K_FACTOR * (1 - expected_w)
    df.at[l_idx, "elo"] = l_rating + K_FACTOR * (0 - expected_l)

    df.at[w_idx, "wins"] += 1
    df.at[l_idx, "losses"] += 1

    df.to_csv(csv_path, index=False)
