"""Middleware for collecting metrics and monitoring requests."""

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from monitoring import get_metrics_collector


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics for monitoring."""

    def __init__(self, app):
        super().__init__(app)
        self.metrics_collector = get_metrics_collector()

    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""
        start_time = time.time()

        # Record request start
        endpoint = str(request.url.path)
        method = request.method
        # metrics dispatch start

        # Process the request
        try:
            response = await call_next(request)
            status_code = response.status_code
            # call_next returned
        except Exception as e:
            # Log error and return 500
            self.metrics_collector.add_log(f"Request error: {str(e)}", "ERROR")
            status_code = 500
            response = Response("Internal Server Error", status_code=500)

        # Calculate response time
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000

        # Record metrics (skip health endpoint to avoid circular logging)
        if not endpoint.startswith("/api/v1/health"):
            self.metrics_collector.record_request(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
            )

        # Add response headers for monitoring
        response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"

        return response
