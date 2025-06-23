import os

import google.generativeai as genai
import numpy as np

# Modelo de embedding a ser usado.
# A documentação menciona "gemini-embedding-exp-03-07", "text-embedding-004", "embedding-001"
# Vamos usar o mais recente ou recomendado, gemini-embedding-exp-03-07 por agora.
EMBEDDING_MODEL = "gemini-embedding-exp-03-07"


def get_embeddings(
    texts: list[str], task_type: str = "SEMANTIC_SIMILARITY"
) -> list[list[float]] | None:
    """
    Gera embeddings para uma lista de textos usando a API Gemini.

    Args:
        texts: Uma lista de strings para gerar embeddings.
        task_type: O tipo de tarefa para otimizar os embeddings.
                   Padrão é "SEMANTIC_SIMILARITY". Outros podem ser
                   "RETRIEVAL_DOCUMENT" para busca, etc.

    Returns:
        Uma lista de embeddings (lista de listas de float), ou None se ocorrer um erro
        ou a chave de API não estiver configurada.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Erro: GEMINI_API_KEY não configurada.")
        return None

    try:
        # genai.configure(api_key=api_key) # Não é mais necessário se o cliente é instanciado com a chave
        # O cliente é instanciado em gemini_util, idealmente deveríamos reutilizá-lo
        # ou passar a chave para cá de forma mais explícita.
        # Por simplicidade, vamos instanciar um cliente aqui também por enquanto.
        client = genai.Client(api_key=api_key)

        # A API pode aceitar uma lista de textos diretamente em `contents`.
        # No entanto, a documentação para `embed_content` mostra `contents` como uma string única.
        # E "You can also generate embeddings for multiple chunks at once by passing them in as a list of strings."
        # Isso sugere que `contents` pode ser uma lista.
        # Se `contents` for uma string, precisamos iterar.
        # Se `contents` pode ser List[str], melhor.
        # A API reference (https://ai.google.dev/api/python/google/generativeai/GenerativeModel/embed_content)
        # mostra `content: Content | str | Iterable[str]`
        # Então podemos passar a lista diretamente.

        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            content=texts,
            task_type=task_type,  # Passando a lista de textos
        )
        return result.get("embedding") if isinstance(result, dict) else result.embeddings
    except Exception as e:
        print(f"Erro ao gerar embeddings: {e}")
        return None


def get_average_embedding(embeddings: list[list[float]]) -> list[float] | None:
    """
    Calcula a média de uma lista de vetores de embedding.
    """
    if not embeddings:
        return None

    embedding_array = np.array(embeddings)
    avg_embedding = np.mean(embedding_array, axis=0)
    return avg_embedding.tolist()


def get_narrative_space_embedding(
    chapter_texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",  # Usar um tipo de tarefa para documentos
) -> list[float] | None:
    """
    Gera um embedding único representando o espaço narrativo de uma lista de capítulos.

    Args:
        chapter_texts: Uma lista de strings, cada uma sendo o conteúdo de um capítulo.
        task_type: O tipo de tarefa para os embeddings.

    Returns:
        Um único vetor de embedding (lista de float) representando a média dos embeddings
        dos capítulos, ou None se ocorrer um erro.
    """
    if not chapter_texts:
        return None

    embeddings = get_embeddings(texts=chapter_texts, task_type=task_type)

    if embeddings:
        return get_average_embedding(embeddings)
    return None


if __name__ == "__main__":
    # Exemplo de uso (requer GEMINI_API_KEY no ambiente)
    # Configurar a chave para teste local:
    # from dotenv import load_dotenv
    # load_dotenv()
    # if not os.getenv("GEMINI_API_KEY"):
    # print("Por favor, configure GEMINI_API_KEY no seu arquivo .env para testar.")
    # exit()

    sample_texts = [
        "I owe the discovery of Uqbar to the conjunction of a mirror and an encyclopedia.",
        "The unsettling truth is that Tlön is a vast, intricate conspiracy of intellectuals.",
        "Orbis Tertius is the name of the secret society that conceived Tlön.",
    ]

    print(f"Testando com {len(sample_texts)} textos de exemplo:")

    # Teste 1: Obter embeddings individuais
    individual_embeddings = get_embeddings(sample_texts)
    if individual_embeddings:
        print(f"Obtidos {len(individual_embeddings)} embeddings individuais.")
        for i, emb in enumerate(individual_embeddings):
            print(f"  Embedding {i + 1} (primeiras 5 dimensões de {len(emb)}): {emb[:5]}")
    else:
        print("Falha ao obter embeddings individuais.")

    print("\n---\n")

    # Teste 2: Obter embedding médio do espaço narrativo
    narrative_embedding = get_narrative_space_embedding(sample_texts)
    if narrative_embedding:
        print(
            f"Embedding médio do espaço narrativo (primeiras 5 dimensões de {len(narrative_embedding)}):"
        )
        print(f"  {narrative_embedding[:5]}")
    else:
        print("Falha ao obter embedding do espaço narrativo.")

    # Teste com um único texto
    single_text_embedding = get_narrative_space_embedding([sample_texts[0]])
    if single_text_embedding:
        print(
            f"\nEmbedding para um único texto (primeiras 5 dimensões de {len(single_text_embedding)}):"
        )
        print(f"  {single_text_embedding[:5]}")

    # Teste com lista vazia
    empty_embedding = get_narrative_space_embedding([])
    if empty_embedding is None:
        print("\nTeste com lista vazia retornou None (correto).")
    else:
        print(f"\nTeste com lista vazia retornou: {empty_embedding} (incorreto).")

    # Teste de get_embeddings com erro (sem chave, se não estiver configurada)
    # current_key = os.environ.pop("GEMINI_API_KEY", None)
    # print("\nTestando get_embeddings sem GEMINI_API_KEY (esperado falhar):")
    # error_embeddings = get_embeddings(["teste"])
    # if error_embeddings is None:
    # print("  Falhou como esperado.")
    # else:
    # print(f"  Obteve embeddings inesperadamente: {error_embeddings}")
    # if current_key:
    # os.environ["GEMINI_API_KEY"] = current_key # Restaurar chave
