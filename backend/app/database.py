from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None

CREATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS url_observations (
    id TEXT PRIMARY KEY, url_hash TEXT NOT NULL UNIQUE, normalized_url TEXT NOT NULL,
    domain TEXT NOT NULL, threat_score REAL NOT NULL, action TEXT NOT NULL,
    reason TEXT NOT NULL, model_version TEXT NOT NULL, feature_snapshot TEXT NOT NULL,
    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, observation_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source TEXT NOT NULL, action TEXT NOT NULL,
    threat_score REAL NOT NULL, reason TEXT NOT NULL, payload TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_url_observations_domain ON url_observations(domain);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at DESC);
CREATE TABLE IF NOT EXISTS domain_reviews (
    domain TEXT PRIMARY KEY, status TEXT NOT NULL, reason TEXT NOT NULL, reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS domain_review_audit (
    id TEXT PRIMARY KEY, domain TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
    reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_domain_review_audit_domain ON domain_review_audit(domain, reviewed_at DESC);
"""


class ThreatRepository:
    async def review_domain(self, domain: str, status: str, reason: str, reviewed_by: str) -> None:
        reviewed_at = datetime.now(timezone.utc).isoformat()
        values = (domain, status, reason, reviewed_at)
        query = "INSERT INTO domain_reviews(domain,status,reason,reviewed_at) VALUES ({}) ON CONFLICT(domain) DO UPDATE SET status=excluded.status,reason=excluded.reason,reviewed_at=excluded.reviewed_at"
        if self.pool is not None:
            async with self.pool.acquire() as connection:
                await connection.execute(query.format("$1,$2,$3,$4"), *values)
        elif self.sqlite_path is not None:
            def write():
                with closing(self._sqlite()) as connection:
                    connection.execute(query.format("?,?,?,?"), values)
                    connection.commit()
            await asyncio.to_thread(write)
        await self._record_review_audit(domain, status, reason, reviewed_by, reviewed_at)

    async def _record_review_audit(self, domain: str, status: str, reason: str,
                                   reviewed_by: str, reviewed_at: str) -> None:
        values = (str(uuid.uuid4()), domain, status, reason, reviewed_by, reviewed_at)
        if self.pool is not None:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    "INSERT INTO domain_review_audit(id,domain,status,reason,reviewed_by,reviewed_at) VALUES ($1,$2,$3,$4,$5,$6)",
                    *values,
                )
            return
        if self.sqlite_path is not None:
            def write() -> None:
                with closing(self._sqlite()) as connection:
                    connection.execute(
                        "INSERT INTO domain_review_audit(id,domain,status,reason,reviewed_by,reviewed_at) VALUES (?,?,?,?,?,?)",
                        values,
                    )
                    connection.commit()
            await asyncio.to_thread(write)

    async def list_domain_audit(self, domain: str, limit: int = 50) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 200))
        if self.pool is not None:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(
                    "SELECT domain,status,reason,reviewed_by,reviewed_at FROM domain_review_audit WHERE domain=$1 ORDER BY reviewed_at DESC LIMIT $2",
                    domain, bounded_limit,
                )
            return [dict(row) for row in rows]
        if self.sqlite_path is not None:
            def read() -> list[dict[str, Any]]:
                with closing(self._sqlite()) as connection:
                    rows = connection.execute(
                        "SELECT domain,status,reason,reviewed_by,reviewed_at FROM domain_review_audit WHERE domain=? ORDER BY reviewed_at DESC LIMIT ?",
                        (domain, bounded_limit),
                    ).fetchall()
                return [dict(row) for row in rows]
            return await asyncio.to_thread(read)
        return []

    async def get_domain_review(self, domain: str) -> dict | None:
        if self.pool is not None:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow("SELECT * FROM domain_reviews WHERE domain=$1", domain)
            return dict(row) if row else None
        if self.sqlite_path is not None:
            def read():
                with closing(self._sqlite()) as connection:
                    row = connection.execute("SELECT * FROM domain_reviews WHERE domain=?", (domain,)).fetchone()
                return dict(row) if row else None
            return await asyncio.to_thread(read)
        return None

    def __init__(self, pool: Any | None = None, database_url: str = ""):
        self.pool = pool
        self.sqlite_path = None
        if pool is None and database_url.startswith("sqlite:///"):
            self.sqlite_path = Path(database_url.removeprefix("sqlite:///"))
            if not self.sqlite_path.is_absolute():
                self.sqlite_path = Path.cwd() / self.sqlite_path

    def _sqlite(self) -> sqlite3.Connection:
        assert self.sqlite_path is not None
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    async def ensure_schema(self) -> None:
        if asyncpg is not None and self.pool is not None:
            async with self.pool.acquire() as connection:
                await connection.execute(CREATE_SCHEMA.replace("JSONB", "JSONB"))
            return
        if self.sqlite_path is not None:
            def create() -> None:
                with closing(self._sqlite()) as connection:
                    connection.executescript(CREATE_SCHEMA)
                    connection.commit()
            await asyncio.to_thread(create)

    async def upsert_observation(self, *, url_hash: str, normalized_url: str, domain: str,
                                 threat_score: float, action: str, reason: str,
                                 features: dict[str, Any], model_version: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        bounded = min(1.0, max(0.0, threat_score))
        if asyncpg is not None and self.pool is not None:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """INSERT INTO url_observations
                    (id,url_hash,normalized_url,domain,threat_score,action,reason,model_version,feature_snapshot,first_seen_at,last_seen_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10)
                    ON CONFLICT (url_hash) DO UPDATE SET threat_score=EXCLUDED.threat_score, action=EXCLUDED.action,
                    reason=EXCLUDED.reason, feature_snapshot=EXCLUDED.feature_snapshot, model_version=EXCLUDED.model_version,
                    last_seen_at=EXCLUDED.last_seen_at, observation_count=url_observations.observation_count+1""",
                    str(uuid.uuid4()), url_hash, normalized_url, domain, bounded, action, reason, model_version,
                    json.dumps(features, ensure_ascii=False), now,
                )
            return
        if self.sqlite_path is not None:
            def write() -> None:
                with closing(self._sqlite()) as connection:
                    connection.execute(
                        """INSERT INTO url_observations
                        (id,url_hash,normalized_url,domain,threat_score,action,reason,model_version,feature_snapshot,first_seen_at,last_seen_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(url_hash) DO UPDATE SET threat_score=excluded.threat_score, action=excluded.action,
                        reason=excluded.reason, feature_snapshot=excluded.feature_snapshot, model_version=excluded.model_version,
                        last_seen_at=excluded.last_seen_at, observation_count=url_observations.observation_count+1""",
                        (str(uuid.uuid4()), url_hash, normalized_url, domain, bounded, action, reason, model_version,
                         json.dumps(features, ensure_ascii=False), now, now),
                    )
                    connection.commit()
            await asyncio.to_thread(write)

    async def record_incident(self, incident: dict[str, Any]) -> None:
        score = float(incident["threat_score"])
        action = "BLOCK" if score >= 0.85 else "REVIEW"
        reason = ", ".join(incident.get("analysis", {}).get("key_trigger_words", [])) or "incident telemetry"
        payload = json.dumps(incident, ensure_ascii=False)
        if asyncpg is not None and self.pool is not None:
            async with self.pool.acquire() as connection:
                await connection.execute(
                    """INSERT INTO incidents (id,created_at,source,action,threat_score,reason,payload)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload,
                    threat_score=EXCLUDED.threat_score, action=EXCLUDED.action""",
                    str(incident["id"]), incident["created_at"],
                    incident.get("source", "extension"), action, score, reason, payload,
                )
            return
        if self.sqlite_path is not None:
            def write() -> None:
                with closing(self._sqlite()) as connection:
                    connection.execute(
                        """INSERT INTO incidents(id,created_at,source,action,threat_score,reason,payload)
                        VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                        threat_score=excluded.threat_score, action=excluded.action""",
                        (str(incident["id"]), incident["created_at"], incident.get("source", "extension"), action,
                         score, reason, payload),
                    )
                    connection.commit()
            await asyncio.to_thread(write)

    async def list_incidents(self, limit: int = 100) -> list[dict[str, Any]]:
        if asyncpg is not None and self.pool is not None:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch("SELECT payload FROM incidents ORDER BY created_at DESC LIMIT $1", max(1, min(limit, 500)))
            # The shared schema stores payload as TEXT so SQLite and PostgreSQL
            # behave identically.  Some existing deployments may already use a
            # native JSON/JSONB column, so accept both representations.
            return [
                json.loads(row["payload"])
                if isinstance(row["payload"], str)
                else dict(row["payload"])
                for row in rows
            ]
        if self.sqlite_path is not None:
            def read() -> list[dict[str, Any]]:
                with closing(self._sqlite()) as connection:
                    rows = connection.execute("SELECT payload FROM incidents ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
                return [json.loads(row["payload"]) for row in rows]
            return await asyncio.to_thread(read)
        return []

    async def domain_reputation(self, domain: str) -> dict[str, Any] | None:
        normalized = domain.lower().strip().strip(".")
        if not normalized:
            return None
        if asyncpg is not None and self.pool is not None:
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(
                    """SELECT domain, MAX(threat_score) AS threat_score,
                    MAX(last_seen_at) AS last_seen_at, SUM(observation_count) AS observation_count
                    FROM url_observations WHERE domain=$1 GROUP BY domain""",
                    normalized,
                )
            return dict(row) if row else None
        if self.sqlite_path is not None:
            def read() -> dict[str, Any] | None:
                with closing(self._sqlite()) as connection:
                    row = connection.execute(
                        """SELECT domain, MAX(threat_score) AS threat_score,
                        MAX(last_seen_at) AS last_seen_at, SUM(observation_count) AS observation_count
                        FROM url_observations WHERE domain=? GROUP BY domain""",
                        (normalized,),
                    ).fetchone()
                return dict(row) if row else None
            return await asyncio.to_thread(read)
        return None

    async def list_domains(self, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 500))
        query = """SELECT domain, MAX(threat_score) AS threat_score,
            MAX(last_seen_at) AS last_seen_at, SUM(observation_count) AS observation_count
            FROM url_observations GROUP BY domain
            ORDER BY threat_score DESC, last_seen_at DESC"""
        if asyncpg is not None and self.pool is not None:
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query + " LIMIT $1", bounded_limit)
            return [dict(row) for row in rows]
        if self.sqlite_path is not None:
            def read() -> list[dict[str, Any]]:
                with closing(self._sqlite()) as connection:
                    rows = connection.execute(query + " LIMIT ?", (bounded_limit,)).fetchall()
                return [dict(row) for row in rows]
            return await asyncio.to_thread(read)
        return []
