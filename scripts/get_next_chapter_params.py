import sys
from pathlib import Path

# Adiciona o diretório pai ao sys.path para permitir importações relativas
# Útil se o script for executado diretamente e precisar importar de hronir_encyclopedia
sys.path.append(str(Path(__file__).resolve().parent.parent))

try:
    from hronir_encyclopedia import storage
except ImportError:
    print(
        "Erro: Não foi possível importar 'hronir_encyclopedia.storage'. Certifique-se de que o PYTHONPATH está configurado ou execute o script de uma maneira que permita a importação (ex: como um módulo)."
    )
    sys.exit(1)


# UUID do hrönir para o capítulo inicial "Tlön, Uqbar..."
# Este é o hrönir_uuid da Posição 0 no data/canonical_path.json
# É usado como fallback se o canonical_path.json não existir ou estiver malformado.
DEFAULT_HRONIR_CHAPTER_0_UUID = "dae9d8b4-3122-56e0-a665-5dfc10101a6b"


def main():
    canonical_path_file = Path("data/canonical_path.json")
    next_pos = 0
    prev_hrönir_uuid = (
        DEFAULT_HRONIR_CHAPTER_0_UUID  # UUID do hrönir predecessor para a próxima geração
    )

    if not canonical_path_file.exists():
        print(f"Arquivo de caminho canônico '{canonical_path_file}' não encontrado.")
        print(
            "Assumindo Posição 0 para a próxima geração, com predecessor padrão (para o capítulo inicial)."
        )
        # Para a primeira geração (posição 0), não há predecessor real,
        # mas para consistência, podemos usar um UUID especial ou o UUID do capítulo inicial
        # se a lógica de geração sempre espera um prev_uuid.
        # No entanto, a lógica de storage.get_canonical_fork_info já trata a Posição 0.
        # O importante é definir next_pos = 0 e um prev_hrönir_uuid que faça sentido
        # para a geração do *primeiro* hrönir, que é o dae9d8b4...
        # Se estamos gerando para a Posição 0, o "predecessor" é conceitualmente nulo.
        # O script de geração usará `next_pos` para determinar a posição do novo hrönir
        # e `prev_hrönir_uuid` como o hrönir ao qual o novo se conecta.

        # Se o arquivo canônico não existe, vamos gerar para a Posição 0.
        # O `prev_hrönir_uuid` para a Posição 0 é tipicamente vazio ou um placeholder.
        # No entanto, `synthesize` espera um `prev` UUID.
        # Se estamos no início absoluto, o primeiro `synthesize` será para `position=0`
        # e `prev` será algo como "00000000-0000-0000-0000-000000000000" ou o UUID do texto semente.
        # Por ora, o script vai focar em encontrar o *fim* do caminho canônico existente.

        # Se o arquivo não existe, o "último" hrönir canônico é, por definição, inexistente.
        # A próxima posição a ser gerada é a 0.
        # O "predecessor" para a posição 0 é uma string vazia ou um UUID nulo,
        # dependendo de como o `store` ou `synthesize` lida com isso.
        # O `DEFAULT_HRONIR_CHAPTER_0_UUID` é o *resultado* da primeira geração, não seu input predecessor.
        # Vamos assumir que se o arquivo não existe, a primeira posição a ser preenchida é 0.
        # E o predecessor para esta primeira posição é uma string vazia.
        next_pos = 0
        prev_hrönir_uuid = ""  # Para a Posição 0, o predecessor é vazio.
        print(
            f"Próxima posição para geração: {next_pos}. Predecessor UUID: '{prev_hrönir_uuid}' (para Posição 0)."
        )

    else:
        try:
            current_pos = 0
            found_end_of_path = False
            while True:  # Itera para encontrar a última posição canônica definida
                canonical_info = storage.get_canonical_fork_info(current_pos, canonical_path_file)
                if canonical_info and "hrönir_uuid" in canonical_info:
                    # Encontrou um hrönir canônico para esta posição.
                    # Este hrönir_uuid é o predecessor para a *próxima* posição.
                    prev_hrönir_uuid = canonical_info["hrönir_uuid"]
                    current_pos += 1  # Move para a próxima posição a ser verificada
                else:
                    # Não há hrönir canônico para current_pos.
                    # Isso significa que current_pos é a próxima posição a ser gerada.
                    next_pos = current_pos
                    found_end_of_path = True
                    # prev_hrönir_uuid já foi definido na iteração anterior como o sucessor do fork canônico de (current_pos - 1)
                    # Se current_pos é 0 e não encontrou, prev_hrönir_uuid será o default (seed) ou vazio.
                    if current_pos == 0:  # Caso especial: Posição 0 não encontrada no arquivo
                        prev_hrönir_uuid = ""  # Predecessor para Posição 0 é vazio
                        print(
                            f"Caminho canônico não contém Posição 0. Próxima posição: {next_pos}. Predecessor UUID: '{prev_hrönir_uuid}'."
                        )
                    else:
                        print(f"Fim do caminho canônico encontrado na Posição {current_pos -1}.")
                        print(
                            f"Hrönir predecessor para a próxima geração (Posição {next_pos}): {prev_hrönir_uuid}"
                        )
                    break

            if not found_end_of_path:  # Segurança, não deve acontecer com o loop while True/break
                print("Não foi possível determinar o fim do caminho canônico. Usando defaults.")
                next_pos = 0
                prev_hrönir_uuid = ""

        except Exception as e:  # Captura json.JSONDecodeError ou outros erros de leitura/lógica
            print(f"Erro ao processar o arquivo de caminho canônico '{canonical_path_file}': {e}")
            print("Assumindo Posição 0 para a próxima geração, com predecessor vazio.")
            next_pos = 0
            prev_hrönir_uuid = ""

    # Salvar em arquivos para o GitHub Actions ler
    Path(".next_pos").write_text(str(next_pos))
    Path(".prev_uuid").write_text(str(prev_hrönir_uuid))

    print(f"Script finalizado. Próxima posição determinada para geração: {next_pos}")
    print(f"UUID do hrönir predecessor para geração: {prev_hrönir_uuid}")


if __name__ == "__main__":
    main()
