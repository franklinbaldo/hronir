# Voting as Information: The Purely Entropic System

In The Hrönir Encyclopedia, voting is a direct contribution to reducing uncertainty within the narrative's ranking. The system is governed by a single, powerful principle: **maximization of information gain (Entropy)**. Each vote is directed by the system to resolve the most ambiguous point in the current literary landscape.

## The Philosophy: Pure Informational Relevance

The guiding philosophy is that every vote must be as informative as possible. There are no special cases or alternative strategies; the system *always* seeks out the pair of `hrönirs` (chapter variants) for a given position whose relative order is most uncertain. By resolving this "Duelo de Máxima Entropia," the collective ranking converges more efficiently towards the most "inevitable" or "true" narrative paths. A new `hrönir` simply joins the pool and will be selected for a duel if and when its inclusion in a pair results in the highest current entropy.

## Proof-of-Work: Earning Your Voice

Before you can contribute your judgment, you must first expand the narrative space. This is the "Proof-of-Work":
1.  **Create:** Generate one or more new `hrönirs`.
2.  **Store:** Use the `store` command to add your `hrönirs` to `the_library/`.
3.  **Connect:** Record the lineage of your new `hrönirs` by adding entries to `forking_path/yu-tsun.csv`. Each entry links a `prev_uuid` (the UUID of the preceding chapter) to your new `hrönir's` `uuid`. This action generates a unique `fork_uuid`.

This `fork_uuid` is your credential. It signifies your active participation in building the encyclopedia and grants you the right to help refine its structure through voting.

## The Purely Entropic Voting Process: A Two-Step Resolution

With your `fork_uuid`, you engage in a precise, system-guided voting process:

**Step 1: Discover the Point of Maximum Uncertainty (`get-duel`)**

The system itself identifies the duel that will yield the most information. You, the voter, are directed to this specific point of ambiguity.
```bash
uv run python -m hronir_encyclopedia.cli get-duel --position <position_number>
```
This command will return a JSON object detailing the duel. The `strategy` field will **always** be `"max_entropy_duel"`:

*   **`max_entropy_duel` (Duelo de Máxima Entropia):**
    *   This is the **only** strategy. The system calculates the Shannon entropy for potential duels, prioritizing those between `hrönirs` with the closest Elo ratings, as their outcome is the most unpredictable.
    *   The current implementation uses an efficient heuristic: it primarily considers `hrönirs` that are adjacent in the Elo-sorted ranking to find the pair with the highest entropy.
    *   *Example Output Snippet:*
        ```json
        {
          "position": 1,
          "strategy": "max_entropy_duel",
          "hronir_A": "uuid_of_hronir1",
          "hronir_B": "uuid_of_hronir2",
          "entropy": 0.999123, // Value close to 1.0 indicates high uncertainty
          // ...
        }
        ```

**Step 2: Cast Your Decisive Vote (`vote`)**

After `get-duel` has presented the system-selected pair, you cast your vote using your `fork_uuid`:
```bash
uv run python -m hronir_encyclopedia.cli vote \
  --position <position_number> \
  --voter <your_fork_uuid> \
  --winner <uuid_A_from_get_duel> \
  --loser <uuid_B_from_get_duel>
```
**Crucially, your vote will only be accepted if the `winner` and `loser` UUIDs precisely match the `hronir_A` and `hronir_B` provided by `get-duel` for that position.**

This strict validation ensures that your intellectual effort is applied directly to the system's current point of greatest informational need.

## Advantages of the Purely Entropic Model

*   **Philosophical Consistency:** A single, elegant rule governs the selection of all duels. The system is a pure embodiment of the quest for information.
*   **Fairness and Organic Growth:** New `hrönirs` are not subjected to arbitrary "calibration" duels against potentially much stronger opponents. They integrate into the ranking and are selected for duels based on their potential to resolve uncertainty, allowing for more organic and fair competition.
*   **Implementation Simplicity:** Removing special-case logic (like calibration duels) results in cleaner, more maintainable code in `ratings.determine_next_duel`.
*   **Clarity in Communication:** A system driven by one powerful, unifying principle is easier to understand, explain, and trust.

By participating in this purely entropy-guided voting, you are not just picking favorites; you are a critical agent in the encyclopedia's process of self-discovery, helping to illuminate the most "inevitable" narrative pathways from a universe of possibilities.
