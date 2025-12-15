"""
Load testing module for simulating concurrent model downloads.
Spawns N concurrent clients to download a model URL concurrently.
"""

import asyncio
import logging
from typing import List, Dict, Optional
import httpx
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class LoadTestResult:
    """Result from a load test run."""

    def __init__(self, model_id: str, model_url: str, num_clients: int):
        self.model_id = model_id
        self.model_url = model_url
        self.num_clients = num_clients
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.results: List[Dict] = []
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.total_bytes_downloaded = 0
        self.errors: List[str] = []

    @property
    def duration(self) -> float:
        """Total duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

    @property
    def throughput(self) -> float:
        """Throughput in MB/s."""
        if self.duration > 0:
            return (self.total_bytes_downloaded / (1024 * 1024)) / self.duration
        return 0

    @property
    def success_rate(self) -> float:
        """Percentage of successful downloads."""
        if self.num_clients > 0:
            return (self.successful_downloads / self.num_clients) * 100
        return 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "model_url": self.model_url,
            "num_clients": self.num_clients,
            "duration_seconds": round(self.duration, 2),
            "throughput_mbps": round(self.throughput, 2),
            "success_rate_percent": round(self.success_rate, 2),
            "successful_downloads": self.successful_downloads,
            "failed_downloads": self.failed_downloads,
            "total_bytes_downloaded": self.total_bytes_downloaded,
            "timestamp": datetime.utcnow().isoformat(),
            "errors": self.errors[:10],  # Keep first 10 errors
        }


async def download_model(
    client_id: int,
    url: str,
    timeout: int = 30,
) -> Dict:
    """
    Simulate a single client downloading a model.

    Args:
        client_id: Unique identifier for this client
        url: URL of the model to download
        timeout: Download timeout in seconds

    Returns:
        Dictionary with download result
    """
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            elapsed = time.time() - start
            content_length = len(response.content)

            return {
                "client_id": client_id,
                "success": True,
                "status_code": response.status_code,
                "bytes_downloaded": content_length,
                "duration_seconds": elapsed,
                "speed_mbps": (content_length / (1024 * 1024)) / elapsed
                if elapsed > 0
                else 0,
            }
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        return {
            "client_id": client_id,
            "success": False,
            "error": "Timeout",
            "duration_seconds": elapsed,
        }
    except httpx.HTTPError as e:
        elapsed = time.time() - start
        return {
            "client_id": client_id,
            "success": False,
            "error": str(e),
            "duration_seconds": elapsed,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "client_id": client_id,
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "duration_seconds": elapsed,
        }


async def run_load_test(
    model_id: str,
    model_url: str,
    num_clients: int = 100,
    timeout: int = 30,
) -> LoadTestResult:
    """
    Run a load test with N concurrent clients downloading the model.

    Args:
        model_id: ID of the model
        model_url: URL to download the model from
        num_clients: Number of concurrent clients (default 100)
        timeout: Download timeout in seconds per client

    Returns:
        LoadTestResult with statistics
    """
    result = LoadTestResult(model_id, model_url, num_clients)
    result.start_time = time.time()

    logger.info(
        f"Starting load test for {model_id} with {num_clients} concurrent clients"
    )

    try:
        # Create tasks for all clients
        tasks = [
            download_model(client_id, model_url, timeout)
            for client_id in range(num_clients)
        ]

        # Run all downloads concurrently
        download_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for download_result in download_results:
            if isinstance(download_result, Exception):
                result.failed_downloads += 1
                result.errors.append(str(download_result))
            elif download_result.get("success"):
                result.successful_downloads += 1
                result.total_bytes_downloaded += download_result.get(
                    "bytes_downloaded", 0
                )
                result.results.append(download_result)
            else:
                result.failed_downloads += 1
                error_msg = download_result.get("error", "Unknown error")
                result.errors.append(f"Client {download_result.get('client_id')}: {error_msg}")
                result.results.append(download_result)

    except Exception as e:
        logger.error(f"Load test failed: {str(e)}")
        result.errors.append(f"Load test execution failed: {str(e)}")

    result.end_time = time.time()

    logger.info(
        f"Load test completed: {result.successful_downloads}/{num_clients} successful, "
        f"throughput: {result.throughput:.2f} MB/s, "
        f"duration: {result.duration:.2f}s"
    )

    return result


def run_load_test_sync(
    model_id: str,
    model_url: str,
    num_clients: int = 100,
    timeout: int = 30,
) -> LoadTestResult:
    """
    Synchronous wrapper for running a load test.

    Args:
        model_id: ID of the model
        model_url: URL to download the model from
        num_clients: Number of concurrent clients (default 100)
        timeout: Download timeout in seconds per client

    Returns:
        LoadTestResult with statistics
    """
    return asyncio.run(run_load_test(model_id, model_url, num_clients, timeout))
