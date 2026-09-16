from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover - optional dependency in local fallback mode
    asyncpg = None


CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS url_observations (
    id UUID PRIMARY KEY,
    url_hash CHAR(64) NOT NULL UNIQUE,
    normalized_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    threat_score DOUBLE PRECISION NOT NULL CHECK (threat_score >= 0 AND threat_score <= 1),
    action VARCHAR(10) NOT NULL CHECK (action IN ('ALLOW', 'REVIEW', 'BLOCK')),
    reason TEXT NOT NULL,
    model_version TEXT NOT NULL,
    feature_snapshot JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(40) NOT NULL,
    action VARCHAR(10) NOT NULL,
    threat_score DOUBLE PRECISION NOT NULL,
    reason TEXT NOT NULL,
    payload JSONB NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_url_observations_domain ON url_observations(domain);
CREATE TABLE IF NOT EXISTS threat_events (
    id UUID PRIMARY KEY,
    url_hash CHAR(64) NOT NULL REFERENCES url_observations(url_hash),
    source VARCHAR(40) NOT NULL,
    evidence JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
"""


class ThreatRepository:
    def __init__(self, pool: Any | None = None):
        self.pool = pool

    async def ensure_schema(self) -> None:
        if asyncpg is None or self.pool is None:
            return
        async with self.pool.acquire() as connection:
            await connection.execute(CREATE_SCHEMA)

    async def upsert_observation(
        self,
        url_hash: str,
        normalized_url: str,
        domain: str,
        threat_score: float,
        action: str,
        reason: str,
        features: dict[str, Any],
        model_version: str,
    ) -> None:
        if asyncpg is None or self.pool is None:
            return
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO url_observations
                (id, url_hash, normalized_url, domain, threat_score, action, reason,
                 model_version, feature_snapshot, first_seen_at, last_seen_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10)
                ON CONFLICT (url_hash) DO UPDATE SET
                    threat_score = EXCLUDED.threat_score,
                    action = EXCLUDED.action,
                    reason = EXCLUDED.reason,
                    feature_snapshot = EXCLUDED.feature_snapshot,
                    model_version = EXCLUDED.model_version,
                    last_seen_at = EXCLUDED.last_seen_at,
                    observation_count = url_observations.observation_count + 1
                """,
                uuid.uuid4(),
                url_hash,
                normalized_url,
                domain,
                min(1.0, max(0.0, threat_score)),
                action,
                reason,
                model_version,
                json.dumps(features, ensure_ascii=False),
                now,
            )

    async def record_event(self, url_hash: str, source: str, evidence: dict[str, Any], confidence: float) -> None:
        if asyncpg is None or self.pool is None:
            return
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO threat_events (id, url_hash, source, evidence, confidence, created_at)
                VALUES ($1,$2,$3,$4,$5,$6)
                """,
                uuid.uuid4(),
                url_hash,
                source,
                json.dumps(evidence, ensure_ascii=False),
                min(1.0, max(0.0, confidence)),
                datetime.now(timezone.utc),
            )

    async def list_incidents(self, limit: int = 100) -> list[dict[str, Any]]:
        if asyncpg is None or self.pool is None:
            return []
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT id, created_at, source, action, threat_score, reason, payload, resolved "
                "FROM incidents ORDER BY created_at DESC LIMIT $1", max(1, min(limit, 500))
            )
        return [dict(row) for row in rows]

    async def record_incident(self, incident: dict[str, Any]) -> None:
        if asyncpg is None or self.pool is None:
            return
        async with self.pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO incidents (id, created_at, source, action, threat_score, reason, payload) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7)",
                uuid.UUID(str(incident["id"])),
                incident["created_at"],
                incident.get("source", "verify"),
                incident["action"],
                float(incident["threat_score"]),
                incident["reason"],
                json.dumps(incident.get("payload", {}), ensure_ascii=False),
            )
