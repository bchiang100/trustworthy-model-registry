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
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from acme_cli.urls import parse_artifact_url, is_code_url, is_dataset_url, is_model_url
from acme_cli.hf.client import HfClient
from .route_util import validate_url_string, get_github_readme, make_id
import hashlib



from acme_cli.lineage_graph import LineageExtractor

router = APIRouter()


# S3 config
S3_BUCKET_NAME = os.getenv("ACME_S3_BUCKET", "acme-model-registry")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# initialize the S3 client
s3_client = boto3.client('s3', region_name=AWS_REGION)
hf_client = HfClient()

# other constants
PAGINATION_SIZE = 10

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
# Register an exception handler if the APIRouter supports it (older/newer
# FastAPI versions vary), otherwise provide a no-op function to avoid
# import-time errors during tests.
if hasattr(router, "exception_handler"):
    @router.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        return Response(status_code=400)
else:
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        return Response(status_code=400)

# python data structures to hold metdata of artifacts
# id -> name, type, url, downloadable s3 url
artifacts_metadata = {} 
# order of ids 
artifact_ids = []
# name -> id 
artifact_name_to_id: dict[str, List[int]] = {}

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

class QueryRequest(BaseModel):
    name: str 
    types: List[str]  # "model", "dataset", "code"

## SPEC COMPLIANT ENDPOINTS 

# health check / heartbeat
@router.get("/health/")
async def get_health():
    return Response(status_code = 200)

# query artifacts
@router.post("/artifacts/")
async def get_artifacts(request: List[QueryRequest], offset: str = "0"):
    pagination_offset: int = int(offset)

    # enumerate all artifacts in the registry metadata up to pagination size or end of registry
    if len(request) == 0 and request[0].name == "":
        for id in artifact_ids[pagination_offset:min(pagination_offset+PAGINATION_SIZE, len(artifacts_metadata))]:
            name = artifacts_metadata[id]["name"]
            type = artifacts_metadata[id]["type"]
            artifacts.append({"name": name, "id": id, "type": type})
        headers = {offset: str(pagination_offset + len(artifacts))}
        return JSONResponse(content=artifacts, headers=headers, status_code=200)

    # parse each query request, search for matches by name and then validate type 
    artifacts = [] 
    for query in request:
        name = query.name
        types = query.types
        for id in artifact_name_to_id.get(name, []):
            artifact = artifacts_metadata[id]
            if artifact["type"] in types: 
                type = artifacts_metadata[id]["type"]
                artifacts.append({"name": name, "id": id, "type": type})
    headers = {offset: str(pagination_offset + len(artifacts))}

    # too many artifacts returned
    if len(artifacts) > PAGINATION_SIZE:
        return Response(status_code=413)
    # return artifact matches 
    return JSONResponse(content=artifacts, headers=headers, status_code=200)

# reset registry (remove all entries)
@router.delete("/reset/")
async def reset_registry():
    # TODO: implement logic to batch enumerate from s3 and delete
    # TODO: also clear metadata dicts 
    return Response(status_code=200)

# get specific artifact
@router.get("/artifact/{artifact_type}/{id}/")
async def get_artifact(artifact_type: str, id: str):
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    # check if id exists in the registry metadata db 
    if id not in artifacts_metadata: 
        return Response(status_code=404)
    # if it does not, return 404
    # parse artifact metadata from db 
    name = artifacts_metadata[id]["name"]
    url = artifacts_metadata[id]["url"]
    metadata = {"name": name, "id": id, "type": artifact_type}
    data = {"url": url}
    artifact = {"metadata": metadata, "data": data}
    return JSONResponse(content=artifact, status_code=200)

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

    # retrieves all metric values 
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
            s3_key = f"{artifact_type}/{id}/.tar.gz"

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
            artifact_ids.append(id)
            # for new ids, handles the case where multiple artifacts share the same name
            if artifact_name not in artifact_name_to_id:
                artifact_name_to_id[artifact_name] = []
            artifact_name_to_id[artifact_name].append(id)

            # return artifact metadata and data as json
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
    # return track as json
    return JSONResponse(content={"plannedTracks": "Performance track"}, status_code=200)

# Regex search
@router.post("/artifact/byRegEx/")
async def get_artifacts(request: RegexSearch):
    # grab regex from request, start timer, and store matches in a list 
    regex = request.regex
    # compile regex safely
    try:
        pattern = re.compile(regex)
    except re.error:
        return Response(status_code=400)

    start_time = time.monotonic()
    matching_artifacts: list[dict] = []

    # search through artifact metadata to determine if there are any matches
    for artifact_id, meta in artifacts_metadata.items():
        name = meta.get("name", "")
        url = meta.get("url", "")

        # match on name first
        if pattern.search(name):
            matching_artifacts.append({"name": name, "id": artifact_id, "type": meta.get("type")})
            # skip readme fetch if name matched
            continue

        # only attempt README search for GitHub or Hugging Face model/dataset URLs
        try:
            if url and ("github.com" in url or "huggingface.co" in url):
                # GitHub: use our route_util helper which validates and fetches the README
                if "github.com" in url:
                    # use a short timeout for README fetches to avoid blocking
                    valid, readme = get_github_readme(url, timeout=2)
                    if valid and readme and pattern.search(readme):
                        matching_artifacts.append({"name": name, "id": artifact_id, "type": meta.get("type")})
                        continue

                # Hugging Face: try to download README.md from the repo
                if "huggingface.co" in url:
                    parsed = parse_artifact_url(url)
                    repo_id = getattr(parsed, "repo_id", None)
                    if repo_id and (is_model_url(url) or is_dataset_url(url)):
                        try:
                            repo_type = "model" if is_model_url(url) else "dataset"
                            local_readme = hf_client._api.hf_hub_download(repo_id=repo_id, filename="README.md", repo_type=repo_type)
                            with open(local_readme, "r", encoding="utf-8", errors="replace") as f:
                                readme = f.read()
                            if readme and pattern.search(readme):
                                matching_artifacts.append({"name": name, "id": artifact_id, "type": meta.get("type")})
                                continue
                        except Exception:
                            # ignore any HF read errors and continue
                            pass

        except Exception:
            # tolerate any unexpected per-artifact errors
            pass

        # support timeout of 2 seconds to ensure regex search does not hang
        if time.monotonic() - start_time > 2:
            return Response(status_code=400)

    # return results
    if not matching_artifacts:
        return Response(status_code=404)
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
    project_has_license = readme.lower().find("license") != -1
    if not project_has_license:
        return Response(status_code=502)
    # use llm to determine whether the project can use the model for fine tuning and inference
    license_compatible = True
    if not license_compatible:
        return JSONResponse(content="false", status_code=200)
    # return status as true or false in json 
    return JSONResponse(content="true", status_code=200)

