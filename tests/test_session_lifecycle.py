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
    chapter_uuid = storage.store_chapter_text(text, base=library_path)
    return chapter_uuid

def _get_head_transaction_uuid(tx_dir: Path | None = None) -> str | None:
    # This helper might become obsolete if transaction_manager stops using file-based HEAD
    if tx_dir is None: # pragma: no cover
        tx_dir = transaction_manager.TRANSACTIONS_DIR

    head_file = tx_dir if tx_dir.name == "HEAD" else tx_dir / "HEAD"

    if not head_file.exists():
        return None
    return head_file.read_text().strip()


class TestSessionLifecycle(unittest.TestCase):
    runner = CliRunner()
    base_dir = Path("temp_test_hronir_data_session_lifecycle") # Unique temp dir

    @classmethod
    def setUpClass(cls):
        cls.base_dir.mkdir(parents=True, exist_ok=True)
        cls.library_path = cls.base_dir / "the_library"
        cls.transactions_dir = cls.base_dir / "data" / "transactions"
        cls.sessions_dir = cls.base_dir / "data" / "sessions"
        cls.canonical_path_file = cls.base_dir / "data" / "canonical_path.json"

        cls.library_path.mkdir(parents=True, exist_ok=True)
        cls.transactions_dir.parent.mkdir(parents=True, exist_ok=True)
        cls.transactions_dir.mkdir(parents=True, exist_ok=True)
        cls.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not (cls.transactions_dir / "HEAD").exists() and hasattr(transaction_manager, 'HEAD_FILE'):
             (cls.transactions_dir / "HEAD").write_text("")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base_dir, ignore_errors=True)

    def setUp(self):
        if self.transactions_dir.exists(): shutil.rmtree(self.transactions_dir)
        if self.sessions_dir.exists(): shutil.rmtree(self.sessions_dir)
        if self.canonical_path_file.exists(): self.canonical_path_file.unlink()

        self.transactions_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(transaction_manager, 'HEAD_FILE'):
            (self.transactions_dir / "HEAD").write_text("")

        self.original_tm_transactions_dir = getattr(transaction_manager, 'TRANSACTIONS_DIR', None)
        self.original_tm_head_file = getattr(transaction_manager, 'HEAD_FILE', None)
        self.original_sm_sessions_dir = getattr(session_manager, 'SESSIONS_DIR', None)
        self.original_sm_consumed_file = getattr(session_manager, 'CONSUMED_PATHS_FILE', None)
        self.original_env_library_dir = os.getenv("HRONIR_LIBRARY_DIR")

        if hasattr(transaction_manager, 'TRANSACTIONS_DIR'):
            transaction_manager.TRANSACTIONS_DIR = self.transactions_dir
        if hasattr(transaction_manager, 'HEAD_FILE'):
            transaction_manager.HEAD_FILE = self.transactions_dir / "HEAD"
        if hasattr(session_manager, 'SESSIONS_DIR'):
            session_manager.SESSIONS_DIR = self.sessions_dir
        if hasattr(session_manager, 'CONSUMED_PATHS_FILE'):
            session_manager.CONSUMED_PATHS_FILE = self.sessions_dir / "consumed_path_uuids.json"

        os.environ["HRONIR_LIBRARY_DIR"] = str(self.library_path)

        storage.data_manager.initialize_and_load(clear_existing_data=True)

        self.predecessor_ch_uuid_pos0 = _create_dummy_chapter(
            self.library_path, "predecessor_pos0_session_lc"
        )

    def tearDown(self):
        if self.original_tm_transactions_dir and hasattr(transaction_manager, 'TRANSACTIONS_DIR'):
            transaction_manager.TRANSACTIONS_DIR = self.original_tm_transactions_dir
        if self.original_tm_head_file and hasattr(transaction_manager, 'HEAD_FILE'):
            transaction_manager.HEAD_FILE = self.original_tm_head_file
        if self.original_sm_sessions_dir and hasattr(session_manager, 'SESSIONS_DIR'):
            session_manager.SESSIONS_DIR = self.original_sm_sessions_dir
        if self.original_sm_consumed_file and hasattr(session_manager, 'CONSUMED_PATHS_FILE'):
            session_manager.CONSUMED_PATHS_FILE = self.original_sm_consumed_file

        if self.original_env_library_dir is None:
            if "HRONIR_LIBRARY_DIR" in os.environ: del os.environ["HRONIR_LIBRARY_DIR"]
        else:
            os.environ["HRONIR_LIBRARY_DIR"] = self.original_env_library_dir

    def _create_path_entry(
        self, position: int, prev_uuid_str: str | None, current_hrönir_uuid: str, status: str = "PENDING"
    ) -> str:
        path_uuid_obj = storage.compute_narrative_path_uuid(
            position, prev_uuid_str if prev_uuid_str else "", current_hrönir_uuid
        )
        model_prev_uuid = uuid.UUID(prev_uuid_str) if prev_uuid_str and prev_uuid_str != "" else None
        path_model = PathModel(
            path_uuid=path_uuid_obj,
            position=position,
            prev_uuid=model_prev_uuid,
            uuid=uuid.UUID(current_hrönir_uuid),
            status=status, # Allow setting status directly for testing setup
        )
        storage.data_manager.add_path(path_model)
        storage.data_manager.save_all_data()
        return str(path_uuid_obj)

    def test_qualified_path_becomes_spent_after_session(self): # Renamed from test_mandate_double_spend_prevention
        pos0_hrönir_pred = _create_dummy_chapter(self.library_path, "pos0_chDS_pred_slc")
        self._create_path_entry(0, None, pos0_hrönir_pred) # Ensure predecessor path exists

        path_to_spend_hrönir = _create_dummy_chapter(self.library_path, "ch_to_spend_pos1_slc")

        path_to_spend_uuid = self._create_path_entry(
            position=1, prev_uuid_str=pos0_hrönir_pred, current_hrönir_uuid=path_to_spend_hrönir
        )

        # Manually qualify the path for the test, simulating it won enough duels
        storage.data_manager.update_path_status(
            path_uuid=path_to_spend_uuid,
            status="QUALIFIED",
            mandate_id=str(uuid.uuid4()), # Assign a dummy mandate ID
            set_mandate_explicitly=True
        )
        storage.data_manager.save_all_data()


        path_data_qualified_obj = storage.data_manager.get_path_by_uuid(path_to_spend_uuid)
        self.assertIsNotNone(path_data_qualified_obj)
        self.assertEqual(path_data_qualified_obj.status, "QUALIFIED")
        self.assertIsNotNone(path_data_qualified_obj.mandate_id)

        # Create dummy paths for dossier generation if session start needs them
        p0_duel_chA = _create_dummy_chapter(self.library_path, "p0_duelA_ds_slc")
        p0_duel_chB = _create_dummy_chapter(self.library_path, "p0_duelB_ds_slc")
        self._create_path_entry(position=0, prev_uuid_str=None, current_hrönir_uuid=p0_duel_chA)
        self._create_path_entry(position=0, prev_uuid_str=None, current_hrönir_uuid=p0_duel_chB)
        storage.data_manager.save_all_data()

        if not self.canonical_path_file.exists():
            self.canonical_path_file.write_text(json.dumps({"title": "Test Canonical Path", "path": {}}))

        start_result = self.runner.invoke(
            cli.app,
            ["session", "start", "--path-uuid", path_to_spend_uuid, "--canonical-path-file", str(self.canonical_path_file)],
            catch_exceptions=False
        )
        self.assertEqual(start_result.exit_code, 0, f"Session start failed: {start_result.stdout}")
        start_output = json.loads(start_result.stdout)
        session_id_spent = start_output["session_id"]

        self.assertTrue(session_manager.is_path_consumed(path_to_spend_uuid) == session_id_spent or path_data_qualified_obj.status == "ACTIVE_SESSION")


        verdicts_for_commit_str = "{}" # Empty verdicts, just to complete session

        commit_result = self.runner.invoke(
            cli.app,
            [
                "session", "commit",
                "--session-id", session_id_spent,
                "--verdicts", verdicts_for_commit_str,
                "--canonical-path-file", str(self.canonical_path_file),
            ],
            catch_exceptions=False
        )
        self.assertEqual(commit_result.exit_code, 0, f"Session commit failed: {commit_result.stdout}\nStderr: {commit_result.stderr}")

        path_data_spent_obj = storage.data_manager.get_path_by_uuid(path_to_spend_uuid)
        self.assertIsNotNone(path_data_spent_obj)
        self.assertEqual(path_data_spent_obj.status, "SPENT", "Path should be SPENT after session commit.")

        second_start_result = self.runner.invoke(
            cli.app,
            ["session", "start", "--path-uuid", path_to_spend_uuid, "--canonical-path-file", str(self.canonical_path_file)],
            catch_exceptions=False
        )
        self.assertNotEqual(second_start_result.exit_code, 0, "Second session start with SPENT path should fail.")
        self.assertTrue(
            "not QUALIFIED" in second_start_result.stdout or "already been used" in second_start_result.stdout,
            f"Second session start output unexpected: {second_start_result.stdout}"
        )

if __name__ == "__main__": # pragma: no cover
    unittest.main()
