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

    db.add(new_organization)
    db.commit()
    db.refresh(new_organization)

    return new_organization