# HRONIR TODO - Post Simplification & Session Removal

## ✅ COMPLETED ITEMS (from original TODO & recent work)

- **DONE**: `hronir_encyclopedia/storage_old.py` deleted (was not present).
- **DONE**: `hronir_encyclopedia/cli.py` split into command modules:
    - `commands/store.py` (existing, verified)
    - `commands/path.py` (existing, verified)
    - `commands/query.py` (created)
    - `commands/admin.py` (created)
    - `commands/snapshot.py` (created)
    - `commands/session.py` (created then deleted as sessions were removed)
- **DONE**: `cli_utils.py` created and specific CLI utilities moved (`git_remove_deleted_files`).
- **DONE**: `tests/test_system_dynamics.py` - File not found, assumed already refactored or tests reorganized.
- **DONE**: `tests/test_protocol_v2.py` - File not found, assumed already refactored or tests reorganized.
- **DONE**: `SIMPLIFY: hronir_encyclopedia/transaction_manager.py`:
    - PGP, Merkle trees, sharding, conflict detection, optimistic locking, IA upload automation confirmed removed.
    - Refactored to handle vote transactions instead of session commits.
    - Integrated with DuckDB for transaction storage (removed JSON file ledger and HEAD file).
    - Models (`TransactionContent`) updated.
    - `duckdb_storage.py` updated with new `transactions` table schema and access methods.
- **DONE**: Session-related files deleted:
    - `hronir_encyclopedia/session_manager.py`
    - `tests/test_session_lifecycle.py`
    - `tests/test_sessions.py`
    - `tests/test_sessions_and_cascade.py` (fully removed as heavily session-dependent)
    - `tests/test_temporal_cascade.py` (fully removed as heavily session-dependent)
- **DONE**: Implemented initial new voting mechanism:
    - `commands/vote.py` with `submit-votes` command.
    - `PathModel` and `paths` table in DB updated with `is_canonical` flag.
    - `canon.py` functions (`get_canonical_path_from_db`, `get_canonical_hronir_uuid_for_position`, `run_temporal_cascade`) refactored to be DB-centric.
- **DONE**: Documentation (`README.md`, `BUSINESS_RULES.md`, `CLAUDE.md`) updated to reflect removal of sessions and introduction of new voting mechanism.

## 🎯 NEW/REMAINING ACTION ITEMS

### Core Protocol & Voting Mechanism Refinements
- [ ] **Refactor `canon.py` `run_temporal_cascade` (and its callers):**
    - Ensure `get_canonical_hronir_uuid_for_position` (used by `run_temporal_cascade` to find predecessor for cascade start if `start_position > 0`, and also by `query get-duel`) correctly reads `is_canonical` flags from DB to provide a stable context. Currently, `get_canonical_path_from_db` (which it calls) derives from ratings, which might be circular if `run_temporal_cascade` is meant to *set* those flags based on a fixed predecessor determined by prior *canonical* state.
    - Remove reliance on `legacy_canonical_path_file` parameter in `commands/vote.py` when calling `run_temporal_cascade`. The cascade should purely use DB state.
- [ ] **Review `PathStatus.SPENT` for Mandates:**
    - Confirm if the current single-submission consumption of a mandate (QUALIFIED -> SPENT) is sufficient for the `sqrt(N)` voting rule.
    - If `sqrt(N)` votes can be submitted across multiple `vote submit` calls for a single mandate, then `PathModel` needs a vote counter (e.g., `remaining_votes`), and `update_path_status` logic needs adjustment. (Current implementation: one `vote submit` uses the whole mandate and marks path `SPENT`).
- [ ] **Implement `canon.get_canonical_hronir_uuid_for_position` fully based on `is_canonical` flags:**
    - This function should reliably return the hrönir UUID of the path marked as `is_canonical=True` at the given `position - 1` to serve as the correct predecessor context for `query get-duel` and potentially for the start of `run_temporal_cascade`.

### Testing
- [ ] **Write comprehensive tests for the new voting mechanism:**
    - Test `hronir vote submit` command:
        - Valid and invalid mandate usage (path not QUALIFIED, path already SPENT).
        - Enforcement of `sqrt(N)` vote limit.
        - Malformed/invalid `--votes-json` input (structure, missing fields, invalid UUIDs).
        - Correct transaction recording in DuckDB.
        - Correct update of mandate path status to `SPENT`.
        - Verification that Temporal Cascade is triggered and correctly updates `is_canonical` flags.
    - Test `hronir query get-duel` command:
        - Correct duel presentation for various positions using DB-derived canonical predecessors.
        - Behavior when no duels are available or no canonical predecessor exists.
    - Test `canon.py` functions directly:
        - `run_temporal_cascade` with various vote scenarios and their impact on `is_canonical` flags in DB.
        - `get_canonical_path_from_db` (deriving from ratings).
        - `get_canonical_hronir_uuid_for_position` (deriving from `is_canonical` flags in DB).
- [ ] **Refactor/Rewrite `tests/test_e2e_full_workflow.py`:**
    - Adapt to the new voting mechanism for a true end-to-end test: from hrönir creation, path creation, path qualification, vote submission, to canon update.
- [ ] **Review and update `tests/test_transactions.py`:** Add more scenarios for vote transaction processing if current tests are insufficient (e.g., transaction with multiple votes, transaction that doesn't lead to promotions).
- [ ] **Review `tests/test_canonical_dynamics.py` (currently skipped):** Determine its relevance to the new DB-centric canonical system and either update or remove it.

### Code Quality & Minor Refactoring
- [ ] **Review `storage.py` `clean_invalid_data`:** The `hronir admin clean` command notes that this function returns issues, not file paths for git removal. If file system artifact cleaning is still desired (e.g., for `the_library`), this needs addressing. (Lower priority given DuckDB focus).
- [ ] **Address `E402` errors in `test_agents.py`:** If possible without breaking its standalone script nature, or document why they are acceptable if intentionally structured for direct execution.

### Documentation
- [x] `README.md` updated.
- [x] `BUSINESS_RULES.md` updated.
- [x] `CLAUDE.md` updated.
- [x] `TODO.md` updated (this file).

---

*This literary protocol should be elegant and simple, not a distributed systems nightmare!* (Still true!)