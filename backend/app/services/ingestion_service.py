from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.vector.base import VectorStore
from app.services.chunking_service import chunk_text
from app.services.extraction_service import extract_text_from_pdf


async def ingest_document(
    db: Session,
    document: Document,
    embedding_provider: EmbeddingProvider,
    vector_store: VectorStore,
) -> list[DocumentChunk]:
    document.status = "PROCESSING"
    document.error_message = None
    document.error_code = None

    try:
        if document.content_type != "application/pdf":
            raise ValueError(
                "Only PDF documents are supported right now."
            )

        # Extract text from the stored document.
        text = extract_text_from_pdf(
            document.storage_path
        )

        # Split extracted text into chunks.
        chunks = chunk_text(text)

        if not chunks:
            raise ValueError(
                "Document produced no usable chunks."
            )

        # Create database chunk records.
        document_chunks: list[DocumentChunk] = []

        for index, content in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=content,
            )

            db.add(chunk)
            document_chunks.append(chunk)

        # Flush so chunk IDs are generated before creating
        # the Qdrant payloads.
        db.flush()

        # Generate embeddings for every chunk.
        chunk_texts = [
            chunk.content
            for chunk in document_chunks
        ]

        embeddings = await embedding_provider.embed(
            chunk_texts
        )

        if len(embeddings) != len(document_chunks):
            raise ValueError(
                "Embedding count does not match chunk count."
            )

        # Build organization-scoped Qdrant payloads.
        payloads: list[dict[str, Any]] = []

        organization_id = str(
            document.organization_id
        )

        for chunk in document_chunks:
            payloads.append(
                {
                    "organization_id": organization_id,
                    "document_id": str(document.id),
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "filename": document.filename,
                }
            )

        # Store embeddings in Qdrant.
        await vector_store.upsert(
            organization_id=organization_id,
            vectors=embeddings,
            payloads=payloads,
        )

        # Everything succeeded.
        document.status = "READY"
        document.error_message = None
        document.error_code = None

        db.commit()

        return document_chunks

    except Exception as exc:
        document.status = "FAILED"
        document.error_message = "Document processing failed."
        document.error_code = "PROCESSING_FAILED"

        db.rollback()

        raise ValueError(
            "Document processing failed."
        ) from exc