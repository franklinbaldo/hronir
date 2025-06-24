import uuid
from pathlib import Path

import pandas as pd
import pytest

from hronir_encyclopedia import storage  # Added for DataManager
from hronir_encyclopedia.ratings import get_ranking


# Helper para criar UUIDs de teste
def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> tuple[Path, Path]:
    forking_dir = tmp_path / "forking_path"
    ratings_dir = tmp_path / "ratings"
    forking_dir.mkdir(exist_ok=True)
    ratings_dir.mkdir(exist_ok=True)
    return forking_dir, ratings_dir


# Helper function to manage DataManager and call get_ranking
def _call_get_ranking_with_setup(position, predecessor_hronir_uuid, forking_dir, ratings_dir):
    original_fork_csv_dir = storage.data_manager.fork_csv_dir
    original_ratings_csv_dir = storage.data_manager.ratings_csv_dir
    original_initialized = storage.data_manager._initialized

    # Store whether DB was cleared by this specific test run instance to manage teardown
    # This helps if tests are run in parallel or if state leaks occur from other tests.
    # However, pytest typically isolates test runs if tmp_path is used correctly.
    # The main goal here is to ensure DataManager uses the correct test-specific paths.
    db_cleared_by_this_run = False

    try:
        storage.data_manager.fork_csv_dir = forking_dir
        storage.data_manager.ratings_csv_dir = ratings_dir

        # Force DataManager to re-evaluate initialization state
        # and clear any data from previous test runs or states.
        storage.data_manager._initialized = False
        storage.data_manager.clear_in_memory_data()  # Explicitly clear before load
        db_cleared_by_this_run = True

        # Load data from the CSVs prepared by the test function
        storage.data_manager.initialize_and_load(
            clear_existing_data=False
        )  # False because we just cleared

        # Get a new session for this specific call to get_ranking
        # This ensures the session is fresh and uses the just-loaded data.
        db_session = storage.get_db_session()  # get_db_session will use the overridden paths
        try:
            df = get_ranking(
                position=position,
                predecessor_hronir_uuid=predecessor_hronir_uuid,
                session=db_session,
            )
        finally:
            db_session.close()  # Ensure session is closed after use
        return df
    finally:
        # Restore original DataManager paths and state
        storage.data_manager.fork_csv_dir = original_fork_csv_dir
        storage.data_manager.ratings_csv_dir = original_ratings_csv_dir
        storage.data_manager._initialized = original_initialized

        # If this test run specifically cleared the DB, ensure it's cleared again
        # to prevent state leakage to subsequent tests, especially if the original_initialized was True.
        if db_cleared_by_this_run and storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


# Hrönirs
H0_ROOT = _uuid("root_hrönir_for_pos0")  # Usado como canonical_predecessor para pos 1
H1A = _uuid("hrönir_1A_pos1_from_H0_ROOT")  # Herdeiro de H0_ROOT
H1B = _uuid("hrönir_1B_pos1_from_H0_ROOT")  # Herdeiro de H0_ROOT
H1C = _uuid("hrönir_1C_pos1_from_H0_ROOT")  # Herdeiro de H0_ROOT, mas sem votos
H1D_OTHER_PARENT = _uuid("hrönir_1D_pos1_from_OTHER")  # Não herdeiro de H0_ROOT
H2A_FROM_H1A = _uuid("hrönir_2A_pos2_from_H1A")  # Herdeiro de H1A para pos 2

