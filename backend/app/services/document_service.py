import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models import Document
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.storage.base import StorageProvider
from app.providers.vector.base import VectorStore
from app.services.ingestion_service import ingest_document


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

    try:
        storage_path = await storage_provider.save(
            organization_id=str(organization_id),
            filename=filename,
            content=file_content,
        )
    except Exception as exc:
        raise ValueError(
            "Failed to store uploaded document."
        ) from exc

    document = Document(
        organization_id=organization_id,
        filename=filename,
        content_type=(
            file.content_type
            or "application/octet-stream"
        ),
        file_size=len(file_content),
        storage_path=storage_path,
        content_hash=content_hash,
        status="UPLOADED",
        error_message=None,
    )

    try:
        db.add(document)
        db.flush()

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