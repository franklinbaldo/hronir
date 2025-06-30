# TODO.md · Development Roadmap — **Hrönir Encyclopedia**

This document outlines the development roadmap for the **Hrönir Encyclopedia** project. The core **Protocol v2** architecture is implemented with pandas-based data management and narrative path lifecycle management.

---

## ❗ P0 – Pivot Plan v2.0
Esta seção resume as tarefas de migração para o sistema distribuído proposto em [pivot_plan_v2.md](docs/pivot_plan_v2.md).

### 1. Para Decisão
- [x] **Revisão técnica do plano v2.0** — avaliar a viabilidade de DuckDB + P2P e registrar parecer em `docs/decisions/`.
- [x] **Aprovação de 3 semanas extras** — ajustar cronograma no `README.md`.
- [x] **Security audit de Merkle + PGP** — revisar `transaction_manager.py` e `duckdb_storage.py`.
- [x] **Definir critérios de sucesso** — documentar métricas de aceitação no `README.md`.

### 2. Cronograma de Execução
#### Semanas 1-2 – Base + Sharding
- [x] Instalar `duckdb`, `internetarchive` e `zstd` no `pyproject.toml`.
- [x] Criar script `migrate_to_duckdb.py --backup --enable-sharding`.
- [x] Implementar `hronir_encyclopedia/sharding.py` com `ShardingManager`.
- [x] Refatorar `storage.py` para usar `DuckDBDataManager` e sharding.
- [x] Salvar backup dos CSVs em `data/backup/`.
- [x] Cobrir migração com testes em `tests/`.

#### Semanas 3-4 – Conflicts + Security
- [x] Implementar locking por sequence number em `transaction_manager.py`.
- [x] Adicionar comando `hronir sync --retry` no `cli.py`.
- [x] Criar comando `hronir push` com verificação de conflitos.
- [x] Exigir assinatura PGP nas operações (scripts e CLI).
- [x] Melhorar discovery com retry em `duckdb_storage.py`. # Corrected from transaction_manager.py based on my previous work.
- [x] Documentar testes manuais de conflito em `docs/manual_testing.md`.

#### Semanas 5-6 – Trust Protocol
- [x] Implementar Merkle tree em `transaction_manager.py`.
- [x] Verificar provas de Merkle.
- [x] Realizar trust check com amostragem criptográfica.
- [x] Criar discovery anti-Sybil em `session_manager.py`.
- [x] Executar testes de integração em `tests/test_system_dynamics.py`.

#### Semanas 7-9 – Automação + Testing
- [x] Configurar GitHub Action com PGP e sequence check.
- [x] Definir secrets `IA_ACCESS_KEY`, `PGP_PRIVATE_KEY` e `NETWORK_UUID`.
- [x] Automatizar detecção de mudanças e publicação.
- [x] Atualizar `README.md` com nova arquitetura.
- [x] Testes end-to-end em múltiplas redes.
- [x] Benchmarks comparando DuckDB x CSV.
- [x] Registrar resultado da security audit em `docs/security_audit.md`.

### 3. Critérios de Sucesso
- [ ] Zero perda de dados em conflitos.
- [ ] Resistência a Sybil acima de 95%.
- [ ] Sharding transparente para o usuário.
- [ ] Consultas abaixo de 5s em média.
- [ ] Auditoria externa aprovada.
- [ ] CI/CD com taxa >95%.
- [ ] Distribuição P2P via torrents.

### 4. Stakeholder Sign-off
- [ ] Aprovação arquitetural pelo Tech Lead.
- [ ] Auditoria de algoritmos pelo Security Lead.
- [ ] Alinhamento de roadmap pelo Product.
- [ ] Validação de CI/CD e deployment pelo DevOps.
- [ ] Registrar decisão final em `docs/decisions/`.

## P0 - Post-Pivot Cleanup & Refinement

