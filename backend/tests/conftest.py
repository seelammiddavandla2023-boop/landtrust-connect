"""
Test isolation.

The suite exercises real write paths — it uploads documents, sends relay messages,
decides consent requests and applies resolution steps. Run against the demo database
those writes would leave residue behind: an extra message on a property changes its
interaction risk, and the next person to open the demo would find a scenario that no
longer matches what the guide says it does.

So the tests get their own database, seeded once per session from the same synthetic
corpus. `DATABASE_URL` must be set before anything under `app.` is imported, because
`app.config.settings` is constructed at import time — which is why this happens at
module scope in conftest rather than in a fixture.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.gettempdir()) / "landtrust_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ.setdefault("EXTRACTION_MODE", "DEMO")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_database():
    """Build a fresh database from the synthetic corpus for the whole session."""
    from app.config import settings
    from app.seed.generate import generate
    from app.seed.seed import run

    assert str(settings.database_url).endswith("landtrust_test.db"), (
        "the test suite must not run against the demo database; "
        f"DATABASE_URL resolved to {settings.database_url}"
    )

    if not (settings.synthetic_dir / "ground_truth.json").exists():
        generate()
    run(reset=True)

    yield

    _TEST_DB.unlink(missing_ok=True)
