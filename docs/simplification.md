Of course. Based on a comprehensive review of the `hrönir-encyclopedia` codebase, I have prepared a strategic plan to simplify the system.

The project has a brilliant and ambitious core concept, but its implementation shows signs of rapid evolution, particularly the recent pivot from a CSV-based system to a DuckDB architecture. This has left behind legacy code and created architectural seams that are the primary source of complexity.

This plan focuses on paying down that "architectural debt" to make the codebase more coherent, maintainable, and easier to understand, fully realizing the vision outlined in `docs/pivot_plan_v2.md`.

---

## Simplification Plan: The Great Consolidation

### Guiding Principles

1.  **DuckDB is the Single Source of Truth (SSOT):** All persistent state (paths, votes, content, transactions, sessions) must live in the `encyclopedia.duckdb` file. All file-based data storage (CSVs, individual JSONs) is to be considered a legacy format used only for initial migration or as temporary artifacts.
2.  **Clear Separation of Concerns:** Business logic (protocol rules) must be decoupled from the presentation layer (CLI) and the persistence layer (data access).
3.  **Explicit over Implicit:** Dependencies and state should be passed explicitly (e.g., dependency injection of a DB session) rather than relying on global singletons or hidden state.

### Phase 1: Foundational Cleanup & Establishing the SSOT

This is the most critical phase. Simplifying the rest of the system is impossible without a stable and coherent data foundation.

| Problem                                                                                | Action                                                                                                                                                             | Rationale & Outcome                                                                                                                                                                           |
| :------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Legacy Code Confusion**                                                              | **1.1: Purge `storage_old.py` and related CSV logic.**                                                                                                             | (`Remove dead code`) Eliminates a major source of confusion. The file contains outdated SQLAlchemy models and CSV-based logic that directly contradicts the DuckDB-centric architecture.          |
| **Scattered Data Sources**                                                             | **1.2: Migrate `sessions` and `transactions` to DuckDB.**                                                                                                          | (`Improve abstraction`) Storing session and transaction data from `data/sessions/*.json` and `data/transactions/*.json` into dedicated DuckDB tables makes the DB the true SSOT.                |
| **God-Object `DataManager`**                                                           | **1.3: Refactor the `DataManager` and data access patterns.**                                                                                                      | (`Reduce dependencies`) Instead of a global singleton, refactor core logic functions in `ratings.py`, `session_manager.py`, etc., to accept a database connection/session object.               |
| **Unclear `storage.py` Role**                                                          | **1.4: Split `storage.py` into a focused data access layer.**                                                                                                      | (`Decompose large classes`) Rename or refactor `storage.py`. It should only contain the `DuckDBDataManager`. Move utility functions like `compute_narrative_path_uuid` to a `utils.py` module. |
| **Hrönir Content Duality**                                                             | **1.5: Deprecate `the_library/` as a primary source.**                                                                                                             | (`Eliminate duplication`) The `hronirs` table in DuckDB should be the canonical store. The `the_library/` directory should only be used as a source for the initial migration.                      |

---

### Phase 2: Refactoring Core Logic

With a solid data foundation, we can now simplify the business logic that uses it.

| Problem                                                                           | Action                                                                                                                                                      | Rationale & Outcome                                                                                                                                                                                               |
| :-------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **"Fat" CLI with Business Logic**                                                 | **2.1: Move `run_temporal_cascade` and other logic out of `cli.py`.**                                                                                       | (`Decompose large functions`) The `run_temporal_cascade` function contains critical business logic. Move it to a new module like `hronir_encyclopedia/canon.py`. The CLI command should be a thin wrapper.     |
| **Inconsistent Data Handling**                                                    | **2.2: Refactor `session_manager` and `transaction_manager` to be DB-only.**                                                                                | (`Improve abstraction`) These modules should be stateless and operate solely on data passed to them or retrieved via the data access layer. Remove all direct file I/O (e.g., writing to `HEAD` or session JSONs). |
| **Complex Path Status Management**                                                | **2.3: Simplify path status updates.**                                                                                                                      | (`Decompose large functions`) The logic for updating a path's status (`PENDING` -> `QUALIFIED` -> `SPENT`) is spread across `transaction_manager` and `session_manager`. Consolidate it into a single, clear function. |

---

### Phase 3: Enhancing Developer Experience & Maintainability

This phase makes the newly simplified system robust and easy to work on.

| Problem                                                                               | Action                                                                                                                                                     | Rationale & Outcome                                                                                                                                                                                                     |
| :------------------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Failing / Legacy Tests**                                                            | **3.1: Fix the test suite to reflect the DuckDB architecture.**                                                                                            | (`Improve testability`) Tests in `test_ranking_filtering.py` and others rely on creating mock CSVs. They must be refactored to populate a test DuckDB instance directly. A passing test suite is non-negotiable.       |
| **Implicit Configuration**                                                            | **3.2: Centralize configuration.**                                                                                                                         | (`Improve abstraction`) Instead of `os.getenv` calls scattered throughout the code, use a Pydantic `BaseSettings` model to load configuration from environment variables into a single, explicit object.                    |
| **Outdated Documentation**                                                            | **3.3: Update all documentation to reflect the new architecture.**                                                                                         | (`Documentation`) `README.md`, `CLAUDE.md`, and `BUSINESS_RULES.md` must be updated to describe the DuckDB-centric reality. All references to CSV workflows, `the_garden`, and old commands must be purged.                |

### Summary of Actions

| Phase | Action                                              | Goal                                               |
| :---- | :-------------------------------------------------- | :------------------------------------------------- |
| **1** | Purge `storage_old.py`                              | Eliminate legacy code.                             |
| **1** | Move all data into DuckDB                           | Establish a Single Source of Truth.                |
| **1** | Refactor `DataManager`                              | Promote explicit dependency injection.             |
| **1** | Deprecate `the_library/`                            | Remove data duplication.                           |
| **2** | Decouple business logic from `cli.py`               | Improve separation of concerns.                    |
| **2** | Refactor managers to be DB-only                     | Enforce the SSOT principle.                        |
| **2** | Consolidate path status logic                       | Reduce complexity and duplication.                 |
| **3** | Fix test suite for DuckDB                           | Ensure reliability and correctness.                |
| **3** | Centralize configuration                            | Make system configuration explicit and manageable. |
| **3** | Update all documentation                            | Ensure documentation reflects reality.             |

### Conclusion

This simplification plan is ambitious but essential. By executing these three phases, the **Hrönir Encyclopedia** will transform from a system in a state of architectural flux into a clean, coherent, and robust protocol. This will not only make it easier to understand and maintain but will also provide a solid foundation for implementing the advanced features on the roadmap, such as the P2P distribution and the Merkle-based trust protocol.