from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Length of the vectors this provider produces.

        The vector store must be configured with the same value.
        Changing provider or model without recreating the collection
        and re-embedding is not supported. See AGENTS.md section 14.
        """

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        pass
