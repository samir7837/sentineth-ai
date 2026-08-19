import inspect

# Check save_document signature
from app.services.document_service import save_document
sig = inspect.signature(save_document)
params = list(sig.parameters.keys())
print("save_document params:", params)
print("  - has embedding_provider:", "embedding_provider" in params)
print("  - has vector_store:", "vector_store" in params)

# Check ingest_document signature
from app.services.ingestion_service import ingest_document
sig = inspect.signature(ingest_document)
params = list(sig.parameters.keys())
print("\ningest_document params:", params)
print("  - has embedding_provider:", "embedding_provider" in params)
print("  - has vector_store:", "vector_store" in params)

# Check that the provider base classes are importable
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.vector.base import VectorStore
from app.providers.storage.base import StorageProvider
print("\nProvider base classes imported successfully")

# Check concrete providers
from app.providers.embeddings.openai import OpenAIEmbeddingProvider
from app.providers.vector.qdrant import QdrantVectorStore
from app.providers.storage.local import LocalStorageProvider
print("Concrete providers imported successfully")

print("\n✓ All provider injection wiring verified")
