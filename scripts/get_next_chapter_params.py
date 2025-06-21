import json
import uuid # Para o namespace UUID.NAMESPACE_URL
from pathlib import Path

# Este script determina a próxima posição do capítulo a ser gerado e o UUID do seu predecessor.
# Ele lê o book_index.json para encontrar o último capítulo canônico.

# UUID do capítulo 0 (Tlön, Uqbar, Orbis Tertius) - usado como fallback.
# Conteúdo original: "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia."
# Calculado com uuid.uuid5(uuid.NAMESPACE_URL, CONTENT_CHAP_0)
# NAMESPACE_URL = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
DEFAULT_CHAPTER_0_CONTENT = "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia."
DEFAULT_CHAPTER_0_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, DEFAULT_CHAPTER_0_CONTENT))
# Este UUID é dae12890-8385-5091-9f63-9a398f281918

def get_chapter_0_uuid(book_dir: Path, filename: str = "00_tlon_uqbar.md") -> str:
    """
    Tenta ler o conteúdo do arquivo do capítulo 0 e calcular seu UUID.
    Se o arquivo não existir, retorna o UUID padrão pré-calculado.
    """
    chap_0_file_path = book_dir / filename
    if chap_0_file_path.exists():
        try:
            content = chap_0_file_path.read_text()
            # É importante que o UUID seja calculado da mesma forma que no storage.py (usando NAMESPACE_URL)
            return str(uuid.uuid5(uuid.NAMESPACE_URL, content))
        except Exception as e:
            print(f"Erro ao ler ou calcular UUID para {chap_0_file_path}: {e}. Usando UUID padrão para cap 0.")
            return DEFAULT_CHAPTER_0_UUID
    else:
        print(f"Arquivo do capítulo 0 ({chap_0_file_path}) não encontrado. Usando UUID padrão para cap 0.")
        return DEFAULT_CHAPTER_0_UUID

def main():
    book_index_path = Path("book/book_index.json")
    book_dir = Path("book") # Usado para encontrar o arquivo do capítulo 0

    # Determinar o UUID do predecessor
    # Começa com o UUID do capítulo 0 como padrão.
    prev_uuid = get_chapter_0_uuid(book_dir)
    next_pos = 1  # Padrão é gerar para a posição 1, sucessora do capítulo 0.

    if book_index_path.exists():
        try:
            data = json.loads(book_index_path.read_text())
            chapters = data.get("chapters", {})

            if chapters:
                numeric_positions = []
                for p_str in chapters.keys():
                    try:
                        numeric_positions.append(int(p_str))
                    except ValueError:
                        # Ignorar chaves não numéricas (ex: "title", ou se o formato mudar)
                        # No entanto, o capítulo "0" (zero) é uma posição válida.
                        if p_str == "0": # Tratar "0" como numérico para consistência
                             numeric_positions.append(0)
                        else:
                            print(f"Aviso: Ignorando chave de capítulo não numérica ou não tratada: '{p_str}'")


                if numeric_positions: # Verifica se há alguma posição numérica (incluindo 0)
                    last_pos = max(numeric_positions)
                    next_pos = last_pos + 1 # A próxima posição é sempre last_pos + 1

                    # Obter o UUID do último capítulo diretamente do book_index
                    last_chapter_info = chapters.get(str(last_pos))

                    if isinstance(last_chapter_info, dict) and "uuid" in last_chapter_info:
                        prev_uuid = last_chapter_info["uuid"]
                        print(f"Última posição canônica encontrada: {last_pos}. UUID do predecessor: {prev_uuid}")
                    elif isinstance(last_chapter_info, str) and last_pos == 0:
                        # Caso especial: se book_index.json ainda estiver no formato antigo apenas para o cap 0
                        # e last_pos é 0, prev_uuid já foi definido por get_chapter_0_uuid.
                        # Isso mantém a compatibilidade retroativa se o cap 0 não foi atualizado no index.
                        print(f"Capítulo 0 encontrado no formato antigo. Usando UUID calculado: {prev_uuid}")
                    elif last_pos == 0 and not last_chapter_info: # Caso o cap 0 não esteja no index mas seja o único
                         print(f"Índice de livro não contém explicitamente o capítulo 0. Usando UUID calculado para o cap 0: {prev_uuid}")
                    else:
                        # Se a informação do último capítulo não for um dict com 'uuid' (e não for o caso especial do cap 0)
                        # ou se last_pos não estiver em chapters (não deveria acontecer se numeric_positions não estiver vazio)
                        print(f"Aviso: UUID não encontrado para a última posição canônica ({last_pos}) no book_index.json.")
                        print(f"Usando o UUID do capítulo anterior conhecido ou do capítulo 0: {prev_uuid}")
                        # Neste caso, prev_uuid mantém o valor do capítulo anterior válido ou do capítulo 0.
                        # Se last_pos > 0, isso significa que o predecessor de next_pos (last_pos) não tem UUID
                        # no índice. Isso é um estado inconsistente do índice.
                        # O script tentará prosseguir com o melhor prev_uuid que tem (que pode ser o do cap 0).
                else:
                    # Nenhuma posição numérica encontrada, mas 'chapters' existe (pode ser um índice vazio {}).
                    # Ou pode ter tido chaves não numéricas que foram ignoradas.
                    # prev_uuid (do cap 0) e next_pos=1 já são os padrões corretos.
                    print("Nenhuma posição numérica de capítulo encontrada no índice. Usando padrões baseados no capítulo 0.")
            else:
                # 'chapters' está vazio ou não existe no JSON.
                # prev_uuid (do cap 0) e next_pos=1 já são os padrões corretos.
                print("Nenhum capítulo encontrado no book_index.json. Usando padrões baseados no capítulo 0.")

        except json.JSONDecodeError:
            print(f"Erro ao decodificar {book_index_path}. Usando padrões baseados no capítulo 0.")
            # prev_uuid (do cap 0) e next_pos=1 já são os padrões.
    else:
        print(f"{book_index_path} não encontrado. Usando padrões baseados no capítulo 0.")
        # prev_uuid (do cap 0) e next_pos=1 já são os padrões.

    # Salvar em arquivos para o GitHub Actions ler
    Path(".next_pos").write_text(str(next_pos))
    Path(".prev_uuid").write_text(str(prev_uuid))

    print(f"Próxima posição determinada para geração: {next_pos}")
    print(f"UUID do predecessor para geração: {prev_uuid}")


if __name__ == "__main__":
    main()
    Path(".prev_uuid").write_text(prev_uuid)

    print(f"Próxima posição determinada: {next_pos}")
    print(f"UUID do predecessor determinado: {prev_uuid}")


if __name__ == "__main__":
    main()
