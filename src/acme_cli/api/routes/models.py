# manages model endpoints for CR[U]D operations

import re
import os
import tempfile
import time
from typing import List, Optional

# uses core scoring logic from ./run
from acme_cli.scoring_engine import ModelScorer
from acme_cli.context import ContextBuilder
from acme_cli.net_score import compute_net_score
from acme_cli.types import ScoreTarget

import boto3
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, JSONResponse, Response, Request, RequestValidationError
from pydantic import BaseModel
from acme_cli.urls import parse_artifact_url, is_code_url, is_dataset_url, is_model_url
from acme_cli.hf.client import HfApiClient
from route_util import get_github_readme, validate_url_string, make_id

router = APIRouter()

# S3 config
S3_BUCKET_NAME = os.getenv("ACME_S3_BUCKET", "acme-model-registry")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# initialize the S3 client
s3_client = boto3.client('s3', region_name=AWS_REGION)
hf_client = HfApiClient()

def upload_to_s3(local_file_path: str, s3_key: str) -> str:
    """Upload file to S3 and return download URL."""
    try:
        s3_client.upload_file(local_file_path, S3_BUCKET_NAME, s3_key)
        # generates download URL
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )
        return download_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

def download_artifact_from_hf(url: str, artifact_id: str) -> str:
    """Download artifact from Hugging Face and return local path."""
    try:
        parsed_url = parse_artifact_url(url)
        if not parsed_url:
            raise ValueError(f"Invalid artifact URL: {url}")

        # Create temporary directory for download
        temp_dir = tempfile.mkdtemp()
        local_path = os.path.join(temp_dir, f"{artifact_id}.tar.gz")

        # Download based on artifact type
        if is_model_url(url):
            # Download model repository
            repo_path = hf_client.snapshot_download(parsed_url.repo_id, cache_dir=temp_dir)
            # Create archive of the downloaded content
            import shutil
            shutil.make_archive(local_path.replace('.tar.gz', ''), 'gztar', repo_path)
        elif is_dataset_url(url):
            # Download dataset
            repo_path = hf_client.snapshot_download(parsed_url.repo_id, repo_type="dataset", cache_dir=temp_dir)
            import shutil
            shutil.make_archive(local_path.replace('.tar.gz', ''), 'gztar', repo_path)
        else:
            raise ValueError(f"Unsupported artifact type for URL: {url}")

        return local_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
    
def calculate_metrics(artifact_url: str) -> dict:
    """
    Calculate and return all metric scores for an artifact
    """
    try:
        target = ScoreTarget(model_url=artifact_url)
        context_builder = ContextBuilder()
        scorer = ModelScorer(context_builder=context_builder)

        summary = scorer.score(target)
        outcome = summary.outcome

        net_metric = compute_net_score(outcome)
        outcome.metrics[net_metric.name] = net_metric

        metrics: dict[str, float | dict] = {}

        for name, metric in outcome.metrics.items():
            value = metric.value
            if isinstance(value, dict):
                metrics[name] = dict(value)
            else:
                metrics[name] = float(value)

        return metrics

    except Exception:
        return {}


# invalid requests for our spec use status code 400
@router.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return Response(status_code=400)

# python dict to hold metdata of artifacts
# id -> name, type, url, downloadable s3 url
artifacts_metadata = {} 

class RegexSearch(BaseModel):
    regex: str

class IngestRequest(BaseModel):
    name: str
    url: str

class ArtifactMetadata(BaseModel):
    name: str
    id: str 
    type: str  # "model", "dataset", "code" 

class ArtifactData(BaseModel):
    url: str
    download_url: str

class LicenseCheckRequest(BaseModel):
    github_url: str

class UpdateArtifactRequest(BaseModel):
    metadata: ArtifactMetadata
    data: ArtifactData

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


## SPEC COMPLIANT ENDPOINTS 

# health check / heartbeat
@router.get("/health/")
async def get_health():
    return Response(status_code = 200)

# query artifacts
@router.post("/artifacts/")
async def get_artifacts(offset: str = "0"):
    try:
        pagination_offset: int = int(offset)
        # TODO: some math and query parsing to return artifacts based on type + offset
        artifacts = {}
        headers = {offset: str(pagination_offset + len(artifacts))}
        content = {}
        return JSONResponse(content=content, headers=headers)
    except:
        return Response(status_code=403)

# reset registry (remove all entries)
@router.delete("/reset/")
async def reset_registry():
    # TODO: implement logic to batch enumerate from s3 and delete
    # TODO: also clear metadata db 
    return Response(status_code=200)

# get specific artifact
@router.get("/artifact/{artifact_type}/{id}/")
async def get_artifact(artifact_type: str, id: str):
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    # check if id exists in the registry metadata db 
    # if it does not, return 404
    # parse artifact metadata from db 
    # return artifact metadata as json 
    pass