### Critical Bug Fixes & Stability 🐛
- [ ] **Stabilize existing test suite (Pytest)** - Actively fixing test failures. Resolved several issues in `test_protocol_v2.py` related to data consistency for CLI subprocesses and corrected argument/UUID handling. Work ongoing for remaining assertion errors. *(Was [~])*
- [ ] **Path→hrönir mapping issues** in session commit workflow - Some aspects investigated/addressed by test fixes ensuring correct UUID generation (v5 for paths, content-based for hrönirs) and data handling logic, particularly in `test_sessions_and_cascade.py` and `test_protocol_v2.py`. *(Was [~])*
- [ ] **Automatic qualification** based on Elo ratings not working - Progress made. Test fixes for `initiating_fork_uuid` (ensuring valid UUIDv5) and ensuring data persistence for CLI interactions in `test_protocol_v2.py` are crucial for testing qualification logic. Failures in qualification are still observed in tests like `test_legitimate_promotion_and_mandate_issuance`. *(Was [~])*
- [ ] **Integrity validation** for path→hrönir relationships - Partially addressed by fixes in test data generation (correct UUID types and sources) and consistency checks for `prev_uuid` / `current_hrönir_uuid` during path construction in tests. *(Was [~])*
- [ ] **Error messages** need more context about predecessors

### Enhanced Data Models 🏗️
- [ ] **Session models** (`Session`, `SessionDossier`, `SessionDuel`) for type-safe session management
- [ ] **Hrönir content model** (`Hronir`) for story content with metadata and validation
- [ ] **Canonical path models** (`CanonicalPath`, `CanonicalEntry`) for structured canonical state
- [ ] **Enhanced transaction model** (`TransactionContent`, `SessionVerdict`) for structured transaction content
- [ ] **Duel/ranking models** (`DuelResult`, `RankingEntry`) for Elo system type safety
- [ ] **Mandate/qualification models** (`Mandate`, `QualificationCriteria`) for validation logic
- [ ] **Configuration models** (`SystemConfig`, `StoragePaths`) for system administration
- [ ] **Validation models** (`ValidationIssue`, `DataIntegrityReport`) for debugging and maintenance

### Essential CLI Commands 📟
- [ ] **`hronir validate-paths`** command for debugging path integrity
- [ ] **`hronir tutorial`** command that executes complete workflow demonstration
- [ ] **`hronir dev-qualify PATH_UUID`** for testing purposes

### System Robustness
- [ ] Add comprehensive **automated testing** for full workflow
- [ ] Implement **detailed logging** for system debugging
- [ ] Create **debug mode** that shows internal mappings
- [ ] Add **path tree visualization** functionality

### Documentation & UX
- [ ] Improve **README with practical examples**
- [ ] Update **CLAUDE.md** with current architecture (Note: AGENTS.md redirects here, so this is important)
- [ ] Create **complete workflow guide** (store → path → session → vote)
- [ ] Fix **CLI parameter documentation** inconsistencies

### Performance & Quality
- [ ] **Pre-commit hooks** resolution for clean development setup
- [ ] **Error handling** improvements for file operations
- [ ] **Code refactoring** to simplify complex functions in `cli.py`
- [ ] **Type annotation** coverage completion

### Phase 1: Enhanced CLI Experience (from PLANNED FEATURES)
- [ ] **Interactive tutorial mode** with step-by-step guidance
- [ ] **Rich output formatting** with better visualization
- [ ] **Progress indicators** for long-running operations
- [ ] **Configuration management** for user preferences

---

## P1 – Immediate Priorities
(This section is now superseded by "P0 - Post-Pivot Cleanup & Refinement". Items moved.)

### Terminology Cleanup 🔥
- [x] **Complete fork→path terminology replacement** using regex `\Wfork\W` patterns throughout codebase
- [x] **Update all documentation** to use path terminology consistently
- [x] **Fix CLI command references** in help text and examples

---

## 📋 **HIGH PRIORITY TASKS**
(This section is now superseded by "P0 - Post-Pivot Cleanup & Refinement". Items moved.)

