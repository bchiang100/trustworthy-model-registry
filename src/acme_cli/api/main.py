# How to Test:
# Start server: uvicorn src.acme_cli.api.main:app --host 0.0.0.0 --port 8000

# Test if server is running: curl http://localhost:8000/
# List all models: curl http://localhost:8000/api/v1/models
# Get a specific model: curl http://localhost:8000/api/v1/models/model-001
# Test Download: curl http://localhost:8000/api/v1/models/model-001/download
# Test Upload: echo "fake content" > /tmp/test.zip
# curl -X POST "http://localhost:8000/api/v1/models/upload" \
#   "?name=verify-test&version=1.0.0" -F "file=@/tmp/test.zip"
# Test HuggingFace ingest:
# curl -X POST "http://localhost:8000/api/v1/models/ingest" \
#   "?huggingface_url=https://huggingface.co/gpt2"

# ------ Health Dashboard ------

# How to Start Server & Open Dashboard:
# 1. Install dependencies: python3 -m pip install -e .
# 2. Start the server: python3 -m acme_cli.api.server
# 3. Server will be running at: http://localhost:8000
# 4. Open the health dashboard:
#    http://localhost:8000/api/v1/health/dashboard/ui

# What Dashboard Shows:
# - Live system health: CPU, memory, disk usage (updates every 30 seconds)
# - Registry activity: uploads, downloads, and searches in the past hour
# - Performance stats: Average response times, error counts, throughput
# - Recent logs: System events and API requests with timestamps
# - Status indicators: Green = healthy, yellow = warning, red = error

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from acme_cli.api.middleware import MetricsMiddleware
from acme_cli.api.routes import models, health

app = FastAPI(
    title="ACME Trustworthy Model Registry",
    description="A registry for storing and managing machine learning models",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics collection middleware
app.add_middleware(MetricsMiddleware)

app.include_router(
    health.router, prefix="/api/v1", tags=["health"]
)  # adds health endpoints
app.include_router(
    models.router, prefix="/api/v1", tags=["models"]
)  # adds model endpoints


@app.get("/")
async def root():
    """Root endpoint returning basic API information."""
    return {
        "message": "ACME Trustworthy Model Registry API",
        "version": "0.1.0",
        "status": "operational",
    }
