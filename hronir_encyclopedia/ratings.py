import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine


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