---

## 🎯 **PLANNED FEATURES**

### Phase 2: Web Interface
- [ ] **Dashboard** for real-time protocol state visualization
- [ ] **Interactive reader** to navigate canonical and alternative paths
- [ ] **Session interface** for web-based judgment participation
- [ ] **Analytics dashboard** for path performance metrics

### Phase 3: Export & Distribution
- [ ] **EPUB generation** with interactive path selection
- [ ] **HTML export** for static site generation
- [ ] **REST API** endpoints for external integrations
- [ ] **Mobile-responsive** reading interfaces

### Phase 4: Advanced AI Systems
- [ ] **Multi-agent protocols** for coordinated AI interactions
- [ ] **Specialized agents** for different genres or styles
- [ ] **Learning systems** that adapt based on success rates
- [ ] **Human-AI collaboration** in judgment sessions

### Phase 5: Scalability
- [ ] **Optional PostgreSQL backend** for large datasets
- [ ] **Distributed processing** capabilities
- [ ] **Caching systems** for performance optimization
- [ ] **Archive management** strategies

---

## 🔬 **RESEARCH & EXPERIMENTAL**

### Narrative Science
- [ ] **Emergence metrics** to measure narrative coherence
- [ ] **Reader psychology** analysis of preference patterns
- [ ] **Collaborative dynamics** study of human-AI interaction
- [ ] **Temporal analysis** of canonical path evolution

### Protocol Extensions
- [ ] **Multi-narrative support** for parallel encyclopedia instances
- [ ] **Cross-pollination** mechanisms for chapter sharing
- [ ] **Versioning systems** for protocol upgrades
- [ ] **Governance models** for community-driven evolution

---

## ✅ **COMPLETED ACHIEVEMENTS**

### Core Architecture ✅
- [x] **Protocol v2** fully implemented with pandas data management
- [x] **UUID-based storage** system with deterministic chapter storage
- [x] **Path management** with position-based narrative connections
- [x] **Elo ranking system** with sophisticated duel mechanics
- [x] **Session management** with static dossiers and temporal cascades
- [x] **Transaction ledger** with immutable blockchain-like recording

### Fork → Path Migration ✅
- [x] **Pydantic models** updated from Fork to Path
- [x] **Data manager** refactored for path terminology
- [x] **Storage layer** updated with new function signatures
- [x] **Ratings system** migrated to path-based calculations
- [x] **CLI commands** renamed (fork → path, list-forks → list-paths)
- [x] **Directory structure** renamed (the_garden → narrative_paths)
- [x] **CSV headers** updated (fork_uuid → path_uuid)
- [x] **Documentation** comprehensively updated

### Development Infrastructure ✅
- [x] **Repository structure** with proper Python package
- [x] **Development environment** with uv package manager
- [x] **Code quality** with ruff linting and formatting
- [x] **Testing framework** with comprehensive protocol validation
- [x] **AI integration** with Gemini-based content generation

### CLI Interface ✅
- [x] **Core commands** implemented (`store`, `ranking`, `audit`, `clean`)
- [x] **Session commands** implemented (`session start`, `session commit`)
- [x] **Path management** commands (`path`, `list-paths`, `path-status`)
- [x] **Advanced features** (`recover-canon`, `synthesize`, `metrics`)
- [x] **Validation systems** for comprehensive content checking

---

## 📊 **SUCCESS METRICS**

- **Protocol Stability**: Zero data corruption incidents
- **Code Quality**: All ruff checks pass, comprehensive type coverage
- **Generation Quality**: AI-generated content passes validation >95%
- **Session Efficiency**: Judgment sessions complete without errors
- **Canonical Coherence**: Temporal cascades maintain narrative consistency
- **Developer Experience**: New contributors can onboard within 1 hour
- **Documentation Accuracy**: All CLI examples work as documented

---

## 🗓️ **CURRENT STATUS**

