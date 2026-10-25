from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.database import ThreatRepository
from backend.app.main import app
from backend.app.config import settings

# External services are optional for this integration suite; SQLite exercises
# the full persistence contract without requiring Docker.
settings.redis_url = ""
settings.database_url = 'sqlite:///unused-test.db'
settings.guardain_allow_synthetic_model = False
_temporary_database = tempfile.TemporaryDirectory(prefix="guardain-tests-")
main_module.repository = ThreatRepository(
    database_url=f"sqlite:///{Path(_temporary_database.name) / 'guardain-test.db'}"
)


def test_page_review_and_cross_client_reputation():
    with TestClient(app) as client:
        domain = 'reported-new-domain.test'
        report = client.post('/v1/page-check', json={'domain': domain, 'signals': {'coercion': True}})
        assert report.status_code == 200 and report.json()['action'] == 'ALLOW'
        assert client.get('/v1/reputation/domain', params={'domain': domain}).json()['action'] == 'ALLOW'
        review = {'domain': domain, 'status': 'malicious', 'reason': 'Verified in controlled test'}
        assert client.post('/v1/admin/domains/review', json=review).status_code == 401
        token = client.post('/v1/admin/login', json={'username': 'admin', 'password': 'admin@26'}).json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        assert client.post('/v1/admin/domains/review', json=review, headers=headers).status_code == 200
        assert client.post('/v1/page-check', json={'domain': domain}).json()['action'] == 'BLOCK'
        review['status'] = 'safe'
        assert client.post('/v1/admin/domains/review', json=review, headers=headers).status_code == 200
        assert client.post('/v1/page-check', json={'domain': domain}).json()['action'] == 'ALLOW'
        review.update(domain='google.com', status='malicious')
        assert client.post('/v1/admin/domains/review', json=review, headers=headers).status_code == 409
        assert client.post('/v1/page-check', json={'domain': 'google.com'}).json()['action'] == 'ALLOW'


def test_health_and_static_clients() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "online"
        assert client.get("/").status_code == 200
        assert client.get("/pwa/").status_code == 200
        assert client.get("/pwa/manifest.json").status_code == 200
        assert client.get("/pwa/../README.md").status_code == 404
        demo = client.get("/demo/extension-test")
        assert demo.status_code == 200
        assert "DemoPay Secure" in demo.text
        for name in ("upi-payment", "review-only", "awareness", "normal-login"):
            assert client.get(f"/demo/{name}").status_code == 200
        assert client.get("/demo/not-a-demo").status_code == 404


def test_extension_origin_is_allowed_but_random_web_origin_is_not() -> None:
    with TestClient(app) as client:
        origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
        extension_preflight = client.options(
            "/v1/page-check",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )
        assert extension_preflight.status_code == 200
        assert extension_preflight.headers["access-control-allow-origin"] == origin
        random_web_preflight = client.options(
            "/v1/page-check",
            headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
        )
        assert random_web_preflight.status_code == 400


def test_verify_safe_and_scam_messages() -> None:
    with TestClient(app) as client:
        safe = client.post("/v1/verify", json={"message": "hello", "url": "https://google.com"})
        assert safe.status_code == 200
        assert safe.json()["risk_level"] == "safe"

        scam = client.post(
            "/v1/verify",
            json={"message": "CBI digital arrest. Pay bail immediately and share OTP.", "url": "https://new-scam-domain.test/"},
        )
        assert scam.status_code == 200
        assert scam.json()["threat_score"] >= 0.5
        assert scam.json()["label"] == "fraud"
        reputation = client.get("/v1/reputation/domain?domain=new-scam-domain.test")
        assert reputation.status_code == 200
        assert reputation.json()["known"] is True
        assert reputation.json()["threat_score"] >= 0.5
        login = client.post(
            "/v1/admin/login", json={"username": "admin", "password": "admin@26"}
        )
        domains = client.get(
            "/v1/admin/domains", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
        )
        assert domains.status_code == 200
        assert any(item["domain"] == "new-scam-domain.test" for item in domains.json()["domains"])


def test_admin_login_incident_and_authenticated_feed() -> None:
    with TestClient(app) as client:
        login = client.post(
            "/v1/admin/login", json={"username": "admin", "password": "admin@26"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        screenshot = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
        created = client.post(
            "/v1/reports/incidents",
            json={
                "url": "https://phishing.site/login",
                "screenshot_base64": screenshot,
                "message": "verify account immediately",
                "threat_score": 0.9,
            },
        )
        assert created.status_code == 202
        assert created.json()["status"] == "accepted"

        assert client.get("/v1/admin/incidents").status_code == 401
        feed = client.get(
            "/v1/admin/incidents", headers={"Authorization": f"Bearer {token}"}
        )
        assert feed.status_code == 200
        assert any(item["id"] == created.json()["incident_id"] for item in feed.json()["incidents"])


def test_rejects_invalid_screenshot() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/reports/incidents",
            json={"url": "https://example.com", "screenshot_base64": "not-base64"},
        )
        assert response.status_code == 422


def test_accepts_message_only_pwa_triage_incident() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/v1/telemetry",
            json={
                "message": "Controlled PWA fraud triage test",
                "threat_score": 0.8,
                "source": "pwa-triage",
                "analysis": {"engine": "test", "key_trigger_words": ["controlled_test"]},
            },
        )
        assert created.status_code == 202
        token = client.post("/v1/admin/login", json={"username": "admin", "password": "admin@26"}).json()["access_token"]
        feed = client.get("/v1/admin/incidents", headers={"Authorization": f"Bearer {token}"}).json()
        entry = next(item for item in feed["incidents"] if item["id"] == created.json()["incident_id"])
        assert entry["source"] == "pwa-triage"
        assert entry["url"] is None
