import uuid
from pathlib import Path

import pandas as pd
import pytest

from hronir_encyclopedia import storage  # Added for DataManager
from hronir_encyclopedia.ratings import get_ranking


# Helper para criar UUIDs de teste
def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> tuple[Path, Path]:
    forking_dir = tmp_path / "forking_path"
    ratings_dir = tmp_path / "ratings"
    forking_dir.mkdir(exist_ok=True)
    ratings_dir.mkdir(exist_ok=True)
    return forking_dir, ratings_dir


# Helper function to manage DataManager and call get_ranking
def _call_get_ranking_with_setup(position, predecessor_hronir_uuid, forking_dir, ratings_dir):
    original_fork_csv_dir = storage.data_manager.fork_csv_dir
    original_ratings_csv_dir = storage.data_manager.ratings_csv_dir
    original_initialized = storage.data_manager._initialized

    db_cleared_by_this_run = False

    try:
        storage.data_manager.fork_csv_dir = forking_dir
        storage.data_manager.ratings_csv_dir = ratings_dir

        storage.data_manager._initialized = False
        storage.data_manager.clear_in_memory_data()
        db_cleared_by_this_run = True

        storage.data_manager.initialize_and_load(
            clear_existing_data=False
        )

        df = get_ranking(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
            # session argument removed
        )
        return df
    finally:
        storage.data_manager.fork_csv_dir = original_fork_csv_dir
        storage.data_manager.ratings_csv_dir = original_ratings_csv_dir
        storage.data_manager._initialized = original_initialized

        if db_cleared_by_this_run and storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


# Hrönirs
H0_ROOT = _uuid("root_hrönir_for_pos0")
H1A = _uuid("hrönir_1A_pos1_from_H0_ROOT")
H1B = _uuid("hrönir_1B_pos1_from_H0_ROOT")
H1C = _uuid("hrönir_1C_pos1_from_H0_ROOT")
H1D_OTHER_PARENT = _uuid("hrönir_1D_pos1_from_OTHER")
H2A_FROM_H1A = _uuid("hrönir_2A_pos2_from_H1A")

# Forking path data
forks_main_data = [
    {"position": 0, "prev_uuid": "", "uuid": H0_ROOT, "fork_uuid": _uuid("fork_0_H0_ROOT")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("fork_1_H0_ROOT_H1A")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1B, "fork_uuid": _uuid("fork_1_H0_ROOT_H1B")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1C, "fork_uuid": _uuid("fork_1_H0_ROOT_H1C")},
    {
        "position": 1,
        "prev_uuid": _uuid("OTHER_PARENT_UUID"),
        "uuid": H1D_OTHER_PARENT,
        "fork_uuid": _uuid("fork_1_OTHER_H1D"),
    },
    {"position": 2, "prev_uuid": H1A, "uuid": H2A_FROM_H1A, "fork_uuid": _uuid("fork_2_H1A_H2A")},
]

ratings_pos1_data = [
    {
        "uuid": _uuid("vote1"),
        "voter": _uuid("voter1"),
        "winner": H1A,
        "loser": H1B,
    },
    {
        "uuid": _uuid("vote2"),
        "voter": _uuid("voter2"),
        "winner": H1A,
        "loser": H1B,
    },
    {
        "uuid": _uuid("vote3"),
        "voter": _uuid("voter3"),
        "winner": H1B,
        "loser": H1A,
    },
    {"uuid": _uuid("vote4"), "voter": _uuid("voter4"), "winner": H1A, "loser": H1D_OTHER_PARENT},
    {"uuid": _uuid("vote5"), "voter": _uuid("voter5"), "winner": H1D_OTHER_PARENT, "loser": H1B},
]

ratings_pos0_data = []
ratings_pos2_data = []


def create_csv(data: list[dict], path: Path):
    if data:
        pd.DataFrame(data).to_csv(path, index=False)
    else:
        if data == [] and path.name.startswith("position_"):
            pd.DataFrame(columns=["uuid", "voter", "winner", "loser"]).to_csv(path, index=False)
        elif data == [] and path.name.startswith("forks_"):
            pd.DataFrame(columns=["position", "prev_uuid", "uuid", "fork_uuid"]).to_csv(
                path, index=False
            )
        else:
            path.touch()


def test_get_ranking_filters_by_canonical_predecessor(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(forks_main_data, forking_dir / "forks_main.csv")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )

    assert not ranking_df.empty
    expected_heirs = {H1A, H1B, H1C}
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_heirs == expected_heirs

    h1a_data = ranking_df[ranking_df["hrönir_uuid"] == H1A].iloc[0]
    h1b_data = ranking_df[ranking_df["hrönir_uuid"] == H1B].iloc[0]
    h1c_data = ranking_df[ranking_df["hrönir_uuid"] == H1C].iloc[0]

    assert h1a_data["wins"] == 2
    assert h1a_data["losses"] == 1
    assert h1a_data["elo_rating"] == 1515

    assert h1b_data["wins"] == 1
    assert h1b_data["losses"] == 2
    assert h1b_data["elo_rating"] == 1485

    assert h1c_data["wins"] == 0
    assert h1c_data["losses"] == 0
    assert h1c_data["elo_rating"] == 1500

    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[1]["hrönir_uuid"] == H1C
    assert ranking_df.iloc[2]["hrönir_uuid"] == H1B


