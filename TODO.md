# TODO.md · Development Roadmap — **Hrönir Encyclopedia**

This document outlines the development roadmap for the **Hrönir Encyclopedia** project. The core **Protocol v2** architecture has been implemented, featuring sophisticated judgment sessions, temporal cascades, and fork lifecycle management.

## ✅ Completed Core Implementation

### Phase 0 — Foundation ✅
- [x] Repository structure with `hronir_encyclopedia/` Python package
- [x] Data architecture: `the_library/`, `data/`, `forking_path/`, `ratings/`
- [x] Essential files: `.gitignore`, `LICENSE`, `pyproject.toml`, `uv.lock`
- [x] Development environment with `uv` package manager

### Phase 1 — Protocol v2 Core ✅
- [x] **Storage System**: UUID-based deterministic chapter storage
- [x] **Fork Management**: Position-based forking with UUID generation
- [x] **Elo Ranking System**: Sophisticated rating calculations with duel mechanics
- [x] **Session Management**: Judgment sessions with static dossiers
- [x] **Transaction Ledger**: Immutable blockchain-like transaction recording
- [x] **Temporal Cascade**: Canonical path recalculation system

### Phase 2 — CLI Interface ✅
- [x] **Core Commands**: `store`, `ranking`, `get-duel`, `audit`, `clean`
- [x] **Session Commands**: `session start`, `session commit`
- [x] **Advanced Features**: `recover-canon`, `synthesize`, `metrics`
- [x] **Validation**: Comprehensive chapter and fork validation
- [x] **Status Management**: Fork lifecycle (PENDING → QUALIFIED → SPENT)

### Phase 3 — AI Integration ✅
- [x] **Gemini Integration**: Automated chapter generation
- [x] **Semantic Extraction**: Narrative space analysis
- [x] **Prompt Building**: Synthesis from accumulated narrative
- [x] **Auto-voting**: AI agent participation in duels

### Phase 4 — Quality Assurance ✅
- [x] **Test Suite**: Comprehensive protocol testing
- [x] **Validation Logic**: Fake content detection and removal
- [x] **Pre-commit Hooks**: Automated validation and cleanup
- [x] **Linting**: Ruff and Black code formatting

---

## 🚧 Critical Missing Components (Discovered via Testing)

### Phase 5 — Core CLI Gaps 🔥 **HIGH PRIORITY**
- [x] **Fork Creation Command**: `hronir fork` with clean `--source` → `--target` parameters ✅ COMPLETED
- [x] **Fork Listing Command**: `hronir list-forks` to show existing narrative structure ✅ COMPLETED
- [ ] **Fork Status Command**: `hronir fork-status` to check individual fork state
- [ ] **Quick Start Command**: `hronir init-test` to create sample narrative for testing
- [ ] **System Status Command**: `hronir status` to show current canonical path and system state

### Phase 6 — Architectural Cleanup 🔧
- [ ] **Remove Creator Attribution**: Eliminate `creator_id` from forking path structure (pure meritocracy)
- [ ] **Fix CLI Parameter Mismatches**: `get_ranking()` function signature vs CLI usage
- [ ] **Empty CSV Handling**: Graceful handling of empty CSV files in database loading
- [ ] **Storage Parameter Cleanup**: Remove outdated `--prev` parameter from store command ✅ COMPLETED
- [ ] **Anonymous Forking**: Ensure all fork creation is content-based, not author-based

### Phase 7 — Documentation & UX 🎯
- [ ] **Fix Documentation Confusion**: Remove all `--prev` parameter references from documentation
- [ ] **Update Fork Examples**: Replace confusing hrönir/fork terminology with clear source → target examples
- [ ] **Node/Edge Distinction**: Clarify hrönirs (nodes) vs forking_paths (edges) in docs
- [ ] **Complete Workflow Guide**: "Store → Fork → Vote" tutorial with clean CLI examples
- [ ] **Remove Creator Attribution**: Eliminate all references to creator/author tracking (pure meritocracy)
- [ ] **CLI Reference**: Complete command reference with new `--source` `--target` parameters
- [ ] **Architecture Overview**: Visual diagram of hybrid storage system

---

## 🎯 Planned Features

### Phase 7 — User Interfaces
- [ ] **Web Dashboard**: Real-time protocol state visualization
- [ ] **Interactive Reader**: Navigate canonical and alternative paths
- [ ] **Session Interface**: Web-based judgment session participation
- [ ] **Analytics Dashboard**: Fork performance and canonical path evolution

