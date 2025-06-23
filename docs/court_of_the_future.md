# 🔒 Tribunal do Futuro – Defesa Contra o Mantenedor Malicioso (v3.0 – sem dependências externas)

## 1. Problema Central
O mantenedor do ledger pode:
- **Reordenar** merges manualmente  
- **Bloquear/censurar** branches indesejados  
- **Rollbacks** forçar histórico alternativo  

Tudo isso mina a confiança na narrativa emergente.

---

## 2. Objetivos da Solução
1. **Ordens objetivas**: merge só por regra interna.  
2. **Liveness garantido**: nenhum ramo preso indefinidamente.  
3. **Resistência a splits artificiais**: divisão não dribla a regra.  
4. **Imutabilidade interna**: sem push-force bem-sucedido.  
5. **Zero dependências externas**: nada de PoW ou serviços fora do protocolo.

---

## 3. Regra Principal: Merge Só Entre Ramos do Mesmo Tamanho Válido
```yaml
Rule_Merge_Same_Size:
  branches_must_be: QUALIFIED
  merge_condition: valid_tx_count_A == valid_tx_count_B
````

---

## 4. Garantia de Liveness

* **Timeout T = 10 epochs**
  Após T epochs sem par exato, **merge** com bucket adjacente (±1), mantendo densidade de transações válidas.
* **Prova**: em qualquer conjunto finito, pelo menos um merge ocorre em ≤ T+1 ciclos.

---

## 5. Defesa Contra Particionamento Artificial

* **K\_max\_splits = 2**
  Cada branch QUALIFIED só pode ser dividido até 2×; mais → `EXPIRED`.
* **Só contam transações válidas**
  Duelo vencedor ou Elo ≥ mediana; no-ops são descartados antes de contar `valid_tx_count`.

---

## 6. Segurança de Rollback – Protocolo Interno

* **Merge bidirecional**
  Cada super-block registra `parent_A` e `parent_B`.
* **Verificação de ancestors**
  Clientes recusam qualquer cadeia cujo HEAD refira pai ausente no histórico local.
* **Rejeição de force-push**
  Se mantiver histórico faltando blocks antigos, o CLI não avança o HEAD.

---

## 7. Parâmetros Explícitos

| Parâmetro          | Valor Padrão | Descrição                                     |
| ------------------ | -----------: | --------------------------------------------- |
| `T_timeout_epochs` |           10 | Epochs até merge fallback ±1 tamanho          |
| `K_max_splits`     |            2 | Splits permitidos por branch antes de expirar |
| `μ_position`       |      mediana | Elo mínimo para contar transação como válida  |

---

## 8. Fluxo Completo (incorpora SC.13)

1. **Fork criado** → `PENDING`
2. **Duelos internos** → atinge limiar → `QUALIFIED`
3. **Entra em waiting\_branches\[valid\_tx\_count]**
4. **Merge** por Regra 3 ou fallback Regra 4
5. **Super-block** com `parent_A`+`parent_B` → append-only

---

## 9. Exemplos Ilustrados

### 9.1 Honesto

```text
E1: A(3) QUALIFIED → espera  
E2: B(3) QUALIFIED → merge A↔B → HEAD → progresso  
```

### 9.2 Malicioso

```text
- Tenta split D(4)→D1(2)+D2(2): cada metade perde densidade → dificil QUALIFY  
- Tenta push-force sem parent_X: CLI recusa por missing ancestor  
```

---

## 10. Conclusão

Sem notarização externa ou multisig, este design:

* **Elimina discricionariedade** do mantenedor
* **Garante liveness** via timeout/fallback
* **Impede rollback** com verificação interna de ancestors
* **Mantém simplicidade** e coerência com filosofia Hrönir

Pronto para v3.0-alpha, totalmente self-contained.

## Steelmanning da “Regra do Mesmo Tamanho”

> **Princípio-chave** Só é permitido fundir (merge) dois ramos quando ambos têm **exatamente o mesmo número de transações válidas**. Enquanto o par não aparece, cada ramo fica em espera.

---

### 1 · Por que essa regra é elegantemente robusta

| Vantagem                             | Mecanismo                                                                                                                                      | Resultado                                                                                                                |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Neutraliza o “avalanche merge”**   | Cada merge combina *duas* cadeias que já custaram esforço narrativo idêntico.                                                                  | Um bot não consegue atropelar a linha do tempo com uma super-cadeia gigante: ela estagna até surgir igual-em-peso.       |
| **Sybil vira autodestrutivo**        | Para ganhar influência, o adversário precisa criar **dois** ramos do mesmo tamanho — dobrando o custo narrativo/computacional.                 | O ROI de spam cai pela metade de cara; e cai mais a cada round, pois o tamanho exigido cresce exponencialmente (2→4→8…). |
| **Seleção darwiniana intra-ramo**    | Inflar com transações inúteis **não** é isca gratuita: só as válidas contam, e o ramo internaliza seu próprio lixo (é purgado antes do merge). | O atacante que infla perde densidade de “qualidade por bloco”, dificultando futuras vitórias no Elo.                     |
| **Ordenação determinística natural** | “Quem chega primeiro” não importa: pares são formados por **tamanho**, não por timestamp, evitando corridas maliciosas.                        | Elimina a manipulação de relógio e flash-publishing.                                                                     |
| **Escalonamento binário**            | O sistema vira um torneio de bracket: 2 → 4 → 8 → 16… blocos.                                                                                  | Crescimento log₂ mantém verificação barata e previsível.                                                                 |
| **Liveness sob controle**            | Um ramo ímpar só espera até aparecer outro de mesmo tamanho; se ninguém produzir, significa que a cadeia perdeu relevância.                    | Tempo de espera vira *proxy* de interesse: conteúdo sem eco morre por inanição natural, sem exigir árbitro.              |

---

### 2 · Resposta aos principais ataques

1. **“O bot corta a própria cadeia em dois pedaços iguais.”**
   *Corte tem preço:* cada metade sacrifica profundidade narrativa (menos vitórias, Elo menor) ⇒ menor chance de vencer duelos futuros. Além disso, cada divisão reinicia o relógio de espera; não há ganho instantâneo.

2. **“Ele infla com no-ops.”**
   Antes do merge roda-se `garbage_collect()` que descarta transações sem duelo ou com Elo < *ε*. Como só as válidas contam para o tamanho, o inflador só troca spam por atraso.

3. **“Liveness falha se o número de ramos for ímpar.”**
   Estatisticamente, em rede aberta sempre surge novo ramo — mas para casos extremos adiciona-se **timeout T**: se esperar > T epochs, o ramo menor é *promovido* a par do maior imediato (garante progresso).

---

### 3 · Integração com as regras existentes

| Camada existente                     | Ajuste mínimo                                                                                                   |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **Qualificação por Mérito (SC .13)** | Continua igual: só ramos QUALIFIED entram na fila de merge.                                                     |
| **Mandate único por fork**           | O *mandate* só nasce após primeiro merge bem-sucedido. Multiplica a fricção para Sybil.                         |
| **Enum de status**                   | `WAITING_FOR_PAIR` novo status intermediário.                                                                   |
| **Ledger append-only**               | Ao fundir, grava um “super-bloco” com `parent_A`, `parent_B`, `size=N`. O hash desse super-bloco é o novo head. |

---

### 4 · Algoritmo em pseudocódigo

```python
def try_merge(branch):
    N = branch.valid_tx_count
    bucket = waiting_branches[N]

    if bucket:
        mate = bucket.pop()
        merged = merge_pair(branch, mate)  # intercalar por UUID ou Elo
        gc_purge(merged)                   # remove no-ops antes de fixar tamanho
        ledger.append(merged.superblock)
        return merged
    else:
        waiting_branches[N].push(branch)
        branch.status = WAITING_FOR_PAIR
        return None
