# Hrönir Encyclopedia: Ledger-Based Voting Protocol (v2.1)

This document outlines the revised voting and mandate protocol for the Hrönir Encyclopedia, transitioning from a session-based system with path statuses to an atomic, ledger-driven approach.

## Core Concepts

1.  **Voting Token (`path_uuid`)**:
    *   The unique identifier of a narrative path (`path_uuid`) serves as the **voting token**.
    *   `path_uuid`s are UUIDv5, deterministically generated based on `(position, predecessor_hrönir_uuid, current_hrönir_uuid)`.
    *   A new, validly created path automatically grants its `path_uuid` as a potential voting token.
    *   **Validity Check**: For a `path_uuid` to be a valid voting token, the hrönirs it references (its own content hrönir and its predecessor, if any) must exist in `the_library/`. This check is primarily done during path creation.

2.  **Voting Power**:
    *   Each `path_uuid` (voting token) possesses a certain amount of "voting power," defined as the number of distinct positional duels it can cast a vote on.
    *   The voting power is calculated as `ceil(sqrt(N))`, where `N` is the `position` of the path corresponding to the `voting_token_path_uuid`.
        *   Position 0: `ceil(sqrt(0)) = 0` votes. (Paths at position 0 cannot cast votes).
        *   Position 1: `ceil(sqrt(1)) = 1` vote.
        *   Position 2: `ceil(sqrt(2)) = 2` votes.
        *   Position 3: `ceil(sqrt(3)) = 2` votes.
        *   Position 4: `ceil(sqrt(4)) = 2` votes.
        *   And so on.
    *   If a path has 0 voting power, it cannot be used as a `--voting-token` in the `cast-vote` command.

3.  **One-Shot Token Consumption**:
    *   A `voting_token_path_uuid` can be used to cast votes in **exactly one atomic transaction** (i.e., one call to the `hronir cast-vote` command).
    *   In this single transaction, the agent can cast up to the path's total calculated voting power (e.g., if power is 3, they can vote on up to 3 different positions' pending duels).
    *   Any unused portion of the voting power from that transaction is **nullified and cannot be used later**. The token is entirely consumed after its one use.
    *   A new table, `consumed_voting_tokens (voting_token_path_uuid TEXT PRIMARY KEY, consumed_at TIMESTAMP)`, tracks which `path_uuid`s have been used.

4.  **Ledger of Pending Duels**:
    *   The system maintains a ledger of "pending duels."
    *   For each narrative `position` where duels are possible, there is (ideally) one currently active pending duel.
    *   This ledger is stored in a `pending_duels` table: `(duel_id TEXT PRIMARY KEY, position INT, path_A_uuid TEXT, path_B_uuid TEXT, created_at TIMESTAMP, is_active BOOLEAN)`. An index on `(position, is_active)` allows efficient lookup of the active duel for a position.
    *   Agents consult this ledger (e.g., via `hronir list-pending-duels` or `hronir get-pending-duel --position X`) to see current contestable pairs.

5.  **Casting Votes (Atomic Transaction - `hronir cast-vote` command)**:
    *   The agent provides their chosen `voting_token_path_uuid` and a set of verdicts.
    *   Verdicts are of the form `{"position_string": "chosen_winning_path_uuid"}`.
    *   The command validates:
        *   The `voting_token_path_uuid` exists and its hrönirs are valid.
        *   The `voting_token_path_uuid` is not already in `consumed_voting_tokens`.
        *   The path has voting power > 0 (`ceil(sqrt(N)) > 0`).
        *   The number of submitted verdicts does not exceed the token's voting power.
        *   Each verdict's `chosen_winning_path_uuid` must be part of the *currently active pending duel* for that `position` in the `pending_duels` ledger. Votes for non-pending or mismatched duels are not computed.
    *   **Execution (within a single database transaction):**
        1.  For each valid submitted verdict:
            a.  The `duel_id` of the pending duel for that position is retrieved.
            b.  The `chosen_winner_side` ('A' or 'B') is determined.
            c.  A new vote record is created in the `recorded_votes` table.
            d.  The just-voted-on pending duel is marked `is_active = FALSE`.
            e.  Elo ratings are updated based on this vote.
            f.  A new pending duel for this position is generated (using `ratings.determine_next_duel_entropy` with updated ratings) and added to `pending_duels` as `is_active = TRUE`.
        2.  The `voting_token_path_uuid` is added to the `consumed_voting_tokens` table.
        3.  The database transaction is committed.
        4.  If any valid votes were processed, `run_temporal_cascade` is triggered from the oldest affected position.

6.  **`recorded_votes` Table Structure**:
    *   `(vote_id TEXT PRIMARY KEY, duel_id TEXT REFERENCES pending_duels(duel_id), voting_token_path_uuid TEXT, chosen_winner_side TEXT CHECK (chosen_winner_side IN ('A', 'B')), position INT, recorded_at TIMESTAMP)`
    *   This structure simplifies vote recording by linking directly to a `duel_id` and specifying the chosen side, rather than storing winner/loser hrönirs directly in the vote record.

## Benefits of this Approach

*   **Simplified Mandate Logic**: Removes complex path statuses (PENDING, QUALIFIED, SPENT) and separate `mandate_id`s. The `path_uuid` is the key.
*   **Clear Voting Power**: Voting power is deterministically calculated from a path's position.
*   **Atomic Voting**: All votes from a single token are cast in one transaction, simplifying consumption tracking.
*   **Explicit Duel Context**: Votes are always against known, system-defined "pending duels," preventing ambiguous or out-of-context votes.
*   **Dynamic Duel Generation**: The duel for a position is refreshed after each vote, ensuring the next contest is always based on the latest ratings.

This protocol aims for a more robust, transparent, and potentially simpler system for managing voting and narrative evolution.
