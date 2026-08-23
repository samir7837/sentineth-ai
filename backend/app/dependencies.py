"""Application-scoped provider factories used as FastAPI dependencies.

Providers are cached for the lifetime of the process. Before this module
existed, `Depends(get_embedding_provider)` constructed a new
`LocalEmbeddingProvider` on *every* request, which reloaded the
all-MiniLM-L6-v2 weights from disk each time, and every request also
re-ran the Qdrant `collection_exists` round-trip.

Caching here is what AGENTS.md section 29-30 asks for: a single place that owns
provider construction, with heavyweight clients reused rather than
rebuilt per request.

The cached factories are plain functions, so they can also be called
from scripts and background jobs, not just from request handlers.
"""

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.local import LocalEmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.providers.llm.openrouter import OpenRouterProvider
from app.providers.storage.base import StorageProvider
from app.providers.storage.local import LocalStorageProvider
from app.providers.vector.base import VectorStore
from app.providers.vector.qdrant import QdrantVectorStore


logger = logging.getLogger(__name__)


# backend/
BACKEND_DIR = Path(__file__).resolve().parents[1]

STORAGE_DIR = BACKEND_DIR / "storage" / "documents"


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    provider = LocalEmbeddingProvider()

    logger.info(
        "Embedding provider ready: %s (dimension=%s)",
        type(provider).__name__,
        provider.dimension,
    )

    return provider


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    # Derive the collection dimension from the active embedding provider
    # instead of hardcoding it, so the two can never drift apart.
    dimension = get_embedding_provider().dimension

    store = QdrantVectorStore(
        vector_size=dimension,
    )

    logger.info(
        "Vector store ready: collection=%s dimension=%s",
        store.collection_name,
        dimension,
    )

    return store


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    return LocalStorageProvider(STORAGE_DIR)


@lru_cache(maxsize=1)
def _build_llm_provider() -> LLMProvider:
    return OpenRouterProvider()


def get_llm_provider() -> LLMProvider:
    # lru_cache does not cache exceptions, so a misconfigured provider
    # keeps raising instead of poisoning the cache with a failure.
    try:
        return _build_llm_provider()
    except ValueError as exc:
        logger.error("LLM provider is not configured: %s", exc)

        raise HTTPException(
            status_code=500,
            detail="LLM provider is not configured.",
        ) from exc


def reset_provider_cache() -> None:
    """Drop all cached providers.

    Intended for tests and for scripts that change provider
    configuration at runtime.
    """
    get_embedding_provider.cache_clear()
    get_vector_store.cache_clear()
    get_storage_provider.cache_clear()
    _build_llm_provider.cache_clear()
