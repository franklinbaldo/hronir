# Plano de Arquitetura Distribuída

Este documento apresenta o plano de pivotagem para uma arquitetura distribuída da Enciclopédia Hrönir. O texto está em português e resume todas as etapas discutidas na mensagem do usuário.

## 1. Objetivo

Garantir que o protocolo possa ser executado por vários nós independentes, mantendo consistência do histórico e permitindo colaboração descentralizada.

## 2. Etapas do Plano

1. **Transição para Banco de Dados Local Unificado**
   - Consolidar leituras e escritas em um único banco SQLite por nó.
   - Gerar arquivos CSV apenas para versões e auditoria.

2. **Sincronização entre Nós**
   - Utilizar repositórios Git para propagar atualizações do banco e dos CSVs.
   - Definir política de resolução de conflitos baseada na temporalidade dos registros.

3. **API Padronizada**
   - Criar camada de API (FastAPI) para interações entre nós e aplicações externas.
   - Autenticar requisições e registrar operações no ledger local.

4. **Fila de Eventos Distribuída**
   - Introduzir mensageria (por exemplo, Redis Streams) para propagar novos caminhos e sessões.
   - Garantir processamento idempotente de cada evento.

5. **Validação de Consistência**
   - Rodar rotina de `audit` em cada nó para garantir integridade dos dados recebidos.
   - Bloquear commits inválidos e solicitar retransmissão.

6. **Interface de Monitoramento**
   - Implementar painel web básico para visualizar estado do nó e sincronização.
   - Expor métricas de saúde (lags, última sessão aplicada, etc.).

## 3. Próximos Passos

- Prototipar sincronização Git automatizada.
- Definir esquema de mensagens e assinaturas digitais.
- Testar replicação em ambiente controlado com dois nós.

