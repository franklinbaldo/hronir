import json
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


class TestProtocolV2(unittest.TestCase):
    runner = CliRunner()
    base_dir = Path("temp_test_hronir_data")

    @classmethod
    def setUpClass(cls):
        cls.base_dir.mkdir(parents=True, exist_ok=True)
        # Define specific paths for test data
        cls.library_path = cls.base_dir / "the_library"
        cls.forking_path_dir = cls.base_dir / "forking_path"
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
        self.original_sm_consumed_file = session_manager.CONSUMED_PATHS_FILE # Changed FORKS to PATHS
        self.original_storage_uuid_namespace = storage.UUID_NAMESPACE

        self.original_dm_fork_csv_dir = storage.data_manager.fork_csv_dir
        self.original_dm_ratings_csv_dir = storage.data_manager.ratings_csv_dir
        self.original_dm_transactions_json_dir = storage.data_manager.transactions_json_dir

        storage.data_manager.fork_csv_dir = self.forking_path_dir
        storage.data_manager.ratings_csv_dir = self.ratings_dir
        storage.data_manager.transactions_json_dir = self.transactions_dir

        transaction_manager.TRANSACTIONS_DIR = self.transactions_dir
        transaction_manager.HEAD_FILE = self.transactions_dir / "HEAD"
        session_manager.SESSIONS_DIR = self.sessions_dir
        session_manager.CONSUMED_FORKS_FILE = self.sessions_dir / "consumed_fork_uuids.json"

        storage.data_manager._initialized = False
        storage.data_manager.initialize_and_load(clear_existing_data=True)

        self.predecessor_ch_uuid_pos0 = _create_dummy_chapter(
            self.library_path, "predecessor_pos0_test"
        )

    def tearDown(self):
        transaction_manager.TRANSACTIONS_DIR = self.original_tm_transactions_dir
        transaction_manager.HEAD_FILE = self.original_tm_head_file
        session_manager.SESSIONS_DIR = self.original_sm_sessions_dir
        session_manager.CONSUMED_PATHS_FILE = self.original_sm_consumed_file # Changed FORKS to PATHS
        storage.UUID_NAMESPACE = self.original_storage_uuid_namespace

        storage.data_manager.fork_csv_dir = self.original_dm_fork_csv_dir
        storage.data_manager.ratings_csv_dir = self.original_dm_ratings_csv_dir
        storage.data_manager.transactions_json_dir = self.original_dm_transactions_json_dir

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
        return str(path_uuid_obj)

    def test_sybil_resistance(self):
        num_sybil_forks = 50
        sybil_path_uuids = []

        pos0_prev_hrönir_uuid = None
        pos0_canonical_hrönir_uuid = _create_dummy_chapter(self.library_path, "sybil_pos0_canon")
        self._create_fork_entry(0, pos0_prev_hrönir_uuid, pos0_canonical_hrönir_uuid)

        for i in range(num_sybil_forks):
            sybil_hrönir_uuid = _create_dummy_chapter(self.library_path, f"sybil_ch_pos1_{i}")
            path_uuid = self._create_fork_entry(
                position=1,
                prev_uuid_str=pos0_canonical_hrönir_uuid,
                current_hrönir_uuid=sybil_hrönir_uuid,
            )
            sybil_path_uuids.append(path_uuid)

        storage.data_manager.save_all_data_to_csvs()  # Ensure data is on disk for CLI

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
                    "--path-uuid", # Changed --fork-uuid to --path-uuid
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
            # CLI commands now print errors to stderr by default with Typer/Rich.
            # The output JSON is only for success cases.
            if result.stderr:
                self.assertTrue(
                    "does not have 'QUALIFIED' status" in result.stderr
                    or "already been used" in result.stderr
                )
            elif (
                result.stdout and result.stdout.strip()
            ):  # Check if stdout has non-whitespace content
                try:
                    output_json = json.loads(result.stdout)
                    self.assertIn("error", output_json, "Error key missing in JSON output")
                    self.assertIn("does not have 'QUALIFIED' status", output_json["error"])
                except json.JSONDecodeError:
                    self.fail(
                        f"Session start for PENDING path {path_uuid} produced non-JSON output: {result.stdout}"
                    )
            else:
                self.fail(
                    f"Session start for PENDING path {path_uuid} did not produce expected error output on stderr or JSON error on stdout."
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
        storage.data_manager.save_all_data_to_csvs()

        tx_result_data = transaction_manager.record_transaction(
            session_id=dummy_session_id,
            initiating_path_uuid=dummy_initiating_voter_path_uuid, # Ensure this is path_uuid
            session_verdicts=votes_to_qualify_fgood,
        )
        self.assertIsNotNone(tx_result_data)
        self.assertIn("transaction_uuid", tx_result_data)

        fgood_final_obj = storage.data_manager.get_path_by_uuid(fgood_path_uuid)
        self.assertIsNotNone(
            fgood_final_obj, "F_good path data should still exist in DB after transaction."
        )
        self.assertEqual(fgood_final_obj.status, "QUALIFIED", "F_good path should be QUALIFIED.")

        generated_mandate_id = fgood_final_obj.mandate_id
        self.assertIsNotNone(generated_mandate_id, "F_good should have a mandate_id.")
        self.assertTrue(len(str(generated_mandate_id)) > 0)

        import blake3

        expected_mandate_id_source = fgood_path_uuid + last_tx_hash_before_qualifying_tx
        expected_mandate_id = blake3.blake3(expected_mandate_id_source.encode("utf-8")).hexdigest()[
            :16
        ]

        self.assertEqual(
            str(generated_mandate_id),
            expected_mandate_id,
            "Generated mandate_id is not as expected.",
        )

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
        storage.data_manager.save_all_data_to_csvs()

        qualifying_tx_data = transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_path_uuid=ds_initiating_path_uuid, # Ensure this is path_uuid
            session_verdicts=votes_for_qualification,
        )
        self.assertIsNotNone(qualifying_tx_data)

        storage.data_manager.save_all_data_to_csvs()  # Save after TX before CLI

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
                "--fork-uuid",
                path_to_spend_uuid,
                "--forking-path-dir",
                str(self.forking_path_dir),
                "--ratings-dir",
                str(self.ratings_dir),
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertEqual(start_result.exit_code, 0, f"Session start failed: {start_result.stdout}")
        start_output = json.loads(start_result.stdout)
        session_id_spent = start_output["session_id"]

        self.assertEqual(session_manager.is_fork_consumed(path_to_spend_uuid), session_id_spent)

        session_data_for_commit = session_manager.get_session(session_id_spent)
        dossier_duels = session_data_for_commit.get("dossier", {}).get("duels", {})

        verdicts_for_commit = {}
        if "0" in dossier_duels:
            duel_at_0 = dossier_duels["0"]
            verdicts_for_commit["0"] = duel_at_0["path_A_uuid"]

        commit_result = self.runner.invoke(
            cli.app,
            [
                "session",
                "commit",
                "--session-id",
                session_id_spent,
                "--verdicts",
                json.dumps(verdicts_for_commit),
                "--forking-path-dir",
                str(self.forking_path_dir),
                "--ratings-dir",
                str(self.ratings_dir),
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertEqual(
            commit_result.exit_code, 0, f"Session commit failed: {commit_result.stdout}"
        )

        # CLI's session commit would have updated CSV files through its own DataManager instance.
        # The test's DataManager instance needs to reload to see these changes.
        storage.data_manager.initialize_and_load(clear_existing_data=True)

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
                    "--path-uuid", # Changed --fork-uuid to --path-uuid
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
        self.assertTrue(
            "does not have 'QUALIFIED' status" in second_start_result.stdout
            or "already been used to initiate a judgment session" in second_start_result.stdout,
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
        storage.data_manager.save_all_data_to_csvs()

        transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_path_uuid=tc_initiating_path_uuid, # Ensure this is path_uuid
            session_verdicts=votes_for_qf_qualification,
        )

        storage.data_manager.save_all_data_to_csvs()  # Save after TX, before CLI

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
                "--forking-path-dir",
                str(self.forking_path_dir),
                "--ratings-dir",
                str(self.ratings_dir),
                "--canonical-path-file",
                str(self.canonical_path_file),
            ],
        )
        self.assertEqual(
            commit_res.exit_code, 0, f"Session commit for cascade test failed: {commit_res.stdout}"
        )

        # CLI session commit updated CSVs and canonical_path.json. Reload DataManager for test assertions.
        storage.data_manager.initialize_and_load(clear_existing_data=True)

        final_canon_data = json.loads(self.canonical_path_file.read_text())

        self.assertEqual(final_canon_data["path"]["0"]["path_uuid"], p0_path_B_uuid)
        self.assertEqual(final_canon_data["path"]["0"]["hrönir_uuid"], p0_ch_B)

        self.assertIn("1", final_canon_data["path"], "Position 1 should exist in canonical path")
        self.assertEqual(final_canon_data["path"]["1"]["path_uuid"], p1_path_Z_from_B_uuid)
        self.assertEqual(final_canon_data["path"]["1"]["hrönir_uuid"], p1_ch_Z_from_B)


if __name__ == "__main__":
    unittest.main()
