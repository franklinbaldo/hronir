# TODO.md · Development Roadmap — **Hrönir Encyclopedia**

This document outlines the development roadmap for the **Hrönir Encyclopedia** project. The core **Protocol v2** architecture is implemented with pandas-based data management and narrative path lifecycle management.

---

## 🚨 **IMMEDIATE PRIORITIES**

### Terminology Cleanup 🔥
- [x] **Complete fork→path terminology replacement** using regex `\Wfork\W` patterns throughout codebase
- [x] **Update all documentation** to use path terminology consistently
- [x] **Fix CLI command references** in help text and examples

### Critical Bug Fixes 🐛
- [~] **Stabilize existing test suite (Pytest)** - Actively fixing test failures. Resolved several issues in `test_protocol_v2.py` related to data consistency for CLI subprocesses and corrected argument/UUID handling. Work ongoing for remaining assertion errors.
- [~] **Path→hrönir mapping issues** in session commit workflow - Some aspects investigated/addressed by test fixes ensuring correct UUID generation (v5 for paths, content-based for hrönirs) and data handling logic, particularly in `test_sessions_and_cascade.py` and `test_protocol_v2.py`.
- [~] **Automatic qualification** based on Elo ratings not working - Progress made. Test fixes for `initiating_fork_uuid` (ensuring valid UUIDv5) and ensuring data persistence for CLI interactions in `test_protocol_v2.py` are crucial for testing qualification logic. Failures in qualification are still observed in tests like `test_legitimate_promotion_and_mandate_issuance`.
- [~] **Integrity validation** for path→hrönir relationships - Partially addressed by fixes in test data generation (correct UUID types and sources) and consistency checks for `prev_uuid` / `current_hrönir_uuid` during path construction in tests.
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

---

## 📋 **HIGH PRIORITY TASKS**

### System Robustness
- [ ] Add comprehensive **automated testing** for full workflow
- [ ] Implement **detailed logging** for system debugging
- [ ] Create **debug mode** that shows internal mappings
- [ ] Add **path tree visualization** functionality

### Documentation & UX
- [ ] Improve **README with practical examples**
- [ ] Update **CLAUDE.md** with current architecture
- [ ] Create **complete workflow guide** (store → path → session → vote)
- [ ] Fix **CLI parameter documentation** inconsistencies

### Performance & Quality
- [ ] **Pre-commit hooks** resolution for clean development setup
- [ ] **Error handling** improvements for file operations
- [ ] **Code refactoring** to simplify complex functions in `cli.py`
- [ ] **Type annotation** coverage completion

---

## 🎯 **PLANNED FEATURES**

### Phase 1: Enhanced CLI Experience
- [ ] **Interactive tutorial mode** with step-by-step guidance
- [ ] **Rich output formatting** with better visualization
- [ ] **Progress indicators** for long-running operations
- [ ] **Configuration management** for user preferences

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

**Phase**: Post-Migration Cleanup & Enhancement  
**Priority**: Immediate terminology cleanup and bug fixes  
**Next Milestone**: Complete fork→path migration and robust CLI workflow

**Architecture**: ✅ Pandas-based data management with CSV storage  
**Terminology**: 🚧 Major migration complete, cleanup in progress  
**CLI Interface**: ✅ Functional with path-based commands  
**Documentation**: 🚧 Updated for new terminology, refinement needed  
**Testing**: ✅ Core functionality validated  
**Quality**: 🚧 Linting issues resolved, type coverage improving  

**Ready for**: Web interface development and enhanced user experience