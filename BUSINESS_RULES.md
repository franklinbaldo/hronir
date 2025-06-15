# Business Rules of The Hrönir Encyclopedia

This table defines the fundamental rules, principles, and constraints that govern The Hrönir Encyclopedia. These rules are the "laws of physics" for this narrative universe, ensuring its integrity, coherence, and ability to evolve. All participants, whether human contributors or automated agents, must operate within this framework.

### Content & Storage (The Hrönirs)

| ID    | Rule Name                  | Description                                                                                                                                                                                             |
| :---- | :------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CS.1  | Hrönir Immutability & UUID | The canonical identifier for a hrönir is a version 5 UUID, deterministically generated from the full, exact text content of its `index.md` file. Hrönirs are immutable.                                 |
| CS.2  | Canonical File Path        | Each hrönir is stored in a unique directory path derived from its UUID. The path is constructed by using each character of the UUID as a subdirectory name (e.g., `hronirs/d/9/4/4/...`).                  |
| CS.3  | Required Folder Contents   | Each hrönir directory **must** contain an `index.md` file with the chapter's text and a `metadata.json` file.                                                                                             |
| CS.4  | Metadata Integrity         | The `metadata.json` file **must** contain a `uuid` field that exactly matches the content-derived UUID of the `index.md` file. It may also contain a `previous_uuid`.                                     |
| CS.5  | Hrönir Validity Conditions | A hrönir is only valid if it exists at its correct UUID-derived path and its `metadata.json` `uuid` matches its content-derived UUID. Invalid hrönirs are subject to automated purging.                   |

### Narrative Structure (The Forking Paths)

| ID    | Rule Name               | Description                                                                                                                                                                                     |
| :---- | :---------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NS.1  | Path Definition         | Forking paths are defined in `.csv` files within the `forking_path/` directory. Each row represents a single fork and **must** contain `position`, `prev_uuid`, and `uuid`.                       |
| NS.2  | Fork UUID Generation    | Each forking path row **must** have a `fork_uuid` field, which is a version 5 UUID deterministically generated from the combined string of `position:prev_uuid:uuid`.                              |
| NS.3  | Forking Path Validity   | A forking path entry is only valid if its `fork_uuid` is correct and both its `prev_uuid` and `uuid` fields point to existing, valid hrönirs. Invalid entries are subject to automated purging.      |

### Selection & Canonization (Voting)

| ID    | Rule Name                      | Description                                                                                                                                                                                                                          |
| :---- | :----------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC.1  | Proof-of-Work for Voting       | Voting is not a free action; it is an act of contribution. To vote, a participant must first expand the narrative possibilities, typically by generating new hrönirs and forking paths.                                                 |
| SC.2  | Vote Record Structure          | Votes are recorded in `.csv` files within the `ratings/` directory. Each record **must** contain a unique `uuid` (for the vote itself), a `voter`, a `winner` (hrönir UUID), and a `loser` (hrönir UUID).                              |
| SC.3  | Voter Identity (Fork UUID)     | The `voter` field in a vote record **must** be the `fork_uuid` of a valid, existing forking path. A vote is cast "as" a specific narrative branch.                                                                                     |
| SC.4  | One Vote per Voter per Position| A single `voter` (`fork_uuid`) may only cast **one vote** per position. Subsequent votes from the same `fork_uuid` for the same position are invalid.                                                                                   |
| SC.5  | Vote Validity Conditions       | A vote is only valid if its `voter` is a valid `fork_uuid`, its `winner` and `loser` point to valid hrönirs, and the voter has not already voted for that position. Invalid votes are subject to automated purging.                      |

### Generation & Contribution (Agents)

| ID    | Rule Name                      | Description                                                                                                                                                                                                                         |
| :---- | :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GC.1  | Commit All Generated Artifacts | All generated content—including hrönirs, forking path entries, and votes created for any purpose (testing, PoW, etc.)—**must** be committed to the repository to ensure transparency and reproducibility.                               |
| GC.2  | Agent Compliance               | Automated agents (e.g., GitHub Actions) are bound by the same rules as human contributors.                                                                                                                                            |
| GC.3  | Automated System Cleaning      | The system **must** maintain its own integrity through automated cleaning processes. The `hronir-clean` pre-commit hook is a mandatory process that purges all invalid artifacts to keep the repository in a consistent and valid state. |
