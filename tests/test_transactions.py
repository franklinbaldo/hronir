import datetime
import os  # Added import
import uuid

import pytest

from hronir_encyclopedia import ratings, storage, transaction_manager
from hronir_encyclopedia.models import Path as PathModel
from hronir_encyclopedia.models import PathStatus

# More imports might be needed as tests are developed, e.g., for specific test data setup


@pytest.fixture(autouse=True)
def setup_and_teardown_test_db(tmp_path):
    """
    Fixture to set up a clean DuckDB for each test and tear it down.
    It also ensures DataManager uses this temporary DB.
    """
    test_db_path = tmp_path / "test_encyclopedia.duckdb"
    original_env_db_path = os.getenv("HRONIR_DUCKDB_PATH")
    original_dm_instance = storage.DataManager._instance

    os.environ["HRONIR_DUCKDB_PATH"] = str(test_db_path)
    storage.DataManager._instance = None  # Force re-creation of DataManager

    # Access the global storage.data_manager to initialize it with the new path
    # This instance will be used by the tests implicitly via module-level access
    # or explicitly if tests use storage.data_manager.
    # The DataManager() call itself will pick up HRONIR_DUCKDB_PATH.
    # The initialize_and_load ensures tables are created and data is clean.
    dm_for_test_setup = storage.DataManager()
    dm_for_test_setup.initialize_and_load(clear_existing_data=True)

    yield  # Test runs here

    # Teardown
    if hasattr(dm_for_test_setup, "conn") and dm_for_test_setup.conn:
        try:
            dm_for_test_setup.conn.close()
        except Exception:  # pragma: no cover (ignore errors on close if already closed)
            pass

    if original_env_db_path is None:
        if "HRONIR_DUCKDB_PATH" in os.environ:
            del os.environ["HRONIR_DUCKDB_PATH"]
    else:
        os.environ["HRONIR_DUCKDB_PATH"] = original_env_db_path

    storage.DataManager._instance = (
        original_dm_instance  # Restore original singleton instance state
    )
    # If original_dm_instance was None, next call to DataManager() will create a fresh default.
    # If it existed, it's restored. This is a bit fragile; ideally, tests shouldn't rely on
    # restoring global state perfectly but rather ensure their own setup.
    # Forcing a re-init of a default storage.data_manager might be safer if other non-test code expects it.
    if original_dm_instance is None:
        storage.data_manager = storage.DataManager()  # Re-init global to default
        storage.data_manager.initialize_if_needed()


