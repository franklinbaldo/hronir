# TODO · Pivot Plan v2.0

Esta lista consolida as tarefas propostas em [pivot_plan_v2.md](docs/pivot_plan_v2.md) e indica onde agir no repositório.

## 1. Para Decisão
- [ ] **Revisão técnica do plano v2.0**
  - Ler `docs/pivot_plan_v2.md` e registrar parecer em `docs/decisions/`
- [ ] **Aprovação de 3 semanas extras**
  - Atualizar cronograma no `README.md`
- [ ] **Security audit de Merkle + PGP**
  - Revisar `hronir_encyclopedia/transaction_manager.py` e `duckdb_storage.py`
- [ ] **Definir critérios de sucesso**
  - Criar seção no `README.md` com métricas de aceitação

## 2. Cronograma de Execução

### Semanas 1-2 – Base + Sharding
- [ ] Instalar `duckdb`, `internetarchive` e `zstd` em `pyproject.toml`
- [ ] Criar `scripts/migrate_to_duckdb.py --backup --enable-sharding`
- [ ] Implementar `hronir_encyclopedia/sharding.py` com `ShardingManager`
- [ ] Refatorar `hronir_encyclopedia/storage.py` para usar `DuckDBDataManager` e sharding
- [ ] Salvar backup dos CSVs em `data/backup/`
- [ ] Cobrir migração com testes em `tests/`

### Semanas 3-4 – Conflicts + Security
- [ ] Implementar locking por sequence number em `transaction_manager.py`
- [ ] Adicionar comando `hronir sync --retry` em `cli.py`
- [ ] Criar comando `hronir push` com verificação de conflitos
- [ ] Exigir assinatura PGP nas operações (`scripts/` e `cli.py`)
- [ ] Melhorar discovery com retry em `duckdb_storage.py`
- [ ] Documentar testes manuais de conflito em `docs/manual_testing.md`

### Semanas 5-6 – Trust Protocol
- [ ] Implementar Merkle tree em `transaction_manager.py`
- [ ] Verificar provas de Merkle
- [ ] Realizar trust check com amostragem criptográfica
- [ ] Criar discovery anti-Sybil em `session_manager.py`
- [ ] Executar testes de integração em `tests/test_system_dynamics.py`

### Semanas 7-9 – Automação + Testing
- [ ] Configurar GitHub Action com PGP e sequence check (`.github/workflows/`)
- [ ] Definir secrets `IA_ACCESS_KEY`, `PGP_PRIVATE_KEY` e `NETWORK_UUID`
- [ ] Automatizar detecção de mudanças e publicação
- [ ] Atualizar `README.md` com nova arquitetura
- [ ] Testes end-to-end em múltiplas redes
- [ ] Benchmarks comparando DuckDB x CSV
- [ ] Registrar resultado da security audit em `docs/security_audit.md`

## 3. Critérios de Sucesso
- [ ] Zero perda de dados em conflitos
- [ ] Resistência a Sybil acima de 95%
- [ ] Sharding transparente para o usuário
- [ ] Consultas abaixo de 5s em média
- [ ] Auditoria externa aprovada
- [ ] CI/CD com taxa >95%
- [ ] Distribuição P2P via torrents

## 4. Stakeholder Sign-off
- [ ] Aprovação arquitetural pelo Tech Lead
- [ ] Auditoria de algoritmos pelo Security Lead
- [ ] Alinhamento de roadmap pelo Product
- [ ] Validação de CI/CD e deployment pelo DevOps
- [ ] Registrar decisão final em `docs/decisions/`
