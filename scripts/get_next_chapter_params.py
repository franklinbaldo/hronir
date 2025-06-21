import json
import uuid  # For UUID calculation
from pathlib import Path

# Namespace para calcular UUIDs de capítulos de forma determinística
# Este UUID foi gerado aleatoriamente uma vez e agora é fixo para este projeto.
NAMESPACE_HRONIR = uuid.UUID("1345c8a0-3f22-4c69-83c1-55759a2910ba")


def get_uuid_from_content(content: str) -> str:
    """Calcula um UUID v5 determinístico para o conteúdo do capítulo."""
    return str(uuid.uuid5(NAMESPACE_HRONIR, content))


def get_uuid_from_canonical_file(book_dir: Path, canonical_filename: str) -> str | None:
    """
    Extrai o UUID de um arquivo canônico.
    Primeiro tenta pelo nome do arquivo (formato <pos>_<uuid_prefix>.md).
    Se não, lê o conteúdo e calcula o UUID.
    NOTA: Esta função assume que se o prefixo UUID está no nome, ele é o UUID correto.
    Uma abordagem mais robusta seria sempre ler o metadata.json do capítulo original na library.
    Mas para o book/ onde os arquivos são cópias, calcular do conteúdo é uma opção.
    """
    file_path = book_dir / canonical_filename
    if not file_path.exists():
        print(f"Arquivo canônico não encontrado: {file_path}")
        return None

    # Tenta extrair dos primeiros 8 chars do UUID no nome do arquivo, se existir.
    # Ex: "1_dae12890.md" -> "dae12890"
    # Esta é uma simplificação. O ideal seria o book_index.json armazenar o UUID completo.
    parts = canonical_filename.split("_")
    if len(parts) > 1 and len(parts[1].split(".")[0]) >= 8:
        # Não podemos reconstruir o UUID completo a partir do prefixo.
        # Então, vamos calcular a partir do conteúdo.
        pass

    content = file_path.read_text()
    return get_uuid_from_content(content)


def main():
    book_index_path = Path("book/book_index.json")
    book_dir = Path("book")

    # UUID do capítulo 0 (Tlön, Uqbar, Orbis Tertius)
    # Conteúdo: "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia."
    # Este conteúdo está em book/00_tlon_uqbar.md
    chap_0_file = book_dir / "00_tlon_uqbar.md"
    if not chap_0_file.exists():
        print(f"Erro: Arquivo do capítulo 0 não encontrado em {chap_0_file}")
        # Fallback para um UUID conhecido se o arquivo não estiver lá (não ideal)
        # Este UUID é derivado do conteúdo:
        # "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia."
        # usando o NAMESPACE_HRONIR definido acima.
        # uuid.uuid5(uuid.UUID("1345c8a0-3f22-4c69-83c1-55759a2910ba"),
        # "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia.")
        # é 4a9c2a35-3fd0-563a-8c69-c7971e8e616a
        # Este UUID é diferente do usado no exemplo do workflow (dae12890-...),
        # pois o namespace é diferente. É crucial usar o mesmo namespace em todo o projeto.
        # O storage.py usa uuid.NAMESPACE_URL. Vamos alinhar.
        # NAMESPACE_URL = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
        # uuid.uuid5(uuid.NAMESPACE_URL,
        # "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia.")
        # é dae12890-8385-5091-9f63-9a398f281918
        # Vou usar NAMESPACE_URL para consistência com storage.py
        global NAMESPACE_HRONIR
        NAMESPACE_HRONIR = uuid.NAMESPACE_URL  # Alinhando com storage.py
        default_chap_0_uuid = "dae12890-8385-5091-9f63-9a398f281918"
        print(f"Usando UUID padrão para capítulo 0: {default_chap_0_uuid}")
        prev_uuid = default_chap_0_uuid
    else:
        chap_0_content = chap_0_file.read_text()
        # Usar o mesmo namespace que storage.py para consistência
        prev_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, chap_0_content))

    next_pos = 1  # Padrão é gerar para a posição 1

    if book_index_path.exists():
        try:
            data = json.loads(book_index_path.read_text())
            chapters = data.get("chapters", {})
            if chapters:
                # Encontrar a maior posição numérica nas chaves
                numeric_positions = [int(p) for p in chapters.keys() if p.isdigit()]
                if numeric_positions:
                    last_pos = max(numeric_positions)
                    next_pos = last_pos + 1

                    last_pos_filename = chapters.get(str(last_pos))
                    if last_pos_filename:
                        # Tentar obter o UUID do arquivo canônico.
                        # Esta é a parte mais frágil, pois o nome do arquivo em book/ é <pos>_<uuid_prefix>.md
                        # A função get_uuid_from_canonical_file tentará calcular a partir do conteúdo.
                        arg1_book_dir = book_dir
                        arg2_filename = last_pos_filename
                        uuid_from_last_canon = get_uuid_from_canonical_file(
                            arg1_book_dir, arg2_filename
                        )
                        if uuid_from_last_canon:
                            prev_uuid = uuid_from_last_canon
                        else:
                            msg = (
                                f"Não foi possível obter UUID para o último arquivo canônico {last_pos_filename}. "
                                "Usando UUID do cap 0 ou anterior."
                            )
                            print(msg)
                            # Mantém o prev_uuid do capítulo 0 ou o último conhecido válido
                    else:
                        part1 = "Nome do arquivo não encontrado para a"
                        part2 = f" última posição {last_pos}."
                        part3 = "Usando UUID do cap 0 ou anterior."
                        msg = f"{part1}{part2} {part3}"
                        print(msg)
                else:  # Nenhuma chave numérica encontrada (ex: só tem "0")
                    # Se "0" existe, prev_uuid já está (corretamente) como o UUID do capítulo 0.
                    # next_pos continua 1.
                    pass
            # Se não há 'chapters' ou está vazio, prev_uuid é do cap 0, next_pos é 1.
        except json.JSONDecodeError:
            print(f"Erro ao decodificar {book_index_path}. Usando padrões.")
            # prev_uuid (do cap 0) e next_pos=1 já são os padrões.
    else:
        msg = (
            f"{book_index_path} não encontrado. "
            "Usando padrões para gerar a partir do capítulo 0."
        )
        print(msg)
        # prev_uuid (do cap 0) e next_pos=1 já são os padrões.

    # Salvar em arquivos para o GitHub Actions ler
    Path(".next_pos").write_text(str(next_pos))
    Path(".prev_uuid").write_text(prev_uuid)

    print(f"Próxima posição determinada: {next_pos}")
    print(f"UUID do predecessor determinado: {prev_uuid}")


if __name__ == "__main__":
    main()
