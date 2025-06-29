# Manual Testing Scenarios for Conflict Resolution (Optimistic Locking)

This document outlines manual test cases for verifying the conflict resolution mechanism (optimistic locking with sequence numbers) as part of the Pivot Plan v2.0.

**Prerequisites:**
- Two separate local environments (User A, User B) capable of running `hronir` CLI commands.
- Each environment should be configured with its own local data directory but pointing to the SAME `HRONIR_NETWORK_UUID`.
- `HRONIR_PGP_KEY_ID` should be set for both users if PGP signing is enforced.
- A shared "remote" state needs to be simulated. Since actual IA upload is placeholder, the `data/snapshots_meta/` directory (where local manifests are saved by `ConflictDetection`) can act as a proxy for the "remote" state for these manual tests. One user's push will update this, and the other user's discovery will read from it.

**Key CLI Commands Involved:**
- `hronir sync`: To pull the latest "remote" state.
- `hronir push`: To attempt to publish local changes.
- `uv run hronir store ...` & `uv run hronir path ...`: To make local changes to the database content (indirectly, by adding paths/hrönirs that modify the underlying DuckDB). For simplicity, we can assume a command like `hronir make-change` that modifies the DB content slightly for testing.

---

## Test Scenarios

### Scenario 1: Simple Conflict - User B pushes stale state

**Objective:** Verify that User B's push is rejected if User A has pushed a newer version.

**Steps:**

1.  **Initial State (Both Users):**
    *   User A: `hronir sync` (Ensures local state is at sequence `N` or starts fresh at seq -1 if no remote).
    *   User B: `hronir sync` (Ensures local state is also at sequence `N` or seq -1).
    *   Verify that `data/snapshots_meta/{NETWORK_UUID}_seq_N.json` (or no file if first push) is consistent for both if they were to discover.

2.  **User A - Makes a change and pushes:**
    *   User A: Make a local data change (e.g., `uv run hronir store some_new_chapter_A.md`).
    *   User A: `hronir push`
    *   **Expected Outcome (User A):** Push succeeds. A new manifest `data/snapshots_meta/{NETWORK_UUID}_seq_{N+1}.json` is created. Output indicates successful push with sequence `N+1`.

3.  **User B - Attempts to push without syncing (stale state):**
    *   User B: Make a local data change (e.g., `uv run hronir store some_new_chapter_B.md`). This change is based on sequence `N`.
    *   User B: `hronir push`
    *   **Expected Outcome (User B):** Push fails.
        *   Error message similar to: "Sequence conflict detected! Local manifest's prev_sequence: N. Expected prev_sequence (latest remote sequence): N+1. Someone else may have pushed sequence N+1 first."
        *   Recommendation to run `hronir sync` should be displayed.
        *   No new manifest file for User B's attempted sequence should be saved in `data/snapshots_meta/`.

---

### Scenario 2: Conflict Resolved - User B syncs, then pushes

**Objective:** Verify that User B can resolve a conflict by syncing, (optionally merging/replaying changes), and then successfully pushing.

**Steps:**

1.  **Initial State:** User A has successfully pushed sequence `N+1`. User B has local changes based on sequence `N` and their previous push attempt failed (as per Scenario 1).

2.  **User B - Syncs to get latest remote state:**
    *   User B: `hronir sync`
    *   **Expected Outcome (User B):**
        *   Sync process discovers and downloads snapshot for sequence `N+1`.
        *   Local database for User B is updated to reflect state from sequence `N+1`.
        *   User B's local changes (made on top of seq `N`) are either overwritten or User B is prompted to re-apply/merge them (actual merge logic is TBD, for this test, assume overwrite or manual re-application is needed).
        *   Output indicates successful sync to sequence `N+1`.

