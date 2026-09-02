import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.storage.base import StorageProvider
from app.providers.vector.base import VectorStore
from app.services.ingestion_service import ingest_document


async def delete_document(db: Session, organization_id: UUID, document_id: UUID, storage_provider: StorageProvider, vector_store: VectorStore) -> None:
    document = db.get(Document, document_id)
    if document is None or document.organization_id != organization_id:
        raise LookupError("Document not found.")
    await vector_store.delete_document(str(organization_id), str(document_id))
    await storage_provider.delete(document.storage_path)
    db.delete(document)
    db.commit()


async def reindex_document(db: Session, organization_id: UUID, document_id: UUID, embedding_provider: EmbeddingProvider, vector_store: VectorStore) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.organization_id != organization_id:
        raise LookupError("Document not found.")
    await vector_store.delete_document(str(organization_id), str(document_id))
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    db.flush()
    await ingest_document(db, document, embedding_provider, vector_store)
    db.refresh(document)
    return document


def _compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def save_document(
    db: Session,
    organization_id: UUID,
    file: UploadFile,
    storage_provider: StorageProvider,
    embedding_provider: EmbeddingProvider,
    vector_store: VectorStore,
) -> Document:

    file_content = await file.read()

    if not file_content:
        raise ValueError("Uploaded document is empty.")

    content_hash = _compute_sha256(file_content)

    filename = Path(
        file.filename or "unnamed_file"
    ).name

    document = Document(
        organization_id=organization_id,
        filename=filename,
        content_type=(
            file.content_type
            or "application/octet-stream"
        ),
        file_size=len(file_content),
        # Placeholder. The real path needs document.id, which only exists
        # after the flush below, and is set before anything commits.
        storage_path="",
        content_hash=content_hash,
        status="UPLOADED",
        error_message=None,
    )

    # Flush before writing any bytes, so the row and its id exist first. The
    # id is what makes the storage path unique, and a row without a file is
    # recoverable in a way a file without a row is not.
    db.add(document)
    db.flush()

    try:
        document.storage_path = await storage_provider.save(
            organization_id=str(organization_id),
            document_id=str(document.id),
            filename=filename,
            content=file_content,
        )
        db.flush()
    except Exception as exc:
        db.rollback()

        raise ValueError(
            "Failed to store uploaded document."
        ) from exc

    try:
        await ingest_document(
            db=db,
            document=document,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        )

        db.commit()
        db.refresh(document)

    except Exception as exc:
        db.rollback()

        document.status = "FAILED"
        document.error_message = "Document processing failed."

        try:
            db.add(document)
            db.commit()
        except Exception:
            db.rollback()

        raise ValueError(
            "Document processing failed."
        ) from exc

    return document
