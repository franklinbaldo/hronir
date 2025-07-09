import json
import os
import shutil
import unittest
import uuid
from pathlib import Path

from typer.testing import CliRunner

from hronir_encyclopedia import cli, storage, transaction_manager, session_manager # Added session_manager
from hronir_encyclopedia.models import Path as PathModel


# Helper to create a unique dummy chapter file and return its UUID
def _create_dummy_chapter(library_path: Path, content_prefix: str) -> str:
    text = f"Chapter content for {content_prefix} {uuid.uuid4()}"
    chapter_uuid = storage.store_chapter_text(text, base=library_path)
    return chapter_uuid

def _get_head_transaction_uuid(tx_dir: Path | None = None) -> str | None:
    # This helper might become obsolete if transaction_manager stops using file-based HEAD
    if tx_dir is None: # pragma: no cover
        tx_dir = transaction_manager.TRANSACTIONS_DIR

    # Adjust path if TRANSACTIONS_DIR itself is the file, or contains HEAD file
    head_file = tx_dir if tx_dir.name == "HEAD" else tx_dir / "HEAD"

    if not head_file.exists():
        return None
    return head_file.read_text().strip()


class TestPathQualification(unittest.TestCase):
    runner = CliRunner()
    base_dir = Path("temp_test_hronir_data_path_qual") # Unique temp dir

    @classmethod
    def setUpClass(cls):
        cls.base_dir.mkdir(parents=True, exist_ok=True)
        cls.library_path = cls.base_dir / "the_library"
        # cls.forking_path_dir = cls.base_dir / "narrative_paths" # No longer primary for paths
        # cls.ratings_dir = cls.base_dir / "ratings" # No longer primary for ratings
        cls.transactions_dir = cls.base_dir / "data" / "transactions" # For TM HEAD file if still used
        cls.sessions_dir = cls.base_dir / "data" / "sessions" # For SM consumed file if still used
        cls.canonical_path_file = cls.base_dir / "data" / "canonical_path.json" # Still used by CLI

        cls.library_path.mkdir(parents=True, exist_ok=True)
        # (cls.forking_path_dir).mkdir(parents=True, exist_ok=True)
        # (cls.ratings_dir).mkdir(parents=True, exist_ok=True)
        cls.transactions_dir.parent.mkdir(parents=True, exist_ok=True)
        cls.transactions_dir.mkdir(parents=True, exist_ok=True)
        cls.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not (cls.transactions_dir / "HEAD").exists() and hasattr(transaction_manager, 'HEAD_FILE'): # Check if TM uses HEAD file
             (cls.transactions_dir / "HEAD").write_text("")


    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base_dir, ignore_errors=True)

    def setUp(self):
        # Clean specific dirs, not the whole base_dir subdirs like library
        # if self.forking_path_dir.exists(): shutil.rmtree(self.forking_path_dir)
        # if self.ratings_dir.exists(): shutil.rmtree(self.ratings_dir)
        if self.transactions_dir.exists(): shutil.rmtree(self.transactions_dir)
        if self.sessions_dir.exists(): shutil.rmtree(self.sessions_dir)
        if self.canonical_path_file.exists(): self.canonical_path_file.unlink()

        # self.forking_path_dir.mkdir(parents=True, exist_ok=True)
        # self.ratings_dir.mkdir(parents=True, exist_ok=True)
        self.transactions_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(transaction_manager, 'HEAD_FILE'): # Check if TM uses HEAD file
            (self.transactions_dir / "HEAD").write_text("")


        # Store original env vars and module-level configs
        self.original_tm_transactions_dir = getattr(transaction_manager, 'TRANSACTIONS_DIR', None)
        self.original_tm_head_file = getattr(transaction_manager, 'HEAD_FILE', None)
        self.original_sm_sessions_dir = getattr(session_manager, 'SESSIONS_DIR', None)
        self.original_sm_consumed_file = getattr(session_manager, 'CONSUMED_PATHS_FILE', None)
        # self.original_storage_uuid_namespace = storage.UUID_NAMESPACE # UUID_NAMESPACE is const
        self.original_env_library_dir = os.getenv("HRONIR_LIBRARY_DIR")

        # Patch module-level paths for transaction_manager and session_manager if they use them
        if hasattr(transaction_manager, 'TRANSACTIONS_DIR'):
            transaction_manager.TRANSACTIONS_DIR = self.transactions_dir
        if hasattr(transaction_manager, 'HEAD_FILE'):
            transaction_manager.HEAD_FILE = self.transactions_dir / "HEAD"
        if hasattr(session_manager, 'SESSIONS_DIR'):
            session_manager.SESSIONS_DIR = self.sessions_dir
        if hasattr(session_manager, 'CONSUMED_PATHS_FILE'):
            session_manager.CONSUMED_PATHS_FILE = self.sessions_dir / "consumed_path_uuids.json"

        os.environ["HRONIR_LIBRARY_DIR"] = str(self.library_path)

        # DataManager is managed by conftest.py for DuckDB tests.
        # We need to ensure its state is clean for each test.
        storage.data_manager.initialize_and_load(clear_existing_data=True)

        self.predecessor_ch_uuid_pos0 = _create_dummy_chapter(
            self.library_path, "predecessor_pos0_path_qual"
        )

    def tearDown(self):
        # Restore original module-level configurations
        if self.original_tm_transactions_dir and hasattr(transaction_manager, 'TRANSACTIONS_DIR'):
            transaction_manager.TRANSACTIONS_DIR = self.original_tm_transactions_dir
        if self.original_tm_head_file and hasattr(transaction_manager, 'HEAD_FILE'):
            transaction_manager.HEAD_FILE = self.original_tm_head_file
        if self.original_sm_sessions_dir and hasattr(session_manager, 'SESSIONS_DIR'):
            session_manager.SESSIONS_DIR = self.original_sm_sessions_dir
        if self.original_sm_consumed_file and hasattr(session_manager, 'CONSUMED_PATHS_FILE'):
            session_manager.CONSUMED_PATHS_FILE = self.original_sm_consumed_file

        # storage.UUID_NAMESPACE = self.original_storage_uuid_namespace # UUID_NAMESPACE is const

        if self.original_env_library_dir is None:
            if "HRONIR_LIBRARY_DIR" in os.environ: del os.environ["HRONIR_LIBRARY_DIR"]
        else:
            os.environ["HRONIR_LIBRARY_DIR"] = self.original_env_library_dir


    def _create_path_entry( # Renamed from _create_fork_entry
        self, position: int, prev_uuid_str: str | None, current_hrönir_uuid: str
    ) -> str:
        """Helper to create a path entry and return the path_uuid."""
        path_uuid_obj = storage.compute_narrative_path_uuid(
            position, prev_uuid_str if prev_uuid_str else "", current_hrönir_uuid
        )
        model_prev_uuid = uuid.UUID(prev_uuid_str) if prev_uuid_str and prev_uuid_str != "" else None
        path_model = PathModel(
            path_uuid=path_uuid_obj,
            position=position,
            prev_uuid=model_prev_uuid,
            uuid=uuid.UUID(current_hrönir_uuid),
            status="PENDING",
        )
        storage.data_manager.add_path(path_model)
        storage.data_manager.save_all_data()
        return str(path_uuid_obj)

    def test_pending_paths_cannot_start_session(self): # Renamed from test_sybil_resistance
        num_sybil_paths = 5 # Reduced for speed, original was 50
        sybil_path_uuids = []

        pos0_prev_hrönir_uuid = None # For root position
        pos0_canonical_hrönir_uuid = _create_dummy_chapter(self.library_path, "sybil_pos0_canon_pq")
        self._create_path_entry(0, pos0_prev_hrönir_uuid, pos0_canonical_hrönir_uuid)

        for i in range(num_sybil_paths):
            sybil_hrönir_uuid = _create_dummy_chapter(self.library_path, f"sybil_ch_pos1_pq_{i}")
            path_uuid = self._create_path_entry(
                position=1,
                prev_uuid_str=pos0_canonical_hrönir_uuid,
                current_hrönir_uuid=sybil_hrönir_uuid,
            )
            sybil_path_uuids.append(path_uuid)

        for path_uuid in sybil_path_uuids:
            path_data_obj = storage.data_manager.get_path_by_uuid(path_uuid)
            self.assertIsNotNone(path_data_obj, f"Path data for {path_uuid} should exist in DB.")
            self.assertEqual(
                path_data_obj.status, "PENDING", f"Sybil path {path_uuid} should be PENDING."
            )

            # Create a dummy canonical_path.json file for the session start command
            if not self.canonical_path_file.exists():
                self.canonical_path_file.write_text(json.dumps({"title": "Test", "path": {}}))


            result = self.runner.invoke(
                cli.app,
                [
                    "session", "start",
                    "--path-uuid", path_uuid,
                    "--canonical-path-file", str(self.canonical_path_file),
                ],
                catch_exceptions=False # To see full traceback for unexpected errors
            )
            self.assertNotEqual(
                result.exit_code, 0, f"session start should fail for PENDING path {path_uuid}. Output: {result.stdout}"
            )
            self.assertTrue(
                "not QUALIFIED" in result.stdout or "already been used" in result.stdout,
                f"Session start for PENDING path {path_uuid} did not produce expected error. Output: {result.stdout}"
            )

    def test_legitimate_promotion_and_mandate_issuance(self):
        pos0_hrönir_A = _create_dummy_chapter(self.library_path, "pos0_chA_promo_pq")
        fgood_hrönir = _create_dummy_chapter(self.library_path, "fgood_ch_pos1_pq")
        self._create_path_entry( # Create a path for pos0_hrönir_A to be a valid predecessor
            position=0, prev_uuid_str=None, current_hrönir_uuid=pos0_hrönir_A
        )

        fgood_path_uuid = self._create_path_entry(
            position=1, prev_uuid_str=pos0_hrönir_A, current_hrönir_uuid=fgood_hrönir
        )

        fgood_initial_obj = storage.data_manager.get_path_by_uuid(fgood_path_uuid)
        self.assertIsNotNone(fgood_initial_obj)
        self.assertEqual(fgood_initial_obj.status, "PENDING")

        dummy_session_id = str(uuid.uuid4())
        dummy_initiator_prev_hr_uuid = _create_dummy_chapter(self.library_path, "dummy_initiator_prev_hr_pq")
        dummy_initiator_curr_hr_uuid = _create_dummy_chapter(self.library_path, "dummy_initiator_curr_hr_pq")
        # The initiating path for the transaction doesn't need to be QUALIFIED itself for this test's purpose,
        # as we are testing the promotion of fgood_path_uuid through verdicts.
        # It just needs to be a valid path UUID.
        dummy_initiating_voter_path_uuid = self._create_path_entry(
            position=0,
            prev_uuid_str=dummy_initiator_prev_hr_uuid,
            current_hrönir_uuid=dummy_initiator_curr_hr_uuid
        )


        votes_to_qualify_fgood = []
        num_wins_for_elo_qualification = transaction_manager.ELO_WINS_FOR_QUALIFICATION # Use configured value

        for i in range(num_wins_for_elo_qualification):
            dummy_loser_hrönir = _create_dummy_chapter(self.library_path, f"dummy_loser_promo_pq_{i}")
            self._create_path_entry( # Ensure loser paths exist
                position=1, prev_uuid_str=pos0_hrönir_A, current_hrönir_uuid=dummy_loser_hrönir
            )
            votes_to_qualify_fgood.append({
                "position": 1,
                "winner_hrönir_uuid": fgood_hrönir,
                "loser_hrönir_uuid": dummy_loser_hrönir,
                "predecessor_hrönir_uuid": pos0_hrönir_A,
            })

        storage.data_manager.save_all_data()

        tx_result_data = transaction_manager.record_transaction(
            session_id=dummy_session_id,
            initiating_path_uuid=dummy_initiating_voter_path_uuid, # Changed from initiating_fork_uuid
            session_verdicts=votes_to_qualify_fgood,
        )
        self.assertIsNotNone(tx_result_data)
        self.assertIn("transaction_uuid", tx_result_data)

        # Check HEAD file if transaction_manager uses it
        if hasattr(transaction_manager, 'HEAD_FILE') and (self.transactions_dir / "HEAD").exists():
            self.assertEqual(_get_head_transaction_uuid(self.transactions_dir), tx_result_data["transaction_uuid"])

        fgood_final_obj = storage.data_manager.get_path_by_uuid(fgood_path_uuid)
        self.assertIsNotNone(fgood_final_obj)
        self.assertEqual(fgood_final_obj.status, "QUALIFIED")

        generated_mandate_id = fgood_final_obj.mandate_id
        self.assertIsNotNone(generated_mandate_id)
        try:
            uuid.UUID(str(generated_mandate_id))
            is_valid_uuid = True
        except ValueError:
            is_valid_uuid = False # pragma: no cover
        self.assertTrue(is_valid_uuid, f"Generated mandate_id '{generated_mandate_id}' is not a valid UUID.")

        promotions = tx_result_data.get("promotions_granted", [])
        self.assertIn(fgood_path_uuid, [str(p) for p in promotions])


if __name__ == "__main__": # pragma: no cover
    unittest.main()
