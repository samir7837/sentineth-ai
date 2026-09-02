from app.providers.embeddings.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        # Imported lazily: sentence-transformers pulls in torch, which is
        # slow and memory-hungry to import. Deferring it here keeps app
        # startup (and any code path not using local embeddings) cheap.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return 384

    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
        )

        return embeddings.tolist()
