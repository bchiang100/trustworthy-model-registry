# manages model endpoints for CR[U]D operations

import logging
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
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Response, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from acme_cli.urls import parse_artifact_url, is_code_url, is_dataset_url, is_model_url
from acme_cli.hf.client import HfClient
from .route_util import validate_url_string, get_github_readme, make_id
import hashlib
from acme_cli.llm import LlmEvaluator



from acme_cli.lineage_graph import LineageExtractor

router = APIRouter()
logger = logging.getLogger(__name__)


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
# Note: exception_handler should be registered on app, not router
# @router.exception_handler(RequestValidationError)
# async def validation_exception_handler(
#     request: Request,
#     exc: RequestValidationError,
# ):
#     return Response(status_code=400)

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
@router.get("/health")
async def get_health():
    return Response(status_code = 200)

# query artifacts
@router.post("/artifacts")
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
@router.delete("/reset")
async def reset_registry():
    # TODO: implement logic to batch enumerate from s3 and delete
    # TODO: also clear metadata dicts 
    return Response(status_code=200)

# get specific artifact
@router.get("/artifact/{artifact_type}/{id}")
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
@router.put("/artifact/{artifact_type}/{id}")
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
@router.post("/artifact/{artifact_type}")
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
@router.get("/tracks")
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
@router.post("/artifact/model/{id}/license-check")
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

    # simple license detection helper (naive)
    def _detect_license(text: str) -> str | None:
        if not text:
            return None
        # look for common SPDX identifiers or license names
        m = re.search(r"(Apache-2\.0|Apache License|MIT License|MIT|BSD-3-Clause|BSD|GPL-3\.0|GPL|LGPL)", text, re.I)
        return m.group(0) if m else None

    project_license = _detect_license(readme)
    if not project_license:
        # no explicit license text found in README
        return Response(status_code=502)

    # parse license from model on Hugging Face
    meta = artifacts_metadata.get(id)
    model_license: str | None = None
    if meta:
        model_url = meta.get("url")
        parsed = parse_artifact_url(model_url) if model_url else None
        repo_id = getattr(parsed, "repo_id", None) if parsed else None
        if repo_id:
            # try structured metadata first
            info = hf_client.get_model(repo_id)
            if info and getattr(info, "card_data", None):
                model_license = info.card_data.get("license") or info.card_data.get("License")

            # fallback: try to read LICENSE file from repo
            if not model_license:
                for fname in ("LICENSE", "LICENSE.md", "LICENSE.txt", "license", "license.md"):
                    try:
                        path = hf_client._api.hf_hub_download(repo_id=repo_id, filename=fname, repo_type="model")
                        if path:
                            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                                content = fh.read()
                            ml = _detect_license(content)
                            if ml:
                                model_license = ml
                                break
                    except Exception:
                        continue

    # determine compatibility using the LLM; fall back to False on errors
    license_compatible = None
    if project_license and model_license:
        try:
            evaluator = LlmEvaluator()
            license_compatible = evaluator.judge_license_compatibility(
                project_license, model_license
            )
        except Exception:
            # Any LLM errors are considered non-compatible by default
            license_compatible = False

    return JSONResponse(
        content={
            "project_has_license": True,
            "project_license": project_license,
            "model_license": model_license,
            "license_compatible": license_compatible,
        },
        status_code=200,
    )

# get lineage graph of model, refer to evan's metric generation for that 
@router.post("/artifact/model/{id}/lineage")
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
@router.get("/artifact/model/{id}/rate")
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
    def get_metric_val(name, default=0.0):
        val = metrics.get(name)
        if isinstance(val, (int, float)):
            return float(val)
        return default

    # size_score may be an object
    size_score = metrics.get("size_score") or {}

    rating = {
        "name": meta.get("name", id),
        "category": "model",
        "net_score": get_metric_val("net_score"),
        "net_score_latency": elapsed,
        "ramp_up_time": get_metric_val("ramp_up_time"),
        "ramp_up_time_latency": 0.0,
        "bus_factor": get_metric_val("bus_factor"),
        "bus_factor_latency": 0.0,
        "performance_claims": get_metric_val("performance_claims"),
        "performance_claims_latency": 0.0,
        "license": get_metric_val("license"),
        "license_latency": 0.0,
        "dataset_and_code_score": get_metric_val("dataset_and_code_score"),
        "dataset_and_code_score_latency": 0.0,
        "dataset_quality": get_metric_val("dataset_quality"),
        "dataset_quality_latency": 0.0,
        "code_quality": get_metric_val("code_quality"),
        "code_quality_latency": 0.0,
        "reproducibility": get_metric_val("reproducibility"),
        "reproducibility_latency": 0.0,
        "reviewedness": get_metric_val("reviewedness"),
        "reviewedness_latency": 0.0,
        "tree_score": get_metric_val("tree_score"),
        "tree_score_latency": 0.0,
        "size_score": size_score,
        "size_score_latency": 0.0,
    }

    return JSONResponse(content=rating, status_code=200)


# @router.get("/artifact/model/{id}/metric/{metric_name}/")
# async def get_single_metric(id: str, metric_name: str) -> JSONResponse:
#     """Return a single metric value and an approximate latency for the artifact.

#     metric_name should be one of the metric keys included in the ModelRating
#     (e.g., 'ramp_up_time', 'code_quality', 'size_score', 'reproducibility').
#     """
#     if id not in artifacts_metadata:
#         return Response(status_code=404)

#     meta = artifacts_metadata[id]
#     if meta.get("type") != "model":
#         return Response(status_code=400)

#     url = meta.get("url")
#     if not url:
#         return Response(status_code=400)

