"""Verify cloud dependencies without printing secrets.

Run this from a machine with the same environment variables as the deployed
API. It connects to PostgreSQL and Redis, applies the idempotent schema, and
reports whether a verified MuRIL ONNX artifact is loaded.
"""
from __future__ import annotations

import asyncio
import json


async def main() -> int:
    from backend.app.config import settings
    from backend.app.database import ThreatRepository
    from backend.app.inference import MuRILInferenceService

    result: dict[str, object] = {"postgres": False, "redis": False}
    if not settings.database_url.startswith(("postgres://", "postgresql://")):
        print(json.dumps({"ok": False, "error": "DATABASE_URL is not PostgreSQL"}))
        return 2

    try:
        import asyncpg
        from backend.app.main import _postgres_connection_options
        pool = await asyncpg.create_pool(**_postgres_connection_options(settings.database_url), min_size=1, max_size=1)
        try:
            repository = ThreatRepository(pool)
            await repository.ensure_schema()
            async with pool.acquire() as connection:
                await connection.fetchval("SELECT 1")
            result["postgres"] = True
        finally:
            await pool.close()
    except Exception as exc:
        result["postgres_error"] = type(exc).__name__

    try:
        import redis.asyncio as redis
        client = redis.from_url(settings.redis_url, socket_connect_timeout=5, socket_timeout=5)
        try:
            result["redis"] = bool(await client.ping())
        finally:
            await client.aclose()
    except Exception as exc:
        result["redis_error"] = type(exc).__name__

    model = MuRILInferenceService()
    try:
        result["inference"] = model.status()
    finally:
        await model.close()
    result["ok"] = bool(result["postgres"] and result["redis"])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
