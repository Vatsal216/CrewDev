from typing import Optional
from config import settings

_voyage_client = None


def _get_voyage():
    global _voyage_client
    if not _voyage_client and settings.voyage_api_key:
        import voyageai
        _voyage_client = voyageai.Client(api_key=settings.voyage_api_key)
    return _voyage_client


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    vc = _get_voyage()
    if vc:
        result = vc.embed(texts, model=settings.embed_model)
        return result.embeddings
    # Fallback: zero vectors (dev mode without voyage key)
    return [[0.0] * 1024 for _ in texts]
