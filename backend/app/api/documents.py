import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.local import LocalEmbeddingProvider

from app.providers.llm.base import LLMProvider
from app.providers.llm.openrouter import OpenRouterProvider

from app.providers.storage.base import StorageProvider
from app.providers.storage.local import LocalStorageProvider

from app.providers.vector.base import VectorStore
from app.providers.vector.qdrant import QdrantVectorStore

from app.schemas import (
    QueryRequest,
    QueryResponse,
    SearchRequest,
    SearchResponse,
)

from app.services.document_service import save_document
from app.services.query_service import answer_query
from app.services.retrieval_service import retrieve


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/organizations",
    tags=["Documents"],
)


def get_embedding_provider() -> EmbeddingProvider:
    return LocalEmbeddingProvider()


def get_vector_store() -> VectorStore:
    return QdrantVectorStore(
        vector_size=384,
    )


def get_storage_provider() -> StorageProvider:
    base_dir = Path(__file__).resolve().parents[2]
    storage_dir = base_dir / "storage" / "documents"

    return LocalStorageProvider(storage_dir)


def get_llm_provider() -> LLMProvider:
    try:
        return OpenRouterProvider()
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail="LLM provider is not configured.",
        ) from exc


@router.post("/{organization_id}/documents")
async def upload_document(
    organization_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage_provider: StorageProvider = Depends(get_storage_provider),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
):
    try:
        document = await save_document(
            db=db,
            organization_id=organization_id,
            file=file,
            storage_provider=storage_provider,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    if document.status == "READY":
        message = "Document uploaded and processed successfully."
    elif document.status == "FAILED":
        message = "Document uploaded but processing failed."
    else:
        message = "Document uploaded and is being processed."

    return {
        "id": str(document.id),
        "filename": document.filename,
        "content_type": document.content_type,
        "file_size": document.file_size,
        "storage_path": document.storage_path,
        "status": document.status,
        "message": message,
        "chunks": len(document.chunks),
    }


@router.post(
    "/{organization_id}/search",
    response_model=SearchResponse,
)
async def search_documents(
    organization_id: UUID,
    payload: SearchRequest,
    embedding_provider: EmbeddingProvider = Depends(
        get_embedding_provider
    ),
    vector_store: VectorStore = Depends(
        get_vector_store
    ),
):
    try:
        results = await retrieve(
            organization_id=organization_id,
            query=payload.query,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            limit=payload.limit,
        )

    except ValueError as exc:
        logger.exception("Search validation error")

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Search failed for organization %s",
            organization_id,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {exc}",
        ) from exc

    return {
        "query": payload.query,
        "results": results,
    }


@router.post(
    "/{organization_id}/query",
    response_model=QueryResponse,
)
async def query_documents(
    organization_id: UUID,
    payload: QueryRequest,
    embedding_provider: EmbeddingProvider = Depends(
        get_embedding_provider
    ),
    vector_store: VectorStore = Depends(
        get_vector_store
    ),
    llm_provider: LLMProvider = Depends(
        get_llm_provider
    ),
):
    try:
        result = await answer_query(
            organization_id=organization_id,
            query=payload.query,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            llm_provider=llm_provider,
            limit=payload.limit,
        )

        return result

    except ValueError as exc:
        logger.exception("Query validation error")

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Query processing failed for organization %s",
            organization_id,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {exc}",
        ) from exc