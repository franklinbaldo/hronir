import datetime
import uuid
import warnings
from pathlib import Path
from typing import Any

import logging # Added
import time # Added
# import internetarchive as ia # For actual IA interaction, would be needed. Placeholder for now.

from .models import Transaction, TransactionContent
from .sharding import SnapshotManifest # Added

TRANSACTIONS_DIR = Path("data/transactions")
SNAPSHOTS_META_DIR = Path("data/snapshots_meta") # For storing manifest JSONs locally
HEAD_FILE = TRANSACTIONS_DIR / "HEAD" # This HEAD is for local transactions, not snapshot sequence
UUID_NAMESPACE = uuid.NAMESPACE_URL

# Placeholder for PGP signing function
def sign_manifest_pgp(manifest_data: str, key_id: str) -> str:
    """Placeholder for PGP signing. Returns dummy signature."""
    logging.warning(f"PGP signing requested for key {key_id}, but using dummy signature.")
    return f"dummy_pgp_signature_for_{hash(manifest_data)}"

# Placeholder for actual snapshot upload logic
def upload_sharded_snapshot_to_ia(manifest: SnapshotManifest, snapshot_dir: Path) -> str:
    """Placeholder for uploading sharded snapshot to Internet Archive."""
    logging.warning(f"Placeholder: Uploading snapshot for manifest (Merkle: {manifest.merkle_root}) from {snapshot_dir} to IA.")
    # In a real scenario, this would upload all files in manifest.shards and the manifest itself.
    # It would return an IA item identifier.
    return f"ia_dummy_item_{manifest.sequence or 'unknown_seq'}"


class ConflictError(Exception):
    """Custom exception for sequence conflicts."""
    pass