```

*Tempo total de verificação:*
`O(log₂ total_tx)` – cresce suavemente, ideal para agentes off-chain de baixo poder.

---

### 5 · Caminho de adoção incremental

1. **Adicionar campo `valid_tx_count`** (já computado na qualificação).
2. **Implementar fila `waiting_branches`** indexada por tamanho.
3. **Escrever `garbage_collect()`** determinístico, rule-based.
4. **Criar teste “imbalance flood”:** 100 ramos de tamanhos aleatórios ⇒ sistema converge.
5. **Lançar test-net** com bounty: win se quebrar a liveness sem gastar stake real.

---

### 6 · Por que vale experimentar

* Concretiza a estética “babel binária” — cada merge dobra a *granularidade histórica*.
* É **trivial de auditar**: basta contar linhas; nenhum hash-score obscuro.
* Mantém a filosofia de “fricção como filtro”, mas usa fricção **simétrica**: o adversário paga o mesmo pedágio que qualquer agente honesto.

---

**Resumo ultra-claro:** A regra “mesmo tamanho” cria um funil binário que exige trabalho narrativo pareado, corta spam por desinteresse econômico e mantém cadeia auditável sem trusted score. Não é bala de prata, mas é um experimento conceitualmente coeso e simples de implementar — vale o sandbox.
