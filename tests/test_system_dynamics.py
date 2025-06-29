import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from hronir_encyclopedia import cli, storage


# Helper to create minimal hrönir files for testing
def create_mock_hronir(
    library_path: Path, text_content: str, uuid_override: str | None = None
) -> str:
    """Creates a mock hrönir file and returns its UUID."""
    hronir_uuid = uuid_override if uuid_override else storage.compute_uuid(text_content)
    hronir_dir = storage.uuid_to_path(hronir_uuid, library_path)
    hronir_dir.mkdir(parents=True, exist_ok=True)
    (hronir_dir / "index.md").write_text(text_content)
    meta = {"uuid": hronir_uuid}
    (hronir_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return hronir_uuid


# Helper to create a fork entry CSV
def create_fork_csv(fork_dir: Path, filename: str, forks_data: list[dict]):
    """Creates a CSV file for fork entries."""
    df = pd.DataFrame(forks_data)
    fork_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(fork_dir / filename, index=False)


# Helper to create a ratings CSV
def create_ratings_csv(ratings_dir: Path, filename: str, ratings_data: list[dict]):
    """Creates a CSV file for ratings."""
    df = pd.DataFrame(ratings_data)
    ratings_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(ratings_dir / filename, index=False)


@pytest.fixture
def setup_test_environment(tmp_path: Path) -> dict[str, Path]:
    """Sets up a temporary test environment with mock data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    library_dir = tmp_path / "the_library"
    library_dir.mkdir(parents=True, exist_ok=True)
    fork_dir = tmp_path / "narrative_paths"
    fork_dir.mkdir(parents=True, exist_ok=True)
    ratings_dir = tmp_path / "ratings"
    ratings_dir.mkdir(parents=True, exist_ok=True)

    # --- Create Hrönirs ---
    # Position 0
    create_mock_hronir(
        library_dir, "Seed content", "00000000-seed-0000-0000-000000000000"
    )  # Placeholder for actual seed if needed by forks
    hronir_A_content = "Content for Hrönir A, successor of Fork A"
    hronir_A_suc = create_mock_hronir(
        library_dir, hronir_A_content, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    )

    hronir_B_content = "Content for Hrönir B, successor of Fork B"
    hronir_B_suc = create_mock_hronir(
        library_dir, hronir_B_content, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )

    # Position 1 - Children of hrönir_A_suc (current canonical path)
    hronir_C_content = "Content for Hrönir C, successor of Fork C (child of A)"
    hronir_C_suc = create_mock_hronir(
        library_dir, hronir_C_content, "cccccccc-cccc-cccc-cccc-cccccccccccc"
    )
    hronir_D_content = "Content for Hrönir D, successor of Fork D (child of A)"
    hronir_D_suc = create_mock_hronir(
        library_dir, hronir_D_content, "dddddddd-dddd-dddd-dddd-dddddddddddd"
    )

    # Position 1 - Children of hrönir_B_suc (non-canonical path that will become canonical)
    hronir_E_content = "Content for Hrönir E, successor of Fork E (child of B)"
    hronir_E_suc = create_mock_hronir(
        library_dir, hronir_E_content, "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    )
    hronir_F_content = "Content for Hrönir F, successor of Fork F (child of B)"
    hronir_F_suc = create_mock_hronir(
        library_dir, hronir_F_content, "ffffffff-ffff-ffff-ffff-ffffffffffff"
    )

    # --- Define Forks ---
    # Position 0 Forks
    fork_A_uuid = storage.compute_forking_uuid(
        position=0, prev_uuid="", cur_uuid=hronir_A_suc
    )  # Fork A leads to hrönir_A_suc
    fork_B_uuid = storage.compute_forking_uuid(
        position=0, prev_uuid="", cur_uuid=hronir_B_suc
    )  # Fork B leads to hrönir_B_suc

    # Position 1 Forks (Children of A's successor)
    fork_C_uuid = storage.compute_forking_uuid(
        position=1, prev_uuid=hronir_A_suc, cur_uuid=hronir_C_suc
    )
    fork_D_uuid = storage.compute_forking_uuid(
        position=1, prev_uuid=hronir_A_suc, cur_uuid=hronir_D_suc
    )

    # Position 1 Forks (Children of B's successor)
    fork_E_uuid = storage.compute_forking_uuid(
        position=1, prev_uuid=hronir_B_suc, cur_uuid=hronir_E_suc
    )
    fork_F_uuid = storage.compute_forking_uuid(
        position=1, prev_uuid=hronir_B_suc, cur_uuid=hronir_F_suc
    )

    # Create narrative_paths CSV
    forks_data = [
        {"position": 0, "prev_uuid": "", "uuid": hronir_A_suc, "fork_uuid": fork_A_uuid},
        {"position": 0, "prev_uuid": "", "uuid": hronir_B_suc, "fork_uuid": fork_B_uuid},
        {"position": 1, "prev_uuid": hronir_A_suc, "uuid": hronir_C_suc, "fork_uuid": fork_C_uuid},
        {"position": 1, "prev_uuid": hronir_A_suc, "uuid": hronir_D_suc, "fork_uuid": fork_D_uuid},
        {"position": 1, "prev_uuid": hronir_B_suc, "uuid": hronir_E_suc, "fork_uuid": fork_E_uuid},
        {"position": 1, "prev_uuid": hronir_B_suc, "uuid": hronir_F_suc, "fork_uuid": fork_F_uuid},
    ]
    create_fork_csv(fork_dir, "path_0.csv", forks_data)

    # --- Initial Canonical Path ---
    # Fork A is initially canonical for Position 0
    initial_canonical_path_content = {
        "title": "The Hrönir Encyclopedia - Canonical Path",
        "path": {"0": {"fork_uuid": fork_A_uuid, "hrönir_uuid": hronir_A_suc}},
    }
    canonical_path_file = data_dir / "canonical_path.json"
    with open(canonical_path_file, "w") as f:
        json.dump(initial_canonical_path_content, f, indent=2)

    # --- Ratings ---
    # Votes that will make Fork B win Position 0 after the new vote
    # For simplicity, we'll represent votes in terms of their successor hrönirs,
    # as that's what Elo calculation in ratings.py currently expects for winner/loser.
    # The voter is a fork_uuid.
    # Let's assume fork_B already has some advantage or fork_A has some disadvantage.
    # For this test, the critical part is that the *new vote* tips the balance.
    # The actual Elo values don't matter as much as the rank change.

    # To make Fork B win, we need votes where hronir_B_suc (successor of Fork B) wins.
    # And hronir_A_suc (successor of Fork A) loses.
    # The voter can be any valid fork_uuid not involved in the duel.
    # Let's create a dummy voter fork for this.
    dummy_voter_hronir_content = "Dummy voter hrönir"
    dummy_voter_hronir_uuid = create_mock_hronir(
        library_dir, dummy_voter_hronir_content, "dddddddd-voter-dummy-dddddddddddd"
    )
    voter_for_initial_ratings_fork_uuid = storage.compute_forking_uuid(
        position=99, prev_uuid="", cur_uuid=dummy_voter_hronir_uuid
    )
    # Add this dummy fork to a separate CSV to ensure it's found by storage.narrative_paths_exists
    create_fork_csv(
        fork_dir,
        "dummy_forks.csv",
        [
            {
                "position": 99,
                "prev_uuid": "",
                "uuid": dummy_voter_hronir_uuid,
                "fork_uuid": voter_for_initial_ratings_fork_uuid,
            }
        ],
    )

    # Initial ratings for Position 0: Make Fork A slightly ahead or tied initially.
    # For simplicity, one vote making A win B.
    # The key is that the *next* vote will make B win.
    ratings_pos0_data = [
        {
            "voter": voter_for_initial_ratings_fork_uuid,
            "winner": hronir_A_suc,
            "loser": hronir_B_suc,
            "elo_winner_pre": 1500,
            "elo_loser_pre": 1500,
            "elo_winner_post": 1516,
            "elo_loser_post": 1484,
        }
    ]
    create_ratings_csv(ratings_dir, "position_0.csv", ratings_pos0_data)

    # Ratings for Position 1 (children of A) - to ensure C vs D is the duel if A remains canonical
    # Voter for these can be another dummy fork.
    voter_pos1_A_children_fork_uuid = storage.compute_forking_uuid(
        position=98, prev_uuid="", cur_uuid=dummy_voter_hronir_uuid
    )  # Re-use dummy hronir for new fork
    create_fork_csv(
        fork_dir,
        "dummy_forks_pos1A.csv",
        [
            {
                "position": 98,
                "prev_uuid": "",
                "uuid": dummy_voter_hronir_uuid,
                "fork_uuid": voter_pos1_A_children_fork_uuid,
            }
        ],
    )

    ratings_pos1_children_A_data = [
        # Make C slightly ahead of D
        {
            "voter": voter_pos1_A_children_fork_uuid,
            "winner": hronir_C_suc,
            "loser": hronir_D_suc,
            "elo_winner_pre": 1500,
            "elo_loser_pre": 1500,
            "elo_winner_post": 1516,
            "elo_loser_post": 1484,
        }
    ]
    create_ratings_csv(ratings_dir, "position_1.csv", ratings_pos1_children_A_data)

    # Ratings for Position 1 (children of B) - to ensure E vs F is the duel if B becomes canonical
    # Voter for these can be another dummy fork.
    voter_pos1_B_children_fork_uuid = storage.compute_forking_uuid(
        position=97, prev_uuid="", cur_uuid=dummy_voter_hronir_uuid
    )  # Re-use dummy hronir for new fork
    create_fork_csv(
        fork_dir,
        "dummy_forks_pos1B.csv",
        [
            {
                "position": 97,
                "prev_uuid": "",
                "uuid": dummy_voter_hronir_uuid,
                "fork_uuid": voter_pos1_B_children_fork_uuid,
            }
        ],
    )
    # Append to position_1.csv or create new if logic handles multiple files per position
    # For simplicity with current ratings.py, ensure position_1.csv contains all relevant votes for pos 1
    # So, we should merge these if determine_next_duel reads only one file per position.
    # However, ratings.get_ranking and determine_next_duel iterate all CSVs in ratings_dir.
    # So, separate files are fine. Let's keep them separate for clarity of setup.
    # create_ratings_csv(ratings_dir, "position_1_children_B.csv", ratings_pos1_children_B_data)
    # Actually, ratings.py consolidates from all files in ratings_dir for a given position,
    # but then filters by predecessor. So it's fine. Let's add to the same position_1.csv for simplicity of fixture.
    # We need to ensure these votes for E vs F don't interfere with C vs D unless B is canonical.
    # The determine_next_duel logic should filter by predecessor_hronir_uuid.
    # For now, let's not add these E vs F votes yet, to keep initial state clean for C vs D.
    # We will add them if needed, or rely on determine_next_duel to pick them if they are unrated.

    return {
        "tmp_path": tmp_path,
        "data_dir": data_dir,
        "library_dir": library_dir,
        "fork_dir": fork_dir,
        "ratings_dir": ratings_dir,
        "canonical_path_file": canonical_path_file,
        "fork_A_uuid": fork_A_uuid,
        "hronir_A_suc": hronir_A_suc,
        "fork_B_uuid": fork_B_uuid,
        "hronir_B_suc": hronir_B_suc,
        "fork_C_uuid": fork_C_uuid,
        "hronir_C_suc": hronir_C_suc,
        "fork_D_uuid": fork_D_uuid,
        "hronir_D_suc": hronir_D_suc,
        "fork_E_uuid": fork_E_uuid,
        "hronir_E_suc": hronir_E_suc,
        "fork_F_uuid": fork_F_uuid,
        "hronir_F_suc": hronir_F_suc,
        "voter_for_decisive_vote_fork_uuid": voter_for_initial_ratings_fork_uuid,  # Re-use this as the decisive voter
    }


@pytest.mark.skip(
    reason="The 'vote' CLI command has been removed. Test needs rewrite to use session commit flow."
)
def test_system_dynamics_cascade(setup_test_environment):
    runner = CliRunner()
    env = setup_test_environment

    # --- Verify Initial State (Optional but good for debugging) ---
    # Ensure C vs D is the duel for Pos 1 initially
    # This requires mocking `determine_next_duel` to return A and B for pos 0 for the vote.
    # For the actual test, we first vote, then consolidate, then check duel.

    # --- Ação 1: Voto Decisivo (para Posição 0) ---
    # This vote should make Fork B win over Fork A for Position 0.
    # The `vote` command needs the official duel. We need to ensure get-duel for Pos 0 returns A vs B.
    # Since ratings for A vs B exist (A won once), they are not new. Max entropy might pick them.
    # Let's assume get-duel for pos 0 (no predecessor) will offer Fork A vs Fork B.
    # The voter is `voter_for_decisive_vote_fork_uuid`.
    # Winner is Fork B, Loser is Fork A.

    # To make the vote valid, we need to ensure that `get-duel` for position 0
    # returns Fork A and Fork B as the duel pair.
    # With one vote (A wins B), their Elos are 1516 and 1484. This should be a max-entropy duel.

    result_get_duel_pos0 = runner.invoke(
        cli.app,
        [
            "get-duel",
            "--position",
            "0",
            "--ratings-dir",
            str(env["ratings_dir"]),
            "--forking-path-dir",
            str(env["fork_dir"]),
            "--canonical-path-file",
            str(env["canonical_path_file"]),
        ],
        catch_exceptions=False,
    )
    assert result_get_duel_pos0.exit_code == 0
    duel_info_pos0 = json.loads(result_get_duel_pos0.stdout)
    assert duel_info_pos0["position"] == 0
    assert "duel_pair" in duel_info_pos0
    # Ensure the duel is indeed between fork_A and fork_B
    assert {duel_info_pos0["duel_pair"]["fork_A"], duel_info_pos0["duel_pair"]["fork_B"]} == {
        env["fork_A_uuid"],
        env["fork_B_uuid"],
    }

    # Now, cast the decisive vote making Fork B the winner.
    # The vote is recorded in terms of hrönir_uuids, but validated against fork_uuids from get-duel.
    vote_winner_fork = env["fork_B_uuid"]
    vote_loser_fork = env["fork_A_uuid"]

    result_vote = runner.invoke(
        cli.app,
        [
            "vote",
            "--position",
            "0",
            "--voter-fork-uuid",
            env["voter_for_decisive_vote_fork_uuid"],
            "--winner-fork-uuid",
            vote_winner_fork,  # Fork B wins
            "--loser-fork-uuid",
            vote_loser_fork,  # Fork A loses
            "--ratings-dir",
            str(env["ratings_dir"]),
            "--forking-path-dir",
            str(env["fork_dir"]),
            "--canonical-path-file",
            str(env["canonical_path_file"]),
        ],
        catch_exceptions=False,
    )
    # This block is at the function's top level of indentation
    if result_vote.exit_code != 0:
        print(f"Vote command failed. Output:\n{result_vote.stdout}")
    assert result_vote.exit_code == 0  # This should also be at the function's top level

    vote_output = json.loads(result_vote.stdout)
    assert (
        vote_output["message"]
        == "Vote for forks successfully validated and recorded (as hrönir duel). System uncertainty reduced."
    )
    assert vote_output["winner_fork_uuid"] == vote_winner_fork
    assert (
        vote_output["recorded_duel_hrönirs"]["winner"] == env["hronir_B_suc"]
    )  # Successor of Fork B
    assert (
        vote_output["recorded_duel_hrönirs"]["loser"] == env["hronir_A_suc"]
    )  # Successor of Fork A

    # --- Ação 2: O Pulso Canônico ---
    result_consolidate = runner.invoke(
        cli.app,
        [
            "consolidate-book",
            "--ratings-dir",
            str(env["ratings_dir"]),
            "--forking-path-dir",
            str(env["fork_dir"]),
            "--canonical-path-file",
            str(env["canonical_path_file"]),
        ],
        catch_exceptions=False,
    )
    assert result_consolidate.exit_code == 0
    assert "Canonical path file updated" in result_consolidate.stdout

    # --- Asserção 1: Mudança no Cânone ---
    with open(env["canonical_path_file"]) as f:
        updated_canonical_data = json.load(f)

    assert "0" in updated_canonical_data["path"], (
        "Position 0 should be in the updated canonical path."
    )
    canonical_pos0_entry = updated_canonical_data["path"]["0"]
    assert canonical_pos0_entry["fork_uuid"] == env["fork_B_uuid"], (
        f"Fork B ({env['fork_B_uuid']}) should now be canonical for Position 0."
    )
    assert canonical_pos0_entry["hrönir_uuid"] == env["hronir_B_suc"], (
        f"Successor hrönir for canonical Fork B ({env['hronir_B_suc']}) should be recorded."
    )

    # --- Asserção 2: O Eco ---
    # Chamar `cli.get_duel` para a Posição 1.
    # O duelo retornado DEVE ser entre `fork_E` e `fork_F` (descendentes do novo cânone `fork_B` via `hronir_B_suc`)
    # e NÃO entre `fork_C` e `fork_D`.

    # Before calling get-duel for pos 1, we might need to ensure E and F have some ratings,
    # or that they are the only eligible ones.
    # If E and F are unrated, determine_next_duel might pick them if they are the only children of B_suc.
    # Let's add some initial ratings for E vs F to make them comparable, similar to C vs D.
    # This ensures that if the lineage is correctly B_suc, then E vs F is chosen.
    voter_pos1_B_children_fork_uuid = storage.compute_forking_uuid(
        position=96, prev_uuid="", cur_uuid=env["hronir_A_suc"]
    )  # Just need a valid fork UUID
    create_fork_csv(
        env["fork_dir"],
        "dummy_forks_pos1B_extra.csv",
        [
            {
                "position": 96,
                "prev_uuid": "",
                "uuid": env["hronir_A_suc"],
                "fork_uuid": voter_pos1_B_children_fork_uuid,
            }
        ],
    )

    ratings_pos1_children_B_data = [
        {
            "voter": voter_pos1_B_children_fork_uuid,
            "winner": env["hronir_E_suc"],
            "loser": env["hronir_F_suc"],
            "elo_winner_pre": 1500,
            "elo_loser_pre": 1500,
            "elo_winner_post": 1516,
            "elo_loser_post": 1484,
        }
    ]
    # Append to existing position_1.csv or ensure ratings loader handles multiple files.
    # Let's append to the existing position_1.csv file for simplicity in test setup.
    # However, the current ratings loader (ratings.get_ratings_for_position) reads all CSVs.
    # So, creating a new file specifically for these ratings is also fine.
    # To avoid mutating the fixture's ratings_dir mid-test for other parts, let's assume this is enough.
    # If determine_next_duel doesn't find them, this assertion will fail.
    # The key is that they *are* children of hronir_B_suc.
    # And that C and D are children of hronir_A_suc.
    # `ratings.get_eligible_forks` should filter correctly.

    # Add ratings for E vs F to position_1.csv.
    # This ensures they have Elo scores and can be chosen for a duel.
    pos1_ratings_file = env["ratings_dir"] / "position_1.csv"
    if pos1_ratings_file.exists():
        existing_ratings_df = pd.read_csv(pos1_ratings_file)
        new_ratings_df = pd.DataFrame(ratings_pos1_children_B_data)
        combined_df = pd.concat([existing_ratings_df, new_ratings_df], ignore_index=True)
        combined_df.to_csv(pos1_ratings_file, index=False)
    else:
        create_ratings_csv(env["ratings_dir"], "position_1.csv", ratings_pos1_children_B_data)

    result_get_duel_pos1 = runner.invoke(
        cli.app,
        [
            "get-duel",
            "--position",
            "1",
            "--ratings-dir",
            str(env["ratings_dir"]),
            "--forking-path-dir",
            str(env["fork_dir"]),
            "--canonical-path-file",
            str(env["canonical_path_file"]),
        ],
        catch_exceptions=False,
    )
    assert result_get_duel_pos1.exit_code == 0, (
        f"get-duel for pos 1 failed. Output: {result_get_duel_pos1.stdout}"
    )

    duel_info_pos1 = json.loads(result_get_duel_pos1.stdout)
    assert duel_info_pos1["position"] == 1, "Duel info should be for position 1."
    assert "duel_pair" in duel_info_pos1, "Duel info must contain a duel_pair."

    returned_duel_forks = {
        duel_info_pos1["duel_pair"]["fork_A"],
        duel_info_pos1["duel_pair"]["fork_B"],
    }
    expected_duel_forks = {env["fork_E_uuid"], env["fork_F_uuid"]}

    assert returned_duel_forks == expected_duel_forks, (
        f"Duel for Position 1 should be between Fork E and Fork F. Got: {returned_duel_forks}, Expected: {expected_duel_forks}"
    )

    # Cleanup (optional, as tmp_path handles it, but good for illustration if not using tmp_path)
    # shutil.rmtree(tmp_path) # Pytest's tmp_path fixture handles cleanup automatically
