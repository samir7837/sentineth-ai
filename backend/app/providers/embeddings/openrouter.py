import os

from openai import AsyncOpenAI

from app.providers.embeddings.base import EmbeddingProvider


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured.")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=os.getenv(
                "OPENROUTER_BASE_URL",
                "https://openrouter.ai/api/v1",
            ),
        )

        self._model = os.getenv(
            "OPENROUTER_EMBEDDING_MODEL",
            "nvidia/nemotron-3-embed-1b:free",
        )

    @property
    def dimension(self) -> int:
        return 2048

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )

        return [
            item.embedding
            for item in response.data
        ]