class ConflictDetection:
    """
    Handles optimistic locking based on sequence numbers for snapshots.
    Based on pivot_plan_v2.md.
    """
    def __init__(self, network_uuid: str, pgp_key_id: Optional[str] = None):
        self.network_uuid = network_uuid
        self.pgp_key_id = pgp_key_id
        SNAPSHOTS_META_DIR.mkdir(parents=True, exist_ok=True)

    def _get_latest_local_manifest(self) -> Optional[SnapshotManifest]:
        """Gets the latest SnapshotManifest stored locally, based on sequence number."""
        manifest_files = sorted(
            SNAPSHOTS_META_DIR.glob(f"{self.network_uuid}_seq_*.json"),
            key=lambda f: int(f.stem.split("_seq_")[-1]), # Sort by sequence number
            reverse=True
        )
        if manifest_files:
            try:
                return SnapshotManifest.from_json(manifest_files[0].read_text())
            except Exception as e:
                logging.error(f"Error loading local manifest {manifest_files[0]}: {e}")
                return None
        return None

    def _save_local_manifest(self, manifest: SnapshotManifest):
        """Saves a SnapshotManifest locally."""
        if manifest.sequence is None:
            raise ValueError("Manifest sequence number cannot be None for saving.")
        file_path = SNAPSHOTS_META_DIR / f"{self.network_uuid}_seq_{manifest.sequence}.json"
        file_path.write_text(manifest.to_json(indent=2))
        logging.info(f"Saved local manifest: {file_path.name}")


    def discover_latest_remote_snapshot_robust(self) -> Optional[SnapshotManifest]:
        """
        Discovers the latest snapshot manifest from the remote source (e.g., Internet Archive).
        Includes retry logic for IA indexing delay.
        This is a placeholder implementation.
        """
        logging.info(f"Discovering latest remote snapshot for network {self.network_uuid}...")
        # Placeholder: In a real system, this would query Internet Archive or other P2P discovery.
        # For now, let's simulate by checking if there's a local "remote" copy,
        # or assume no remote exists for the first push.

        # Simulate IA search with retries (conceptual)
        for attempt, delay in enumerate([0, 1, 2]): # Simulating a few retries
            if attempt > 0:
                logging.info(f"Simulating IA search retry #{attempt} after {delay}s delay...")
                # time.sleep(delay) # time.sleep() is problematic in some environments

            # Placeholder for ia.search logic from pivot_plan_v2.md
            # results = ia.search(
            #     f"collection:hronir-network AND network_uuid:{self.network_uuid}",
            #     sort="created_at desc", # This should ideally be sequence number
            #     timeout=10
            # )
            # if results:
            #    latest_item = results[0]
            #    # Download manifest from item, parse it
            #    # manifest_content = download_manifest_from_ia(latest_item)
            #    # return SnapshotManifest.from_json(manifest_content)
            #    pass

            # Simplified placeholder: try to load the highest sequence local manifest
            # In a real scenario, this would be fetching from a remote like IA.
            # For this test, we assume the "remote" is reflected by the latest local one.
            # This part needs to be adapted for actual remote fetching.

            # To make this testable without actual IA, we'll rely on local "remote" state.
            # If we want to simulate a remote state different from local, we'd need another mechanism.
            # For now, this will behave like there's no *other* remote if no local snapshots exist.

            # Let's assume for now it returns the highest local one as if it was fetched from remote.
            # This is not a true remote discovery but helps test sequence logic.
            # A real implementation would use 'internetarchive' library or a custom API client.

            # To properly simulate, we'd need a mock IA or a way to inject remote manifests.
            # For now, let's assume it might find a local representation of a remote manifest.
            # This is highly simplified.

            # If we are to simulate a "real" remote, we need a way to store/fetch these.
            # For this step, let's assume the local highest sequence is the "remote" for now.
            # This is okay for testing the sequence increment logic.

            # A more robust placeholder:
            # Try to find a file that represents the "remote" head.
            # This could be a specific file, or we could query a mock service.
            # For now, returning the latest local one to allow sequence increment.
            latest_local = self._get_latest_local_manifest()
            if latest_local:
                logging.info(f"Placeholder discovery: found local manifest seq {latest_local.sequence} as 'remote'.")
                return latest_local

            if attempt == 0 and delay == 0: # First try, no remote found yet
                logging.info("Placeholder discovery: No remote snapshot found on first attempt.")
                # continue # In real scenario, continue to retry

        logging.info("Placeholder discovery: No remote snapshot found after all attempts.")
        return None # No remote snapshot found

    def push_with_locking(self, local_snapshot_manifest: SnapshotManifest, snapshot_dir: Path) -> str:
        """
        Prepares and 'pushes' a local snapshot manifest after checking for sequence conflicts.
        This involves assigning a sequence number, (placeholder) PGP signing,
        and (placeholder) uploading the snapshot.
        Returns the IA item identifier or an error message.
        """
        if not local_snapshot_manifest.network_uuid:
            local_snapshot_manifest.network_uuid = self.network_uuid
        elif local_snapshot_manifest.network_uuid != self.network_uuid:
            raise ValueError("Manifest network_uuid does not match ConflictDetection instance's network_uuid.")

        latest_remote_manifest = self.discover_latest_remote_snapshot_robust()

        expected_prev_sequence = -1 # For the very first snapshot
        if latest_remote_manifest and latest_remote_manifest.sequence is not None:
            expected_prev_sequence = latest_remote_manifest.sequence

        # Assign prev_sequence to the local manifest for validation.
        # If this is the first snapshot, prev_sequence could be 0 or a special marker.
        # Let's assume local_snapshot_manifest.prev_sequence is set by the caller
        # to what it *thinks* the last sequence was.
        # If not set, we assume it's trying to be the next one.
        if local_snapshot_manifest.prev_sequence is None:
             local_snapshot_manifest.prev_sequence = expected_prev_sequence

        if local_snapshot_manifest.prev_sequence != expected_prev_sequence:
            raise ConflictError(
                f"Sequence conflict detected for network {self.network_uuid}!\n"
                f"Local manifest's prev_sequence: {local_snapshot_manifest.prev_sequence}\n"
                f"Expected prev_sequence (latest remote sequence): {expected_prev_sequence}\n"
                f"Someone else may have pushed sequence {expected_prev_sequence + 1} first."
            )

        # Assign the new sequence number
        local_snapshot_manifest.sequence = expected_prev_sequence + 1
        logging.info(f"Assigned new sequence: {local_snapshot_manifest.sequence} for network {self.network_uuid}")

        # (Placeholder) Sign manifest with PGP
        if self.pgp_key_id:
            # In a real scenario, you'd serialize the manifest parts to be signed consistently.
            # For simplicity, using its JSON representation.
            manifest_json_for_signing = local_snapshot_manifest.to_json()
            local_snapshot_manifest.pgp_signature = sign_manifest_pgp(manifest_json_for_signing, self.pgp_key_id)
            logging.info(f"Manifest signed with PGP key ID {self.pgp_key_id} (dummy signature).")
        else:
            logging.warning("No PGP key ID provided. Manifest will not be PGP signed.")

        # (Placeholder) Upload sharded snapshot and manifest to Internet Archive
        # The actual upload logic would involve using the 'internetarchive' library
        # and uploading each file in local_snapshot_manifest.shards plus the manifest itself.
        ia_item_id = upload_sharded_snapshot_to_ia(local_snapshot_manifest, snapshot_dir)
        logging.info(f"Snapshot (sequence {local_snapshot_manifest.sequence}) uploaded to IA (placeholder). Item ID: {ia_item_id}")

        # Save this successfully pushed manifest locally as the new latest
        self._save_local_manifest(local_snapshot_manifest)

        return ia_item_id


