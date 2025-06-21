# Voting as Information: The Entropy-Guided System

In The Hrönir Encyclopedia, voting is not merely an expression of preference but a crucial act of information contribution. The system is designed to maximize the knowledge gained from each vote, guiding the collective effort towards resolving the greatest uncertainties in the narrative's evolving structure. This is achieved through a **Proof-of-Work** mechanism coupled with an **Entropy-Guided Duel Selection** process.

## The Philosophy: Relevância Informativa

The core idea is that each vote should be as informative as possible. Instead of allowing votes on any arbitrary pair of `hrönirs`, the system directs your intellectual labor to where it's most needed. This ensures that the collective ranking converges efficiently towards the "true" or most "inevitable" narrative paths.

## Proof-of-Work: Earning Your Say

Before you can vote, you must contribute to the encyclopedia's expansion. This is the "Proof-of-Work":
1.  **Create:** Generate one or more new `hrönirs` (chapter variants).
2.  **Store:** Use the `store` command to add your `hrönirs` to `the_library/`.
3.  **Connect:** Record the lineage of your new `hrönirs` by adding entries to `forking_path/yu-tsun.csv`. Each entry links a `prev_uuid` (the UUID of the preceding chapter) to your new `hrönir's` `uuid`. This action generates a unique `fork_uuid`.

This `fork_uuid` is your credential. It proves you have expanded the narrative space and grants you the right to help refine it through voting.

## The Entropy-Guided Voting Process: A Two-Step Dance

Once you have your `fork_uuid`, you participate in a curated voting process:

**Step 1: Discover the Most Informative Duel (`get-duel`)**

The system identifies the duel that will provide the most information to refine the rankings. You don't choose the combatants; the system presents them to you.
```bash
uv run python -m hronir_encyclopedia.cli get-duel --position <position_number>
```
This command will return a JSON object detailing the duel. The `strategy` field indicates why this duel was chosen:

*   **`calibration_duel` (Duelo de Calibração):**
    *   **Priority 1.** Occurs when a `hrönir` has no recorded duels (it's "new" to the ranking system for that position).
    *   The new `hrönir` is pitted against the current **champion** (highest Elo `hrönir`) of that position.
    *   This quickly establishes a baseline Elo for the new entrant, integrating it into the existing ranking structure.
    *   *Example Output Snippet:*
        ```json
        {
          "strategy": "calibration_duel",
          "hronir_A": "champion_uuid",
          "hronir_B": "new_hronir_uuid",
          // ...
        }
        ```

*   **`max_entropy_duel` (Duelo de Máxima Entropia):**
    *   **Priority 2.** Occurs if there are no `hrönirs` needing calibration.
    *   The system selects two `hrönirs` whose Elo ratings are very close. The outcome of such a duel is highly uncertain (high Shannon entropy).
    *   Resolving this duel provides the maximum possible information to distinguish between closely ranked contenders, thus refining the ordering most effectively.
    *   The current implementation uses a heuristic: it compares `hrönirs` that are adjacent in the Elo-sorted ranking, as these are strong candidates for high entropy.
    *   *Example Output Snippet:*
        ```json
        {
          "strategy": "max_entropy_duel",
          "hronir_A": "uuid_of_hronir1",
          "hronir_B": "uuid_of_hronir2",
          "entropy": 0.999, // Value close to 1.0 indicates high uncertainty
          // ...
        }
        ```

**Step 2: Cast Your Vote (`vote`)**

After `get-duel` has informed you of the system-selected pair, you cast your vote using your `fork_uuid`:
```bash
uv run python -m hronir_encyclopedia.cli vote \
  --position <position_number> \
  --voter <your_fork_uuid> \
  --winner <uuid_A_from_get_duel> \
  --loser <uuid_B_from_get_duel>
```
**Crucially, your vote will only be accepted if `winner` and `loser` match the `hronir_A` and `hronir_B` provided by `get-duel` for that position.**

This strict validation ensures that your vote directly addresses the system's current point of maximum uncertainty, making your contribution as valuable as possible.

## Why This Approach?

*   **Efficiency:** Directs limited human attention to where it has the most impact.
*   **Robust Rankings:** Helps build a more accurate and stable Elo ranking system quickly.
*   **Philosophical Alignment:** Reinforces the idea of the encyclopedia as a system discovering itself, with human input serving to clarify its inherent structure rather than impose arbitrary choices.

By participating in this entropy-guided voting, you are not just picking winners; you are actively helping to reveal the most "inevitable" narrative threads within the Hrönir Encyclopedia.
