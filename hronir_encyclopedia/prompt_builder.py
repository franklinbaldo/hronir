
# Limite de palavras para o trecho do capítulo anterior a ser incluído no prompt
PREDECESSOR_SNIPPET_WORD_LIMIT = 100


def get_predecessor_snippet(text: str, word_limit: int) -> str:
    """
    Retorna as últimas 'word_limit' palavras de um texto.
    """
    words = text.split()
    if len(words) > word_limit:
        return " ".join(words[-word_limit:])
    return text


def build_synthesis_prompt(
    predecessor_text: str,
    predecessor_uuid: str,
    predecessor_position: int,  # Posição do capítulo predecessor
    next_position: int,
    narrative_embedding: list[float] | None = None,  # Placeholder para uso futuro
) -> str:
    """
    Constrói um prompt para o LLM sintetizar o próximo capítulo.

    Args:
        predecessor_text: O texto completo do capítulo predecessor.
        predecessor_uuid: UUID do capítulo predecessor.
        predecessor_position: A posição do capítulo predecessor.
        next_position: A posição do novo capítulo a ser gerado.
        narrative_embedding: O embedding representando o espaço narrativo atual (uso futuro).

    Returns:
        Uma string de prompt formatada.
    """

    snippet = get_predecessor_snippet(predecessor_text, PREDECESSOR_SNIPPET_WORD_LIMIT)

    prompt = f"""Você é um escritor no estilo de Jorge Luis Borges, criando capítulos para uma enciclopédia fantástica e labiríntica.

O capítulo anterior (Posição {predecessor_position}, UUID: {predecessor_uuid}) conclui com o seguinte trecho:
---
...{snippet}
---

Sua tarefa é escrever o próximo capítulo (Posição {next_position}).

Instruções:
1.  Continue a narrativa a partir do capítulo anterior, expandindo os temas e o mistério.
2.  Mantenha um tom erudito, filosófico e ligeiramente perturbador, característico de Borges.
3.  Introduza novos elementos, conceitos ou reflexões que se entrelacem com o já estabelecido, mas que também abram novas avenidas de pensamento.
4.  O capítulo deve ser relativamente conciso, evocando mais do que explicitando. Idealmente, entre 200 e 500 palavras.
5.  Evite repetições diretas do trecho fornecido; use-o como ponto de partida para novas ideias.
6.  Se o espaço narrativo acumulado (representado por um embedding vetorial, não diretamente visível a você aqui) sugerir certos temas ou direções, deixe que essas influências sutis guiem sua escrita. (Esta é uma nota para o sistema, você deve focar na continuidade e no estilo.)

Comece diretamente com o texto do novo capítulo.
"""
    # TODO (Futuro): Usar o narrative_embedding para:
    # 1. Extrair palavras-chave ou conceitos temáticos e injetá-los no prompt.
    #    (Ex: "A história até agora ressoa com os conceitos de X, Y, Z. Explore um deles ou introduza um novo que se relacione.")
    # 2. Validar a coerência do capítulo gerado em relação ao espaço narrativo.

    if (
        narrative_embedding
    ):  # Apenas para mostrar que foi recebido, não usado no prompt em si ainda.
        print(
            f"[PromptBuilder] Embedding do espaço narrativo recebido (dimensões: {len(narrative_embedding)}), mas ainda não usado ativamente na construção do prompt de texto."
        )

    return prompt


if __name__ == "__main__":
    # Exemplo de uso
    sample_predecessor_text = (
        "As páginas da enciclopédia falavam de um planeta chamado Tlön. "
        "No início, pensei que fosse um mero exercício de erudição, uma ficção engenhosa. "
        "Contudo, os detalhes eram demasiadamente precisos, a geografia e a história "
        "demasiadamente coerentes. Havia mapas de suas regiões, cronologias de suas dinastias, "
        "gramáticas de suas línguas impossíveis. O mais alarmante eram os objetos de Tlön: "
        " bússolas que apontavam para um norte inexistente, moedas de um metal desconhecido, "
        "artefatos cuja função era inimaginável. Pouco a pouco, o mundo começou a ser invadido por Tlön. "
        "Um espelho refletiu o que não estava lá. Uma enciclopédia apócrifa começou a reescrever a realidade."
    )
    sample_uuid = "abc-123"
    sample_pred_pos = 0
    sample_next_pos = 1

    # Simular um embedding (não será usado no prompt desta versão)
    sample_embedding = [0.1] * 768  # Dimensão típica de embeddings

    generated_prompt = build_synthesis_prompt(
        predecessor_text=sample_predecessor_text,
        predecessor_uuid=sample_uuid,
        predecessor_position=sample_pred_pos,
        next_position=sample_next_pos,
        narrative_embedding=sample_embedding,
    )

    print("\n--- PROMPT GERADO ---")
    print(generated_prompt)

    print(f"\n--- Snippet usado (últimas {PREDECESSOR_SNIPPET_WORD_LIMIT} palavras) ---")
    print(get_predecessor_snippet(sample_predecessor_text, PREDECESSOR_SNIPPET_WORD_LIMIT))

    short_text = "Uma frase curta."
    print(f"\n--- Snippet de texto curto ({PREDECESSOR_SNIPPET_WORD_LIMIT} palavras) ---")
    print(get_predecessor_snippet(short_text, PREDECESSOR_SNIPPET_WORD_LIMIT))
