from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
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
from app.db import models
from app.db.database import get_db
from app.schemas import OrganizationCreate, OrganizationResponse
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


@app.post("/organizations/{organization_id}/api-keys/rotate")
def rotate_api_key(organization_id, key=Depends(require_organization_access), db: Session = Depends(get_db)):
    key.revoked_at = datetime.utcnow()
    token = new_api_key()
    db.add(models.OrganizationApiKey(organization_id=organization_id, token_hash=hash_api_key(token)))
    db.commit()
    return {"api_key": token}
