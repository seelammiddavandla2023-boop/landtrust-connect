"""
LandTrust Connect — API entrypoint.

    uvicorn app.main:app --reload --port 8000

Interactive API documentation is served at /docs (OpenAPI at /openapi.json).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api import (
    routes_control,
    routes_documents,
    routes_interaction,
    routes_platform,
    routes_properties,
)
from .config import settings
from .db import SessionLocal, init_db
from .domain import DISCLAIMER, Role
from .models import Property


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        if db.scalar(select(Property).limit(1)) is None:
            from .seed.seed import seed

            seed(db)
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "**LandTrust Connect** — an AI-based evidence-gated land ownership verification, "
        "secure owner interaction and autonomous transaction risk resolution system.\n\n"
        "Research prototype (Review-2). Every response describes agreement between documents "
        "uploaded to this platform. Nothing here is an official land record, a certification of "
        "title, or legal advice.\n\n"
        "Set the `X-Demo-Role` header to `OWNER`, `BUYER`, `VERIFIER`, `LEGAL_REVIEWER` or "
        "`ADMIN` to switch role. Redaction and consent apply for real: a buyer request cannot "
        "retrieve a masked value."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")] or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_properties.router)
app.include_router(routes_documents.router)
app.include_router(routes_interaction.router)
app.include_router(routes_control.router)
app.include_router(routes_platform.router)


@app.get("/api/health", tags=["platform"])
def health():
    from .services.extractor.registry import available_modes

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "extraction_mode": settings.extraction_mode,
        "extraction_backends": available_modes(),
        "database": settings.database_url.split("///")[-1],
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/roles", tags=["platform"])
def roles():
    return {
        "roles": [
            {"role": Role.OWNER.value, "label": "Land Owner",
             "description": "Uploads evidence, decides access requests, responds through the "
                            "relay."},
            {"role": Role.BUYER.value, "label": "Buyer",
             "description": "Sees the evidence-gated profile, requests disclosure, cannot see "
                            "masked values."},
            {"role": Role.VERIFIER.value, "label": "Verifier",
             "description": "Reviews claims, contradictions and integrity indicators in full."},
            {"role": Role.LEGAL_REVIEWER.value, "label": "Legal Reviewer",
             "description": "Handles escalated cases; sees the full evidence set and audit "
                            "trail."},
            {"role": Role.ADMIN.value, "label": "Administrator",
             "description": "Platform operations, demo control and the research dashboards."},
        ],
        "header": "X-Demo-Role",
    }
