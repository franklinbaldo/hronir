import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

import math # Adicionado para math.log2
# from itertools import combinations # Não é mais explicitamente necessário para a estratégia de vizinhos


def _calculate_elo_probability(elo_a: float, elo_b: float) -> float:
    """Calcula a probabilidade de A vencer B."""
    return 1 / (1 + 10**((elo_b - elo_a) / 400))

def _calculate_duel_entropy(elo_a: float, elo_b: float) -> float:
    """Calcula a entropia de Shannon para um duelo Elo."""
    p_a = _calculate_elo_probability(elo_a, elo_b)
    if p_a == 0 or p_a == 1: # Evita math.log2(0)
        return 0.0 # Retorna 0.0 para consistência de tipo float
    p_b = 1 - p_a
    # A verificação de p_b == 0 é implicitamente coberta por p_a == 1.
    return - (p_a * math.log2(p_a) + p_b * math.log2(p_b))


def record_vote(
    position: int,
    voter: str,
    winner: str,
    loser: str,
    base: Path | str = "ratings",
    conn: Engine | None = None,
) -> None:
    """Append a vote to the ratings table."""
    if conn is not None:
        table = f"position_{position:03d}"
        with conn.begin() as con:
            con.exec_driver_sql(
                f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    uuid TEXT,
                    voter TEXT,
                    winner TEXT,
                    loser TEXT
                )
                """
            )
            con.exec_driver_sql(
                f"INSERT INTO `{table}` (uuid, voter, winner, loser) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), voter, winner, loser),
            )
        return

    base = Path(base)
    base.mkdir(exist_ok=True)
    csv_path = base / f"position_{position:03d}.csv"

    row = {
        "uuid": str(uuid.uuid4()),
        "voter": voter,
        "winner": winner,
        "loser": loser,
    }
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        df = pd.DataFrame([row])
    df.to_csv(csv_path, index=False)


def get_ranking(
    position: int,
    canonical_predecessor_uuid: str | None, # None para Posição 0
    forking_path_dir: Path,
    ratings_base_dir: Path
) -> pd.DataFrame:
    """
    Calcula o ranking Elo para hrönirs de uma dada 'position', considerando
    apenas os herdeiros diretos do 'canonical_predecessor_uuid'.
    Para a Posição 0, 'canonical_predecessor_uuid' pode ser None,
    e todos os hrönirs da Posição 0 são considerados.
    """
    # 1. Identificar os Herdeiros
    heir_uuids = set()
    all_forking_files = list(forking_path_dir.glob("*.csv"))

    if not all_forking_files and canonical_predecessor_uuid is not None:
        # Se não há arquivos de forking path, não pode haver herdeiros de um predecessor específico.
        # No entanto, se canonical_predecessor_uuid é None (caso da Posição 0),
        # continuaremos para tentar encontrar hrönirs da Posição 0 diretamente dos votos.
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    for csv_file in all_forking_files:
        if csv_file.stat().st_size == 0:
            continue
        try:
            df_forks = pd.read_csv(csv_file)
            if df_forks.empty:
                continue

            # Filtrar por posição e predecessor canônico
            # Certificar que as colunas de posição são comparadas como o mesmo tipo
            df_forks["position"] = df_forks["position"].astype(int)

            if canonical_predecessor_uuid is None: # Caso especial para Posição 0
                 # Considera todos os hrönirs na Posição 0 como "herdeiros"
                # desde que não tenham um prev_uuid (ou um prev_uuid específico para raiz, se definido)
                # Por simplicidade, se canonical_predecessor_uuid é None, pegamos todos da Posição 0.
                # O `prev_uuid` para a Posição 0 pode ser variado ou NaN.
                # A lógica aqui é que se estamos pedindo ranking para Posição 0 sem predecessor,
                # então todos os hrönirs na Posição 0 são candidatos.
                # No entanto, a especificação da tarefa é que `get_ranking` é chamado com N e N-1.
                # Se N=0, N-1 é -1. `get_canonical_uuid(-1)` falharia.
                # A "Consideração Adicional" do plano sugere que Posição 0 pode ter `None` como predecessor.
                # Se `canonical_predecessor_uuid` é `None`, isso implica que estamos buscando
                # os hrönirs da `position` que *não têm* um `prev_uuid` ou cujo `prev_uuid` é um
                # valor especial indicando a raiz (ex: "ROOT_UUID" ou pd.NA).
                # Para a Posição 0, geralmente não há `prev_uuid`.
                # Se o `forking_path` para a Posição 0 tiver `prev_uuid` como NaN/None/vazio,
                # eles seriam selecionados aqui.
                # O plano diz: "Para a Posição 0, canonical_predecessor_uuid será um valor fixo especial (ex: None)"
                # "que get_ranking interpretará como "sem predecessor, considere todos os hrönirs da posição 0".
                # Isso significa que o filtro em `prev_uuid` deve ser diferente.
                # Se `canonical_predecessor_uuid` é None, queremos hrönirs da `position` (que deve ser 0)
                # cujo `prev_uuid` é efetivamente nulo ou não especificado.
                # Assumindo que para Posição 0, `prev_uuid` nos CSVs é NaN ou uma string vazia.
                if position == 0:
                    # Para a posição 0, `prev_uuid` deve ser nulo ou ausente.
                    # Pandas lê colunas vazias como NaN por padrão.
                    potential_heirs = df_forks[
                        (df_forks["position"] == position) &
                        (df_forks["prev_uuid"].isnull() | (df_forks["prev_uuid"] == ""))
                    ]["uuid"].tolist()
                    heir_uuids.update(potential_heirs)
                else:
                    # Se canonical_predecessor_uuid é None, mas a posição não é 0,
                    # isso é um estado inesperado baseado no plano. Retornar vazio.
                    return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

            else: # canonical_predecessor_uuid is not None
                potential_heirs = df_forks[
                    (df_forks["position"] == position) &
                    (df_forks["prev_uuid"] == canonical_predecessor_uuid)
                ]["uuid"].tolist()
                heir_uuids.update(potential_heirs)

        except pd.errors.EmptyDataError:
            continue # Arquivo CSV vazio
        except Exception:
            # Ignorar arquivos CSV malformados ou com colunas ausentes por enquanto,
            # ou adicionar logging se necessário.
            # Idealmente, o sistema deve ser robusto a isso.
            continue

    # Se nenhum herdeiro for encontrado E não estamos no caso especial da Posição 0
    # (onde herdeiros podem vir diretamente dos votos se não houver forking_path),
    # então não há ninguém para classificar.
    # if not heir_uuids and (canonical_predecessor_uuid is not None or position != 0):
    # Modificação: Se não houver herdeiros do forking_path, não há como rankear.
    if not heir_uuids:
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    # 2. Filtrar os Anais dos Duelos
    ratings_csv_path = ratings_base_dir / f"position_{position:03d}.csv"
    if not ratings_csv_path.exists() or ratings_csv_path.stat().st_size == 0:
        # Se não há votos, mas existem herdeiros, eles terão Elo base, 0 vitórias/derrotas.
        # Ou retornar DataFrame vazio se nenhum duelo significa nenhum ranking.
        # O comportamento atual do Elo é inicializar apenas UUIDs presentes nos duelos.
        # Para consistência, se não há duelos, não há Elo calculado.
        # No entanto, queremos mostrar os herdeiros.
        # Vamos criar um ranking com Elo base para os herdeiros sem duelos.
        ELO_BASE = 1500 # Consistente com o cálculo abaixo
        ranking_data = [{"uuid": hid, "elo": ELO_BASE, "wins": 0, "losses": 0, "total_duels": 0} for hid in heir_uuids]
        if not ranking_data: # Segurança extra
             return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])
        final_df = pd.DataFrame(ranking_data)
        final_df = final_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])
        return final_df

    try:
        df_votes = pd.read_csv(ratings_csv_path)
        if df_votes.empty: # Similar ao caso de arquivo não existente
            ELO_BASE = 1500
            ranking_data = [{"uuid": hid, "elo": ELO_BASE, "wins": 0, "losses": 0, "total_duels": 0} for hid in heir_uuids]
            if not ranking_data:
                return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])
            final_df = pd.DataFrame(ranking_data)
            final_df = final_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])
            return final_df

    except pd.errors.EmptyDataError:
        # Tratar como se não houvesse votos
        ELO_BASE = 1500
        ranking_data = [{"uuid": hid, "elo": ELO_BASE, "wins": 0, "losses": 0, "total_duels": 0} for hid in heir_uuids]
        if not ranking_data:
            return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])
        final_df = pd.DataFrame(ranking_data)
        final_df = final_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])
        return final_df
    except Exception: # Outro erro de leitura, incluindo falha ao encontrar colunas
        # Se houver qualquer erro na leitura ou o arquivo for inválido (e.g. colunas faltando),
        # trata como se não houvesse votos válidos para os herdeiros.
        ELO_BASE = 1500
        ranking_data = [{"uuid": hid, "elo": ELO_BASE, "wins": 0, "losses": 0, "total_duels": 0} for hid in heir_uuids]
        if not ranking_data: # Segurança
             return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])
        final_df = pd.DataFrame(ranking_data)
        final_df = final_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])
        return final_df

    # Verificar se as colunas 'winner' e 'loser' existem
    if 'winner' not in df_votes.columns or 'loser' not in df_votes.columns:
        # Colunas essenciais ausentes, tratar como sem votos válidos.
        ELO_BASE = 1500
        ranking_data = [{"uuid": hid, "elo": ELO_BASE, "wins": 0, "losses": 0, "total_duels": 0} for hid in heir_uuids]
        if not ranking_data:
             return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])
        final_df = pd.DataFrame(ranking_data)
        final_df = final_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])
        return final_df

    # Manter apenas duelos onde ambos os participantes são herdeiros
    # Nota: df_votes['winner'] e df_votes['loser'] devem ser strings para a comparação com heir_uuids (que são strings)
    df_votes['winner'] = df_votes['winner'].astype(str)
    df_votes['loser'] = df_votes['loser'].astype(str)

    filtered_votes = df_votes[
        df_votes["winner"].isin(heir_uuids) & df_votes["loser"].isin(heir_uuids)
    ]

    if filtered_votes.empty:
        # Não há duelos entre os herdeiros. Retornar herdeiros com Elo base.
        ELO_BASE = 1500
        ranking_data = [{"uuid": hid, "elo": ELO_BASE, "wins": 0, "losses": 0, "total_duels": 0} for hid in heir_uuids]
        if not ranking_data: # Segurança
             return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])
        final_df = pd.DataFrame(ranking_data)
        final_df = final_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])
        return final_df

    # 3. Calcular a Hierarquia (Elo)
    ELO_BASE = 1500
    K_FACTOR = 32

    # Inicializar Elo para todos os herdeiros
    elo_ratings = {uuid_str: ELO_BASE for uuid_str in heir_uuids}
    wins_map = {uuid_str: 0 for uuid_str in heir_uuids}
    losses_map = {uuid_str: 0 for uuid_str in heir_uuids}

    # Iterar sobre cada duelo FILTRADO para atualizar os ratings Elo
    for _, row in filtered_votes.iterrows():
        winner_uuid = row["winner"]
        loser_uuid = row["loser"]

        # Adicionar aos contadores de vitórias/derrotas (apenas para herdeiros)
        if winner_uuid in wins_map: wins_map[winner_uuid] += 1
        if loser_uuid in losses_map: losses_map[loser_uuid] += 1

        # Ratings atuais
        r_winner = elo_ratings[winner_uuid]
        r_loser = elo_ratings[loser_uuid]

        expected_winner = _calculate_elo_probability(r_winner, r_loser)
        expected_loser = 1 - expected_winner # _calculate_elo_probability(r_loser, r_winner)

        new_r_winner = r_winner + K_FACTOR * (1 - expected_winner)
        new_r_loser = r_loser + K_FACTOR * (0 - expected_loser)

        elo_ratings[winner_uuid] = new_r_winner
        elo_ratings[loser_uuid] = new_r_loser

    # Criar DataFrame a partir dos ratings Elo calculados e contagens de vitórias/derrotas para os herdeiros
    ranking_data = []
    for uuid_val in heir_uuids: # Iterar sobre os herdeiros, não sobre todos os que participaram
        ranking_data.append({
            "uuid": uuid_val,
            "elo": int(round(elo_ratings[uuid_val])),
            "wins": wins_map[uuid_val],
            "losses": losses_map[uuid_val],
            "total_duels": wins_map[uuid_val] + losses_map[uuid_val]
        })

    if not ranking_data: # Caso extremo, se heir_uuids estivesse vazio após tudo.
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    ranking_df = pd.DataFrame(ranking_data)
    ranking_df = ranking_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])

    return ranking_df[["uuid", "elo", "wins", "losses", "total_duels"]]


def determine_next_duel(
    position: int,
    canonical_predecessor_uuid: str | None,
    forking_path_dir: Path,
    ratings_base_dir: Path
) -> dict | None:
    """
    Determina o próximo duelo para uma posição, considerando apenas os herdeiros
    do canonical_predecessor_uuid, selecionando o par de hrönirs (herdeiros)
    com a maior entropia.
    """
    ranking_df = get_ranking(position, canonical_predecessor_uuid, forking_path_dir, ratings_base_dir)
    if len(ranking_df) < 2:
        return None

    # Utiliza a heurística otimizada: a maior entropia geralmente ocorre
    # entre vizinhos no ranking ordenado por Elo.
    # get_ranking já retorna ordenado, mas re-ordenar aqui garante.
    ranking_df = ranking_df.sort_values(by="elo", ascending=False).reset_index(drop=True)

    # Calcula a entropia para cada par de vizinhos
    # Inicializa a coluna com um valor que indica que a entropia não foi calculada (e.g. < 0)
    ranking_df["entropy_with_next"] = -1.0

    entropies_calculated = []
    for i in range(len(ranking_df) - 1):
        elo_a = ranking_df.loc[i, "elo"]
        elo_b = ranking_df.loc[i + 1, "elo"]
        entropy = _calculate_duel_entropy(elo_a, elo_b)
        ranking_df.loc[i, "entropy_with_next"] = entropy
        entropies_calculated.append(entropy) # Guardar para verificar se alguma entropia foi calculada

    if not entropies_calculated: # Se nenhum par de vizinhos existia (len(ranking_df) < 2, já tratado) ou algo deu errado
        return None

    # Encontra o índice da maior entropia. idxmax() ignora NaNs e valores não numéricos se existirem,
    # mas nossa coluna deve ser float. Se todas as entropias forem -1.0 (caso de 2 hrönirs onde o apply não é ideal),
    # idxmax() pegaria o primeiro.
    # Se houver apenas um par (2 hrönirs), a entropia será calculada para ranking_df.loc[0, "entropy_with_next"]
    # e idxmax() o encontrará.

    # Se todas as entropias calculadas forem 0 (e.g. Elos muito distantes), idxmax() ainda pega o primeiro.
    # Isso é aceitável; um duelo de baixa entropia é melhor que nenhum, se for o máximo disponível.
    max_entropy_idx = ranking_df["entropy_with_next"].idxmax()

    # Verifica se max_entropy_idx é válido e se o valor de entropia é de fato > -1.0 (ou seja, foi calculado)
    # Isso é uma segurança extra, pois se len(ranking_df) == 2, o loop roda uma vez para i=0.
    # ranking_df.loc[0, "entropy_with_next"] será atualizado.
    # ranking_df.loc[1, "entropy_with_next"] permanecerá -1.0. idxmax() pegaria o índice 0.
    if ranking_df.loc[max_entropy_idx, "entropy_with_next"] < 0:
         # Isso não deveria acontecer se len(ranking_df) >= 2, pois pelo menos uma entropia seria calculada.
         # A menos que todas as entropias sejam 0 e, de alguma forma, o valor inicial -1.0 fosse o máximo.
         # Mas _calculate_duel_entropy retorna >= 0.
        return None # Segurança: nenhuma entropia válida foi encontrada.

    hronir_A_uuid = ranking_df.iloc[max_entropy_idx]["uuid"]
    # O par de max_entropy_idx é com max_entropy_idx + 1
    hronir_B_uuid = ranking_df.iloc[max_entropy_idx + 1]["uuid"]
    max_entropy_value = ranking_df.loc[max_entropy_idx, "entropy_with_next"]

    return {
        "strategy": "max_entropy_duel", # Estratégia é sempre esta agora
        "hronir_A": hronir_A_uuid,
        "hronir_B": hronir_B_uuid,
        "entropy": max_entropy_value,
        "position": position, # Adicionando position para consistência com output anterior
    }
