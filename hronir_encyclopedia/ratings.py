import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

import math # Adicionado para math.log2
from itertools import combinations # Adicionado para futuras implementações de entropia global, se necessário


def _calculate_elo_probability(elo_a: float, elo_b: float) -> float:
    """Calcula a probabilidade de A vencer B."""
    return 1 / (1 + 10**((elo_b - elo_a) / 400))

def _calculate_duel_entropy(elo_a: float, elo_b: float) -> float:
    """Calcula a entropia de Shannon para um duelo Elo."""
    p_a = _calculate_elo_probability(elo_a, elo_b)
    if p_a == 0 or p_a == 1: # Evita math.log2(0)
        return 0.0
    p_b = 1 - p_a
    # Se p_b também for 0 (o que implica p_a == 1), já foi tratado acima.
    # No entanto, para robustez, podemos verificar p_b explicitamente se necessário,
    # mas a lógica atual já cobre isso.
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
    Determina o próximo duelo para uma posição usando uma estratégia de relevância informativa.
    """
    ranking_df = get_ranking(position, base=base)

    if len(ranking_df) < 2:
        return None

    # 1. Estratégia de Calibração
    if "total_duels" not in ranking_df.columns:
        # This should ideally not be hit if get_ranking is robust.
        # If it occurs, the following line `ranking_df["total_duels"] == 0` will raise KeyError.
        # This is acceptable as it indicates bad data from get_ranking.
        pass

    new_challengers = ranking_df[ranking_df["total_duels"] == 0]

    if not new_challengers.empty:
        champion_uuid = ranking_df.iloc[0]["uuid"]
        challenger_uuid = new_challengers.iloc[0]["uuid"]

        if champion_uuid != challenger_uuid:
            return {
                "strategy": "calibration_duel",
                "hronir_A": champion_uuid,
                "hronir_B": challenger_uuid,
                "position": position,
            }
        elif len(ranking_df) > 1 and champion_uuid == challenger_uuid:
            # Caso especial: o "novo" hrönir é o único no ranking ou o único sem duelos,
            # e ele é o "campeão" (primeiro na lista).
            # Precisamos de um segundo hrönir para um duelo de calibração.
            # Se houver outro hrönir (que já duelou), calibra contra ele.
            # Se o campeão é o único novo, e há outros que já duelaram,
            # o campeão (novo) deve enfrentar o segundo do ranking (que já duelou).
            # Isso parece um pouco circular. A ideia é que um hrönir SEMPRE novo duele com o CAMPEÃO ATUAL.
            # Se o campeão atual TAMBÉM é novo (total_duels == 0),
            # então o segundo da lista (se existir e não for novo) deveria ser o "campeão estabelecido".
            # Este cenário precisa de clarificação ou uma regra mais robusta.
            # Por ora, se o campeão é novo e é o único novo, e há outros,
            # a lógica abaixo (entropia) será acionada, o que pode ser aceitável.
            # Ou, se o campeão é novo, e há outro hrönir (que não é novo), eles duelam.
            # A lógica original: novo_desafiante vs campeão.
            # Se o campeão é o único novo, e há N outros, ele deve enfrentar o #2 (o "campeão de fato" dos que já duelaram)
            # Isso não está coberto pela lógica atual.
            # A lógica atual pega new_challengers.iloc[0]. Se este for o campeão,
            # e não houver *outros* new_challengers, esta condição if champion_uuid != challenger_uuid falha.
            # E então cai para a estratégia de entropia.
            # Se o campeão for o único hrönir com 0 duelos, ele não será selecionado aqui.
            # E a lógica de entropia será usada. Isso parece razoável.
            pass


    # 2. Estratégia de Máxima Entropia
    # Certifique-se de que o DataFrame está ordenado por Elo para a heurística de vizinhos.
    # get_ranking já retorna ordenado, mas re-ordenar aqui garante.
    ranking_df = ranking_df.sort_values(by="elo", ascending=False).reset_index(drop=True)

    # Se após a tentativa de calibração, ainda temos menos de 2 hrönirs, não podemos formar um duelo.
    # Isso pode acontecer se o único "novo" era o campeão e não havia outros para formar par.
    if len(ranking_df) < 2:
        return None

    # Calcula a entropia apenas entre vizinhos no ranking ordenado por Elo.
    # Esta é uma heurística para encontrar alta entropia sem calcular para todos os pares.
    entropies = []
    for i in range(len(ranking_df) - 1):
        elo_a = ranking_df.iloc[i]["elo"]
        elo_b = ranking_df.iloc[i+1]["elo"]
        entropy = _calculate_duel_entropy(elo_a, elo_b)
        entropies.append({
            "hronir_A_uuid": ranking_df.iloc[i]["uuid"],
            "hronir_B_uuid": ranking_df.iloc[i+1]["uuid"],
            "entropy": entropy,
            "idx_A": i # Guardando para referência, se necessário
        })

    if not entropies: # Não há pares vizinhos (ou seja, menos de 2 hrönirs)
        return None

    # Encontra o par vizinho com a máxima entropia
    max_entropy_duel = max(entropies, key=lambda x: x["entropy"])

    return {
        "strategy": "max_entropy_duel",
        "hronir_A": max_entropy_duel["hronir_A_uuid"],
        "hronir_B": max_entropy_duel["hronir_B_uuid"],
        "entropy": max_entropy_duel["entropy"],
        "position": position,
    }
