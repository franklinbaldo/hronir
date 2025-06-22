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
    predecessor_hronir_uuid: str | None, # UUID do hrönir sucessor do fork canônico anterior
    forking_path_dir: Path,
    ratings_dir: Path
) -> pd.DataFrame:
    """
    Calcula o ranking Elo para fork_uuid's de uma dada 'position', considerando
    apenas os forks que descendem diretamente do 'predecessor_hronir_uuid'.
    Para a Posição 0, 'predecessor_hronir_uuid' é None.

    Retorna um DataFrame com colunas: fork_uuid, hrönir_uuid (sucessor), elo_rating,
                                     games_played, wins, losses.
    """
    output_columns = ["fork_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
    empty_df = pd.DataFrame(columns=output_columns)

    # 1. Identificar Herdeiros (Fork UUIDs Elegíveis e seus sucessores hrönir_uuid)
    # eligible_fork_infos será uma lista de dicts: [{'fork_uuid': str, 'hrönir_uuid': str}]
    eligible_fork_infos_list = []
    if not forking_path_dir.exists() or not forking_path_dir.is_dir():
        return empty_df

    all_forking_files = list(forking_path_dir.glob("*.csv"))
    if not all_forking_files:
        return empty_df

    for csv_file in all_forking_files:
        if csv_file.stat().st_size == 0:
            continue
        try:
            df_forks = pd.read_csv(csv_file, dtype={'position': 'Int64', 'prev_uuid': str, 'uuid': str, 'fork_uuid': str})
            if df_forks.empty or not all(col in df_forks.columns for col in ["position", "prev_uuid", "uuid", "fork_uuid"]):
                continue

            # Garantir que a coluna position seja int para comparação
            df_forks = df_forks[pd.to_numeric(df_forks["position"], errors='coerce') == position]
            if df_forks.empty:
                continue

            if predecessor_hronir_uuid is None: # Caso Posição 0
                if position == 0:
                    # `prev_uuid` deve ser nulo/vazio/NaN
                    selected_forks = df_forks[df_forks["prev_uuid"].fillna('').isin(['', 'nan', 'None'])]
                else:
                    # predecessor_hronir_uuid é None para posição != 0 é um estado inesperado.
                    continue # ou return empty_df se for uma condição de erro global
            else: # predecessor_hronir_uuid is not None
                selected_forks = df_forks[df_forks["prev_uuid"] == predecessor_hronir_uuid]

            for _, row in selected_forks.iterrows():
                eligible_fork_infos_list.append({"fork_uuid": row["fork_uuid"], "hrönir_uuid": row["uuid"]})

        except pd.errors.EmptyDataError:
            continue
        except Exception: # Trata outros erros de parsing ou de arquivo
            # Adicionar logging aqui seria útil
            continue

    if not eligible_fork_infos_list:
        return empty_df

    # Criar um mapeamento de hrönir_uuid (sucessor) para fork_uuid para os forks elegíveis
    # Nota: Um hrönir_uuid pode ser sucessor de múltiplos forks se vier de diferentes CSVs,
    # mas dentro da mesma linhagem (mesmo predecessor_hronir_uuid e posição),
    # o par (prev_uuid, uuid) deve ser único por fork_uuid.
    # Se um hrönir_uuid é sucessor de múltiplos forks ELEGÍVEIS, isso é um problema de dados.
    # Por simplicidade, assumimos que cada hrönir_uuid sucessor em eligible_fork_infos_list
    # está associado a um único fork_uuid elegível nesta chamada.
    # Se um hrönir_uuid pudesse ser o sucessor de MÚLTIPLOS forks elegíveis (mesma posição, mesmo predecessor),
    # precisaríamos de uma regra para desambiguar a qual fork um voto para esse hrönir se aplica.
    # O design atual de fork_uuid (position, prev_uuid, cur_uuid) garante que se cur_uuid é o mesmo,
    # e prev_uuid é o mesmo (nosso predecessor_hronir_uuid), então o fork_uuid será o mesmo.
    # Então, o mapeamento de hrönir_uuid para fork_uuid dentro dos elegíveis deve ser 1:1.

    # eligible_fork_df para fácil lookup e inicialização de ranking
    eligible_fork_df = pd.DataFrame(eligible_fork_infos_list).drop_duplicates(subset=['fork_uuid'])
    if eligible_fork_df.empty: # Após drop_duplicates, se algo estranho acontecer
        return empty_df

    # Mapeamento de hrönir_uuid (sucessor) para seu fork_uuid elegível
    hronir_to_eligible_fork_map = pd.Series(eligible_fork_df.fork_uuid.values, index=eligible_fork_df.hrönir_uuid).to_dict()

    # 2. Preparar DataFrame de Ranking com Elo Base para todos os forks elegíveis
    ELO_BASE = 1500
    ranking_list = [
        {
            "fork_uuid": fork_info["fork_uuid"],
            "hrönir_uuid": fork_info["hrönir_uuid"], # Este é o hrönir SUCESSOR do fork
            "elo_rating": ELO_BASE, "games_played": 0, "wins": 0, "losses": 0
        }
        for fork_info in eligible_fork_df.to_dict('records')
    ]
    # Usar fork_uuid como índice para fácil atualização
    current_ranking_df = pd.DataFrame(ranking_list).set_index("fork_uuid")

    # 3. Ler e Processar os Votos
    ratings_csv_path = ratings_dir / f"position_{position:03d}.csv"

    if ratings_csv_path.exists() and ratings_csv_path.stat().st_size > 0:
        try:
            df_votes = pd.read_csv(ratings_csv_path, dtype=str) # Ler tudo como string inicialmente
            if not df_votes.empty and 'winner' in df_votes.columns and 'loser' in df_votes.columns:

                # Mapear winner/loser hrönir_uuids para fork_uuids elegíveis
                df_votes["winner_fork_uuid"] = df_votes["winner"].map(hronir_to_eligible_fork_map)
                df_votes["loser_fork_uuid"] = df_votes["loser"].map(hronir_to_eligible_fork_map)

                # Filtrar votos onde ambos os hrönirs mapeiam para forks elegíveis
                valid_duel_votes = df_votes.dropna(subset=["winner_fork_uuid", "loser_fork_uuid"])

                # Garantir que o winner_fork e loser_fork não sejam o mesmo
                valid_duel_votes = valid_duel_votes[valid_duel_votes["winner_fork_uuid"] != valid_duel_votes["loser_fork_uuid"]]

                if not valid_duel_votes.empty:
                    K_FACTOR = 32
                    for _, vote_row in valid_duel_votes.iterrows():
                        winner_fork = vote_row["winner_fork_uuid"]
                        loser_fork = vote_row["loser_fork_uuid"]

                        # Atualizar contagens no current_ranking_df (indexado por fork_uuid)
                        current_ranking_df.loc[winner_fork, "wins"] += 1
                        current_ranking_df.loc[loser_fork, "losses"] += 1
                        current_ranking_df.loc[winner_fork, "games_played"] += 1
                        current_ranking_df.loc[loser_fork, "games_played"] += 1

                        r_winner_fork = current_ranking_df.loc[winner_fork, "elo_rating"]
                        r_loser_fork = current_ranking_df.loc[loser_fork, "elo_rating"]

                        expected_winner = _calculate_elo_probability(r_winner_fork, r_loser_fork)

                        new_r_winner_fork = r_winner_fork + K_FACTOR * (1 - expected_winner)
                        new_r_loser_fork = r_loser_fork + K_FACTOR * (0 - (1 - expected_winner))

                        current_ranking_df.loc[winner_fork, "elo_rating"] = new_r_winner_fork
                        current_ranking_df.loc[loser_fork, "elo_rating"] = new_r_loser_fork

                    current_ranking_df["elo_rating"] = current_ranking_df["elo_rating"].round().astype(int)

        except pd.errors.EmptyDataError:
            pass
        except Exception:
            # Adicionar logging
            pass

    # Resetar índice para ter fork_uuid como coluna e ordenar
    final_df = current_ranking_df.reset_index()
    final_df = final_df.sort_values(
        by=["elo_rating", "wins", "games_played"],
        ascending=[False, False, True]
    )

    return final_df[output_columns]


def determine_next_duel(
    position: int,
    predecessor_hronir_uuid: str | None,
    forking_path_dir: Path,
    ratings_dir: Path
) -> dict | None:
    """
    Determina o próximo duelo para uma posição, considerando apenas os forks elegíveis
    que descendem do predecessor_hronir_uuid. Seleciona o par de FORK_UUIDs
    com a maior entropia.
    """
    # get_ranking agora retorna um DataFrame de fork_uuid's
    # Colunas: fork_uuid, hrönir_uuid (sucessor), elo_rating, games_played, wins, losses
    ranking_df = get_ranking(position, canonical_predecessor_uuid, forking_path_dir, ratings_dir)

    if ranking_df.empty or len(ranking_df) < 2:
        return None

    # Ordenar por elo_rating (get_ranking já deve retornar ordenado, mas para garantir)
    # A ordenação de get_ranking é: by=["elo_rating", "wins", "games_played"], ascending=[False, False, True]
    # Para a heurística de vizinhos, a ordenação primária por elo_rating é o que importa.
    # Se já estiver ordenado, esta linha não muda nada. Se não, garante a ordem correta.
    ranking_df = ranking_df.sort_values(by="elo_rating", ascending=False).reset_index(drop=True)

    # Calcula a entropia para cada par de vizinhos no ranking de forks
    max_entropy = -1.0
    duel_fork_A_uuid = None
    duel_fork_B_uuid = None

    for i in range(len(ranking_df) - 1):
        elo_a = ranking_df.loc[i, "elo_rating"]
        elo_b = ranking_df.loc[i + 1, "elo_rating"]

        current_entropy = _calculate_duel_entropy(elo_a, elo_b)

        if current_entropy > max_entropy:
            max_entropy = current_entropy
            duel_fork_A_uuid = ranking_df.loc[i, "fork_uuid"]
            duel_fork_B_uuid = ranking_df.loc[i + 1, "fork_uuid"]

    if duel_fork_A_uuid is None or duel_fork_B_uuid is None : # Não encontrou nenhum par (deveria ser coberto por len < 2)
        return None

    # O critério de aceitação é: Retorna `{ "fork_A": "...", "fork_B": "..." }`
    # O plano menciona: `{"duel_pair": {"fork_A": "fork_uuid_1", "fork_B": "fork_uuid_2"}, "entropy": E, ...}`
    # Vou seguir o formato com "duel_pair" para consistência com o plano.
    return {
        "position": position,
        "strategy": "max_entropy_duel", # Estratégia é sempre esta
        "entropy": max_entropy,
        "duel_pair": {
            "fork_A": duel_fork_A_uuid,
            "fork_B": duel_fork_B_uuid,
        }
    }
