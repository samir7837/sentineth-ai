from sentence_transformers import SentenceTransformer

from app.providers.embeddings.base import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
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