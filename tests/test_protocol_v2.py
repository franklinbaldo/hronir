import json
import os
import shutil
import unittest
import uuid
from pathlib import Path

from typer.testing import CliRunner

from hronir_encyclopedia import cli, session_manager, storage, transaction_manager
from hronir_encyclopedia.models import Path as PathModel


# Helper to create a unique dummy chapter file and return its UUID
def _create_dummy_chapter(library_path: Path, content_prefix: str) -> str:
    text = f"Chapter content for {content_prefix} {uuid.uuid4()}"
    # Use storage.store_chapter_text to ensure it's stored correctly by UUID path
    chapter_uuid = storage.store_chapter_text(text, base=library_path)
    return chapter_uuid


def _get_head_transaction_uuid(tx_dir: Path | None = None) -> str | None:
    if tx_dir is None:
        tx_dir = transaction_manager.TRANSACTIONS_DIR
    head_file = tx_dir / "HEAD"
    if not head_file.exists():
        return None
    return head_file.read_text().strip()


class TestProtocolV2(unittest.TestCase):
    runner = CliRunner()
    base_dir = Path("temp_test_hronir_data")

    @classmethod
    def setUpClass(cls):
        cls.base_dir.mkdir(parents=True, exist_ok=True)
        # Define specific paths for test data
        cls.library_path = cls.base_dir / "the_library"
        cls.forking_path_dir = cls.base_dir / "narrative_paths"
        cls.ratings_dir = cls.base_dir / "ratings"
        cls.transactions_dir = cls.base_dir / "data" / "transactions"
        cls.sessions_dir = cls.base_dir / "data" / "sessions"
        cls.canonical_path_file = cls.base_dir / "data" / "canonical_path.json"

        cls.library_path.mkdir(parents=True, exist_ok=True)
        cls.forking_path_dir.mkdir(parents=True, exist_ok=True)
        cls.ratings_dir.mkdir(parents=True, exist_ok=True)
        cls.transactions_dir.parent.mkdir(parents=True, exist_ok=True)
        cls.transactions_dir.mkdir(parents=True, exist_ok=True)
        cls.sessions_dir.mkdir(parents=True, exist_ok=True)
        (cls.transactions_dir / "HEAD").write_text("")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base_dir, ignore_errors=True)

    def setUp(self):
        shutil.rmtree(self.forking_path_dir, ignore_errors=True)
        shutil.rmtree(self.ratings_dir, ignore_errors=True)
        shutil.rmtree(self.transactions_dir, ignore_errors=True)
        shutil.rmtree(self.sessions_dir, ignore_errors=True)
        if self.canonical_path_file.exists():
            self.canonical_path_file.unlink()

        self.forking_path_dir.mkdir(parents=True, exist_ok=True)
        self.ratings_dir.mkdir(parents=True, exist_ok=True)
        self.transactions_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        (self.transactions_dir / "HEAD").write_text("")

        self.original_tm_transactions_dir = transaction_manager.TRANSACTIONS_DIR
        self.original_tm_head_file = transaction_manager.HEAD_FILE
        self.original_sm_sessions_dir = session_manager.SESSIONS_DIR
        self.original_sm_consumed_file = (
            session_manager.CONSUMED_PATHS_FILE
        )  # Changed FORKS to PATHS
        self.original_storage_uuid_namespace = storage.UUID_NAMESPACE
        self.original_env_library_dir = os.getenv("HRONIR_LIBRARY_DIR")
        self.original_env_narrative_paths_dir = os.getenv("HRONIR_NARRATIVE_PATHS_DIR")
        self.original_env_ratings_dir = os.getenv("HRONIR_RATINGS_DIR")
        self.original_env_use_duckdb = os.getenv("HRONIR_USE_DUCKDB")

        self.original_dm_fork_csv_dir = storage.data_manager.fork_csv_dir
        self.original_dm_ratings_csv_dir = storage.data_manager.ratings_csv_dir
        self.original_dm_transactions_json_dir = storage.data_manager.transactions_json_dir # Keep for restoration if needed by other modules

        # DataManager will now use DuckDB by default, configured by conftest.py's HRONIR_DUCKDB_PATH.
        # The specific CSV dirs (fork_csv_dir, ratings_csv_dir) are less relevant for direct DataManager manipulation here,
        # as operations will go to DuckDB. They are used by DuckDBDataManager for initial load from CSV if DB is empty.
        # We will rely on conftest.py to set up a temporary DuckDB.
        # Legacy HRONIR_LIBRARY_DIR might still be picked up by storage.py for the self.library_path if we don't clear it.
        # For these tests, we want store_hrönir to use the DB, so self.library_path in DataManager should ideally not be used for primary storage.

        os.environ["HRONIR_LIBRARY_DIR"] = str(self.library_path) # store_chapter_text in _create_dummy_chapter uses this
                                                                  # DataManager.store_hrönir uses self.library_path if saving MD files,
                                                                  # but now it saves to DB. The physical library_path is for loading content.

        # Clear any specific CSV path settings on DataManager instance if they were set by old code or other tests.
        # Defaults will be used by DuckDBDataManager for initial load if its DB is empty.
        # storage.data_manager.fork_csv_dir = Path(os.getenv("HRONIR_NARRATIVE_PATHS_DIR", "narrative_paths"))
        # storage.data_manager.ratings_csv_dir = Path(os.getenv("HRONIR_RATINGS_DIR", "ratings"))
        # storage.data_manager.transactions_json_dir = Path(os.getenv("HRONIR_TRANSACTIONS_JSON_DIR", "data/transactions"))
        # The above are not strictly necessary as DataManager init is complex; rely on conftest.py re-init.

        # Ensure the DataManager instance from conftest.py is used.
        # conftest.py already does: storage.DataManager._instance = None; storage.data_manager = storage.DataManager()
        # So, data_manager here is already the test-specific DuckDB one.

        # transaction_manager and session_manager might still use file paths for now.
        # TODO: Update these managers to use DataManager for their persistence.
        transaction_manager.TRANSACTIONS_DIR = self.transactions_dir # This will be unused if TM uses DB
        transaction_manager.HEAD_FILE = self.transactions_dir / "HEAD"
        session_manager.SESSIONS_DIR = self.sessions_dir
        session_manager.CONSUMED_PATHS_FILE = self.sessions_dir / "consumed_fork_uuids.json"

        storage.data_manager._initialized = False
        storage.data_manager.initialize_and_load(clear_existing_data=True)

        self.predecessor_ch_uuid_pos0 = _create_dummy_chapter(
            self.library_path, "predecessor_pos0_test"
        )

    def tearDown(self):
        transaction_manager.TRANSACTIONS_DIR = self.original_tm_transactions_dir
        transaction_manager.HEAD_FILE = self.original_tm_head_file
        session_manager.SESSIONS_DIR = self.original_sm_sessions_dir
        session_manager.CONSUMED_PATHS_FILE = (
            self.original_sm_consumed_file
        )  # Changed FORKS to PATHS
        storage.UUID_NAMESPACE = self.original_storage_uuid_namespace
        if self.original_env_library_dir is None:
            del os.environ["HRONIR_LIBRARY_DIR"]
        else:
            os.environ["HRONIR_LIBRARY_DIR"] = self.original_env_library_dir

        if self.original_env_narrative_paths_dir is None:
            if "HRONIR_NARRATIVE_PATHS_DIR" in os.environ: del os.environ["HRONIR_NARRATIVE_PATHS_DIR"]
        else:
            os.environ["HRONIR_NARRATIVE_PATHS_DIR"] = self.original_env_narrative_paths_dir

        if self.original_env_ratings_dir is None:
            if "HRONIR_RATINGS_DIR" in os.environ: del os.environ["HRONIR_RATINGS_DIR"] # Restored
        else:
            os.environ["HRONIR_RATINGS_DIR"] = self.original_env_ratings_dir # Restored

        # HRONIR_USE_DUCKDB is no longer used by DataManager directly.
        # The conftest.py fixture handles setting up DuckDB for tests.
        # So, no need to restore self.original_env_use_duckdb here for DataManager's direct behavior.
        # However, if other parts of the system (not DataManager) were to check this env var,
        # then restoring it would be important. For now, assume it's only for DataManager.
        if self.original_env_use_duckdb is not None:
            os.environ["HRONIR_USE_DUCKDB"] = self.original_env_use_duckdb
        elif "HRONIR_USE_DUCKDB" in os.environ:
            del os.environ["HRONIR_USE_DUCKDB"]


        # DataManager's paths are now primarily controlled by its internal DuckDB path,
        # set by conftest.py. Resetting library_path from env is okay if some
        # legacy file operations in tests still depend on it.
        # The fork_csv_dir etc. on the instance are less relevant if all ops go to DB.
        storage.data_manager.library_path = Path(os.getenv("HRONIR_LIBRARY_DIR", "the_library"))
        # The following are not strictly necessary to reset if DataManager always uses DuckDB
        # and these are only for initial load from CSV.
        # storage.data_manager.fork_csv_dir = self.original_dm_fork_csv_dir
        # storage.data_manager.ratings_csv_dir = self.original_dm_ratings_csv_dir
        storage.data_manager.transactions_json_dir = self.original_dm_transactions_json_dir # This might be read by other modules

    def _create_fork_entry(
        self, position: int, prev_uuid_str: str | None, current_hrönir_uuid: str
    ) -> str:
        """Helper to create a fork entry and return the path_uuid."""
        path_uuid_obj = storage.compute_narrative_path_uuid(
            position, prev_uuid_str if prev_uuid_str else "", current_hrönir_uuid
        )

        model_prev_uuid = (
            uuid.UUID(prev_uuid_str) if prev_uuid_str and prev_uuid_str != "" else None
        )

        path_model = PathModel(
            path_uuid=path_uuid_obj,
            position=position,
            prev_uuid=model_prev_uuid,
            uuid=uuid.UUID(current_hrönir_uuid),
            status="PENDING",
        )
        storage.data_manager.add_path(path_model)
        storage.data_manager.save_all_data() # Ensure path is committed to DB
        return str(path_uuid_obj)

    def test_sybil_resistance(self):
        num_sybil_forks = 50
        sybil_path_uuids = []

        pos0_prev_hrönir_uuid = None
        pos0_canonical_hrönir_uuid = _create_dummy_chapter(self.library_path, "sybil_pos0_canon")
        self._create_fork_entry(0, pos0_prev_hrönir_uuid, pos0_canonical_hrönir_uuid)
        # _create_dummy_chapter and _create_fork_entry now handle DB writes and commits.

        for i in range(num_sybil_forks):
            sybil_hrönir_uuid = _create_dummy_chapter(self.library_path, f"sybil_ch_pos1_{i}")
            path_uuid = self._create_fork_entry(
                position=1,
                prev_uuid_str=pos0_canonical_hrönir_uuid,
                current_hrönir_uuid=sybil_hrönir_uuid,
            )
            sybil_path_uuids.append(path_uuid)

        # storage.data_manager.save_all_data() # Data is saved/committed by helpers
        # CLI will use the same DB instance via conftest.py's DataManager setup.

        for path_uuid in sybil_path_uuids:
            # Re-fetch after potential save/load cycle or ensure test uses consistent DataManager state
            path_data_obj = storage.data_manager.get_path_by_uuid(path_uuid)
            self.assertIsNotNone(path_data_obj, f"Path data for {path_uuid} should exist in DB.")
            self.assertEqual(
                path_data_obj.status, "PENDING", f"Sybil path {path_uuid} should be PENDING."
            )

            result = self.runner.invoke(
                cli.app,
                [
                    "session",
                    "start",
                    "--path-uuid",  # Changed --fork-uuid to --path-uuid
                    path_uuid,
                    # "--forking-path-dir", str(self.forking_path_dir), # Removed
                    # "--ratings-dir", str(self.ratings_dir), # Removed
                    "--canonical-path-file",
                    str(self.canonical_path_file),
                ],
            )
            self.assertNotEqual(
                result.exit_code, 0, f"session start should fail for PENDING path {path_uuid}"
            )
            # CLI commands print errors. Typer might send them to stderr or stdout depending on context.
            # We expect a non-zero exit code and the error message to be present in either stdout or stderr.
            error_message_found = False
            # Based on cli.py output: f"Error: Path '{path_uuid_str}' not QUALIFIED (status: '{path_data_obj.status}')"
            expected_error_substring_status = "not QUALIFIED" # Adjusted to new wording
            expected_error_substring_used = "already been used" # For other potential failures

            if result.stdout and (expected_error_substring_status in result.stdout or expected_error_substring_used in result.stdout):
                error_message_found = True

            if result.stderr and (expected_error_substring_status in result.stderr or expected_error_substring_used in result.stderr):
                error_message_found = True

            if not error_message_found:
                self.fail(
                    f"Session start for PENDING path {path_uuid} did not produce the expected error string "
                    f"'{expected_error_substring_status}' or '{expected_error_substring_used}' "
                    f"in stdout or stderr.\nStdout: {result.stdout}\nStderr: {result.stderr}"
                )

    def test_legitimate_promotion_and_mandate_issuance(self):
        pos0_hrönir_A = _create_dummy_chapter(self.library_path, "pos0_chA_promo")

        fgood_hrönir = _create_dummy_chapter(self.library_path, "fgood_ch_pos1")
        fother_hrönir = _create_dummy_chapter(self.library_path, "fother_ch_pos1")

        fgood_path_uuid = self._create_fork_entry(
            position=1, prev_uuid_str=pos0_hrönir_A, current_hrönir_uuid=fgood_hrönir
        )
        self._create_fork_entry(
            position=1, prev_uuid_str=pos0_hrönir_A, current_hrönir_uuid=fother_hrönir
        )

        fgood_initial_obj = storage.data_manager.get_path_by_uuid(fgood_path_uuid)
        self.assertIsNotNone(
            fgood_initial_obj, f"F_good path {fgood_path_uuid} not found in DB initially."
        )
        self.assertEqual(
            fgood_initial_obj.status,
            "PENDING",
            f"F_good path {fgood_path_uuid} should be PENDING initially.",
        )

        dummy_session_id = str(uuid.uuid4())
        # This should be a valid path_uuid that is QUALIFIED, or a placeholder if not strictly checked by TM
        # Generate a dummy UUIDv5 for the initiating voter path
        dummy_initiator_prev_hr_uuid = _create_dummy_chapter(
            self.library_path, "dummy_initiator_prev_hr"
        )
        dummy_initiator_curr_hr_uuid = _create_dummy_chapter(
            self.library_path, "dummy_initiator_curr_hr"
        )
        dummy_initiating_voter_path_uuid = str(
            storage.compute_narrative_path_uuid(
                position=0,  # Or any appropriate position for the initiator
                prev_hronir_uuid=dummy_initiator_prev_hr_uuid,
                current_hronir_uuid=dummy_initiator_curr_hr_uuid,
            )
        )
        # Ensure this dummy path is added to storage so it can be found if needed by TM logic (though not strictly required by all TM versions)
        # For this test, we assume the TM doesn't need to fetch the full initiator PathModel object, just its UUID.
        # If it did, we'd need to _create_fork_entry for it and potentially qualify it.

        votes_to_qualify_fgood = []
        num_wins_for_elo_qualification = 4

        for i in range(num_wins_for_elo_qualification):
            dummy_loser_hrönir = _create_dummy_chapter(self.library_path, f"dummy_loser_promo_{i}")
            self._create_fork_entry(
                position=1,
                prev_uuid_str=pos0_hrönir_A,
                current_hrönir_uuid=dummy_loser_hrönir,
            )
            votes_to_qualify_fgood.append(
                {
                    "position": 1,
                    "winner_hrönir_uuid": fgood_hrönir,
                    "loser_hrönir_uuid": dummy_loser_hrönir,
                    "predecessor_hrönir_uuid": pos0_hrönir_A,
                }
            )

        last_tx_hash_before_qualifying_tx = ""

        # Ensure all paths created by _create_fork_entry are saved before record_transaction
        storage.data_manager.save_all_data()

        tx_result_data = transaction_manager.record_transaction(
            session_id=dummy_session_id,
            initiating_fork_uuid=dummy_initiating_voter_path_uuid,  # Ensure this is path_uuid
            session_verdicts=votes_to_qualify_fgood,
        )
        self.assertIsNotNone(tx_result_data)
        self.assertIn("transaction_uuid", tx_result_data)
        self.assertEqual(
            _get_head_transaction_uuid(self.transactions_dir),
            tx_result_data["transaction_uuid"],
        )

        fgood_final_obj = storage.data_manager.get_path_by_uuid(fgood_path_uuid)
        self.assertIsNotNone(
            fgood_final_obj, "F_good path data should still exist in DB after transaction."
        )
        self.assertEqual(fgood_final_obj.status, "QUALIFIED", "F_good path should be QUALIFIED.")

        generated_mandate_id = fgood_final_obj.mandate_id
        self.assertIsNotNone(generated_mandate_id, "F_good should have a mandate_id.")
        self.assertTrue(len(str(generated_mandate_id)) > 0)

        # The mandate_id is now a UUID generated by transaction_manager.
        # The test should verify its presence and that it's a valid UUID.
        # import blake3 # No longer needed for this assertion
        self.assertIsNotNone(generated_mandate_id, "F_good should have a mandate_id.")
        try:
            uuid.UUID(str(generated_mandate_id))
            is_valid_uuid = True
        except ValueError:
            is_valid_uuid = False
        self.assertTrue(is_valid_uuid, f"Generated mandate_id '{generated_mandate_id}' is not a valid UUID.")

        promotions = tx_result_data.get("promotions_granted", [])
        found_promotion_in_tx = False
        for promo_path_uuid in promotions:
            if promo_path_uuid == fgood_path_uuid:
                found_promotion_in_tx = True
                break
        self.assertTrue(
            found_promotion_in_tx, "F_good's promotion should be listed in the transaction result."
        )

    def test_mandate_double_spend_prevention(self):
        pos0_hrönir_pred = _create_dummy_chapter(self.library_path, "pos0_chDS_pred")

        fork_to_spend_hrönir = _create_dummy_chapter(self.library_path, "ch_to_spend_pos1")
        _ = _create_dummy_chapter(self.library_path, "ch_other_ds_pos1")

        path_to_spend_uuid = self._create_fork_entry(
            position=1,
            prev_uuid_str=pos0_hrönir_pred,
            current_hrönir_uuid=fork_to_spend_hrönir,
        )

        votes_for_qualification = []
        for i in range(4):
            dummy_loser_hrönir_ds = _create_dummy_chapter(self.library_path, f"dummy_loser_ds_{i}")
            self._create_fork_entry(
                position=1,
                prev_uuid_str=pos0_hrönir_pred,
                current_hrönir_uuid=dummy_loser_hrönir_ds,
            )
            votes_for_qualification.append(
                {
                    "position": 1,
                    "winner_hrönir_uuid": fork_to_spend_hrönir,
                    "loser_hrönir_uuid": dummy_loser_hrönir_ds,
                    "predecessor_hrönir_uuid": pos0_hrönir_pred,
                }
            )

        # Generate a dummy UUIDv5 for the initiating voter path
        dummy_initiator_prev_hr_uuid_ds = _create_dummy_chapter(
            self.library_path, "dummy_initiator_prev_hr_ds"
        )
        dummy_initiator_curr_hr_uuid_ds = _create_dummy_chapter(
            self.library_path, "dummy_initiator_curr_hr_ds"
        )
        ds_initiating_path_uuid = str(
            storage.compute_narrative_path_uuid(
                position=0,
                prev_hronir_uuid=dummy_initiator_prev_hr_uuid_ds,
                current_hronir_uuid=dummy_initiator_curr_hr_uuid_ds,
            )
        )

        # Ensure all paths created by _create_fork_entry are saved before record_transaction
        storage.data_manager.save_all_data()

        qualifying_tx_data = transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_fork_uuid=ds_initiating_path_uuid,  # Ensure this is path_uuid
            session_verdicts=votes_for_qualification,
        )
        self.assertIsNotNone(qualifying_tx_data)
        # _get_head_transaction_uuid will need to be updated if transactions are in DB
        # For now, assume transaction_manager still writes HEAD file, or this check is adapted/removed.
        # If transaction_manager is updated to use DataManager, this check changes.
        if (self.transactions_dir / "HEAD").exists(): # Conditional check
            self.assertEqual(
                _get_head_transaction_uuid(self.transactions_dir),
                qualifying_tx_data["transaction_uuid"],
            )

        storage.data_manager.save_all_data()  # Save after TX before CLI

        path_data_qualified_obj = storage.data_manager.get_path_by_uuid(path_to_spend_uuid)
        self.assertIsNotNone(
            path_data_qualified_obj,
            f"Path {path_to_spend_uuid} not found in DB after qualification.",
        )
        self.assertEqual(path_data_qualified_obj.status, "QUALIFIED")
        mandate_id_to_spend = path_data_qualified_obj.mandate_id
        self.assertIsNotNone(mandate_id_to_spend)

        p0_duel_chA = _create_dummy_chapter(self.library_path, "p0_duelA_ds")
        p0_duel_chB = _create_dummy_chapter(self.library_path, "p0_duelB_ds")
        # These fork entries also need to be saved if the CLI session start depends on them for duel generation
        _p0_path_A = self._create_fork_entry(
            position=0, prev_uuid_str=None, current_hrönir_uuid=p0_duel_chA
        )
        self._create_fork_entry(position=0, prev_uuid_str=None, current_hrönir_uuid=p0_duel_chB)

        storage.data_manager.save_all_data_to_csvs()  # Save after creating duel options

        self.canonical_path_file.write_text(
            json.dumps({"title": "Test Canonical Path", "path": {}})
        )

        start_result = self.runner.invoke(
            cli.app,
            [
                "session",
                "start",
                "--path-uuid",
                path_to_spend_uuid,
                # "--forking-path-dir", str(self.forking_path_dir),  # Removed
                # "--ratings-dir", str(self.ratings_dir),  # Removed
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertEqual(start_result.exit_code, 0, f"Session start failed: {start_result.stdout}")
        start_output = json.loads(start_result.stdout)
        session_id_spent = start_output["session_id"]

        self.assertEqual(session_manager.is_path_consumed(path_to_spend_uuid), session_id_spent)

        session_data_for_commit = session_manager.get_session(session_id_spent)
        self.assertIsNotNone(session_data_for_commit, "Session data should not be None for commit.")
        dossier_duels = {}
        if session_data_for_commit and session_data_for_commit.dossier:
            dossier_duels = session_data_for_commit.dossier.duels

        verdicts_for_commit = {}
        # if "0" in dossier_duels:
        #     duel_at_0 = dossier_duels["0"]
        #     # Access attributes directly on the Pydantic model instance
        #     verdicts_for_commit["0"] = str(duel_at_0.path_A_uuid) if duel_at_0 else None
        verdicts_for_commit_str = "{}" # Force empty verdicts to test that path

        commit_result = self.runner.invoke(
            cli.app,
            [
                "session",
                "commit",
                "--session-id",
                session_id_spent,
                "--verdicts",
                verdicts_for_commit_str, # Pass empty JSON object
                # --forking-path-dir and --ratings-dir are not params of session commit
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        print(f"DEBUG STDOUT: {commit_result.stdout}") # Print stdout directly
        print(f"DEBUG STDERR: {commit_result.stderr}") # Print stderr directly
        self.assertEqual(
            commit_result.exit_code, 0, f"Session commit failed: {commit_result.stdout}\nStderr: {commit_result.stderr}"
        )

        # CLI's session commit interacts with DataManager (which uses DuckDB).
        # The DataManager instance in the test (storage.data_manager) is the same one
        # used by the CLI code, due to conftest.py and how DataManager is a singleton.
        # No explicit reload from CSVs is needed. Any changes made by CLI are in the DB.

        # --- Debug: Check DB content directly if needed ---
        # Example:
        # path_from_db_after_commit = storage.data_manager.get_path_by_uuid(path_to_spend_uuid)
        # print(f"\nDEBUG: Path {path_to_spend_uuid} from DB after CLI commit: {path_from_db_after_commit}")
        # --- End Debug ---

        # storage.data_manager.initialize_and_load() # No longer reloading from files.

        path_data_spent_obj = storage.data_manager.get_path_by_uuid(path_to_spend_uuid)
        self.assertIsNotNone(
            path_data_spent_obj, f"Path {path_to_spend_uuid} not found in DB after spending."
        )
        self.assertEqual(
            path_data_spent_obj.status, "SPENT", "Path should be SPENT after session commit."
        )

        second_start_result = self.runner.invoke(
            cli.app,
            [
                "session",
                "start",
                "--path-uuid",  # Changed --fork-uuid to --path-uuid
                path_to_spend_uuid,
                # "--forking-path-dir", str(self.forking_path_dir), # Removed
                # "--ratings-dir", str(self.ratings_dir), # Removed
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertNotEqual(
            second_start_result.exit_code, 0, "Second session start with SPENT path should fail."
        )
        # Current CLI output for a SPENT path is "Error: Path '...' not QUALIFIED (status: 'SPENT')."
        # It might also be caught by "is_path_consumed" check if commit also marks consumed.
        self.assertTrue(
            "not QUALIFIED" in second_start_result.stdout  # Simpler check for the primary error
            or "already been used" in second_start_result.stdout, # Check for consumption message
            f"Second session start output unexpected: {second_start_result.stdout}",
        )

    def test_temporal_cascade_trigger(self):
        p0_ch_A = _create_dummy_chapter(self.library_path, "p0_cascade_A")
        p0_ch_B = _create_dummy_chapter(self.library_path, "p0_cascade_B")
        p0_path_A_uuid = self._create_fork_entry(
            position=0, prev_uuid_str=None, current_hrönir_uuid=p0_ch_A
        )
        p0_path_B_uuid = self._create_fork_entry(
            position=0, prev_uuid_str=None, current_hrönir_uuid=p0_ch_B
        )

        p1_ch_X = _create_dummy_chapter(self.library_path, "p1_cascade_X")
        p1_ch_Y = _create_dummy_chapter(self.library_path, "p1_cascade_Y")
        p1_path_X_uuid = self._create_fork_entry(
            position=1, prev_uuid_str=p0_ch_A, current_hrönir_uuid=p1_ch_X
        )
        self._create_fork_entry(position=1, prev_uuid_str=p0_ch_A, current_hrönir_uuid=p1_ch_Y)

        p1_ch_Z_from_B = _create_dummy_chapter(self.library_path, "p1_cascade_Z_from_B")
        p1_path_Z_from_B_uuid = self._create_fork_entry(
            position=1, prev_uuid_str=p0_ch_B, current_hrönir_uuid=p1_ch_Z_from_B
        )

        initial_canon_data = {
            "title": "Initial Canon for Cascade Test",
            "path": {
                "0": {"path_uuid": p0_path_A_uuid, "hrönir_uuid": p0_ch_A},
                "1": {"path_uuid": p1_path_X_uuid, "hrönir_uuid": p1_ch_X},
            },
        }
        self.canonical_path_file.write_text(json.dumps(initial_canon_data, indent=2))

        qualifying_fork_pos = 2
        qf_hrönir = _create_dummy_chapter(self.library_path, "qf_cascade_ch")
        _ = _create_dummy_chapter(self.library_path, "qf_other_cascade_ch")

        qf_path_uuid = self._create_fork_entry(
            position=qualifying_fork_pos,
            prev_uuid_str=p1_ch_X,
            current_hrönir_uuid=qf_hrönir,
        )

        votes_for_qf_qualification = []
        for i in range(4):
            dummy_loser_qf = _create_dummy_chapter(self.library_path, f"dummy_loser_qf_{i}")
            self._create_fork_entry(
                position=qualifying_fork_pos,
                prev_uuid_str=p1_ch_X,
                current_hrönir_uuid=dummy_loser_qf,
            )
            votes_for_qf_qualification.append(
                {
                    "position": qualifying_fork_pos,
                    "winner_hrönir_uuid": qf_hrönir,
                    "loser_hrönir_uuid": dummy_loser_qf,
                    "predecessor_hrönir_uuid": p1_ch_X,
                }
            )

        # Generate a dummy UUIDv5 for the initiating voter path
        dummy_initiator_prev_hr_uuid_tc = _create_dummy_chapter(
            self.library_path, "dummy_initiator_prev_hr_tc"
        )
        dummy_initiator_curr_hr_uuid_tc = _create_dummy_chapter(
            self.library_path, "dummy_initiator_curr_hr_tc"
        )
        tc_initiating_path_uuid = str(
            storage.compute_narrative_path_uuid(
                # The initiating path for qualifying a fork at 'qualifying_fork_pos'
                # would typically be at 'qualifying_fork_pos - 1' or some other existing qualified path.
                # For simplicity, using pos 0, but in a real scenario, it should be a relevant qualified path.
                position=0,
                prev_hronir_uuid=dummy_initiator_prev_hr_uuid_tc,
                current_hronir_uuid=dummy_initiator_curr_hr_uuid_tc,
            )
        )

        # Ensure all paths created by _create_fork_entry are saved before record_transaction
        storage.data_manager.save_all_data()

        transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_fork_uuid=tc_initiating_path_uuid,  # Ensure this is path_uuid
            session_verdicts=votes_for_qf_qualification,
        )

        storage.data_manager.save_all_data()  # Save after TX, before CLI

        qf_data_qualified_obj = storage.data_manager.get_path_by_uuid(qf_path_uuid)
        self.assertIsNotNone(
            qf_data_qualified_obj,
            f"Judging path {qf_path_uuid} not found in DB after qualification.",
        )
        self.assertEqual(
            qf_data_qualified_obj.status, "QUALIFIED", "Judging path QF failed to qualify."
        )

        start_res = self.runner.invoke(
            cli.app,
            [
                "session",
                "start",
                "--path-uuid",
                qf_path_uuid,
                # No longer passing these as session_start uses DataManager internally
                # "--forking-path-dir", str(self.forking_path_dir),
                # "--ratings-dir", str(self.ratings_dir),
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertEqual(start_res.exit_code, 0, f"Session start for QF failed: {start_res.stdout}")
        session_id_for_cascade = json.loads(start_res.stdout)["session_id"]

        verdicts_to_change_canon = {"0": p0_path_B_uuid}

        commit_res = self.runner.invoke(
            cli.app,
            [
                "session",
                "commit",
                "--session-id",
                session_id_for_cascade,
                "--verdicts",
                json.dumps(verdicts_to_change_canon),
                # --forking-path-dir and --ratings-dir are not params of session commit
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertEqual(
            commit_res.exit_code, 0, f"Session commit for cascade test failed: {commit_res.stdout}\nStderr: {commit_res.stderr}"
        )

        # CLI session commit updated data in DuckDB. DataManager instance is shared.
        # storage.data_manager.initialize_and_load() # No longer reloading from files

        final_canon_data = json.loads(self.canonical_path_file.read_text())

        self.assertEqual(final_canon_data["path"]["0"]["path_uuid"], p0_path_B_uuid)
        self.assertEqual(final_canon_data["path"]["0"]["hrönir_uuid"], p0_ch_B)

        self.assertIn("1", final_canon_data["path"], "Position 1 should exist in canonical path")
        self.assertEqual(final_canon_data["path"]["1"]["path_uuid"], p1_path_Z_from_B_uuid)
        self.assertEqual(final_canon_data["path"]["1"]["hrönir_uuid"], p1_ch_Z_from_B)


if __name__ == "__main__":
    unittest.main()
