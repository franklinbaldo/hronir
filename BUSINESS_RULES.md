# Business Rules of The Hrönir Encyclopedia

This table defines the fundamental rules, principles, and constraints that govern The Hrönir Encyclopedia. These rules are the "laws of physics" for this narrative universe, ensuring its integrity, coherence, and ability to evolve. All participants, whether human contributors or automated agents, must operate within this framework.

### Content & Storage (The Hrönirs)

| ID    | Rule Name                  | Description                                                                                                                                                                                             |
| :---- | :------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CS.1  | Hrönir Immutability & UUID | The canonical identifier for a hrön is a version 5 UUID, deterministically generated from the full, exact text content of its `index.md` file. Hrönirs are immutable.                                 |
| CS.2  | Canonical File Path        | Each hrön is stored in a directory named after its UUID, directly under `the_library/` (e.g., `the_library/123e4567-e89b-12d3-a456-426614174000/`). The main content file is `index.md` within this directory. |
| CS.3  | Required Folder Contents   | Each hrön directory **must** contain an `index.md` file with the chapter's text and a `metadata.json` file.                                                                                             |
| CS.4  | Metadata Integrity         | The `metadata.json` file **must** contain a `uuid` field that exactly matches the content-derived UUID of the `index.md` file. It may also contain a `previous_uuid`.                                     |
| CS.5  | Hrönir Validity Conditions | A hrön is only valid if it exists at its correct UUID-derived path and its `metadata.json` `uuid` matches its content-derived UUID. Invalid hrönir are subject to automated purging.                   |

### Narrative Structure (The Forking Paths)

| ID    | Rule Name               | Description                                                                                                                                                                                     |
| :---- | :---------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NS.1  | Path Definition         | Forking paths are defined in `.csv` files within the `forking_path/` directory. Each row represents a single fork and **must** contain `position`, `prev_uuid`, and `uuid`.                       |
| NS.2  | Fork UUID Generation    | Each forking path row **must** have a `fork_uuid` field, which is a version 5 UUID deterministically generated from the combined string of `position:prev_uuid:uuid`.                              |
| NS.3  | Forking Path Validity   | A forking path entry is only valid if its `fork_uuid` is correct and both its `prev_uuid` and `uuid` fields point to existing, valid hrönirs. Invalid entries are subject to automated purging.      |

### Selection & Canonization (Voting)

| ID    | Rule Name                      | Description                                                                                                                                                                                                                          |
| :---- | :----------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC.1  | Proof-of-Work for Voting       | Every vote **must** originate from a new row in `forking_path`. Creating this entry links valid hrönirs and yields a unique `fork_uuid` that acts as the voter identity and proof of work.
| SC.2  | Vote Record Structure          | Votes are recorded in `.csv` files within the `ratings/` directory. Each record **must** contain a unique `uuid` (for the vote itself), a `voter`, a `winner` (hrönir UUID), and a `loser` (hrönir UUID).                              |
| SC.3  | Voter Identity (Fork UUID)     | The `voter` field in a vote record **must** be the `fork_uuid` of a valid, existing forking path. A vote is cast "as" a specific narrative branch.                                                                                     |
| SC.4  | One Vote per Voter per Position| A single `voter` (`fork_uuid`) may only cast **one vote** per position. Subsequent votes from the same `fork_uuid` for the same position are invalid.                                                                                   |
| SC.5  | Vote Validity Conditions       | A vote is only valid if its `voter` (`fork_uuid` from the session-initiating fork) is valid, its `winner` points to a valid hrönir present in the session dossier for that position. Votes are recorded via `session commit`. |
| SC.0  | Canonical Lineage Restriction  | Competition for Position `N` is restricted to forks whose `prev_uuid` matches the `hrönir_uuid` of the canonical fork at Position `N-1`. This is enforced when generating session dossiers. |
| **SC.6**  | **Temporal Cascade for Canonization** | **[DEPRECATED]** ~~The canonical path is determined by the "Temporal Cascade" process, triggered **exclusively** by a `session commit`. It recalculates the canon from the oldest position judged in that session. The `recover-canon` command (formerly `consolidate-book`) is a recovery tool to run this from position 0.~~ This rule is deprecated as it is superseded by rule SC.11, which provides a more comprehensive description of the canonization process. |
| **SC.7**  | **Maximal Entropy Duels in Dossier** | **[DEPRECATED]** ~~When a `session start` occurs, the system generates a static dossier containing the "Maximal Entropy Duel" for each prior position. This duel represents the most uncertain contest (closest Elo scores) among eligible forks at that moment. The user judges based on this static dossier.~~ This rule is deprecated as it is superseded by rule SC.9, which more accurately describes the generation of the static duel dossier. |
| **SC.13** | **Merit-Based Qualification (Anti-Sybil)** | Fork creation is free, but influence (the right to initiate a Judgment Session) is earned. A fork can only be used as a warrant after reaching `QUALIFIED` status by proving its worth in duels of its own position. |
| **SC.8**  | **Single, Causal Judgment Right**       | Qualification of a fork at Position `N` grants its creator the right to initiate **one single** Judgment Session. The fork is then `SPENT` and cannot be reused.                                                                  |
| **SC.9**  | **Static Duel Dossier**                 | Initiating a session generates a static, non-interactive dossier of all maximal entropy duels for positions from `N-1` down to `0`, based on the canonical state at that moment.                                      |
| **SC.10** | **Curatorial Sovereignty**              | **[DEPRECATED]** ~~The agent can only vote on duel forks presented by the system in the session dossier.~~ This rule is deprecated as it describes an implicit system constraint derived from the nature of the static duel dossier (SC.9) and vote validity conditions (SC.5), rather than a standalone explicit business rule. |
| **SC.11** | **Temporal Cascade as Sole Consolidator** | Canonical path determination is **always** a cascade triggered **exclusively** by `session commit`, starting from the oldest position that received a vote in the session.                                                        |
| **SC.12** | **Vote Permanence**                     | Votes recorded in the ledger are permanent. Their relevance in Elo calculation is dynamic, depending on whether their lineage is canonical at the time of calculation.                                                                    |

### System & Ledger

| ID    | Rule Name                               | Description                                                                                                                                                                                                                          |
| :---- | :-------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SYS.1** | **Chronological Transaction Ledger**    | Each `session commit` is a block in a chain, containing a hash of its content and a pointer to the previous block, forming a tamper-proof ledger.                                                                          |

### Generation & Contribution (Agents)

| ID    | Rule Name                      | Description                                                                                                                                                                                                                         |
| :---- | :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GC.1  | Commit All Generated Artifacts | All generated content—including hrönirs, forking path entries, and votes created for any purpose (testing, PoW, etc.)—**must** be committed to the repository to ensure transparency and reproducibility.                               |
| GC.2  | Agent Compliance               | Automated agents (e.g., GitHub Actions) are bound by the same rules as human contributors.                                                                                                                                            |
| GC.3  | Automated System Cleaning      | The system **must** maintain its own integrity through automated cleaning processes. The `hronir-clean` pre-commit hook is a mandatory process that purges all invalid artifacts to keep the repository in a consistent and valid state. |