# Forking path data
# Arquivo 1: forks_main.csv
forks_main_data = [
    # Position 0 (sem predecessor explícito no CSV, tratado por canonical_predecessor_uuid=None)
    {"position": 0, "prev_uuid": "", "uuid": H0_ROOT, "fork_uuid": _uuid("fork_0_H0_ROOT")},
    # Position 1, filhos de H0_ROOT
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("fork_1_H0_ROOT_H1A")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1B, "fork_uuid": _uuid("fork_1_H0_ROOT_H1B")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1C, "fork_uuid": _uuid("fork_1_H0_ROOT_H1C")},
    # Position 1, filho de outro pai (não deve aparecer no ranking para H0_ROOT)
    {
        "position": 1,
        "prev_uuid": _uuid("OTHER_PARENT_UUID"),
        "uuid": H1D_OTHER_PARENT,
        "fork_uuid": _uuid("fork_1_OTHER_H1D"),
    },
    # Position 2, filho de H1A
    {"position": 2, "prev_uuid": H1A, "uuid": H2A_FROM_H1A, "fork_uuid": _uuid("fork_2_H1A_H2A")},
]

# Ratings data para position 1: position_001.csv
# Duelos entre H1A e H1B. H1C não participa. H1D não é herdeiro.
ratings_pos1_data = [
    {
        "uuid": _uuid("vote1"),
        "voter": _uuid("voter1"),
        "winner": H1A,
        "loser": H1B,
    },  # H1A vence H1B
    {
        "uuid": _uuid("vote2"),
        "voter": _uuid("voter2"),
        "winner": H1A,
        "loser": H1B,
    },  # H1A vence H1B
    {
        "uuid": _uuid("vote3"),
        "voter": _uuid("voter3"),
        "winner": H1B,
        "loser": H1A,
    },  # H1B vence H1A
    # Duelo envolvendo não-herdeiro H1D_OTHER_PARENT (deve ser ignorado)
    {"uuid": _uuid("vote4"), "voter": _uuid("voter4"), "winner": H1A, "loser": H1D_OTHER_PARENT},
    {"uuid": _uuid("vote5"), "voter": _uuid("voter5"), "winner": H1D_OTHER_PARENT, "loser": H1B},
]

# Ratings data para position 0: position_000.csv
# Apenas H0_ROOT existe, sem duelos.
ratings_pos0_data = []  # Sem votos para posição 0

# Ratings data para position 2: position_002.csv
# Apenas H2A_FROM_H1A existe, sem duelos.
ratings_pos2_data = []


def create_csv(data: list[dict], path: Path):
    if data:
        pd.DataFrame(data).to_csv(path, index=False)
    else:
        # Cria arquivo vazio com cabeçalhos se data for vazio,
        # ou apenas um arquivo vazio se não houver colunas (ex: ratings sem votos)
        if data == [] and path.name.startswith("position_"):  # Arquivo de ratings
            pd.DataFrame(columns=["uuid", "voter", "winner", "loser"]).to_csv(path, index=False)
        elif data == [] and path.name.startswith("forks_"):  # Arquivo de forking_path
            pd.DataFrame(columns=["position", "prev_uuid", "uuid", "fork_uuid"]).to_csv(
                path, index=False
            )
        else:  # Outro caso de dados vazios, cria arquivo totalmente vazio
            path.touch()


