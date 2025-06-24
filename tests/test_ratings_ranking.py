from pathlib import Path  # Necessário para Path operations

import pandas as pd  # Necessário para criar DataFrames para CSVs

from hronir_encyclopedia import (
    ratings,
    storage,  # Added for DataManager
)


# Helper function to manage DataManager and call get_ranking
# This is identical to the one in test_ranking_filtering.py
# Consider moving to a conftest.py if used by more test files.
def _call_get_ranking_with_setup(position, predecessor_hronir_uuid, forking_dir, ratings_dir):
    original_fork_csv_dir = storage.data_manager.fork_csv_dir
    original_ratings_csv_dir = storage.data_manager.ratings_csv_dir
    original_initialized = storage.data_manager._initialized
    db_cleared_by_this_run = False

    try:
        storage.data_manager.fork_csv_dir = forking_dir
        storage.data_manager.ratings_csv_dir = ratings_dir
        storage.data_manager._initialized = False
        storage.data_manager.clear_in_memory_data()
        db_cleared_by_this_run = True
        storage.data_manager.initialize_and_load(clear_existing_data=False)

        db_session = storage.get_db_session()
        try:
            df = ratings.get_ranking(
                position=position,
                predecessor_hronir_uuid=predecessor_hronir_uuid,
                session=db_session,
            )
        finally:
            db_session.close()
        return df
    finally:
        storage.data_manager.fork_csv_dir = original_fork_csv_dir
        storage.data_manager.ratings_csv_dir = original_ratings_csv_dir
        storage.data_manager._initialized = original_initialized
        if db_cleared_by_this_run and storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


# Definir UUIDs de teste de forma consistente
UUID_A = "hr-a"
UUID_B = "hr-b"
UUID_C = "hr-c"
PREDECESSOR_POS1 = "pred-pos1"


def test_get_ranking(tmp_path: Path):
    ratings_dir_test_var = tmp_path / "ratings"  # Renamed local variable
    ratings_dir_test_var.mkdir()
    forking_path_dir = tmp_path / "forking_path"
    forking_path_dir.mkdir()

    # Criar dados de forking_path: a, b, c são herdeiros de PREDECESSOR_POS1 para posição 1
    fork_data = [
        {"position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_A, "fork_uuid": "fork-a"},
        {"position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_B, "fork_uuid": "fork-b"},
        {"position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_C, "fork_uuid": "fork-c"},
    ]
    pd.DataFrame(fork_data).to_csv(forking_path_dir / "test_forks.csv", index=False)

    # Criar arquivo de ratings (votos)
    # Usar os mesmos votos que estavam no teste original, mas agora em um CSV
    # Votos: (a W vs b L), (a W vs c L), (b W vs a L)
    votes_for_pos1 = [
        {"uuid": "vote1", "voter": "v1", "winner": UUID_A, "loser": UUID_B},
        {"uuid": "vote2", "voter": "v2", "winner": UUID_A, "loser": UUID_C},
        {"uuid": "vote3", "voter": "v3", "winner": UUID_B, "loser": UUID_A},
    ]
    pd.DataFrame(votes_for_pos1).to_csv(
        ratings_dir_test_var / "position_001.csv", index=False
    )  # Use renamed var

    # Chamar ratings.get_ranking com os novos parâmetros
    df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=PREDECESSOR_POS1,
        forking_dir=forking_path_dir,
        ratings_dir=ratings_dir_test_var,
    )

    # As asserções originais sobre Elos, vitórias e derrotas devem continuar válidas
    # se a lógica de cálculo de Elo não mudou fundamentalmente, apenas a filtragem de dados.
    # Ordem esperada: A, B, C com base nos Elos calculados no teste original.
    assert list(df["hrönir_uuid"]) == [UUID_A, UUID_B, UUID_C]  # Changed "uuid" to "hrönir_uuid"

    row_a = df[df["hrönir_uuid"] == UUID_A].iloc[0]  # Changed "uuid" to "hrönir_uuid"
    row_b = df[df["hrönir_uuid"] == UUID_B].iloc[0]  # Changed "uuid" to "hrönir_uuid"
    row_c = df[df["hrönir_uuid"] == UUID_C].iloc[0]  # Changed "uuid" to "hrönir_uuid"

    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert (
        row_a["elo_rating"] == 1513
    )  # Elo esperado do teste original. Changed "elo" to "elo_rating"

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert (
        row_b["elo_rating"] == 1502
    )  # Elo esperado do teste original. Changed "elo" to "elo_rating"

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    assert (
        row_c["elo_rating"] == 1485
    )  # Elo esperado do teste original. Changed "elo" to "elo_rating"
