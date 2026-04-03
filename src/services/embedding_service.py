from src.ai.clients.cohere_client import co


def get_embedding(text: str):
    """
    Convert text into vector embedding using Cohere
    """

    response = co.embed(
        texts=[text],
        model="embed-english-v3.0",
        input_type="search_document"
    )

    return response.embeddings[0]