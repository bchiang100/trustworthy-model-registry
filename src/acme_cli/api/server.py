"""Server startup script for the ACME Registry API.

When running this file directly (e.g. `python src/acme_cli/api/server.py`), ensure
the project's `src` directory is on `sys.path` so package imports work as expected.
"""

import os
import sys
import uvicorn

# Add project `src` directory to `sys.path` so `acme_cli` can be imported when
# running this module as a script.
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from acme_cli.api.main import app


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """Start the FastAPI server."""
    uvicorn.run(
        "acme_cli.api.main:app", host=host, port=port, reload=reload, log_level="info"
    )


if __name__ == "__main__":
    start_server()
