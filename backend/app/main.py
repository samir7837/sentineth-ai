from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session


# Load environment variables from the project root.
# Structure:
# sentineth/
# ├── .env
# └── backend/
#     └── app/
#         └── main.py

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


from app.api.documents import router as documents_router
from app.clock import utcnow
from app.db import models
from app.db.database import get_db
from app.schemas import (
    ApiKeyIssued,
    ApiKeyResponse,
    ApiKeyRotateRequest,
    OrganizationCreate,
    OrganizationResponse,
)
from app.security import hash_api_key, new_api_key, require_organization_access


app = FastAPI(
    title="Sentineth AI",
    description="Organizational Intelligence Platform",
    version="0.1.0",
)


app.include_router(documents_router)


@app.get("/")
async def root():
    return {
        "name": "Sentineth AI",
        "status": "online",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.post(
    "/organizations",
    response_model=OrganizationResponse,
)
def create_organization(
    organization: OrganizationCreate,
    db: Session = Depends(get_db),
):
    new_organization = models.Organization(
        name=organization.name
    )
    api_key = new_api_key()
    new_organization.api_keys.append(
        models.OrganizationApiKey(token_hash=hash_api_key(api_key))
    )

    db.add(new_organization)
    db.commit()
    db.refresh(new_organization)

    return OrganizationResponse.model_validate(new_organization).model_copy(
        update={"api_key": api_key}
    )


@app.get(
    "/organizations/{organization_id}/api-keys",
    response_model=list[ApiKeyResponse],
)
def list_api_keys(
    organization_id: UUID,
    _: models.OrganizationApiKey = Depends(require_organization_access),
    db: Session = Depends(get_db),
):
    """Metadata for every key ever issued to the organization.

    ApiKeyResponse has no token or token_hash field, so neither can leak
    here even if the ORM object grows one.
    """
    return list(
        db.scalars(
            select(models.OrganizationApiKey)
            .where(models.OrganizationApiKey.organization_id == organization_id)
            .order_by(models.OrganizationApiKey.created_at)
        )
    )


@app.post(
    "/organizations/{organization_id}/api-keys/rotate",
    response_model=ApiKeyIssued,
)
def rotate_api_key(
    organization_id: UUID,
    payload: ApiKeyRotateRequest | None = None,
    key: models.OrganizationApiKey = Depends(require_organization_access),
    db: Session = Depends(get_db),
):
    """Issue a replacement key and revoke the one that authenticated here.

    organization_id must be annotated: unannotated, FastAPI hands the route a
    str, which SQLAlchemy then fails to adapt to a Uuid column.
    """
    token = new_api_key()
    replacement = models.OrganizationApiKey(
        organization_id=organization_id,
        token_hash=hash_api_key(token),
        expires_at=payload.expires_at if payload else None,
    )

    # Insert the replacement before revoking the current key, so a failure
    # here cannot leave the organization with no usable key.
    db.add(replacement)
    db.flush()

    key.revoked_at = utcnow()

    db.commit()
    db.refresh(replacement)

    return ApiKeyIssued(
        **ApiKeyResponse.model_validate(replacement).model_dump(),
        api_key=token,
    )


@app.delete(
    "/organizations/{organization_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_api_key(
    organization_id: UUID,
    key_id: UUID,
    _: models.OrganizationApiKey = Depends(require_organization_access),
    db: Session = Depends(get_db),
):
    """Revoke a key. Revoking is permanent; keys are never deleted, so the
    audit trail of what was issued when survives."""
    target = db.scalar(
        select(models.OrganizationApiKey).where(
            models.OrganizationApiKey.id == key_id,
            models.OrganizationApiKey.organization_id == organization_id,
        )
    )

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found for this organization",
        )

    # Already-revoked keys keep their original timestamp.
    if target.revoked_at is None:
        target.revoked_at = utcnow()
        db.commit()
