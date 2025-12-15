#!/usr/bin/env bash

# Local Development Startup Script
# This script starts the API server for local development

set -e

echo "========================================"
echo "ACME Trustworthy Model Registry"
echo "Starting Development Server"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root."
    exit 1
fi


# Check if virtual environment exists (.venv)
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment in .venv..."
    py -m venv .venv || python -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    echo "Could not find .venv activation script."
    exit 1
fi

# Install dependencies
echo "Installing/updating dependencies..."
pip install -q --upgrade pip setuptools wheel
pip install -q -e .
pip install -q uvicorn gunicorn

# Load environment variables
if [ -f ".env" ]; then
    echo "Loading environment variables from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Note: .env file not found. Using defaults (development mode)"
    export ENVIRONMENT=development
    export API_HOST=0.0.0.0
    export API_PORT=8000
fi

echo ""
echo "========================================"
echo "Development Server Ready"
echo "========================================"
echo "Environment: ${ENVIRONMENT:-development}"
echo "API Host: ${API_HOST:-0.0.0.0}"
echo "API Port: ${API_PORT:-8000}"
echo ""
echo "Starting uvicorn server..."
echo "Access the application at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

# Start the server
uvicorn src.acme_cli.api.main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --reload \
    --log-level "${LOG_LEVEL:-info}"