# update specific artifact
@router.put("/artifact/{artifact_type}/{id}/")
async def update_artifact(artifact_type: str, id: str, request: UpdateArtifactRequest):
    artifact_metadata = request.metadata
    artifact_data = request.data 

    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    # check if name and id exists in the registry metadata db 
    if artifact_metadata.id not in artifacts_metadata: 
        return Response(status_code=404)
    # if it does not, return 404
    new_url = artifact_data.url

    # rate new url, ignore update if new url doesn't pass ratings 
    rating = 0.5 
    if rating < 0.5: 
        return Response(status_code=404)

    # if passes, update metadata and s3 using provided name and url
    artifacts_metadata[id]["name"] = artifact_metadata.name
    artifacts_metadata[id]["url"] = new_url
    # push files to s3 
    # get downloadable link from s3 
    download_link = "temp"
    artifacts_metadata[id]["download_url"] = download_link
    return Response(status_code=200)

# ingest artifact
@router.put("/artifact/{artifact_type}/")
async def ingest_artifact(artifact_type: str, request: IngestRequest):
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)

    # ensure that the url itself is valid
    artifact_url = request.url
    artifact_name = request.name
    if not validate_url_string(artifact_url):
        # invalid url type
        return Response(status_code=400)

    # check if url exists in the registry metadata db
    if artifact_url in [meta.get("url") for meta in artifacts_metadata.values()]:
        # URL already exists, return 409 (Conflict)
        return Response(status_code=409)

    # download files using HF API - done
    # retrieves all metric values and store to memory
    metrics = calculate_metrics(artifact_url)

    # rate artifact
    rating = metrics.get("net_score", 0.0)

    # create id
    id = make_id(artifact_url)

    if rating >= 0.5: # trustworthy
        try:
            # download artifact from huggingface
            local_file_path = download_artifact_from_hf(artifact_url, id) # local_file_path becomes AWS server's local filesystem once deployed

            # creates S3 key for the artifact
            s3_key = f"{artifact_type}/{id}/{artifact_name}.tar.gz"

            # upload to S3 and get download URL
            download_url = upload_to_s3(local_file_path, s3_key)

            # Clean up local file
            import os
            os.remove(local_file_path)
            os.rmdir(os.path.dirname(local_file_path))


            # store metadata in memory
            artifacts_metadata[id] = {
                "name": artifact_name,
                "type": artifact_type,
                "url": artifact_url,
                "download_url": download_url,
                "s3_key": s3_key
            }

            return JSONResponse(
                content={
                    "metadata": {
                        "name": artifact_name,
                        "id": id,
                        "type": artifact_type
                    },
                    "data": {
                        "url": artifact_url,
                        "download_url": download_url
                    }
                },
                status_code=201
            )
        
        except Exception as e:
            # If S3 upload fails, return 500
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    else:
        # if rating fails, return 424
        return Response(status_code=424)

# Get track
@router.get("/tracks/")
async def get_tracks():
    return JSONResponse(content={"plannedTracks": "Performance track"}, status_code=200)

# Regex search
@router.post("/artifact/byRegEx/")
async def get_artifacts(request: RegexSearch):
    # grab regex from request, start timer, and store matches in a list 
    regex = request.regex
    pattern = re.compile(regex)

    start_time = time.monotonic()
    matching_artifacts = []

    # search through artifact metadata to determine if there are any matches
    for artifact_id in artifacts_metadata(): 
        name = artifacts_metadata[artifact_id]["name"]
        if pattern.search(name): # artifact name matches regex
            type = artifacts_metadata[artifact_id]["type"]
            artifact_dict = {"name" : name, "id" : artifact_id, "type": type}
            matching_artifacts.append(artifact_dict) 

        if time.monotonic - start_time > 5: # regex is bad or causing too much backtracking, search time is > 3 seconds
            Response(status_code=400) # invalid regex

    # zero regex matches
    if len(matching_artifacts) == 0:
        return Response(status_code=404)
    else: # nonzero regex matches
        return JSONResponse(content=matching_artifacts, status_code=200)

# license check of model against github project 
@router.post("/artifact/model/{id}/license-check/")
async def check_license(id: str, request: LicenseCheckRequest) -> JSONResponse:
    # checks if artifact is not in registry
    project_url = request.github_url
    if id not in artifacts_metadata: 
        return Response(status_code=404)

    # checks if artifact is a model
    if artifacts_metadata[id]["type"] != "model":
        return Response(status_code=400)
    # parse license from model 

    # parse the project url for readme
    valid, readme = get_github_readme(project_url)
    if not valid:
        return Response(status_code=404)
    # if no license, return 502
    # use llm to determine whether the project can use the model for fine tuning and inference
    # return status as true or false in json 
    pass

# get lineage graph of model, refer to evan's metric generation for that 
@router.post("/artifact/model/{id}/lineage/")
async def get_lineage_graph(id: str) -> JSONResponse:
    # check if id exists in the registry metadata db 
    # if it does not, return 404
    # check if artifact is a model
    # if not, return 400 
    # parse lineage graph from model metadata
    # return lineage graph as json 
    pass

# get cost of artifact
@router.get("/artifact/{artifact_type}/{id}/cost/")
async def get_artifact_cost(artifact_type: str, id: str, dependency: bool = False) -> JSONResponse:
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    # check if id exists in the registry metadata db
    # if it does not, return 404
    # parse cost from artifact metadata
    standalone_cost = 0
    sub_costs = 0
    if (dependency): 
        # find costs of dependencies 
        sub_costs = 1
    total_cost = standalone_cost + sub_costs
    # return cost as json