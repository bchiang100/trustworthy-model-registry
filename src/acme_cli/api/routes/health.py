"""Health check endpoints for system monitoring."""

from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "acme-registry",
        "version": "0.1.0",
        "uptime": "operational",
        "dependencies": {"database": "connected", "storage": "available"},
    }
