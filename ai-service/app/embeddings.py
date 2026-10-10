from .ai_client import AIProvider

async def embed_batches(provider: AIProvider, texts: list[str], size: int = 32) -> list[list[float]]:
    vectors = []
    for start in range(0, len(texts), size):
        vectors.extend(await provider.embed(texts[start:start + size], task_type='RETRIEVAL_DOCUMENT'))
    return vectors