3.  **User B - Makes new changes (or re-applies old ones) and pushes:**
    *   User B: Make new local data changes (or re-apply changes previously attempted) on top of the synced sequence `N+1`.
    *   User B: `hronir push`
    *   **Expected Outcome (User B):** Push succeeds.
        *   A new manifest `data/snapshots_meta/{NETWORK_UUID}_seq_{N+2}.json` is created.
        *   Output indicates successful push with sequence `N+2`.

---

### Scenario 3: No Conflict - Sequential Pushes

**Objective:** Verify that sequential pushes from different users (with syncs in between) work correctly.

**Steps:**

1.  **Initial State (Both Users):**
    *   User A: `hronir sync`
    *   User B: `hronir sync` (Both at sequence `N` or fresh).

2.  **User A - Pushes:**
    *   User A: Make local change.
    *   User A: `hronir push`
    *   **Expected Outcome (User A):** Success (sequence `N+1`).

3.  **User B - Syncs and Pushes:**
    *   User B: `hronir sync` (Gets sequence `N+1`).
    *   User B: Make local change.
    *   User B: `hronir push`
    *   **Expected Outcome (User B):** Success (sequence `N+2`).

4.  **User A - Syncs and Pushes:**
    *   User A: `hronir sync` (Gets sequence `N+2`).
    *   User A: Make local change.
    *   User A: `hronir push`
    *   **Expected Outcome (User A):** Success (sequence `N+3`).

---

### Scenario 4: Force Push (Conceptual - if implemented)

**Objective:** Understand the behavior of `--force` push (Note: actual force logic in `ConflictDetection` is not deeply implemented, this tests the CLI flag and potential bypass).

**Steps:**

1.  **Initial State:** User A has pushed sequence `N+1`. User B has local changes based on sequence `N`.

2.  **User B - Attempts force push:**
    *   User B: `hronir push --force`
    *   **Expected Outcome (User B):**
        *   If force push bypasses sequence check: Push succeeds. A new manifest for sequence `N+1` (or `N+2` if it increments from local `prev_sequence`) is created, potentially overwriting or orphaning User A's sequence `N+1` in the "remote" view if sequence numbers are reused or if discovery always picks the newest timestamp.
        *   The exact behavior depends on how `--force` is implemented in `ConflictDetection.push_with_locking`. The current placeholder doesn't use `--force`.
        *   A clear warning about data loss or creating a divergent state should appear.
        *   **Note:** This scenario is highly dependent on the `--force` implementation details. The primary goal of the test is to observe if the CLI passes the flag and if any specific behavior related to forcing is noted by the system.

---

**General Verification Points for All Scenarios:**

-   Check `stdout` and `stderr` for expected messages (success, conflict errors, warnings).
-   Inspect the `data/snapshots_meta/` directory to verify correct creation and naming of manifest files (e.g., `{NETWORK_UUID}_seq_{sequence_number}.json`).
-   If possible, inspect the contents of the generated `SnapshotManifest` JSON files to verify `sequence`, `prev_sequence`, `pgp_signature` (even if dummy), and `merkle_root` fields are populated as expected.
-   After a `hronir sync`, verify that the local database (e.g., by querying counts or specific data in `encyclopedia.duckdb`) reflects the state of the synced snapshot.

---

**Notes on Simulating "Remote":**

-   The `ConflictDetection.discover_latest_remote_snapshot_robust()` currently uses `_get_latest_local_manifest()` as a placeholder. This means the "remote" state is effectively the highest sequence manifest found in the local `data/snapshots_meta/` directory for the given `NETWORK_UUID`.
-   To simulate two users, ensure they are operating in separate working directories but configure their `hronir` commands (or environment variables) such_that `ConflictDetection` reads/writes manifest metadata to a *shared* `data/snapshots_meta/` path if you want them to see each other's pushes as "remote". Alternatively, manually copy the relevant `_seq_X.json` file from User A's meta dir to User B's meta dir before User B does a push to simulate User B "seeing" User A's push.

This setup allows testing the sequence number conflict logic effectively even before full IA integration for discovery.