**Phase**: Post-Pivot Cleanup & Refinement
**Priority**: P0 - Post-Pivot Cleanup & Refinement
**Next Milestone**: Complete P0 tasks.

**Architecture**: ✅ Pandas-based data management with CSV storage. (P2P/DuckDB implementation from Pivot Plan v2.0 is complete).
**Terminology**: ✅ Major migration complete.
**CLI Interface**: ✅ Functional with path-based commands.
**Documentation**: 🚧 Updated for new terminology, refinement needed. (See P0 section)
**Testing**: 🚧 Core functionality validated, test suite stabilization ongoing. (See P0 section)
**Quality**: 🚧 Ruff checks pass (after recent fixes), type coverage improving. (See P0 section)

**Ready for**: Focusing on "P0 - Post-Pivot Cleanup & Refinement" tasks.

---

## 🔥 NEW HIGH PRIORITY TASKS (Identified YYYY-MM-DD)

The following tasks have been identified as high priority based on recent test suite results and code review. They address critical failures and inconsistencies in core protocol functionality.

- [ ] **Fix `determine_next_duel_entropy` Argument Error in Session Start**
    - **Context**: Multiple tests in `test_protocol_v2.py` (e.g., `test_mandate_double_spend_prevention`, `test_temporal_cascade_trigger`) and `test_sessions_and_cascade.py` (e.g., `test_scenario_1_dossier_and_limited_verdict`) are failing with a `TypeError: determine_next_duel_entropy() got an unexpected keyword argument 'session'`. This error occurs during the `hronir session start` CLI command execution within these tests.
    - **Problem**: The `determine_next_duel_entropy` function, likely called by `session_manager.create_session_dossier` or a related function, is being invoked with an incorrect set of arguments. The `session` argument seems to be unexpected.
    - **Impact**: This is a critical failure blocking the session start mechanism, which is fundamental for users/agents to participate in judgment sessions and influence the narrative.
    - **Action**:
        1. Investigate the call stack leading to `determine_next_duel_entropy` within the `session start` workflow.
        2. Identify where the unexpected `session` argument is introduced or if the function signature has changed and call sites were not updated.
        3. Correct the function call or the function signature to align them. Ensure that `determine_next_duel_entropy` receives all necessary context (e.g., position, predecessor hrönir, existing ratings, canonical path) to correctly select duels.
        4. Verify the fix by ensuring the aforementioned tests pass.

- [ ] **Correct Mandate ID Generation and Verification**
    - **Context**: The test `test_legitimate_promotion_and_mandate_issuance` in `test_protocol_v2.py` fails due to a mismatch between the generated `mandate_id` for a qualified path and the expected `mandate_id`. The test expects a Blake3 hash of `path_uuid + last_tx_hash_before_qualifying_tx`, but the actual `mandate_id` stored on the `PathModel` is a UUID (e.g., `e9e37a68-e268-4e1c-9375-8e7a800c8655`).
    - **Problem**: There's a discrepancy in the logic for generating/assigning `mandate_id` in `transaction_manager.record_transaction` (which updates path status to QUALIFIED) and the test's expectation. The `PathModel.mandate_id` is typed as `Optional[uuid.UUID]`, but the test expects a Blake3-derived string.
    - **Impact**: Incorrect mandate ID generation or validation could compromise the integrity of the "Tribunal of the Future" mechanism, potentially allowing unauthorized sessions or issues with tracking mandate usage.
    - **Action**:
        1. Clarify the intended algorithm for `mandate_id` generation: Is it a UUID or a hash-based string? The `PathModel` suggests UUID.
        2. If UUID: Update the test expectation in `test_legitimate_promotion_and_mandate_issuance` to check for a valid UUID, not a specific Blake3 hash. The current promotion logic in `transaction_manager.record_transaction` assigns `uuid.uuid4()` to `mandate_id`.
        3. If Blake3-based string: Update `PathModel.mandate_id` type to `Optional[str]` and modify `transaction_manager.record_transaction` to generate the mandate ID using the Blake3 algorithm as per the test's original expectation.
        4. Ensure the chosen method is consistently applied and validated.

