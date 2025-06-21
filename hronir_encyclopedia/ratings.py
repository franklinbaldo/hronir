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


def get_ranking(position: int, base: Path | str = "ratings") -> pd.DataFrame:
    csv_path = Path(base) / f"position_{position:03d}.csv"
    if not csv_path.exists():
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses"])  # Elo a ser implementado

    df = pd.read_csv(csv_path)
    # Ensure DataFrame is not empty to prevent errors with value_counts
    if df.empty:
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    wins = df["winner"].value_counts().reset_index()
    wins.columns = ["uuid", "wins"]

    losses = df["loser"].value_counts().reset_index()
    losses.columns = ["uuid", "losses"]

    ranking_df = pd.merge(wins, losses, on="uuid", how="outer").fillna(0)
    ranking_df["wins"] = ranking_df["wins"].astype(int)
    ranking_df["losses"] = ranking_df["losses"].astype(int)
    ranking_df["total_duels"] = ranking_df["wins"] + ranking_df["losses"]

    # Implementação do cálculo de Elo mínimo
    ELO_BASE = 1000
    POINTS_PER_WIN = 15
    POINTS_PER_LOSS = 10  # Poderia ser igual a POINTS_PER_WIN se quisermos um impacto simétrico

    # Implementação do cálculo de Elo tradicional
    ELO_BASE = 1500  # Rating inicial comum para novos jogadores
    K_FACTOR = 32    # Fator K comum, determina a sensibilidade do rating

    # Inicializar Elo para todos os UUIDs únicos presentes nos duelos
    all_uuids = pd.unique(df[["winner", "loser"]].values.ravel("K"))
    elo_ratings = {uuid: ELO_BASE for uuid in all_uuids}

    wins_map = {uuid: 0 for uuid in all_uuids}
    losses_map = {uuid: 0 for uuid in all_uuids}

    # Iterar sobre cada duelo para atualizar os ratings Elo
    for _, row in df.iterrows():
        winner_uuid = row["winner"]
        loser_uuid = row["loser"]

        # Adicionar aos contadores de vitórias/derrotas
        wins_map[winner_uuid] = wins_map.get(winner_uuid, 0) + 1
        losses_map[loser_uuid] = losses_map.get(loser_uuid, 0) + 1

        # Ratings atuais
        r_winner = elo_ratings[winner_uuid]
        r_loser = elo_ratings[loser_uuid]

        # Calcular probabilidades esperadas
        # E_winner = 1 / (1 + 10^((r_loser - r_winner) / 400))
        # E_loser  = 1 / (1 + 10^((r_winner - r_loser) / 400))

        # q_winner = 10^(r_winner / 400) # Esta não é a fórmula correta para E_winner
        # q_loser = 10^(r_loser / 400)   # Esta não é a fórmula correta para E_loser
        # expected_winner = q_winner / (q_winner + q_loser)
        # expected_loser = q_loser / (q_winner + q_loser)

        # Usando a fórmula correta para a expectativa (E_A = 1 / (1 + 10^((R_B - R_A) / 400)))
        expected_winner = 1 / (1 + 10**((r_loser - r_winner) / 400))
        expected_loser = 1 / (1 + 10**((r_winner - r_loser) / 400))


        # Atualizar ratings
        # R'_winner = R_winner + K * (S_winner - E_winner)
        # S_winner = 1 para vitória, 0 para derrota
        new_r_winner = r_winner + K_FACTOR * (1 - expected_winner)
        new_r_loser = r_loser + K_FACTOR * (0 - expected_loser) # S_loser = 0

        elo_ratings[winner_uuid] = new_r_winner
        elo_ratings[loser_uuid] = new_r_loser

    # Criar DataFrame a partir dos ratings Elo calculados e contagens de vitórias/derrotas
    ranking_data = []
    for uuid_val in all_uuids:
        ranking_data.append({
            "uuid": uuid_val,
            "elo": int(round(elo_ratings[uuid_val])), # Elo geralmente é inteiro
            "wins": wins_map.get(uuid_val, 0),
            "losses": losses_map.get(uuid_val, 0)
        })

    ranking_df = pd.DataFrame(ranking_data)

    if ranking_df.empty: # Caso não haja duelos, retorna df vazio com colunas corretas
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    ranking_df["total_duels"] = ranking_df["wins"] + ranking_df["losses"]

    # Ordenar pelo Elo calculado, depois por vitórias para desempate
    ranking_df = ranking_df.sort_values(by=["elo", "wins", "total_duels"], ascending=[False, False, False])

    return ranking_df[["uuid", "elo", "wins", "losses", "total_duels"]]


def determine_next_duel(position: int, base: Path | str = "ratings") -> dict | None:
    """
    Determina o próximo duelo para uma posição selecionando o par de hrönirs
    com a maior entropia, ou seja, o resultado mais incerto.
    """
    ranking_df = get_ranking(position, base=base)
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
