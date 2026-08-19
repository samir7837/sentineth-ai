import os
from typing import Any

from openai import AsyncOpenAI

from app.providers.embeddings.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
        organization: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required to use OpenAIEmbeddingProvider.")

        self.model = model
        self.base_url = base_url
        self.organization = organization
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            organization=self.organization,
            **kwargs,
        )

    @property
    def dimension(self) -> int:
        return 1536

    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return []

        response = await self._client.embeddings.create(
            model=self.model,
            input=texts,
        )

        return [item.embedding for item in response.data]
