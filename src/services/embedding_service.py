from src.ai.clients.cohere_client import co


def get_embedding(text: str):
    """
    Convert text into vector embedding using Cohere.
    Uses input_type='search_document' — for STORING documents in the database.
    """

    response = co.embed(
        texts=[text],
        model="embed-english-v3.0",
        input_type="search_document"
    )

    return response.embeddings[0]


def get_query_embedding(text: str):
    """
    Convert a search query into vector embedding using Cohere.
    Uses input_type='search_query' — for SEARCHING against stored documents.
    
    Cohere v3 embedding models produce better retrieval accuracy when
    queries and documents use their respective input_type values.
    """

    response = co.embed(
        texts=[text],
        model="embed-english-v3.0",
        input_type="search_query"
    )

    return response.embeddings[0]