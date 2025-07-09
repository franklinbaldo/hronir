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

class TestTemporalCascade(unittest.TestCase):
    runner = CliRunner()
    base_dir = Path("temp_test_hronir_data_temporal_cascade") # Unique temp dir

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
            self.library_path, "predecessor_pos0_cascade_test"
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
            status=status,
        )
        storage.data_manager.add_path(path_model)
        storage.data_manager.save_all_data()
        return str(path_uuid_obj)

    def test_temporal_cascade_trigger(self):
        p0_ch_A = _create_dummy_chapter(self.library_path, "p0_cascade_A_tc")
        p0_ch_B = _create_dummy_chapter(self.library_path, "p0_cascade_B_tc")
        p0_path_A_uuid = self._create_path_entry(position=0, prev_uuid_str=None, current_hrönir_uuid=p0_ch_A)
        p0_path_B_uuid = self._create_path_entry(position=0, prev_uuid_str=None, current_hrönir_uuid=p0_ch_B)

        p1_ch_X = _create_dummy_chapter(self.library_path, "p1_cascade_X_tc")
        _ = _create_dummy_chapter(self.library_path, "p1_cascade_Y_tc") # p1_ch_Y
        p1_path_X_uuid = self._create_path_entry(position=1, prev_uuid_str=p0_ch_A, current_hrönir_uuid=p1_ch_X)
        # self._create_path_entry(position=1, prev_uuid_str=p0_ch_A, current_hrönir_uuid=p1_ch_Y) # Path for Y

        p1_ch_Z_from_B = _create_dummy_chapter(self.library_path, "p1_cascade_Z_from_B_tc")
        p1_path_Z_from_B_uuid = self._create_path_entry(position=1, prev_uuid_str=p0_ch_B, current_hrönir_uuid=p1_ch_Z_from_B)

        initial_canon_data = {
            "title": "Initial Canon for Cascade Test",
            "path": {
                "0": {"path_uuid": p0_path_A_uuid, "hrönir_uuid": p0_ch_A},
                "1": {"path_uuid": p1_path_X_uuid, "hrönir_uuid": p1_ch_X},
            },
        }
        self.canonical_path_file.write_text(json.dumps(initial_canon_data, indent=2))

        qualifying_path_pos = 2 # Path at pos 2, whose predecessor is at pos 1 (p1_ch_X)
        qf_hrönir = _create_dummy_chapter(self.library_path, "qf_cascade_ch_tc")

        qf_path_uuid = self._create_path_entry(
            position=qualifying_path_pos, prev_uuid_str=p1_ch_X, current_hrönir_uuid=qf_hrönir
        )

        # Manually qualify qf_path_uuid
        storage.data_manager.update_path_status(
            path_uuid=qf_path_uuid,
            status="QUALIFIED",
            mandate_id=str(uuid.uuid4()),
            set_mandate_explicitly=True
        )
        storage.data_manager.save_all_data()

        qf_data_qualified_obj = storage.data_manager.get_path_by_uuid(qf_path_uuid)
        self.assertIsNotNone(qf_data_qualified_obj)
        self.assertEqual(qf_data_qualified_obj.status, "QUALIFIED")

        start_res = self.runner.invoke(
            cli.app,
            ["session", "start", "--path-uuid", qf_path_uuid, "--canonical-path-file", str(self.canonical_path_file)],
            catch_exceptions=False
        )
        self.assertEqual(start_res.exit_code, 0, f"Session start for QF failed: {start_res.stdout}")
        session_id_for_cascade = json.loads(start_res.stdout)["session_id"]

        # Verdict: Make path B canonical at P0. Path A was previously canonical.
        verdicts_to_change_canon = { "0": p0_path_B_uuid } # Key is string position

        commit_res = self.runner.invoke(
            cli.app,
            [
                "session", "commit",
                "--session-id", session_id_for_cascade,
                "--verdicts", json.dumps(verdicts_to_change_canon),
                "--canonical-path-file", str(self.canonical_path_file),
            ],
            catch_exceptions=False
        )
        self.assertEqual(commit_res.exit_code, 0, f"Session commit failed: {commit_res.stdout}\nStderr: {commit_res.stderr}")

        final_canon_data = json.loads(self.canonical_path_file.read_text())

        # Check P0 update
        self.assertEqual(final_canon_data["path"]["0"]["path_uuid"], p0_path_B_uuid)
        self.assertEqual(final_canon_data["path"]["0"]["hrönir_uuid"], p0_ch_B)

        # Check P1 cascade: should now pick path Z (child of B)
        self.assertIn("1", final_canon_data["path"], "Position 1 should exist in canonical path after cascade")
        self.assertEqual(final_canon_data["path"]["1"]["path_uuid"], p1_path_Z_from_B_uuid)
        self.assertEqual(final_canon_data["path"]["1"]["hrönir_uuid"], p1_ch_Z_from_B)

if __name__ == "__main__": # pragma: no cover
    unittest.main()