### Phase 8 — Export & Distribution
- [ ] **EPUB Generation**: Interactive books with path selection
- [ ] **HTML Export**: Static site generation for canonical narrative
- [ ] **API Endpoints**: REST API for external integrations
- [ ] **Mobile Reading**: Responsive interfaces for mobile devices

### Phase 9 — Advanced Agent Systems
- [ ] **Multi-Agent Protocols**: Coordinated AI agent interactions
- [ ] **Specialization**: Genre-specific or style-specific AI agents
- [ ] **Learning Systems**: Agents that adapt based on success rates
- [ ] **Human-AI Collaboration**: Hybrid judgment sessions

### Phase 10 — Scalability & Performance
- [ ] **Database Migration**: Optional PostgreSQL backend for large datasets
- [ ] **Distributed Processing**: Horizontal scaling for large narratives
- [ ] **Caching Systems**: Performance optimization for frequent operations
- [ ] **Archive Management**: Long-term storage strategies

---

## 🔬 Research & Experimental Features

### Narrative Science
- [ ] **Emergence Metrics**: Measure narrative coherence and inevitability
- [ ] **Reader Psychology**: Analysis of preference patterns
- [ ] **Collaborative Dynamics**: Study of human-AI creative interaction
- [ ] **Temporal Analysis**: How canonical paths evolve over time

### Protocol Extensions
- [ ] **Multi-Narrative Support**: Parallel encyclopedia instances
- [ ] **Cross-Pollination**: Chapter sharing between encyclopedia instances
- [ ] **Versioning Systems**: Protocol upgrade mechanisms
- [ ] **Governance Models**: Community-driven protocol evolution

---

## 🐛 Known Issues & Technical Debt

### Development Environment
- [x] **Code Quality Standards**: Zero-tolerance linting with ruff and black ✅ COMPLETED
- [x] **Documentation Accuracy**: Fixed CLI parameter inconsistencies ✅ COMPLETED  
- [ ] **Pre-commit Resolution**: Fix `core.hooksPath` conflicts for clean setup
- [ ] **Error Handling**: Improve robustness of file operations
- [ ] **Logging**: Implement structured logging throughout the system

### Protocol Robustness
- [ ] **Concurrency**: Handle concurrent session commits safely
- [ ] **Recovery**: Robust recovery from corrupted state
- [ ] **Validation**: Additional edge case handling in validation logic
- [ ] **Performance**: Optimize large dataset operations

### Code Quality
- [ ] **Refactoring**: Simplify complex functions in `cli.py`
- [ ] **Type Safety**: Complete type annotation coverage
- [ ] **Test Coverage**: Expand edge case testing  
- [ ] **Dependencies**: Regular security and compatibility updates

---

## 🗓️ Current Status (Protocol v2)

- **Core Architecture**: ✅ Protocol v2 fully implemented
- **CLI Interface**: ✅ Complete with session management
- **AI Integration**: ✅ Gemini-based generation active
- **Quality Assurance**: ✅ Comprehensive testing and validation
- **Documentation**: ✅ README, CLAUDE.md, and architecture docs complete

**Next Priority**: Web interface development and advanced agent systems.


temp:
     ☐ Investigar e corrigir mapeamento fork→hrönir no session commit
     ☐ Implementar qualificação automática baseada em Elo ratings
     ☐ Adicionar validação automática de integridade fork→hrönir
     ☐ Criar comando 'hronir validate-forks' para debug
     ☐ Melhorar mensagens de erro com mais contexto sobre predecessores
     ☐ Adicionar testes automatizados para fluxo completo
     ☐ Criar comando 'hronir tutorial' que executa fluxo completo
     ☐ Melhorar README com exemplos práticos e reais
     ☐ Adicionar logging detalhado para debug do sistema
     ☐ Criar comando 'hronir dev-qualify FORK_UUID' para testes
     ☐ Implementar modo debug que mostra mapeamentos internos
     ☐ Criar visualização da árvore de forks
---

## 📊 Success Metrics

- **Protocol Stability**: Zero data corruption incidents
- **Generation Quality**: AI-generated content passes validation >95%
- **Session Efficiency**: Judgment sessions complete without errors
- **Canonical Coherence**: Temporal cascades maintain narrative consistency
- **Developer Experience**: New contributors can onboard within 1 hour