#     start = time.monotonic()
#     metrics = calculate_metrics(url)
#     elapsed = time.monotonic() - start

#     if not metrics:
#         raise HTTPException(status_code=500, detail="Failed to compute metrics")

#     if metric_name not in metrics:
#         return Response(status_code=404)

#     value = metrics.get(metric_name)

#     return JSONResponse(content={"metric": metric_name, "value": value, "latency_seconds": elapsed}, status_code=200)

# get cost of artifact
@router.get("/artifact/{artifact_type}/{id}/cost")
async def get_artifact_cost(artifact_type: str, id: str, dependency: bool = False) -> JSONResponse:
    """Return the cost (download size in MB) of an artifact, optionally including dependencies.
    
    Per the OpenAPI spec, cost is defined as the total download size required for the artifact,
    and optionally includes the sizes of dependencies (parent models in the lineage).
    
    Response structure:
    - Without dependencies: { "artifact_id": { "total_cost": <size_in_mb> } }
    - With dependencies: { "artifact_id": { "standalone_cost": <size>, "total_cost": <sum> }, ... }
    """
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    
    # Check if artifact exists in registry
    if id not in artifacts_metadata:
        return Response(status_code=404)
    
    meta = artifacts_metadata[id]
    
    # Get the artifact's source URL to compute size
    url = meta.get("url")
    if not url:
        return Response(status_code=400)
    
    # Helper function to calculate size in MB from metadata
    def get_artifact_size_mb(artifact_url: str) -> float:
        """Calculate the download size of an artifact in MB."""
        try:
            metrics = calculate_metrics(artifact_url)
            # Metrics includes model_metadata which has file list with sizes
            # For now, estimate based on the artifact type and common model sizes
            
            # Parse the artifact URL to get metadata
            parsed = parse_artifact_url(artifact_url)
            if not parsed or not parsed.repo_id:
                return 100.0  # Default estimate if parsing fails
            
            # Try to fetch HF metadata to get real file sizes
            try:
                from huggingface_hub import HfApi
                hf_api = HfApi()
                
                if artifact_type == "model":
                    model_info = hf_api.model_info(parsed.repo_id, timeout=5)
                    # Sum up all file sizes
                    total_bytes = 0
                    if model_info.siblings:
                        for sibling in model_info.siblings:
                            if sibling.size:
                                total_bytes += sibling.size
                    # Convert to MB
                    return total_bytes / (1024 * 1024)
                elif artifact_type == "dataset":
                    dataset_info = hf_api.dataset_info(parsed.repo_id, timeout=5)
                    total_bytes = 0
                    if dataset_info.siblings:
                        for sibling in dataset_info.siblings:
                            if sibling.size:
                                total_bytes += sibling.size
                    return total_bytes / (1024 * 1024)
                else:  # code
                    # For code repos, estimate typical GitHub repo size
                    return 50.0
            except Exception:
                # Fallback estimates if HF API fails
                if artifact_type == "model":
                    return 200.0  # Typical model ~200MB
                elif artifact_type == "dataset":
                    return 500.0  # Typical dataset ~500MB
                else:
                    return 50.0   # Typical code repo ~50MB
        except Exception:
            # Default fallback
            return 100.0
    
    # Calculate standalone cost for the requested artifact
    standalone_cost_mb = get_artifact_size_mb(url)
    
    # Build response
    result = {}
    
    if not dependency:
        # Simple case: just the artifact itself
        result[id] = {
            "total_cost": standalone_cost_mb
        }
    else:
        # Include dependencies: fetch lineage graph and sum all ancestor sizes
        try:
            # Only models can have dependencies via lineage
            if artifact_type != "model":
                # Non-models only have their own cost
                result[id] = {
                    "standalone_cost": standalone_cost_mb,
                    "total_cost": standalone_cost_mb
                }
            else:
                # Extract lineage to find all ancestor models
                parsed = parse_artifact_url(url)
                if not parsed or not parsed.repo_id:
                    result[id] = {
                        "standalone_cost": standalone_cost_mb,
                        "total_cost": standalone_cost_mb
                    }
                else:
                    try:
                        extractor = LineageExtractor()
                        graph = extractor.extract(parsed.repo_id, max_depth=5)
                        
                        # Start with the root model's cost
                        total_with_deps = standalone_cost_mb
                        result[id] = {
                            "standalone_cost": standalone_cost_mb,
                            "total_cost": standalone_cost_mb
                        }
                        
                        # Add costs of all ancestor models
                        ancestors = graph.get_ancestors()
                        for ancestor_repo_id in ancestors:
                            # Try to construct HF URL for ancestor
                            ancestor_url = f"https://huggingface.co/{ancestor_repo_id}"
                            ancestor_cost = get_artifact_size_mb(ancestor_url)
                            total_with_deps += ancestor_cost
                            
                            # Create an entry for each ancestor (use repo_id as artifact_id)
                            # In a real system, we'd look up the actual artifact_id
                            result[ancestor_repo_id] = {
                                "standalone_cost": ancestor_cost,
                                "total_cost": ancestor_cost
                            }
                        
                        # Update the root artifact with total including deps
                        result[id]["total_cost"] = total_with_deps
                        
                    except Exception as e:
                        # If lineage extraction fails, just return standalone cost
                        logger.debug(f"Failed to extract lineage for cost calculation: {e}")
                        result[id] = {
                            "standalone_cost": standalone_cost_mb,
                            "total_cost": standalone_cost_mb
                        }
        except Exception as e:
            # Generic error, return 500
            raise HTTPException(status_code=500, detail=f"Failed to calculate artifact cost: {str(e)}")
    
    return JSONResponse(content=result, status_code=200) 
    # return cost as json