- [ ] **Resolve Failures in Ranking and Filtering Logic**
    - **Context**: Numerous tests in `test_ranking_filtering.py` (7 failures, e.g., `test_get_ranking_filters_by_canonical_predecessor`, `test_get_ranking_no_votes_for_heirs`) and `test_ratings_ranking.py` (`test_get_ranking`) are failing. These tests generally expect non-empty DataFrames with specific path rankings, but are receiving empty DataFrames.
    - **Problem**: This indicates a systemic issue in `ratings.get_ranking` or the underlying data loading/filtering within the `DataManager` (Pandas or DuckDB backend). Paths might not be loaded correctly, votes might not be applied, or filtering logic (e.g., by predecessor hrönir) might be malfunctioning.
    - **Impact**: The ranking system is fundamental to determining path quality, duel selection, and ultimately the canonical path. Failures here mean the core selection mechanism is broken.
    - **Action**:
        1. Debug `ratings.get_ranking` and its interaction with `DataManager` (specifically how paths and votes are loaded and provided for ranking calculations).
        2. Verify that CSV/data file parsing in `PandasDataManager` (and `DuckDBDataManager` if active) correctly loads all necessary data for the test scenarios.
        3. Check filtering logic within `get_ranking` or its helper functions, especially filtering by `predecessor_hrönir_uuid` and handling of position 0.
        4. Ensure Elo calculations are performed correctly and that paths with and without votes are handled as expected by the tests.

- [ ] **Fix Narrative Consistency Check for Cyclic Graphs**
    - **Context**: The test `test_is_narrative_consistent` in `test_graph_logic.py` fails with `AssertionError: assert not True` when checking a graph known to contain a cycle. The function `graph_logic.is_narrative_consistent()` is expected to return `False` for a cyclic graph.
    - **Problem**: The current implementation of `is_narrative_consistent` (or its underlying cycle detection, likely using NetworkX) is incorrectly identifying the test's cyclic graph as non-cyclic (consistent).
    - **Impact**: If cycles are not correctly detected, the system might allow impossible narrative loops, compromising logical coherence.
    - **Action**:
        1. Review the graph construction logic within `is_narrative_consistent` to ensure nodes and edges correctly represent path dependencies.
        2. Verify that the NetworkX function used for cycle detection (e.g., `nx.is_directed_acyclic_graph` or `nx.simple_cycles`) is appropriate and correctly interpreted.
        3. Debug with the specific cyclic data from `test_is_narrative_consistent` to pinpoint why the cycle is not being detected.

- [ ] **Implement Functional PGP Signing for Snapshots**
    - **Context**: The "Security audit de Merkle + PGP" task was marked as complete in the Pivot Plan v2.0. However, the actual PGP signing mechanism in `transaction_manager.py` (`sign_manifest_pgp`) is a placeholder that returns a dummy signature and logs a warning.
    - **Problem**: If PGP signatures are a required security feature for snapshot authenticity and integrity (as implied by including it in the audit and manifest structure), the current placeholder is insufficient.
    - **Impact**: Snapshots lack a verifiable cryptographic signature, potentially undermining trust in the distributed P2P data sharing model.
    - **Action**:
        1. Integrate a Python PGP library (e.g., `python-gnupg` or `pgpy`).
        2. Implement the `sign_manifest_pgp` function to use the chosen library to sign manifest data using a configured PGP private key.
        3. Implement a corresponding verification function (e.g., `verify_manifest_pgp_signature`) that can be used by clients or other nodes to verify snapshot integrity.
        4. Address PGP key management: How will the PGP private key be provided to the system (e.g., env variable, file, HSM)? This needs to be documented and securely handled.
        5. Add tests for successful PGP signing and verification, and for failure modes (e.g., bad signature, wrong key).
        6. Update GitHub Actions that might publish snapshots to include PGP key configuration and signing steps.

[end of TODO.md]