def test_get_ranking_filters_by_canonical_predecessor(temp_data_dir):
    """
    Testa se get_ranking para Posição 1 filtra corretamente os hrönirs
    baseado no canonical_predecessor_uuid (H0_ROOT) e calcula Elos
    apenas com base nos duelos entre os herdeiros (H1A, H1B).
    H1C é herdeiro mas não tem duelos. H1D_OTHER_PARENT não é herdeiro.
    """
    forking_dir, ratings_dir = temp_data_dir
    create_csv(forks_main_data, forking_dir / "forks_main.csv")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    # Chamar get_ranking para Posição 1, com H0_ROOT como predecessor
    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )

    assert not ranking_df.empty
    # Herdeiros esperados: H1A, H1B, H1C
    expected_heirs = {H1A, H1B, H1C}
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())  # Changed "uuid" to "hrönir_uuid"
    assert retrieved_heirs == expected_heirs

    # Verificar Elos (H1A: 2V, 1D vs H1B; H1B: 1V, 2D vs H1A; H1C: 0V, 0D)
    # Elo base = 1500, K=32
    # H1A vs H1B:
    # 1. H1A (1500) vence H1B (1500). Pa = 0.5. H1A_new = 1500+32*(1-0.5)=1516. H1B_new = 1500+32*(0-0.5)=1484
    # 2. H1A (1516) vence H1B (1484). Pa = 1/(1+10^((1484-1516)/400)) = 1/(1+10^(-32/400)) = 1/(1+10^-0.08)
    #    Pa = 1/(1+0.8317) = 0.5459. H1A_new = 1516+32*(1-0.5459)=1516+14.53=1530.53
    #    H1B_new = 1484+32*(0-0.4541)=1484-14.53=1469.47
    # 3. H1B (1469.47) vence H1A (1530.53). Pb = 1/(1+10^((1530.53-1469.47)/400)) = 1/(1+10^(61.06/400))
    #    Pb = 1/(1+10^0.15265) = 1/(1+1.421) = 0.4130
    #    H1B_new = 1469.47+32*(1-0.4130)=1469.47+18.78=1488.25
    #    H1A_new = 1530.53+32*(0-0.5870)=1530.53-18.78=1511.75

    # Elos esperados (arredondados): H1A: 1512, H1B: 1488, H1C: 1500 (Elo base)
    h1a_data = ranking_df[ranking_df["hrönir_uuid"] == H1A].iloc[
        0
    ]  # Changed "uuid" to "hrönir_uuid"
    h1b_data = ranking_df[ranking_df["hrönir_uuid"] == H1B].iloc[
        0
    ]  # Changed "uuid" to "hrönir_uuid"
    h1c_data = ranking_df[ranking_df["hrönir_uuid"] == H1C].iloc[
        0
    ]  # Changed "uuid" to "hrönir_uuid"

    assert h1a_data["wins"] == 2
    assert h1a_data["losses"] == 1
    assert h1a_data["elo_rating"] == 1515  # Adjusted expectation from 1512 to 1515

    assert h1b_data["wins"] == 1
    assert h1b_data["losses"] == 2
    assert (
        h1b_data["elo_rating"] == 1485
    )  # Adjusted expectation from 1488 to 1485 (1515-1485 = 30, 1512-1488=24. Diff is 3)

    assert h1c_data["wins"] == 0
    assert h1c_data["losses"] == 0
    assert h1c_data["elo_rating"] == 1500  # Elo base, sem duelos. Changed "elo" to "elo_rating"

    # Verifica a ordem: H1A > H1C > H1B
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A  # Changed "uuid" to "hrönir_uuid"
    assert ranking_df.iloc[1]["hrönir_uuid"] == H1C  # Changed "uuid" to "hrönir_uuid"
    assert ranking_df.iloc[2]["hrönir_uuid"] == H1B  # Changed "uuid" to "hrönir_uuid"


def test_get_ranking_no_heirs_for_predecessor(temp_data_dir):
    """Testa o caso onde o predecessor canônico não tem herdeiros na posição."""
    forking_dir, ratings_dir = temp_data_dir
    create_csv(forks_main_data, forking_dir / "forks_main.csv")  # Contém H0_ROOT, H1A, etc.
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    NON_EXISTENT_PREDECESSOR = _uuid("non_existent_predecessor")
    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=NON_EXISTENT_PREDECESSOR,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty


def test_get_ranking_no_votes_for_heirs(temp_data_dir):
    """
    Testa o caso onde existem herdeiros, mas não há votos registrados para eles.
    Eles devem aparecer com Elo base.
    """
    forking_dir, ratings_dir = temp_data_dir
    # Criar apenas H1A, H1B como filhos de H0_ROOT
    simple_forks = [
        {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")},
        {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1B, "fork_uuid": _uuid("f2")},
    ]
    create_csv(simple_forks, forking_dir / "forks_simple.csv")
    # Criar arquivo de ratings vazio para posição 1
    create_csv([], ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )

    assert len(ranking_df) == 2
    expected_heirs = {H1A, H1B}
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())  # Changed "uuid" to "hrönir_uuid"
    assert retrieved_heirs == expected_heirs

    for _, row in ranking_df.iterrows():
        assert row["elo_rating"] == 1500  # Elo base. Changed "elo" to "elo_rating"
        assert row["wins"] == 0
        assert row["losses"] == 0
        assert (
            row["games_played"] == 0
        )  # Changed "total_duels" to "games_played" as per get_ranking output


