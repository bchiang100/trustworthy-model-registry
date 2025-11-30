"""Health check endpoints for system monitoring and dashboard."""

import asyncio
import os
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from ..monitoring import MetricsCollector, SystemMonitor

router = APIRouter()
metrics_collector = MetricsCollector()
system_monitor = SystemMonitor()


@router.get("/health")
async def health_check():
    """Basic system health check endpoint."""
    try:
        system_stats = await system_monitor.get_system_stats()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "acme-registry",
            "version": "0.1.0",
            "uptime": system_stats.get("uptime", "operational"),
            "dependencies": {
                "database": "connected",
                "storage": "available",
                "memory_usage": system_stats.get("memory_percent"),
                "cpu_usage": system_stats.get("cpu_percent")
            },
        }
    except Exception as e:
        return {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/health/dashboard")
async def health_dashboard():
    """Comprehensive system health dashboard with semi-real-time metrics."""
    try:
        # Get metrics for the last hour
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        # Collect all metrics
        metrics_data = await metrics_collector.get_metrics_summary(start_time, end_time)
        system_stats = await system_monitor.get_system_stats()
        activity_stats = await metrics_collector.get_activity_stats(start_time, end_time)

        return {
            "timestamp": end_time.isoformat(),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "system_health": {
                "status": "healthy" if system_stats.get("cpu_percent", 0) < 80 else "warning",
                "uptime": system_stats.get("uptime"),
                "cpu_usage_percent": system_stats.get("cpu_percent"),
                "memory_usage_percent": system_stats.get("memory_percent"),
                "disk_usage_percent": system_stats.get("disk_percent"),
                "network_io": system_stats.get("network_io")
            },
            "registry_activity": {
                "total_requests": activity_stats.get("total_requests", 0),
                "model_uploads": activity_stats.get("uploads", 0),
                "model_downloads": activity_stats.get("downloads", 0),
                "search_queries": activity_stats.get("searches", 0),
                "error_count": activity_stats.get("errors", 0),
                "average_response_time_ms": activity_stats.get("avg_response_time", 0)
            },
            "performance_metrics": metrics_data.get("performance", {}),
            "recent_logs": await metrics_collector.get_recent_logs(limit=50),
            "alerts": await system_monitor.get_active_alerts()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


@router.get("/health/metrics")
async def get_metrics(hours: int = 1):
    """Get detailed metrics for the specified time period."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        metrics = await metrics_collector.get_detailed_metrics(start_time, end_time)
        return {
            "timestamp": end_time.isoformat(),
            "time_range_hours": hours,
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/health/logs")
async def get_logs(limit: int = 100, level: str = "INFO"):
    """Get recent system logs with filtering."""
    try:
        logs = await metrics_collector.get_logs(limit=limit, level=level)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "logs": logs,
            "count": len(logs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/health/dashboard/ui", response_class=HTMLResponse)
async def dashboard_ui():
    """Web UI for the system health dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ACME Registry Health Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .dashboard {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                background: #2c3e50;
                color: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .metric-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .metric-value {
                font-size: 2em;
                font-weight: bold;
                color: #27ae60;
            }
            .metric-label {
                color: #7f8c8d;
                margin-bottom: 10px;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-healthy {
                background-color: #27ae60;
            }
            .status-warning {
                background-color: #f39c12;
            }
            .status-error {
                background-color: #e74c3c;
            }
            .logs-section {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .log-entry {
                font-family: monospace;
                font-size: 12px;
                margin: 5px 0;
                padding: 5px;
                background: #ecf0f1;
                border-radius: 3px;
            }
            .refresh-btn {
                background: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div class="header">
                <h1>ACME Registry Health Dashboard</h1>
                <p>Real-time monitoring and system health overview</p>
                <button class="refresh-btn" onclick="refreshData()">Refresh Data</button>
            </div>

            <div id="dashboard-content">
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-label">System Status</div>
                        <div id="system-status">Loading...</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">CPU Usage</div>
                        <div class="metric-value" id="cpu-usage">--%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Memory Usage</div>
                        <div class="metric-value" id="memory-usage">--%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Registry Activity (1h)</div>
                        <div class="metric-value" id="total-requests">--</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Model Downloads</div>
                        <div class="metric-value" id="downloads">--</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Model Uploads</div>
                        <div class="metric-value" id="uploads">--</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Error Count</div>
                        <div class="metric-value" id="errors">--</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Avg Response Time</div>
                        <div class="metric-value" id="response-time">-- ms</div>
                    </div>
                </div>

                <div class="logs-section">
                    <h3>Recent System Logs</h3>
                    <div id="logs-container">
                        Loading logs...
                    </div>
                </div>
            </div>
        </div>

        <script>
            async function fetchDashboardData() {
                try {
                    const response = await fetch('/api/v1/health/dashboard');
                    const data = await response.json();
                    updateDashboard(data);
                } catch (error) {
                    console.error('Error fetching dashboard data:', error);
                }
            }

            function updateDashboard(data) {
                // Update system status
                const statusElement = document.getElementById('system-status');
                const status = data.system_health.status;
                const statusClass = status === 'healthy' ? 'status-healthy' :
                                  status === 'warning' ? 'status-warning' : 'status-error';
                statusElement.innerHTML = `<span class="status-indicator ${statusClass}"></span>${status.toUpperCase()}`;

                // Update metrics
                document.getElementById('cpu-usage').textContent = data.system_health.cpu_usage_percent + '%';
                document.getElementById('memory-usage').textContent = data.system_health.memory_usage_percent + '%';
                document.getElementById('total-requests').textContent = data.registry_activity.total_requests;
                document.getElementById('downloads').textContent = data.registry_activity.model_downloads;
                document.getElementById('uploads').textContent = data.registry_activity.model_uploads;
                document.getElementById('errors').textContent = data.registry_activity.error_count;
                document.getElementById('response-time').textContent = Math.round(data.registry_activity.average_response_time_ms) + ' ms';

                // Update logs
                const logsContainer = document.getElementById('logs-container');
                const logs = data.recent_logs || [];
                logsContainer.innerHTML = logs.length > 0 ?
                    logs.map(log => `<div class="log-entry">${log}</div>`).join('') :
                    '<div class="log-entry">No recent logs available</div>';
            }

            function refreshData() {
                fetchDashboardData();
            }

            // Initial load
            fetchDashboardData();

            // Auto-refresh every 30 seconds
            setInterval(fetchDashboardData, 30000);
        </script>
    </body>
    </html>
    """
    return html_content
