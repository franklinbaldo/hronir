import json
import uuid
from pathlib import Path

import pytest

from hronir_encyclopedia.storage import get_canonical_uuid, compute_uuid


# Helper para criar um UUIDv5 válido para testes
def create_valid_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


@pytest.fixture
def temp_book_index_file(tmp_path: Path) -> Path:
    return tmp_path / "book_index.json"


def test_get_canonical_uuid_success(temp_book_index_file: Path):
    """Testa a recuperação bem-sucedida de um UUID canônico."""
    test_uuid = create_valid_uuid("chapter1.md")
    book_index_content = {
        "title": "Test Encyclopedia",
        "chapters": {
            "0": {"uuid": create_valid_uuid("chapter0.md"), "filename": "0_intro.md"},
            "1": {"uuid": test_uuid, "filename": "1_chapter_one.md"},
        },
    }
    temp_book_index_file.write_text(json.dumps(book_index_content))

    retrieved_uuid = get_canonical_uuid(position=1, book_index_path=temp_book_index_file)
    assert retrieved_uuid == test_uuid


def test_get_canonical_uuid_file_not_found(tmp_path: Path):
    """Testa o erro quando o arquivo book_index.json não existe."""
    non_existent_file = tmp_path / "non_existent_index.json"
    with pytest.raises(FileNotFoundError, match="Arquivo de índice do livro não encontrado"):
        get_canonical_uuid(position=0, book_index_path=non_existent_file)


def test_get_canonical_uuid_invalid_json(temp_book_index_file: Path):
    """Testa o erro quando o arquivo book_index.json contém JSON inválido."""
    temp_book_index_file.write_text("invalid json content {")
    with pytest.raises(ValueError, match="Erro ao decodificar JSON"):
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)


def test_get_canonical_uuid_no_chapters_key(temp_book_index_file: Path):
    """Testa o erro quando a chave 'chapters' está ausente."""
    book_index_content = {"title": "Test Encyclopedia"}
    temp_book_index_file.write_text(json.dumps(book_index_content))
    with pytest.raises(ValueError, match="a chave 'chapters' não é um dicionário ou está ausente"):
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)


def test_get_canonical_uuid_chapters_not_dict(temp_book_index_file: Path):
    """Testa o erro quando 'chapters' não é um dicionário."""
    book_index_content = {"title": "Test Encyclopedia", "chapters": "not a dict"}
    temp_book_index_file.write_text(json.dumps(book_index_content))
    with pytest.raises(ValueError, match="a chave 'chapters' não é um dicionário ou está ausente"):
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)


def test_get_canonical_uuid_position_not_found(temp_book_index_file: Path):
    """Testa o erro quando a posição especificada não é encontrada."""
    book_index_content = {
        "title": "Test Encyclopedia",
        "chapters": {"0": {"uuid": create_valid_uuid("chap0.md"), "filename": "0_intro.md"}},
    }
    temp_book_index_file.write_text(json.dumps(book_index_content))
    with pytest.raises(KeyError, match="Nenhuma entrada de dicionário encontrada para a posição '1'"):
        get_canonical_uuid(position=1, book_index_path=temp_book_index_file)


def test_get_canonical_uuid_entry_not_dict(temp_book_index_file: Path):
    """Testa o erro quando a entrada para uma posição não é um dicionário."""
    book_index_content = {
        "title": "Test Encyclopedia",
        "chapters": {"0": "not a dict entry"},
    }
    temp_book_index_file.write_text(json.dumps(book_index_content))
    with pytest.raises(KeyError, match="Nenhuma entrada de dicionário encontrada para a posição '0'"):
        # A mensagem de erro é a mesma de posição não encontrada porque o get interno falha
        # e depois a verificação de tipo falha. Poderia ser melhorado na função principal,
        # mas o importante é que levanta um erro apropriado.
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)


def test_get_canonical_uuid_no_uuid_in_entry(temp_book_index_file: Path):
    """Testa o erro quando a entrada da posição não contém uma chave 'uuid'."""
    book_index_content = {
        "title": "Test Encyclopedia",
        "chapters": {"0": {"filename": "0_intro.md"}}, # Sem 'uuid'
    }
    temp_book_index_file.write_text(json.dumps(book_index_content))
    with pytest.raises(ValueError, match="Nenhum 'uuid' encontrado para a posição '0'"):
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)


def test_get_canonical_uuid_invalid_uuid_format(temp_book_index_file: Path):
    """Testa o erro quando o UUID armazenado não é um UUIDv5 válido."""
    invalid_uuid_string = "not-a-valid-uuid"
    book_index_content = {
        "title": "Test Encyclopedia",
        "chapters": {"0": {"uuid": invalid_uuid_string, "filename": "0_intro.md"}},
    }
    temp_book_index_file.write_text(json.dumps(book_index_content))
    with pytest.raises(ValueError, match=f"UUID inválido '{invalid_uuid_string}' encontrado"):
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)

