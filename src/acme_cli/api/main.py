# How to Test:
# Test if server is running: curl http://localhost:8000/
# List all models: curl http://localhost:8000/api/v1/models
# Get a specific model: curl http://localhost:8000/api/v1/models/model-001
# Test Download: curl http://localhost:8000/api/v1/models/model-001/download
# Test Upload: echo "fake content" > /tmp/test.zip
## curl -X POST "http://localhost:8000/api/v1/models/upload?name=verify-test&version=1.0.0" -F "file=@/tmp/test.zip"
# Test HuggingFace ingest: curl -X POST "http://localhost:8000/api/v1/models/ingest?huggingface_url=https://huggingface.co/gpt2"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import health, models

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
