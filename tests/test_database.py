from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from backend.app.database import ThreatRepository


def test_domain_review_audit_is_durable_in_sqlite() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repository = ThreatRepository(database_url=f"sqlite:///{Path(directory) / 'guardain.db'}")

        async def exercise() -> None:
            await repository.ensure_schema()
            await repository.review_domain("example.test", "malicious", "Controlled test review", "analyst@example")
            await repository.review_domain("example.test", "safe", "Controlled correction", "analyst@example")
            audit = await repository.list_domain_audit("example.test")
            assert len(audit) == 2
            assert audit[0]["status"] == "safe"
            assert audit[0]["reviewed_by"] == "analyst@example"

        asyncio.run(exercise())
