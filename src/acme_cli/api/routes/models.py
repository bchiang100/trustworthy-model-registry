# manages model endpoints for CR[U]D operations

import re
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, JSONResponse, Response, Request, RequestValidationError
from pydantic import BaseModel
from acme_cli.urls import parse_artifact_url, is_code_url, is_dataset_url, is_model_url
from route_util import validate_url_string, make_id

router = APIRouter()

# invalid requests for our spec use status code 400
@router.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return Response(status_code=400)

# python dict to hold metdata of artifacts
# -> name, type, id, url, downloadable s3 url
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
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    # check if name and id exists in the registry metadata db 
    # if it does not, return 404
    # parse artifact metadata from db 
    # update artifact metadata in db 
    # re-ingest with new link
    pass

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
        return Response(status_code = 400)
    # check if url exists in the registry metadata db
    # if it does, return 409
    # download files using HF API 
    # rate artifact
    rating = 0.5 # edit to use rating system 
    # if pass, ingest and return 201 with artifact metadata and urls as json
    # create id 
    id = make_id(artifact_url)
    if rating >= 0.5: 
        # extract name
        # place metadata in dict
        # -> name, type, id, url, download url
        # download files to s3 and create downloadable link

        # TODO: include the S3 download url
        artifacts_metadata[id] = {"name": artifact_name, "type": artifact_type, "url" : artifact_url} 

    # if fail, return 424
    pass

# Get track
@router.get("/tracks/")
async def get_tracks():
    return JSONResponse(content={"plannedTracks": "Performance track"}, status_code=200)

# Regex search
@router.post("/artifact/byRegEx/")
async def get_artifacts(regex: RegexSearch):
    # TODO: some logic for regex to check validity of expression
    # also validate the request body itself
    pattern = re.compile(regex="regex")
    return Response(status_code=403)

# license check of model against github project 
@router.post("/artifact/model/{id}/license-check/")
async def check_license(id: str, project_url: LicenseCheckRequest) -> JSONResponse:
    # check if id exists in the registry metadata db 
    # if it does not, return 404
    # check if artifact is a model
    # if not, return 400 
    # parse license from model metadata
    # parse the project url to check if it is a valid github url
    project = project_url.github_url
    # if it is not, return 404 
    # if it does, check the license against project url 
    # if no license, return 502
    # return status as true or false in json 
    pass

# get lineage graph of model
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
async def get_artifact_cost(artifact_type: str, id: str) -> JSONResponse:
    if artifact_type not in ["model", "dataset", "code"]:
        return Response(status_code=400)
    # check if id exists in the registry metadata db
    # if it does not, return 404
    # parse cost from artifact metadata
    # return cost as json