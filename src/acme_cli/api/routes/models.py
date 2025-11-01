# manages model endpoints for CR[U]D operations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

router = APIRouter()


class ModelMetadata(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    tags: List[str] = []
    net_score: float
    ramp_up_time: float
    bus_factor: float
    performance_claims: float
    license: float
    dataset_and_code_score: float
    dataset_quality: float
    code_quality: float
    # Phase 2 new metrics
    reproducibility: (
        float  # 0 (no code/doesn't run), 0.5 (runs with debugging), 1 (runs perfectly)
    )
    reviewedness: (
        float  # fraction 0-1 of code introduced via PR with review, -1 if no repo
    )
    treescore: float  # average of parent model scores according to lineage graph


class ModelResponse(BaseModel):
    id: str
    metadata: ModelMetadata
    upload_timestamp: str
    file_size: int
    status: str = "available"


# Mock data for demonstration
MOCK_MODELS = [
    ModelResponse(
        id="model-001",
        metadata=ModelMetadata(
            name="example-bert-model",
            version="1.0.0",
            description="A fine-tuned BERT model for sentiment analysis",
            tags=["bert", "nlp", "sentiment"],
            net_score=0.85,
            ramp_up_time=0.8,
            bus_factor=0.7,
            performance_claims=0.9,
            license=1.0,
            dataset_and_code_score=0.8,
            dataset_quality=0.9,
            code_quality=0.8,
            # Phase 2 new metrics
            reproducibility=1.0,  # runs perfectly with demo code
            reviewedness=0.85,  # 85% of code was PR reviewed
            treescore=0.82,  # average of parent model scores
        ),
        upload_timestamp="2025-01-01T12:00:00Z",
        file_size=512000000,
        status="available",
    ),
    ModelResponse(
        id="model-002",
        metadata=ModelMetadata(
            name="tiny-llm",
            version="0.5.0",
            description="A small language model for testing",
            tags=["llm", "small", "testing"],
            net_score=0.75,
            ramp_up_time=0.9,
            bus_factor=0.6,
            performance_claims=0.7,
            license=1.0,
            dataset_and_code_score=0.7,
            dataset_quality=0.8,
            code_quality=0.7,
            # new phase 2 metrics
            reproducibility=0.5,
            reviewedness=-1,
            treescore=0.73,
        ),
        upload_timestamp="2025-01-02T08:30:00Z",
        file_size=128000000,
        status="available",
    ),
]


# UPLOAD - accepts zip files and creates models
@router.post("/models/upload")
async def upload_model(
    file: UploadFile = File(...),
    name: str = Query(..., description="Model name"),
    version: str = Query(..., description="Model version"),
    description: Optional[str] = Query(None, description="Model description"),
):
    """Upload a new model to the registry."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a zip archive")

    # Mock response - in real implementation, would save file and compute scores
    mock_id = f"model-{len(MOCK_MODELS) + 1:03d}"
    mock_model = ModelResponse(
        id=mock_id,
        metadata=ModelMetadata(
            name=name,
            version=version,
            description=description,
            tags=[],
            net_score=0.8,
            ramp_up_time=0.8,
            bus_factor=0.7,
            performance_claims=0.8,
            license=1.0,
            dataset_and_code_score=0.7,
            dataset_quality=0.8,
            code_quality=0.7,
            reproducibility=0.8,
            reviewedness=0.75,
            treescore=0.78,
        ),
        upload_timestamp="2025-01-03T10:00:00Z",
        file_size=file.size or 100000000,
        status="processing",
    )

    MOCK_MODELS.append(mock_model)

    return {
        "message": "Model uploaded successfully",
        "model_id": mock_id,
        "status": "processing",
        "estimated_processing_time": "5 minutes",
    }


# LIST - Returns the array of all models
@router.get("/models", response_model=List[ModelResponse])
async def list_models(
    search: Optional[str] = Query(
        None, description="Search in model names and descriptions"
    ),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    limit: int = Query(
        50, ge=1, le=1000, description="Maximum number of models to return"
    ),
):
    """List all models in the registry with optional search and filtering."""
    models = MOCK_MODELS.copy()

    if search:
        models = [
            m
            for m in models
            if search.lower() in m.metadata.name.lower()
            or (
                m.metadata.description
                and search.lower() in m.metadata.description.lower()
            )
        ]

    if tag:
        models = [m for m in models if tag in m.metadata.tags]

    return models[:limit]


@router.get("/models/{model_id}", response_model=ModelResponse)
async def get_model(model_id: str):
    """Get detailed information about a specific model."""
    for model in MOCK_MODELS:
        if model.id == model_id:
            return model

    raise HTTPException(status_code=404, detail="Model not found")


# Download - Returns the download link for the model
@router.get("/models/{model_id}/download")
async def download_model(model_id: str):
    """Download a model file."""
    for model in MOCK_MODELS:
        if model.id == model_id:
            # Mock response - in real implementation, would return file stream
            return {
                "message": "Download initiated",
                "model_id": model_id,
                "download_url": f"/downloads/{model_id}.zip",
                "file_size": model.file_size,
                "expires_in": "1 hour",
            }

    raise HTTPException(status_code=404, detail="Model not found")


# Ingest - imports from the HuggingFace URL
@router.post("/models/ingest")
async def ingest_huggingface_model(
    huggingface_url: str = Query(..., description="HuggingFace model URL")
):
    """Ingest a model from HuggingFace Hub."""
    # Mock validation - in real implementation, would fetch and score the model
    if "huggingface.co" not in huggingface_url:
        raise HTTPException(status_code=400, detail="Invalid HuggingFace URL")

    # Extracts model name from URL
    model_name = (
        huggingface_url.split("/")[-1] if "/" in huggingface_url else "unknown-model"
    )

    return {
        "message": "Model ingestion started",
        "huggingface_url": huggingface_url,
        "estimated_model_name": model_name,
        "status": "validating",
        "estimated_completion_time": "10 minutes",
    }
