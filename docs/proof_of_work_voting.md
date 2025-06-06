# Proof-of-Work Voting

The Hr\u00f6nir Encyclopedia adopts a novel proof-of-work mechanism to keep its evolving canon free from spam while simultaneously enriching the narrative universe. This process turns each vote into a creative act.

## Why Proof of Work?

In a system with limitless branching paths, it would be trivial to submit endless votes for a favorite chapter. By requiring each vote to include new hr\u00f6nirs and a unique path, the system ensures that only participants who meaningfully contribute can influence the rankings. Every vote must push the encyclopedia forward.

## How It Works

1. **Discover** two new hr\u00f6nirs that do not yet appear in `hronirs/index.txt`.
2. **Forge** a new forking path that has not been used before.
3. **Submit** the vote along with the two hr\u00f6nirs via the CLI:

   ```bash
   python -m hronir_encyclopedia.cli vote \
     --position 1 \
     --voter 01234567-89ab-cdef-0123-456789abcdef \
     --path "0->1" --hronirs a b
   ```
4. The vote is recorded in `ratings/position_001.csv`. Each row stores the voter uuid along with the winning and losing paths. The CSV uses three columns: `voter`, `winner`, and `loser`. Votes are tallied immediately unless their forking path has the greatest **distance** in the graph. Distance equals the difference in path length from the current leader plus the path's ranking position. Paths with the maximum distance remain recorded but their votes do not influence the standings.

## A Self-Expanding Canon

This ingenious mechanism transforms the act of voting into an engine of discovery. New hr\u00f6nirs fill the index, unexplored branches populate the narrative tree, and frivolous votes are thwarted without heavy moderation. The encyclopedia rewards readers who blaze new trails and share their findings with the community.

## Checking Your Work

You can inspect your local `ratings` directory to see where your path currently ranks. When your path reaches the top position for that chapter, the stored vote activates and influences the overall canon.

The proof-of-work design elegantly balances participation and curation, ensuring the Hr\u00f6nir Encyclopedia grows in both breadth and depth.
