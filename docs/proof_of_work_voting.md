# Voting as Information: The Purely Entropic System

# Voting on Forks: The Purely Entropic System for Narrative Transitions

In The Hrönir Encyclopedia, voting is a direct contribution to reducing uncertainty about which **narrative transition (fork)** is the most "inevitable" or "true" for a given point in the story. The system is governed by a single, powerful principle: **maximization of information gain (Entropy)**. Each vote is directed by the system to resolve the most ambiguous choice between two competing `forks`.

## The Philosophy: Pure Informational Relevance in Narrative Choice

The guiding philosophy is that every vote must be as informative as possible in determining the canonical path of bifurcations. There are no special cases or alternative strategies; the system *always* seeks out the pair of `forks` (for a specific position and following a specific canonical predecessor) whose relative "inevitable" status is most uncertain. By resolving this "Duelo de Máxima Entropia" between `forks`, the collective ranking of these narrative transitions converges more efficiently. A new `fork` (representing a new hrönir connected to a predecessor) simply joins the pool of eligible forks for its position and lineage, and will be selected for a duel if and when its inclusion in a pair results in the highest current entropy.

## Proof-of-Work: Earning Your Voice by Forging a Path

Before you can contribute your judgment, you must first expand the narrative possibilities by defining a new fork. This is the "Proof-of-Work":
1.  **Create:** Generate a new `hrönir` (the textual content).
2.  **Store:** Use the `store` command to add your `hrönir` to `the_library/`, obtaining its `hrönir_uuid`.
3.  **Connect & Define Fork:** Record the lineage of your new `hrönir` by adding an entry to the appropriate `forking_path/*.csv` file. This entry specifies:
    *   `position`: The narrative position this fork is competing for.
    *   `prev_uuid`: The `hrönir_uuid` of the chapter this new hrönir follows.
    *   `uuid`: The `hrönir_uuid` of your newly created hrönir (the successor in this fork).
    This action, upon processing by the system (e.g., via `storage.append_fork` or `audit_forking_csv`), will have a unique `fork_uuid` computed for it, based on `position:prev_uuid:uuid`.

This `fork_uuid` (the one that *you created or proposed* as a PoW) is your credential. It signifies your active participation in building the encyclopedia's branching structure and grants you the right to help refine the canonical path through voting on *other* duels. **The `fork_uuid` itself is the object of competition and canonization.**

## The Purely Entropic Voting Process on Forks: A Two-Step Resolution

With your Proof-of-Work `fork_uuid` (let's call it `voter_fork_uuid`), you engage in a precise, system-guided voting process to decide between *other* competing forks:

**Step 1: Discover the Point of Maximum Uncertainty (`get-duel`)**

The system itself identifies the duel between two `forks` that will yield the most information for a given `position` (respecting the `Restrição de Linhagem Canônica`). You, the voter, are directed to this specific point of ambiguity.
```bash
uv run python -m hronir_encyclopedia.cli get-duel --position <position_number>
```
This command will return a JSON object detailing the duel. The `strategy` field will **always** be `"max_entropy_duel"`:

*   **`max_entropy_duel` (Duelo de Máxima Entropia entre Forks):**
    *   This is the **only** strategy. The system calculates the Shannon entropy for potential duels between eligible `forks`, prioritizing those with the closest Elo ratings, as their outcome is the most unpredictable.
    *   *Example Output Snippet:*
        ```json
        {
          "position": 1,
          "strategy": "max_entropy_duel",
          "duel_pair": {
              "fork_A": "fork_uuid_of_competing_fork1",
              "fork_B": "fork_uuid_of_competing_fork2"
          },
          "entropy": 0.999123, // Value close to 1.0 indicates high uncertainty
          // ...
        }
        ```

**Step 2: Cast Your Decisive Vote (`vote`)**

After `get-duel` has presented the system-selected pair of `forks`, you cast your vote using your `voter_fork_uuid`:
```bash
uv run python -m hronir_encyclopedia.cli vote \
  --position <position_number> \
  --voter-fork-uuid <your_pow_fork_uuid> \
  --winner-fork-uuid <fork_A_uuid_from_get_duel> \
  --loser-fork-uuid <fork_B_uuid_from_get_duel>
```
**Crucially, your vote will only be accepted if the `winner-fork-uuid` and `loser-fork-uuid` precisely match the `fork_A` and `fork_B` provided by `get-duel` for that position.**

This strict validation ensures that your intellectual effort is applied directly to resolving the system's current point of greatest informational need regarding which narrative transition should become canonical.

## Advantages of the Fork-Centric Entropic Model

*   **Philosophical Consistency:** A single, elegant rule governs the selection of all duels. The system is a pure embodiment of the quest for information about narrative inevitability. The `fork_uuid` is the atomic unit of competition.
*   **Fairness and Organic Growth:** New `forks` (narrative transitions) are not subjected to arbitrary "calibration" duels. They integrate into the ranking for their specific lineage and are selected for duels based on their potential to resolve uncertainty, allowing for more organic and fair competition between narrative choices.
*   **Implementation Simplicity:** Focusing on `forks` as the objects of duels and canonization can simplify logic in `ratings.determine_next_duel` and `cli.consolidate_book`.
*   **Clarity in Communication:** A system driven by one powerful, unifying principle—the canonization of forks—is easier to understand, explain, and trust.

By participating in this purely entropy-guided voting on `forks`, you are not just picking favorite hrönirs; you are a critical agent in the encyclopedia's process of self-discovery, helping to illuminate the most "inevitable" sequence of narrative bifurcations from a universe of possibilities.