# The existing record_transaction function is mostly for local session commits.
# The new Pivot Plan v2.0 push logic is encapsulated above.
# We might need a higher-level function in cli.py or elsewhere to:
# 1. Create a snapshot (DataManager.create_snapshot -> ShardingManager)
# 2. Then, pass this manifest to ConflictDetection.push_with_locking

UUID_NAMESPACE = uuid.NAMESPACE_URL # Already defined below, keep one


def _ensure_transactions_dir():
    TRANSACTIONS_DIR.mkdir(parents=True, exist_ok=True)


def record_transaction(
    session_id: str,
    initiating_path_uuid: str | None = None,
    session_verdicts: list[dict[str, Any]] | None = None,
    forking_path_dir: Path | None = None,  # These are not used by this TM
    ratings_dir: Path | None = None,  # These are not used by this TM
    **kwargs,
) -> dict[str, Any]:
    """
    Records a transaction, processes its verdicts to update ratings and path statuses,
    and saves the transaction data.
    """
    if initiating_path_uuid is None and "initiating_fork_uuid" in kwargs:
        warnings.warn(
            "'initiating_fork_uuid' is deprecated; use 'initiating_path_uuid'",
            DeprecationWarning,
            stacklevel=2,
        )
        initiating_path_uuid = kwargs.pop("initiating_fork_uuid")

    if initiating_path_uuid is None:
        raise TypeError("record_transaction() missing required argument 'initiating_path_uuid'")

    if kwargs:
        unexpected = ", ".join(kwargs.keys())
        raise TypeError(f"record_transaction() got unexpected keyword argument(s): {unexpected}")

    if session_verdicts is None:
        raise TypeError("record_transaction() missing required argument 'session_verdicts'")

    _ensure_transactions_dir()

    timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
    # prev_tx_uuid = HEAD_FILE.read_text().strip() if HEAD_FILE.exists() else None # Not used by current model
    prev_tx_uuid = None  # Simplified: prev_uuid is optional in Transaction model

    # Process verdicts to update ratings and check for qualifications
    # This part needs to align with how ratings and qualifications are actually handled.
    # The current version of this function in the codebase seems to do this *after*
    # creating the transaction_data dictionary.
    # For Pydantic validation to pass for Transaction model, 'content' must be structured correctly.

    # --- Logic for processing votes and qualifications (adapted from existing code) ---
    import pandas as pd

    from . import ratings, storage  # Local import for clarity

    dm = storage.DataManager()  # This will use paths set by fixture or defaults relative to CWD
    if not dm._initialized:  # Ensure DataManager is loaded if not already by the test fixture
        dm.initialize_and_load()

    promotions_granted_uuids = []  # Store path_uuids of promoted paths
    oldest_voted_position = float("inf")
    affected_contexts = set()

    processed_verdicts_for_tx_content = []

    for verdict in session_verdicts:
        pos = verdict["position"]
        winner_hrönir_uuid = verdict["winner_hrönir_uuid"]
        loser_hrönir_uuid = verdict["loser_hrönir_uuid"]
        predecessor_hrönir_uuid = verdict.get("predecessor_hrönir_uuid")

        ratings.record_vote(
            position=pos,
            voter=initiating_path_uuid,
            winner=winner_hrönir_uuid,
            loser=loser_hrönir_uuid,
        )
        if pos < oldest_voted_position:
            oldest_voted_position = pos

        affected_contexts.add((pos, predecessor_hrönir_uuid))

        # For TransactionContent.verdicts_processed
        processed_verdicts_for_tx_content.append(
            {
                "position": pos,
                "winner_hrönir_uuid": winner_hrönir_uuid,
                "loser_hrönir_uuid": loser_hrönir_uuid,
                "predecessor_hrönir_uuid": predecessor_hrönir_uuid,
            }
        )

    for pos, pred_uuid_str in affected_contexts:
        current_rankings_df = ratings.get_ranking(pos, pred_uuid_str)

        all_paths_in_context_models = []
        for p_model in dm.get_all_paths():  # Use get_all_paths then filter
            if p_model.position == pos:
                p_model_prev_uuid_str = str(p_model.prev_uuid) if p_model.prev_uuid else None
                # Handle case where pred_uuid_str is None for position 0
                if pred_uuid_str is None and (
                    p_model_prev_uuid_str is None or p_model_prev_uuid_str == ""
                ):
                    all_paths_in_context_models.append(p_model)
                elif p_model_prev_uuid_str == pred_uuid_str:
                    all_paths_in_context_models.append(p_model)

        if not all_paths_in_context_models:
            continue

        all_paths_in_context_df = pd.DataFrame(
            [p.model_dump() for p in all_paths_in_context_models]
        )

        for path_model_to_check in all_paths_in_context_models:
            if path_model_to_check.status == "PENDING":
                is_qualified = ratings.check_path_qualification(
                    path_uuid=str(path_model_to_check.path_uuid),
                    ratings_df=current_rankings_df,
                    all_paths_in_position_df=all_paths_in_context_df,
                )
                if is_qualified:
                    new_mandate_id = uuid.uuid4()  # mandate_id is UUID
                    dm.update_path_status(
                        path_uuid=str(path_model_to_check.path_uuid),
                        status="QUALIFIED",
                        mandate_id=str(new_mandate_id),  # Pass as string if model expects string
                        set_mandate_explicitly=True,
                    )
                    promotions_granted_uuids.append(
                        path_model_to_check.path_uuid
                    )  # Store UUID object

    # Create transaction content for the model
    transaction_content_data = TransactionContent(
        session_id=uuid.UUID(session_id),  # Ensure session_id is UUID object
        initiating_path_uuid=uuid.UUID(initiating_path_uuid),  # Ensure this is UUIDv5
        verdicts_processed=processed_verdicts_for_tx_content,
        promotions_granted=promotions_granted_uuids,
    )

    # Generate transaction UUID based on content to ensure determinism if needed, or just random for now
    # For now, using session_id and timestamp as in original code
    transaction_uuid_obj = uuid.uuid5(UUID_NAMESPACE, f"{session_id}-{timestamp_dt.isoformat()}")

    transaction_model_data = Transaction(
        uuid=transaction_uuid_obj,
        timestamp=timestamp_dt,
        prev_uuid=uuid.UUID(prev_tx_uuid) if prev_tx_uuid else None,
        content=transaction_content_data,
    )

    # Save transaction to file (using model_dump_json for Pydantic model)
    transaction_file = TRANSACTIONS_DIR / f"{str(transaction_uuid_obj)}.json"
    with open(transaction_file, "w") as f:
        f.write(transaction_model_data.model_dump_json(indent=2))

    # Update HEAD to point to this new transaction
    HEAD_FILE.write_text(str(transaction_uuid_obj))

    dm.save_all_data_to_csvs()

    final_oldest_voted_position = (
        int(oldest_voted_position) if oldest_voted_position != float("inf") else -1
    )

    return {
        "transaction_uuid": str(transaction_uuid_obj),
        "promotions_granted": [
            str(p_uuid) for p_uuid in promotions_granted_uuids
        ],  # Return strings
        "new_qualified_forks": [str(p_uuid) for p_uuid in promotions_granted_uuids],  # Consistency
        "status": "completed",  # This status is for the return dict, not part of Transaction model
        "oldest_voted_position": final_oldest_voted_position,
    }