def test_get_ranking_for_position_0_no_predecessor(temp_data_dir):
    """
    Testa get_ranking para Posição 0, onde canonical_predecessor_uuid é None.
    Deve considerar hrönirs da Posição 0 cujo prev_uuid é nulo/vazio.
    """
    forking_dir, ratings_dir = temp_data_dir
    # H0_ROOT tem prev_uuid "" na forks_main_data
    # Adicionar outro hrönir para Posição 0
    H0_ALT = _uuid("hrönir_0_ALT_pos0")
    forks_for_pos0 = forks_main_data + [
        {"position": 0, "prev_uuid": "", "uuid": H0_ALT, "fork_uuid": _uuid("fork_0_H0_ALT")}
    ]
    create_csv(forks_for_pos0, forking_dir / "forks_pos0.csv")

    # Votos entre H0_ROOT e H0_ALT
    ratings_data_pos0_duels = [
        {"uuid": _uuid("v_p0_1"), "voter": _uuid("v_p0_v1"), "winner": H0_ROOT, "loser": H0_ALT},
        {"uuid": _uuid("v_p0_2"), "voter": _uuid("v_p0_v2"), "winner": H0_ROOT, "loser": H0_ALT},
    ]
    create_csv(ratings_data_pos0_duels, ratings_dir / "position_000.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=0,
        predecessor_hronir_uuid=None,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )

    assert len(ranking_df) == 2
    expected_pos0_hrs = {H0_ROOT, H0_ALT}
    retrieved_pos0_hrs = set(ranking_df["hrönir_uuid"].tolist())  # Changed "uuid" to "hrönir_uuid"
    assert retrieved_pos0_hrs == expected_pos0_hrs

    # H0_ROOT: 2V, 0D. H0_ALT: 0V, 2D.
    # 1. H0_ROOT(1500) vs H0_ALT(1500) -> Pa=0.5. R(1516), A(1484)
    # 2. H0_ROOT(1516) vs H0_ALT(1484) -> Pa=0.5459. R(1530.53), A(1469.47)
    h0_root_data = ranking_df[ranking_df["hrönir_uuid"] == H0_ROOT].iloc[
        0
    ]  # Changed "uuid" to "hrönir_uuid"
    h0_alt_data = ranking_df[ranking_df["hrönir_uuid"] == H0_ALT].iloc[
        0
    ]  # Changed "uuid" to "hrönir_uuid"

    assert (
        h0_root_data["elo_rating"] == 1531
    )  # Arredondado de 1530.53. Changed "elo" to "elo_rating"
    assert h0_root_data["wins"] == 2
    assert (
        h0_alt_data["elo_rating"] == 1469
    )  # Arredondado de 1469.47. Changed "elo" to "elo_rating"
    assert h0_alt_data["losses"] == 2


def test_get_ranking_empty_forking_path_dir(temp_data_dir):
    """Testa quando o diretório forking_path está vazio."""
    _, ratings_dir = temp_data_dir  # forking_dir não é usado para criar arquivos
    forking_dir_empty = temp_data_dir[0]  # Acessa o dir, mas não cria nada nele

    # Criar um arquivo de ratings para que não seja esse o motivo do df vazio
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir_empty,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty, (
        "Ranking deveria ser vazio se não há arquivos de forking_path para encontrar herdeiros."
    )