class TestSimplifiedTransactionManager:
    def test_record_vote_transaction_basic(self, setup_and_teardown_test_db):
        """
        Test basic recording of a vote transaction and its storage in DuckDB.
        """
        dm = storage.data_manager  # Use the fixture-configured DataManager

        # 1. Setup: Create initial paths
        h0_uuid = storage.store_chapter_text("Hronir 0")  # Use storage.store_chapter_text

        h1a_uuid = storage.store_chapter_text("Hronir 1A")  # Use storage.store_chapter_text
        p1a_path_uuid_obj = storage.compute_narrative_path_uuid(1, h0_uuid, h1a_uuid)
        p1a_path = PathModel(
            path_uuid=p1a_path_uuid_obj,
            position=1,
            prev_uuid=uuid.UUID(h0_uuid),
            uuid=uuid.UUID(h1a_uuid),
            status=PathStatus.PENDING,
        )
        dm.add_path(p1a_path)

        h1b_uuid = storage.store_chapter_text("Hronir 1B")  # Use storage.store_chapter_text
        p1b_path_uuid_obj = storage.compute_narrative_path_uuid(1, h0_uuid, h1b_uuid)
        p1b_path = PathModel(
            path_uuid=p1b_path_uuid_obj,
            position=1,
            prev_uuid=uuid.UUID(h0_uuid),
            uuid=uuid.UUID(h1b_uuid),
            status=PathStatus.PENDING,
        )
        dm.add_path(p1b_path)

        # Create the initiating path (mandate path) and qualify it
        mandate_h_prev_uuid = storage.store_chapter_text(
            "Mandate H Prev"
        )  # Use storage.store_chapter_text
        mandate_h_curr_uuid = storage.store_chapter_text(
            "Mandate H Curr"
        )  # Use storage.store_chapter_text

        mandate_path_uuid_obj = storage.compute_narrative_path_uuid(
            0, mandate_h_prev_uuid, mandate_h_curr_uuid
        )
        mandate_path = PathModel(
            path_uuid=mandate_path_uuid_obj,
            position=0,
            prev_uuid=uuid.UUID(mandate_h_prev_uuid),
            uuid=uuid.UUID(mandate_h_curr_uuid),
            status=PathStatus.PENDING,
        )
        dm.add_path(mandate_path)
        dm.update_path_status(
            str(mandate_path.path_uuid),
            PathStatus.QUALIFIED.value,
            str(uuid.uuid4()),
            set_mandate_explicitly=True,
        )
        dm.save_all_data()

        # 2. Action: Record a transaction with a single vote
        submitted_votes = [
            {
                "position": 1,
                "winner_hrönir_uuid": h1a_uuid,
                "loser_hrönir_uuid": h1b_uuid,
                "predecessor_hrönir_uuid": h0_uuid,
            }
        ]

        tx_result = transaction_manager.record_transaction(
            initiating_path_uuid=str(mandate_path.path_uuid), submitted_votes=submitted_votes
        )

        # 3. Assertions
        assert "transaction_uuid" in tx_result
        tx_uuid_str = tx_result["transaction_uuid"]

        # Verify transaction is in DuckDB
        retrieved_tx = dm.get_transaction(tx_uuid_str)
        assert retrieved_tx is not None
        assert str(retrieved_tx.uuid) == tx_uuid_str
        assert retrieved_tx.content.initiating_path_uuid == mandate_path.path_uuid
        assert len(retrieved_tx.content.votes_processed) == 1

        vote_processed = retrieved_tx.content.votes_processed[0]
        assert vote_processed.position == 1
        assert str(vote_processed.winner_hrönir_uuid) == h1a_uuid
        assert str(vote_processed.loser_hrönir_uuid) == h1b_uuid
        assert str(vote_processed.predecessor_hrönir_uuid) == h0_uuid

        # Verify ratings were updated (basic check)
        # This requires ratings.get_elo_rating or similar to be implemented/callable
        # For now, just check if a vote was recorded for the position.
        votes_at_pos1 = dm.get_votes_by_position(1)
        assert len(votes_at_pos1) > 0
        recorded_db_vote = next(
            (v for v in votes_at_pos1 if v.winner == h1a_uuid and v.loser == h1b_uuid), None
        )
        assert recorded_db_vote is not None
        assert recorded_db_vote.voter == str(mandate_path.path_uuid)

    def test_record_transaction_qualification_promotion(self, setup_and_teardown_test_db):
        """
        Test that a transaction correctly processes votes leading to a path qualification.
        """
        dm = storage.data_manager

        # Setup paths
        h0_uuid = storage.store_chapter_text("H0 for Qual Test")  # Use storage.store_chapter_text

        path_to_qualify_h_uuid = storage.store_chapter_text(
            "Path to Qualify H"
        )  # Use storage.store_chapter_text
        path_to_qualify_uuid_obj = storage.compute_narrative_path_uuid(
            1, h0_uuid, path_to_qualify_h_uuid
        )
        path_to_qualify = PathModel(
            path_uuid=path_to_qualify_uuid_obj,
            position=1,
            prev_uuid=uuid.UUID(h0_uuid),
            uuid=uuid.UUID(path_to_qualify_h_uuid),
            status=PathStatus.PENDING,
        )
        dm.add_path(path_to_qualify)

        # Create mandate path
        mandate_h_prev_uuid = storage.store_chapter_text("MHP")  # Use storage.store_chapter_text
        mandate_h_curr_uuid = storage.store_chapter_text("MHC")  # Use storage.store_chapter_text
        mandate_path_uuid_obj = storage.compute_narrative_path_uuid(
            0, mandate_h_prev_uuid, mandate_h_curr_uuid
        )
        mandate_path = PathModel(
            path_uuid=mandate_path_uuid_obj,
            position=0,
            prev_uuid=uuid.UUID(mandate_h_prev_uuid),
            uuid=uuid.UUID(mandate_h_curr_uuid),
            status=PathStatus.QUALIFIED,
            mandate_id=str(uuid.uuid4()),
        )
        dm.add_path(mandate_path)
        dm.save_all_data()

        submitted_votes = []
        # Simulate enough wins for qualification (default is 4)
        # ratings.TEST_WINS_FOR_QUALIFICATION might be defined in ratings module
        try:
            wins_needed = ratings.TEST_WINS_FOR_QUALIFICATION
        except AttributeError:
            wins_needed = 4  # Default if not found

        for i in range(wins_needed):
            loser_h_uuid = storage.store_chapter_text(
                f"Loser H {i}"
            )  # Use storage.store_chapter_text
            loser_path_uuid_obj = storage.compute_narrative_path_uuid(1, h0_uuid, loser_h_uuid)
            loser_path = PathModel(
                path_uuid=loser_path_uuid_obj,
                position=1,
                prev_uuid=uuid.UUID(h0_uuid),
                uuid=uuid.UUID(loser_h_uuid),
                status=PathStatus.PENDING,
            )
            dm.add_path(loser_path)
            submitted_votes.append(
                {
                    "position": 1,
                    "winner_hrönir_uuid": path_to_qualify_h_uuid,
                    "loser_hrönir_uuid": loser_h_uuid,
                    "predecessor_hrönir_uuid": h0_uuid,
                }
            )
        dm.save_all_data()

        tx_result = transaction_manager.record_transaction(
            initiating_path_uuid=str(mandate_path.path_uuid), submitted_votes=submitted_votes
        )

        assert str(path_to_qualify.path_uuid) in tx_result["promotions_granted"]

        qualified_path_db = dm.get_path_by_uuid(str(path_to_qualify.path_uuid))
        assert qualified_path_db is not None
        assert qualified_path_db.status == PathStatus.QUALIFIED
        assert qualified_path_db.mandate_id is not None

        retrieved_tx = dm.get_transaction(tx_result["transaction_uuid"])
        assert retrieved_tx is not None
        assert any(
            promo_uuid == path_to_qualify.path_uuid
            for promo_uuid in retrieved_tx.content.promotions_granted
        )

    # Add more tests:
    # - Transaction with multiple votes across different positions
    # - Transaction that doesn't lead to promotions
    # - Error handling (e.g., invalid initiating_path_uuid, invalid vote structure) - though Pydantic handles some
    # - Idempotency if a transaction with the same UUID is recorded again (should be ignored due to ON CONFLICT)
    # - Correct calculation of oldest_voted_position
    # - What happens if initiating_path_uuid is not QUALIFIED or has no mandate? (This should be prevented before calling record_transaction)

    # Test for determinism of transaction UUID if that's important
    def test_transaction_uuid_determinism(self, setup_and_teardown_test_db):
        dm = storage.data_manager
        h0_uuid = storage.store_chapter_text("H0")
        h1a_uuid = storage.store_chapter_text("H1A")
        h1b_uuid = storage.store_chapter_text("H1B")
        mandate_h_prev_uuid = storage.store_chapter_text("MHP")
        mandate_h_curr_uuid = storage.store_chapter_text("MHC")
        mandate_path_uuid_obj = storage.compute_narrative_path_uuid(
            0, mandate_h_prev_uuid, mandate_h_curr_uuid
        )
        mandate_path = PathModel(
            path_uuid=mandate_path_uuid_obj,
            position=0,
            prev_uuid=uuid.UUID(mandate_h_prev_uuid),
            uuid=uuid.UUID(mandate_h_curr_uuid),
            status=PathStatus.QUALIFIED,
            mandate_id=str(uuid.uuid4()),
        )
        dm.add_path(mandate_path)
        dm.save_all_data()

        votes = [
            {
                "position": 1,
                "winner_hrönir_uuid": h1a_uuid,
                "loser_hrönir_uuid": h1b_uuid,
                "predecessor_hrönir_uuid": h0_uuid,
            }
        ]

        # Capture current time for precise comparison if needed, but UUID5 includes timestamp string
        # Forcing timestamp to be the same for two calls to check content hashing
        fixed_timestamp = datetime.datetime.now(datetime.timezone.utc)

        # Temporarily mock datetime.datetime.now for deterministic UUID generation
        class MockDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed_timestamp

        original_datetime = datetime.datetime
        datetime.datetime = MockDateTime  # type: ignore

        try:
            tx_result1 = transaction_manager.record_transaction(str(mandate_path.path_uuid), votes)
            # To truly test determinism, we'd need to reset state and call again with identical inputs,
            # including the timestamp. The current record_transaction uses datetime.now() internally.
            # The UUID5 is based on name + timestamp, so if timestamp changes, UUID changes.
            # The test here is more about ensuring the UUID is generated and stored.
            # For full determinism test of UUID5 itself, one would call uuid.uuid5 directly with same args.

            # Let's simulate the string that would be hashed for UUIDv5
            # This part is tricky because record_transaction itself calls datetime.now()
            # The UUID is generated inside record_transaction.
            # So, we rely on the fact that if all inputs *to the UUID5 call* are same, output is same.

            expected_uuid_str_part = f"{str(mandate_path.path_uuid)}-{fixed_timestamp.isoformat()}"
            expected_tx_uuid = str(
                uuid.uuid5(transaction_manager.UUID_NAMESPACE, expected_uuid_str_part)
            )

            assert tx_result1["transaction_uuid"] == expected_tx_uuid

        finally:
            datetime.datetime = original_datetime  # Restore

        # Note: This test becomes more robust if timestamp is an explicit input to record_transaction
        # or if the UUID generation part is refactored out for easier testing.
        # For now, it checks that the UUID is generated based on the expected deterministic components.
