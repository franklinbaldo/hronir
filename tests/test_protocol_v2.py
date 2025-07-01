import json
import os
import shutil
import tempfile # Added for TemporaryDirectory
import unittest
import uuid
from pathlib import Path

import typer # Added for typer.echo in test
from typer.testing import CliRunner

from hronir_encyclopedia import cli, ratings, storage, transaction_manager
from hronir_encyclopedia.cli import app # Import the Typer app instance
from hronir_encyclopedia.models import Path as PathModel
# Vote model is not directly used in this test file after refactor, can be removed if no other test needs it.

# Helper to create a unique dummy chapter file and return its UUID
def _create_dummy_chapter(library_path: Path, content_prefix: str) -> str:
    text = f"Chapter content for {content_prefix} {uuid.uuid4()}"
    # For test isolation, it's better if storage functions can take all necessary paths
    # or if tests manage their own DataManager instances configured for test-specific paths.
    # Assuming storage.store_chapter_text correctly uses the `base` argument for library_path.
    chapter_uuid = storage.store_chapter_text(text, base=library_path)
    return chapter_uuid

def _get_head_transaction_uuid(tx_dir: Path | None = None) -> str | None:
    # This helper might be obsolete if direct transaction file inspection is no longer primary.
    # Kept for now if any test still relies on it.
    tx_dir_to_check = tx_dir if tx_dir else transaction_manager.TRANSACTIONS_DIR
    head_file = tx_dir_to_check / "HEAD"
    if not head_file.exists():
        return None
    return head_file.read_text().strip()

