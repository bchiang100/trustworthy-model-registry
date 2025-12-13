"""Server startup script for the ACME Registry API."""

import uvicorn

from .main import app


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """Start the FastAPI server."""
    uvicorn.run(
        "acme_cli.api.main:app", host=host, port=port, reload=reload, log_level="info"
    )


if __name__ == "__main__":
    start_server()
