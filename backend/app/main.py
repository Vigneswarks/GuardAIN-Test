"""GuardAIN - Central Police Cyber Cell Main Entry Point"""
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from .api import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("guardain")

# Create application
app = create_app()

# Add admin portal static files if they exist
admin_portal_path = Path(__file__).parent.parent.parent / "admin_portal"
if admin_portal_path.exists():
    @app.get("/", response_class=HTMLResponse, tags=["Portal"])
    async def admin_portal():
        """Serve admin portal"""
        portal_file = admin_portal_path / "index.html"
        if portal_file.exists():
            return portal_file.read_text()
        return "<h1>Admin Portal Not Found</h1>"

    # Mount static assets if needed
    static_path = admin_portal_path
    if (static_path / "static").exists():
        app.mount("/static", StaticFiles(directory=str(static_path / "static")), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🚀 GuardAIN API Starting...")
    logger.info("📊 Portal: http://localhost:8080")
    logger.info("🔐 Default Credentials - Username: admin, Password: admin@26")
    logger.info("✅ Ready to scan threats and analyze evidence")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 GuardAIN API Shutting Down...")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT", "development") == "development",
        log_level="info"
    )