def test_get_ranking_no_heirs_for_predecessor(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(forks_main_data, forking_dir / "forks_main.csv")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    NON_EXISTENT_PREDECESSOR = _uuid("non_existent_predecessor")
    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=NON_EXISTENT_PREDECESSOR,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty


def test_get_ranking_no_votes_for_heirs(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    simple_forks = [
        {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")},
        {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1B, "fork_uuid": _uuid("f2")},
    ]
    create_csv(simple_forks, forking_dir / "forks_simple.csv")
    create_csv([], ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )

    assert len(ranking_df) == 2
    expected_heirs = {H1A, H1B}
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_heirs == expected_heirs

    for _, row in ranking_df.iterrows():
        assert row["elo_rating"] == 1500
        assert row["wins"] == 0
        assert row["losses"] == 0
        assert row["games_played"] == 0


def test_get_ranking_for_position_0_no_predecessor(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    H0_ALT = _uuid("hrönir_0_ALT_pos0")
    forks_for_pos0 = forks_main_data + [
        {"position": 0, "prev_uuid": "", "uuid": H0_ALT, "fork_uuid": _uuid("fork_0_H0_ALT")}
    ]
    create_csv(forks_for_pos0, forking_dir / "forks_pos0.csv")

    ratings_data_pos0_duels = [
        {"uuid": _uuid("v_p0_1"), "voter": _uuid("v_p0_v1"), "winner": H0_ROOT, "loser": H0_ALT},
        {"uuid": _uuid("v_p0_2"), "voter": _uuid("v_p0_v2"), "winner": H0_ROOT, "loser": H0_ALT},
    ]
    create_csv(ratings_data_pos0_duels, ratings_dir / "position_000.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=0,
        predecessor_hronir_uuid=None,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )

    assert len(ranking_df) == 2
    expected_pos0_hrs = {H0_ROOT, H0_ALT}
    retrieved_pos0_hrs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_pos0_hrs == expected_pos0_hrs

    h0_root_data = ranking_df[ranking_df["hrönir_uuid"] == H0_ROOT].iloc[0]
    h0_alt_data = ranking_df[ranking_df["hrönir_uuid"] == H0_ALT].iloc[0]

    assert h0_root_data["elo_rating"] == 1531
    assert h0_root_data["wins"] == 2
    assert h0_alt_data["elo_rating"] == 1469
    assert h0_alt_data["losses"] == 2


def test_get_ranking_empty_forking_path_dir(temp_data_dir):
    _, ratings_dir = temp_data_dir
    forking_dir_empty = temp_data_dir[0]

    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir_empty,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty


def test_get_ranking_empty_ratings_files(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        forks_main_data, forking_dir / "forks_main.csv"
    )

    pd.DataFrame(columns=["uuid", "voter", "winner", "loser"]).to_csv(
        ratings_dir / "position_001.csv", index=False
    )

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 3
    for _, row in ranking_df.iterrows():
        assert row["elo_rating"] == 1500

    (ratings_dir / "position_001.csv").write_text("")
    ranking_df_zero_bytes = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df_zero_bytes) == 3
    for _, row in ranking_df_zero_bytes.iterrows():
        assert row["elo_rating"] == 1500


def test_get_ranking_malformed_forking_csv(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir

    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "good_forks.csv",
    )
    (forking_dir / "bad_forks.csv").write_text(
        "position,prev_uuid\ninvalid,row,with,too,many,columns"
    )

    create_csv([], ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500


def test_get_ranking_malformed_ratings_csv(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "forks.csv",
    )
    (ratings_dir / "position_001.csv").write_text("winner,loser\ninvalid,row")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500
    assert ranking_df.iloc[0]["wins"] == 0
    assert ranking_df.iloc[0]["losses"] == 0


def test_get_ranking_canonical_predecessor_none_not_pos_0(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(forks_main_data, forking_dir / "forks_main.csv")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=None,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty


def test_get_ranking_forking_path_missing_columns(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    (forking_dir / "missing_cols.csv").write_text("uuid,fork_uuid\nval1,val2")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty


def test_get_ranking_ratings_path_missing_columns(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "forks.csv",
    )
    (ratings_dir / "position_001.csv").write_text(
        "voter_id,winning_id,losing_id\nv1,w1,l1"
    )

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500
