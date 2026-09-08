"""Runtime configuration.  Everything has a working default so the prototype runs
with no environment file and no API keys (build brief §26)."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    app_name: str = "LandTrust Connect API"
    version: str = "0.2.0"  # Review-2 prototype

    # SQLite by default; set DATABASE_URL=postgresql+psycopg://... to use PostgreSQL.
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'landtrust.db'}"
    )

    # Storage for uploaded and generated documents.
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", str(PROJECT_ROOT / "data" / "storage")))
    synthetic_dir: Path = Path(
        os.getenv("SYNTHETIC_DIR", str(PROJECT_ROOT / "data" / "synthetic"))
    )
    metrics_path: Path = Path(
        os.getenv("METRICS_PATH", str(PROJECT_ROOT / "data" / "metrics.json"))
    )

    # DEMO | OCR | LLM  — see services/extractor/registry.py
    extraction_mode: str = os.getenv("EXTRACTION_MODE", "DEMO")

    # Optional. When absent the evidence assistant uses the deterministic
    # retrieval-and-template answerer, which is fully evidence-bound.
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_model: str = os.getenv("LLM_MODEL", "")

    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    # Simulated clock for consent-expiry demos.
    demo_mode: bool = os.getenv("DEMO_MODE", "1") == "1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.synthetic_dir.mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