# get lineage graph of model, refer to evan's metric generation for that 
@router.post("/artifact/model/{id}/lineage/")
async def get_lineage_graph(id: str) -> JSONResponse:
    # check if id exists in the registry metadata db 
    # if it does not, return 404
    # check if artifact is a model
    # if not, return 400 
    # parse lineage graph from model metadata
    # return lineage graph as json 
    if id not in artifacts_metadata:
        return Response(status_code=404)

    meta = artifacts_metadata[id]
    if meta.get("type") != "model":
        return Response(status_code=400)

    url = meta.get("url")
    if not url:
        return Response(status_code=400)

    parsed = parse_artifact_url(url)
    if not parsed or not getattr(parsed, "repo_id", None):
        return Response(status_code=400)

    try:
        extractor = LineageExtractor()
        graph = extractor.extract(parsed.repo_id, max_depth=5)
        payload = graph.to_artifact_lineage_graph()
        return JSONResponse(content=payload, status_code=200)
    except Exception as e:
        # log and return 500
        raise HTTPException(status_code=500, detail=f"Failed to compute lineage: {e}")


# Return full model rating per spec
@router.get("/artifact/model/{id}/rate/")
async def get_model_rating(id: str) -> JSONResponse:
    """Return the model rating (all metrics) for the given artifact id.

    This endpoint builds the rating using the same `calculate_metrics` helper
    used during ingest. Latencies are approximate and reported as seconds.
    """
    if id not in artifacts_metadata:
        return Response(status_code=404)

    meta = artifacts_metadata[id]
    if meta.get("type") != "model":
        return Response(status_code=400)

    url = meta.get("url")
    if not url:
        return Response(status_code=400)

    # Compute metrics (may be cached by upstream ingest in a real system)
    start = time.monotonic()
    metrics = calculate_metrics(url)
    elapsed = time.monotonic() - start

    if not metrics:
        # failure computing metrics
        raise HTTPException(status_code=500, detail="Failed to compute metrics")

    # Helper to pull numeric value or default
    def v(name, default=0.0):
        val = metrics.get(name)
        if isinstance(val, (int, float)):
            return float(val)
        return default

    # size_score may be an object
    size_score = metrics.get("size_score") or {}

    rating = {
        "name": meta.get("name", id),
        "category": "model",
        "net_score": v("net_score"),
        "net_score_latency": elapsed,
        "ramp_up_time": v("ramp_up_time"),
        "ramp_up_time_latency": 0.0,
        "bus_factor": v("bus_factor"),
        "bus_factor_latency": 0.0,
        "performance_claims": v("performance_claims"),
        "performance_claims_latency": 0.0,
        "license": v("license"),
        "license_latency": 0.0,
        "dataset_and_code_score": v("dataset_and_code_score"),
        "dataset_and_code_score_latency": 0.0,
        "dataset_quality": v("dataset_quality"),
        "dataset_quality_latency": 0.0,
        "code_quality": v("code_quality"),
        "code_quality_latency": 0.0,
        "reproducibility": v("reproducibility"),
        "reproducibility_latency": 0.0,
        "reviewedness": v("reviewedness"),
        "reviewedness_latency": 0.0,
        "tree_score": v("tree_score"),
        "tree_score_latency": 0.0,
        "size_score": size_score,
        "size_score_latency": 0.0,
    }

    return JSONResponse(content=rating, status_code=200)


@router.get("/artifact/model/{id}/metric/{metric_name}/")
async def get_single_metric(id: str, metric_name: str) -> JSONResponse:
    """Return a single metric value and an approximate latency for the artifact.

    metric_name should be one of the metric keys included in the ModelRating
    (e.g., 'ramp_up_time', 'code_quality', 'size_score', 'reproducibility').
    """
    if id not in artifacts_metadata:
        return Response(status_code=404)

    meta = artifacts_metadata[id]
    if meta.get("type") != "model":
        return Response(status_code=400)

    url = meta.get("url")
    if not url:
        return Response(status_code=400)

    start = time.monotonic()
    metrics = calculate_metrics(url)
    elapsed = time.monotonic() - start

    if not metrics:
        raise HTTPException(status_code=500, detail="Failed to compute metrics")

    if metric_name not in metrics:
        return Response(status_code=404)

    value = metrics.get(metric_name)

    return JSONResponse(content={"metric": metric_name, "value": value, "latency_seconds": elapsed}, status_code=200)

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

    # if error in cost calculation, return 500
    return Response(status_code=500) 
    # return cost as json