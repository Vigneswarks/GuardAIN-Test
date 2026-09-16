"""GuardAIN API - Threat Intelligence Service"""
import logging
from datetime import datetime
from typing import Any, Optional
import hashlib
import json

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger("guardain")


class URLScanRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)


class ScanResult(BaseModel):
    url: str
    status: str
    threat_score: int
    details: str
    timestamp: str


class ThreatDatabase:
    """Simple in-memory threat database for demo"""
    def __init__(self):
        # Known malicious patterns
        self.malicious_domains = {
            'malicious.com', 'phishing.site', 'scam.net', 'fraud.io',
            'banking-fake.com', 'paypal-verify.net', 'amazon-login.site'
        }
        self.malicious_keywords = [
            'phishing', 'malware', 'ransomware', 'trojan', 'spyware',
            'crypto mining', 'click fraud', 'verify account', 'confirm identity',
            'update payment', 'urgent action', 'click here now', 'limited time'
        ]

    def check_url(self, url: str) -> tuple[bool, int, str]:
        """Check if URL is malicious. Returns (is_safe, threat_score, details)"""
        url_lower = url.lower()
        
        # Check known malicious domains
        for domain in self.malicious_domains:
            if domain in url_lower:
                return False, 9, f"Detected known malicious domain: {domain}"
        
        # Check for suspicious patterns
        threat_score = 0
        reasons = []
        
        if 'http://' in url and not 'localhost' in url and not '127.0.0.1' in url:
            threat_score += 2
            reasons.append("Uses unencrypted HTTP")
        
        suspicious_chars = ['%', '://@@', 'redirect', 'click', 'verify', 'confirm']
        for char in suspicious_chars:
            if char in url_lower:
                threat_score += 1
                reasons.append(f"Contains suspicious pattern: {char}")
        
        if threat_score > 0:
            return False, min(threat_score, 8), "; ".join(reasons)
        
        return True, 0, "URL appears safe"


threat_db = ThreatDatabase()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GuardAIN API",
        description="Central Police Cyber Cell Threat Intelligence API",
        version="1.0.0"
    )

    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["Health"])
    async def health():
        """Health check endpoint"""
        return {"status": "online", "service": "guardain-api"}

    @app.post("/api/scan", response_model=ScanResult, tags=["Scanner"])
    async def scan_url(request: URLScanRequest):
        """Scan a URL for threats"""
        try:
            is_safe, threat_score, details = threat_db.check_url(request.url)
            
            result = ScanResult(
                url=request.url,
                status="safe" if is_safe else "dangerous",
                threat_score=threat_score,
                details=details,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(f"Scanned URL: {request.url} - Status: {'SAFE' if is_safe else 'DANGEROUS'}")
            return result
        except Exception as e:
            logger.error(f"Scan error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/stats", tags=["Admin"])
    async def get_stats():
        """Get system statistics"""
        return {
            "total_scans": 0,
            "safe_scans": 0,
            "dangerous_scans": 0,
            "success_rate": 100,
            "uptime": "online"
        }

    @app.post("/api/admin/login", tags=["Admin"])
    async def admin_login(username: str, password: str):
        """Admin login endpoint"""
        # Simple hardcoded auth for admin panel
        if username == "admin" and password == "admin@26":
            return {"status": "authenticated", "token": "admin_token_12345"}
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8080)