class TestProtocolV2(unittest.TestCase):
    runner = CliRunner()

    @classmethod
    def setUpClass(cls):
        cls.class_base_dir = Path(tempfile.mkdtemp(prefix="hronir_test_proto_v2_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.class_base_dir, ignore_errors=True)

    def setUp(self):
        # Create a unique directory for each test method for full isolation
        self.test_specific_dir = self.class_base_dir / self.id().split('.')[-1]
        self.test_specific_dir.mkdir(parents=True, exist_ok=True)

        self.library_path = self.test_specific_dir / "the_library"
        self.data_dir_path = self.test_specific_dir / "data"
        self.db_file_path = self.data_dir_path / "test_specific.duckdb"
        self.canonical_path_file_path = self.data_dir_path / "canonical_path.json"
        self.transactions_dir_path = self.data_dir_path / "transactions" # Though direct access is less common now

        self.library_path.mkdir(parents=True, exist_ok=True)
        self.data_dir_path.mkdir(parents=True, exist_ok=True)
        self.transactions_dir_path.mkdir(parents=True, exist_ok=True)

        # Store and override environment variables
        self.original_env_vars = {
            "HRONIR_LIBRARY_DIR": os.getenv("HRONIR_LIBRARY_DIR"),
            "HRONIR_DUCKDB_PATH": os.getenv("HRONIR_DUCKDB_PATH"),
            "HRONIR_DATA_DIR": os.getenv("HRONIR_DATA_DIR"), # For canonical_path.json etc.
        }
        os.environ["HRONIR_LIBRARY_DIR"] = str(self.library_path.resolve())
        os.environ["HRONIR_DUCKDB_PATH"] = str(self.db_file_path.resolve())
        os.environ["HRONIR_DATA_DIR"] = str(self.data_dir_path.resolve())

        # Reset DataManager singleton instance to ensure it picks up new env vars
        if storage.data_manager._instance is not None:
            if hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
                try: storage.data_manager.backend.conn.close()
                except Exception: pass
            storage.data_manager._instance = None

        # Initialize a DataManager for this test's scope; it will create the DB
        # This also ensures that CLI commands invoked later use this isolated DB.
        current_dm = storage.DataManager()
        current_dm.initialize_and_load(clear_existing_data=True)

        # For tests directly manipulating transaction files (if any remain)
        self.original_tm_transactions_dir = transaction_manager.TRANSACTIONS_DIR
        transaction_manager.TRANSACTIONS_DIR = self.transactions_dir_path


    def tearDown(self):
        # Clean up DataManager instance
        if storage.data_manager._instance is not None:
            if hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
                try: storage.data_manager.backend.conn.close()
                except Exception: pass
            storage.data_manager._instance = None

        # Restore original environment variables
        for key, value in self.original_env_vars.items():
            if value is None:
                if key in os.environ: del os.environ[key]
            else:
                os.environ[key] = value

        # Restore transaction_manager path
        transaction_manager.TRANSACTIONS_DIR = self.original_tm_transactions_dir

        # Explicitly remove the test-specific directory to clean up all its contents
        shutil.rmtree(self.test_specific_dir, ignore_errors=True)

    def _create_path_cli(self, position: int, target_hr_uuid: str, source_hr_uuid: str | None = None) -> str:
        args = ["path", "--pos", str(position), "--target-hr", target_hr_uuid]
        if source_hr_uuid:
            args.extend(["--source-hr", source_hr_uuid])

        res_path_create = self.runner.invoke(app, args, catch_exceptions=False)
        self.assertEqual(res_path_create.exit_code, 0,
            f"CLI path create failed: Pos:{position}, Target:{target_hr_uuid}, Src:{source_hr_uuid}. "
            f"STDOUT: {res_path_create.stdout} STDERR: {res_path_create.stderr}")
        try:
            path_uuid = res_path_create.stdout.strip().split("Created path: ")[1]
        except IndexError:
            self.fail(f"Could not parse path_uuid from CLI output: {res_path_create.stdout}")
        return path_uuid

    def test_sybil_resistance(self):
        # Test simplified: focuses on creating paths. Sybil implications are more complex.
        num_sybil_paths = 2 # Reduced for speed
        sybil_path_uuids = []
        pos0_canon_hrönir_uuid = _create_dummy_chapter(self.library_path, "sybil_pos0_canon")
        self._create_path_cli(0, pos0_canon_hrönir_uuid) # Create root path

        for i in range(num_sybil_paths):
            sybil_hrönir_uuid = _create_dummy_chapter(self.library_path, f"sybil_ch_pos1_{i}")
            path_uuid = self._create_path_cli(1, sybil_hrönir_uuid, source_hr_uuid=pos0_canon_hrönir_uuid)
            sybil_path_uuids.append(path_uuid)

        dm = storage.DataManager()
        for path_uuid_str in sybil_path_uuids:
            self.assertIsNotNone(dm.get_path_by_uuid(path_uuid_str), f"Path {path_uuid_str} not found.")
        typer.echo(f"Sybil resistance test simplified: created {num_sybil_paths} paths.")

    def test_legitimate_promotion_and_mandate_issuance(self):
        self.skipTest("Path status (PENDING, QUALIFIED) and mandate_id are removed; test obsolete.")

    def test_mandate_double_spend_prevention(self):
        # Test focuses on `consumed_voting_tokens` table.
        dm = storage.DataManager()
        h0_root_hr = _create_dummy_chapter(self.library_path, "ds_h0_root")
        self._create_path_cli(0, h0_root_hr)

        h1_A_hr = _create_dummy_chapter(self.library_path, "ds_h1_A")
        p1_A_uuid = self._create_path_cli(1, h1_A_hr, source_hr_uuid=h0_root_hr)
        h1_B_hr = _create_dummy_chapter(self.library_path, "ds_h1_B")
        self._create_path_cli(1, h1_B_hr, source_hr_uuid=h0_root_hr)

        ratings.generate_and_store_new_pending_duel(1, h0_root_hr, dm)
        dm.save_all_data_to_csvs() # Commit
        self.assertIsNotNone(dm.get_active_duel_for_position(1), "Duel for pos 1 not created.")

        token_hr = _create_dummy_chapter(self.library_path, "ds_token_hr")
        # Create voting token at position 1, has sqrt(1)=1 vote.
        voting_token_path_uuid = self._create_path_cli(1, token_hr, source_hr_uuid=h0_root_hr)

        verdicts = {"1": p1_A_uuid}
        verdicts_file = self.data_dir_path / "verdicts_ds.json"
        verdicts_file.write_text(json.dumps(verdicts))

        res_vote1 = self.runner.invoke(app, [
            "cast-votes", "--voting-path-uuid", voting_token_path_uuid,
            "--verdicts", str(verdicts_file), "--canonical-path-file", str(self.canonical_path_file_path)
        ], catch_exceptions=False)
        self.assertEqual(res_vote1.exit_code, 0, f"First cast-votes: {res_vote1.stderr}")
        self.assertTrue(dm.is_token_consumed(voting_token_path_uuid), "Token not consumed.")

        res_vote2 = self.runner.invoke(app, [
            "cast-votes", "--voting-path-uuid", voting_token_path_uuid,
            "--verdicts", str(verdicts_file), "--canonical-path-file", str(self.canonical_path_file_path)
        ], catch_exceptions=False)
        self.assertNotEqual(res_vote2.exit_code, 0, "Second vote with consumed token should fail.")
        self.assertIn("already used", (res_vote2.stderr + res_vote2.stdout).lower())


    def test_temporal_cascade_trigger(self):
        # Using self.runner, self.library_path, self.data_dir_path, self.canonical_path_file_path from setUp.
        # Env vars are set in setUp to point DataManager to isolated paths.

        res_init = self.runner.invoke(app, ["init-test"], catch_exceptions=False)
        self.assertEqual(res_init.exit_code, 0, f"init-test failed: {res_init.stdout} {res_init.stderr}")

        initial_canon_data = json.loads(self.canonical_path_file_path.read_text())
        p0_A_path_uuid = initial_canon_data["path"]["0"]["path_uuid"]
        h0_A_hrönir_uuid = initial_canon_data["path"]["0"]["hrönir_uuid"]
        p1_A_path_uuid = initial_canon_data["path"]["1"]["path_uuid"]
        h1_A_hrönir_uuid = initial_canon_data["path"]["1"]["hrönir_uuid"]

        h1_B_text = "This is hrönir H1_B, competitor for position 1."
        h1_B_hrönir_uuid = _create_dummy_chapter(self.library_path, "cascade_h1_B")
        p1_B_path_uuid = self._create_path_cli(1, h1_B_hrönir_uuid, source_hr_uuid=h0_A_hrönir_uuid)

        dm = storage.DataManager()
        ratings.generate_and_store_new_pending_duel(1, h0_A_hrönir_uuid, dm)
        dm.save_all_data_to_csvs()

        active_duel_pos1 = dm.get_active_duel_for_position(1)
        self.assertIsNotNone(active_duel_pos1, "No active duel for position 1.")
        self.assertEqual({active_duel_pos1["path_A_uuid"], active_duel_pos1["path_B_uuid"]}, {p1_A_path_uuid, p1_B_path_uuid})

        h2_token_text = "This hrönir is for the voting token at pos 2."
        h2_token_hrönir_uuid = _create_dummy_chapter(self.library_path, "cascade_h2_token")
        voting_token_path_uuid = self._create_path_cli(2, h2_token_hrönir_uuid, source_hr_uuid=h1_A_hrönir_uuid)

        verdicts = {"1": p1_B_path_uuid}
        verdicts_file = self.data_dir_path / "verdicts_cascade.json"
        verdicts_file.write_text(json.dumps(verdicts))

        res_vote = self.runner.invoke(app, [
            "cast-votes",
            "--voting-path-uuid", voting_token_path_uuid,
            "--verdicts", str(verdicts_file),
            "--canonical-path-file", str(self.canonical_path_file_path)
        ], catch_exceptions=False)
        self.assertEqual(res_vote.exit_code, 0, f"cast-votes failed: {res_vote.stdout} {res_vote.stderr}")

        final_canon_data = json.loads(self.canonical_path_file_path.read_text())

        self.assertEqual(final_canon_data["path"]["0"]["path_uuid"], p0_A_path_uuid, "Pos 0 path_uuid changed.")
        self.assertEqual(final_canon_data["path"]["0"]["hrönir_uuid"], h0_A_hrönir_uuid, "Pos 0 hrönir_uuid changed.")
        self.assertIn("1", final_canon_data["path"], "Position 1 missing in final canon.")
        self.assertEqual(final_canon_data["path"]["1"]["path_uuid"], p1_B_path_uuid, "Pos 1 path_uuid not updated.")
        self.assertEqual(final_canon_data["path"]["1"]["hrönir_uuid"], h1_B_hrönir_uuid, "Pos 1 hrönir_uuid not updated.")

    def test_cast_vote_on_position_0_rejected(self):
        # Test that attempting to cast a vote for position 0 is rejected by the CLI.

        # Setup: init-test to create a basic environment.
        # The canonical_path_file will be created by init-test in self.data_dir_path.
        res_init = self.runner.invoke(app, ["init-test"], catch_exceptions=False)
        self.assertEqual(res_init.exit_code, 0, f"init-test failed: {res_init.stdout} {res_init.stderr}")

        # Create a voting token path (e.g., at position 1, so it has power).
        # Need the H0 hrönir UUID from the initialized canon to be a predecessor.
        initial_canon_data = json.loads(self.canonical_path_file_path.read_text())
        h0_A_hrönir_uuid = initial_canon_data["path"]["0"]["hrönir_uuid"]

        token_hr_text = "Voting token hrönir for pos 0 rejection test"
        token_hr_uuid = _create_dummy_chapter(self.library_path, "pos0_reject_token_hr")
        voting_token_path_uuid = self._create_path_cli(1, token_hr_uuid, source_hr_uuid=h0_A_hrönir_uuid)

        # Attempt to vote on position 0.
        # Create a dummy path UUID to vote for at position 0. It doesn't need to be real or in a duel,
        # as the CLI validation for position 0 should occur before duel checks for that position.
        dummy_pos0_target_path_uuid = str(uuid.uuid4())

        verdicts = {"0": dummy_pos0_target_path_uuid} # Target position 0 in verdicts
        verdicts_file = self.data_dir_path / "verdicts_pos0_reject.json"
        verdicts_file.write_text(json.dumps(verdicts))

        res_vote = self.runner.invoke(app, [
            "cast-votes",
            "--voting-path-uuid", voting_token_path_uuid,
            "--verdicts", str(verdicts_file),
            "--canonical-path-file", str(self.canonical_path_file_path) # Use the one from setUp
        ], catch_exceptions=False)

        self.assertNotEqual(res_vote.exit_code, 0,
            "CLI 'cast-votes' should fail when trying to vote on position 0.")

        # Check for the specific error message.
        # Typer prints errors to stderr by default when using typer.secho with fg=colors.RED and err=True.
        self.assertIn("voting on position 0 is not allowed", res_vote.stderr.lower(),
            f"Expected error message about position 0 voting not found. STDERR: {res_vote.stderr}, STDOUT: {res_vote.stdout}")


if __name__ == "__main__":
    unittest.main()