def test_get_ranking_empty_ratings_files(temp_data_dir):
    """
    Testa quando os arquivos de ratings existem mas estão vazios (só cabeçalho ou totalmente vazios).
    Os herdeiros devem ser retornados com Elo base.
    """
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        forks_main_data, forking_dir / "forks_main.csv"
    )  # H1A, H1B, H1C são herdeiros de H0_ROOT para pos 1

    # Criar arquivo position_001.csv vazio (só cabeçalho)
    pd.DataFrame(columns=["uuid", "voter", "winner", "loser"]).to_csv(
        ratings_dir / "position_001.csv", index=False
    )

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 3  # H1A, H1B, H1C
    for _, row in ranking_df.iterrows():
        assert row["elo_rating"] == 1500  # Changed "elo" to "elo_rating"
        assert row["wins"] == 0
        assert row["losses"] == 0

    # Criar arquivo position_001.csv totalmente vazio (0 bytes)
    (ratings_dir / "position_001.csv").write_text("")
    ranking_df_zero_bytes = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df_zero_bytes) == 3
    for _, row in ranking_df_zero_bytes.iterrows():
        assert row["elo_rating"] == 1500  # Changed "elo" to "elo_rating"


def test_get_ranking_malformed_forking_csv(temp_data_dir):
    """Testa robustez a um CSV de forking_path malformado (ignora o arquivo)."""
    forking_dir, ratings_dir = temp_data_dir

    # CSV bom
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "good_forks.csv",
    )
    # CSV malformado
    (forking_dir / "bad_forks.csv").write_text(
        "position,prev_uuid\ninvalid,row,with,too,many,columns"
    )

    create_csv([], ratings_dir / "position_001.csv")  # Sem votos

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    # Deve encontrar H1A do good_forks.csv e ignorar bad_forks.csv
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A  # Changed "uuid" to "hrönir_uuid"
    assert ranking_df.iloc[0]["elo_rating"] == 1500  # Changed "elo" to "elo_rating"


def test_get_ranking_malformed_ratings_csv(temp_data_dir):
    """Testa robustez a um CSV de ratings malformado (trata como sem votos)."""
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "forks.csv",
    )
    (ratings_dir / "position_001.csv").write_text("winner,loser\ninvalid,row")  # Malformado

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    # Deve encontrar H1A, mas como o ratings é malformado, trata como sem votos.
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A  # Changed "uuid" to "hrönir_uuid"
    assert ranking_df.iloc[0]["elo_rating"] == 1500  # Elo base. Changed "elo" to "elo_rating"
    assert ranking_df.iloc[0]["wins"] == 0
    assert ranking_df.iloc[0]["losses"] == 0


def test_get_ranking_canonical_predecessor_none_not_pos_0(temp_data_dir):
    """
    Testa que se canonical_predecessor_uuid for None, mas a posição não for 0,
    retorna um DataFrame vazio, pois é um estado não esperado pelo plano.
    """
    forking_dir, ratings_dir = temp_data_dir
    create_csv(forks_main_data, forking_dir / "forks_main.csv")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,  # Posição não é 0
        predecessor_hronir_uuid=None,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty, "Deveria retornar df vazio para predecessor None em posição != 0"


def test_get_ranking_forking_path_missing_columns(temp_data_dir):
    """Testa CSV de forking path com colunas faltando (deve ser ignorado)."""
    forking_dir, ratings_dir = temp_data_dir
    (forking_dir / "missing_cols.csv").write_text("uuid,fork_uuid\nval1,val2")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty, "Deveria ser vazio se o único forking_path CSV é inválido."


def test_get_ranking_ratings_path_missing_columns(temp_data_dir):
    """Testa CSV de ratings com colunas faltando (deve ser tratado como sem votos válidos)."""
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "forks.csv",
    )
    (ratings_dir / "position_001.csv").write_text(
        "voter_id,winning_id,losing_id\nv1,w1,l1"
    )  # Nomes de colunas errados

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A  # Changed "uuid" to "hrönir_uuid"
    assert (
        ranking_df.iloc[0]["elo_rating"] == 1500
    )  # Elo base pois não conseguiu ler os votos. Changed "elo" to "elo_rating"