# Adicionar mais testes para outros cenários de get_canonical_uuid se necessário.
# Por exemplo, diferentes tipos de dados para posição (embora a função use str(position)).
# Testar com um arquivo book_index.json vazio (deve falhar ao decodificar ou na chave 'chapters').

def test_get_canonical_uuid_empty_book_index_file(temp_book_index_file: Path):
    """Testa o comportamento com um arquivo book_index.json vazio."""
    temp_book_index_file.write_text("") # Arquivo vazio
    with pytest.raises(ValueError, match="Erro ao decodificar JSON"): # json.load falha com string vazia
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)

def test_get_canonical_uuid_empty_json_object(temp_book_index_file: Path):
    """Testa o comportamento com um objeto JSON vazio {}."""
    temp_book_index_file.write_text("{}") # Objeto JSON vazio
    with pytest.raises(ValueError, match="a chave 'chapters' não é um dicionário ou está ausente"):
        get_canonical_uuid(position=0, book_index_path=temp_book_index_file)

def test_get_canonical_uuid_position_as_string_in_json(temp_book_index_file: Path):
    """Testa se a função lida com chaves de posição que já são strings."""
    test_uuid = create_valid_uuid("chapter1_s.md")
    book_index_content = {
        "title": "Test Encyclopedia",
        "chapters": {
            "0": {"uuid": create_valid_uuid("chapter0_s.md"), "filename": "0_intro.md"},
            "1": {"uuid": test_uuid, "filename": "1_chapter_one.md"}, # Posição é string "1"
        },
    }
    temp_book_index_file.write_text(json.dumps(book_index_content))
    retrieved_uuid = get_canonical_uuid(position=1, book_index_path=temp_book_index_file) # Passando int
    assert retrieved_uuid == test_uuid
    retrieved_uuid_str_pos = get_canonical_uuid(position="1", book_index_path=temp_book_index_file) # Passando str
    assert retrieved_uuid_str_pos == test_uuid

# (Opcional) Testar a função is_valid_uuid_v5 diretamente se não estiver coberta em outro lugar
# from hronir_encyclopedia.storage import is_valid_uuid_v5
# def test_is_valid_uuid_v5():
#     assert is_valid_uuid_v5(create_valid_uuid("test")) is True
#     assert is_valid_uuid_v5(str(uuid.uuid4())) is False # uuid4
#     assert is_valid_uuid_v5("not-a-uuid") is False
#     assert is_valid_uuid_v5(str(uuid.uuid3(uuid.NAMESPACE_DNS, "test"))) is False # uuid3
# A função compute_uuid já está em storage.py, mas não é diretamente usada por get_canonical_uuid.
# O helper create_valid_uuid usa uuid.uuid5 diretamente para clareza nos testes.
# A função is_valid_uuid_v5 já existe em storage.py e é usada internamente por get_canonical_uuid.
# Os testes para is_valid_uuid_v5 podem ser adicionados aqui ou em test_storage_and_votes.py
# se for mais apropriado. Por agora, focaremos nos testes de get_canonical_uuid.

# Adicionando o teste de is_valid_uuid_v5 aqui para completude
from hronir_encyclopedia.storage import is_valid_uuid_v5

def test_is_valid_uuid_v5_positive():
    """Testa UUIDs v5 válidos."""
    assert is_valid_uuid_v5(str(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))) is True
    assert is_valid_uuid_v5(str(uuid.uuid5(uuid.NAMESPACE_URL, "http://example.com"))) is True

def test_is_valid_uuid_v5_negative_invalid_string():
    """Testa strings que não são UUIDs."""
    assert is_valid_uuid_v5("not-a-uuid") is False
    assert is_valid_uuid_v5("") is False
    assert is_valid_uuid_v5("12345678-1234-1234-1234-1234567890ab") is False # Parece UUID, mas versão errada

def test_is_valid_uuid_v5_negative_other_versions():
    """Testa UUIDs de outras versões."""
    assert is_valid_uuid_v5(str(uuid.uuid1())) is False
    assert is_valid_uuid_v5(str(uuid.uuid3(uuid.NAMESPACE_DNS, "example.com"))) is False
    assert is_valid_uuid_v5(str(uuid.uuid4())) is False

def test_is_valid_uuid_v5_malformed_uuid_string():
    """Testa strings UUID malformadas."""
    # UUID muito curto
    assert is_valid_uuid_v5("d944b780-4f9a-59a1-8a48") is False
    # UUID com caracteres inválidos
    assert is_valid_uuid_v5("d944b780-4f9a-59a1-8a48-xxxxxxxxxxxxZ") is False
