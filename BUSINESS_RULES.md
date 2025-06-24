# Business Rules of The Hrönir Encyclopedia

This table defines the fundamental rules, principles, and constraints that govern The Hrönir Encyclopedia. These rules are the "laws of physics" for this narrative universe, ensuring its integrity, coherence, and ability to evolve. All participants, whether human contributors or automated agents, must operate within this framework.

### Content & Storage (The Hrönirs)

| ID    | Rule Name                  | Description                                                                                                                                                                                             |
| :---- | :------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CS.1  | Hrönir Immutability & UUID | The canonical identifier for a hrön is a version 5 UUID, deterministically generated from the full, exact text content of its `index.md` file. Hrönirs are immutable.                                 |
| CS.2  | Canonical File Path        | Each hrön is stored in a unique directory path derived from its UUID. The path is constructed by using each character of the UUID as a subdirectory name (e.g., `the_library/d/9/4/4/...`).                  |
| CS.3  | Required Folder Contents   | Each hrön directory **must** contain an `index.md` file with the chapter's text and a `metadata.json` file.                                                                                             |
| CS.4  | Metadata Integrity         | The `metadata.json` file **must** contain a `uuid` field that exactly matches the content-derived UUID of the `index.md` file. It may also contain a `previous_uuid`.                                     |
| CS.5  | Hrönir Validity Conditions | A hrön is only valid if it exists at its correct UUID-derived path and its `metadata.json` `uuid` matches its content-derived UUID. Invalid hrönir are subject to automated purging.                   |

### Narrative Structure (The Narrative Paths)

| ID    | Rule Name               | Description                                                                                                                                                                                     |
| :---- | :---------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NS.1  | Path Definition         | Narrative paths are defined in `.csv` files within the `narrative_paths/` directory. Each row represents a single path and **must** contain `position`, `prev_uuid`, and `uuid`.                       |
| NS.2  | Path UUID Generation    | Each narrative path row **must** have a `path_uuid` field, which is a version 5 UUID deterministically generated from the combined string of `position:prev_uuid:uuid`.                              |
| NS.3  | Narrative Path Validity   | A narrative path entry is only valid if its `path_uuid` is correct and both its `prev_uuid` and `uuid` fields point to existing, valid hrönirs. Invalid entries are subject to automated purging.      |

### Selection & Canonization (Voting)

| ID    | Rule Name                      | Description                                                                                                                                                                                                                          |
| :---- | :----------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC.1  | Proof-of-Work for Voting       | Every vote **must** originate from a new row in `narrative_paths`. Creating this entry links valid hrönirs and yields a unique `path_uuid` that acts as the voter identity and proof of work.
| SC.2  | Vote Record Structure          | Votes are recorded in `.csv` files within the `ratings/` directory. Each record **must** contain a unique `uuid` (for the vote itself), a `voter`, a `winner` (hrönir UUID), and a `loser` (hrönir UUID).                              |
| SC.3  | Voter Identity (Path UUID)     | The `voter` field in a vote record **must** be the `path_uuid` of a valid, existing narrative path. A vote is cast "as" a specific narrative branch.                                                                                     |
| SC.4  | One Vote per Voter per Position| A single `voter` (`path_uuid`) may only cast **one vote** per position. Subsequent votes from the same `path_uuid` for the same position are invalid.                                                                                   |
| SC.5  | Vote Validity Conditions       | A vote is only valid if its `voter` (`path_uuid` from the session-initiating path) is valid, its `winner` points to a valid hrönir present in the session dossier for that position. Votes are recorded via `session commit`. |
| SC.0  | Canonical Lineage Restriction  | Competition for Position `N` is restricted to paths whose `prev_uuid` matches the `hrönir_uuid` of the canonical path at Position `N-1`. This is enforced when generating session dossiers. |
| **SC.6**  | **Temporal Cascade for Canonization** | The canonical path is determined by the "Temporal Cascade" process, triggered **exclusively** by a `session commit`. It recalculates the canon from the oldest position judged in that session. The `recover-canon` command (formerly `consolidate-book`) is a recovery tool to run this from position 0. |
| **SC.7**  | **Maximal Entropy Duels in Dossier** | When a `session start` occurs, the system generates a static dossier containing the "Maximal Entropy Duel" for each prior position. This duel represents the most uncertain contest (closest Elo scores) among eligible paths at that moment. The user judges based on this static dossier. |
| **SC.13** | **Qualificação por Mérito (Anti-Sybil)** | A criação de um path é livre, mas a influência (o direito de iniciar uma Sessão de Julgamento) é conquistada. Um path só pode ser usado como mandado após atingir o status `QUALIFIED` ao provar seu valor nos duelos de sua própria posição. |
| **SC.8**  | **Direito de Julgamento Único e Causal** | A qualificação de um path na Posição `N` concede ao seu criador o direito de iniciar **uma única** Sessão de Julgamento. O path é então `SPENT` e não pode ser reutilizado.                                                                   |
| **SC.9**  | **Dossiê Estático de Duelos**           | O início de uma sessão gera um dossiê estático e não-interativo de todos os duelos de máxima entropia para as posições de `N-1` a `0`, com base no estado canônico daquele momento.                                                       |
| **SC.10** | **Soberania da Curadoria**              | O agente só pode votar nos duelos de paths apresentados pelo sistema no dossiê da sessão.                                                                                                                                               |
| **SC.11** | **Cascata Temporal como Único Consolidador** | A determinação do caminho canônico é **sempre** uma cascata acionada **exclusivamente** pelo `session commit`, começando na posição mais antiga que recebeu um voto na sessão.                                                         |
| **SC.12** | **Perenidade do Voto**                  | Votos registrados no ledger são permanentes. Sua relevância no cálculo de Elo é dinâmica, dependendo se sua linhagem é canônica no momento do cálculo.                                                                                     |

### System & Ledger

| ID    | Rule Name                               | Description                                                                                                                                                                                                                          |
| :---- | :-------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SYS.1** | **Ledger Cronológico de Transações**    | Cada `session commit` é um bloco em uma cadeia, contendo um hash de seu conteúdo e um ponteiro para o bloco anterior, formando um ledger à prova de adulteração.                                                                          |

### Generation & Contribution (Agents)

| ID    | Rule Name                      | Description                                                                                                                                                                                                                         |
| :---- | :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GC.1  | Commit All Generated Artifacts | All generated content—including hrönirs, narrative path entries, and votes created for any purpose (testing, PoW, etc.)—**must** be committed to the repository to ensure transparency and reproducibility.                               |
| GC.2  | Agent Compliance               | Automated agents (e.g., GitHub Actions) are bound by the same rules as human contributors.                                                                                                                                            |
| GC.3  | Automated System Cleaning      | The system **must** maintain its own integrity through automated cleaning processes. The `hronir-clean` pre-commit hook is a mandatory process that purges all invalid artifacts to keep the repository in a consistent and valid state. |
