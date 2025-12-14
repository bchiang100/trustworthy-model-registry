"""System monitoring and metrics collection for health dashboard."""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List

import psutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and stores application metrics."""

    def __init__(self):
        self.metrics_store = defaultdict(list)
        self.activity_counters = defaultdict(int)
        self.response_times = deque(maxlen=1000)  # Keep last 1000 response times
        self.logs_buffer = deque(maxlen=500)  # Keep last 500 log entries
        self.start_time = time.time()
        self._lock = threading.RLock()

    def record_request(
        self, endpoint: str, method: str, status_code: int, response_time_ms: float
    ):
        """Record an API request with metrics."""
        # record_request start
        with self._lock:
            timestamp = datetime.utcnow()

            # Record in metrics store
            self.metrics_store["requests"].append(
                {
                    "timestamp": timestamp,
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                }
            )

            # Update counters
            self.activity_counters["total_requests"] += 1
            if status_code >= 400:
                self.activity_counters["errors"] += 1

            # Track specific endpoints
            if "upload" in endpoint:
                self.activity_counters["uploads"] += 1
            elif "download" in endpoint:
                self.activity_counters["downloads"] += 1
            elif "search" in endpoint or "models" in endpoint:
                self.activity_counters["searches"] += 1

            # Store response time
            self.response_times.append(response_time_ms)

            # Log the request
            self.add_log(f"[{method}] {endpoint} - {status_code} ({response_time_ms:.1f}ms)")

    def add_log(self, message: str, level: str = "INFO"):
        """Add a log entry to the buffer."""
        # add_log start
        with self._lock:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {message}"
            self.logs_buffer.append(log_entry)
            logger.info(message)

    async def get_metrics_summary(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get summarized metrics for a time period."""
        with self._lock:
            # Filter requests in time range
            requests_in_range = [
                r
                for r in self.metrics_store["requests"]
                if start_time <= r["timestamp"] <= end_time
            ]

            if not requests_in_range:
                return {
                    "performance": {
                        "total_requests": 0,
                        "avg_response_time": 0,
                        "error_rate": 0,
                    }
                }

            # Calculate performance metrics
            total_requests = len(requests_in_range)
            avg_response_time = (
                sum(r["response_time_ms"] for r in requests_in_range) / total_requests
            )
            error_count = sum(1 for r in requests_in_range if r["status_code"] >= 400)
            error_rate = (
                (error_count / total_requests) * 100 if total_requests > 0 else 0
            )

            return {
                "performance": {
                    "total_requests": total_requests,
                    "avg_response_time": avg_response_time,
                    "error_rate": error_rate,
                    "error_count": error_count,
                }
            }

    async def get_activity_stats(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, int]:
        """Get activity statistics for the specified time period."""
        with self._lock:
            # Filter requests in time range
            requests_in_range = [
                r
                for r in self.metrics_store["requests"]
                if start_time <= r["timestamp"] <= end_time
            ]

            # Count activities
            uploads = sum(1 for r in requests_in_range if "upload" in r["endpoint"])
            downloads = sum(1 for r in requests_in_range if "download" in r["endpoint"])
            searches = sum(
                1
                for r in requests_in_range
                if "search" in r["endpoint"] or r["endpoint"].endswith("/models")
            )
            errors = sum(1 for r in requests_in_range if r["status_code"] >= 400)

            # Calculate average response time
            avg_response_time = 0
            if requests_in_range:
                avg_response_time = sum(
                    r["response_time_ms"] for r in requests_in_range
                ) / len(requests_in_range)

            return {
                "total_requests": len(requests_in_range),
                "uploads": uploads,
                "downloads": downloads,
                "searches": searches,
                "errors": errors,
                "avg_response_time": avg_response_time,
            }

    async def get_detailed_metrics(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get detailed metrics breakdown."""
        with self._lock:
            requests_in_range = [
                r
                for r in self.metrics_store["requests"]
                if start_time <= r["timestamp"] <= end_time
            ]

            # Group by endpoint
            endpoint_stats = defaultdict(list)
            for request in requests_in_range:
                endpoint_stats[request["endpoint"]].append(request)

            # Calculate per-endpoint statistics
            endpoint_metrics = {}
            for endpoint, reqs in endpoint_stats.items():
                endpoint_metrics[endpoint] = {
                    "count": len(reqs),
                    "avg_response_time": sum(r["response_time_ms"] for r in reqs)
                    / len(reqs),
                    "error_rate": (
                        sum(1 for r in reqs if r["status_code"] >= 400) / len(reqs)
                    )
                    * 100,
                }

            return {
                "endpoint_metrics": endpoint_metrics,
                "time_series": [
                    {
                        "timestamp": r["timestamp"].isoformat(),
                        "response_time": r["response_time_ms"],
                        "status_code": r["status_code"],
                    }
                    for r in requests_in_range[-100:]  # Last 100 requests
                ],
            }

    async def get_recent_logs(self, limit: int = 50) -> List[str]:
        """Get recent log entries."""
        with self._lock:
            return list(self.logs_buffer)[-limit:]

    async def get_logs(self, limit: int = 100, level: str = "INFO") -> List[str]:
        """Get filtered log entries."""
        with self._lock:
            filtered_logs = [
                log
                for log in self.logs_buffer
                if level.upper() in log or level == "ALL"
            ]
            return filtered_logs[-limit:]


class SystemMonitor:
    """Monitors system-level metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.alerts = []

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        try:
            # CPU usage (non-blocking - gets instantaneous reading)
            cpu_percent = psutil.cpu_percent(interval=None)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100

            # Network I/O
            net_io = psutil.net_io_counters()

            # System uptime
            uptime_seconds = time.time() - self.start_time
            uptime = str(timedelta(seconds=int(uptime_seconds)))

            return {
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory_percent, 1),
                "disk_percent": round(disk_percent, 1),
                "uptime": uptime,
                "network_io": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                },
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "disk_percent": 0,
                "uptime": "unknown",
                "network_io": {"bytes_sent": 0, "bytes_recv": 0},
            }

    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active system alerts."""
        alerts = []

        try:
            stats = await self.get_system_stats()

            # Check for high resource usage
            if stats["cpu_percent"] > 80:
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"High CPU usage: {stats['cpu_percent']}%",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            if stats["memory_percent"] > 85:
                alerts.append(
                    {
                        "type": "warning",
                        "message": f"High memory usage: {stats['memory_percent']}%",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            if stats["disk_percent"] > 90:
                alerts.append(
                    {
                        "type": "critical",
                        "message": f"Low disk space: {stats['disk_percent']}% used",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        except Exception as e:
            alerts.append(
                {
                    "type": "error",
                    "message": f"Error checking system health: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        return alerts


# Global instances
metrics_collector = MetricsCollector()
system_monitor = SystemMonitor()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector


def get_system_monitor() -> SystemMonitor:
    """Get the global system monitor instance."""
    return system_monitor
