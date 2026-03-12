"""Metrics API endpoints"""

from fastapi import APIRouter, Response
from typing import Dict, Any
from src.utils.metrics import get_metrics_collector

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_class=Response)
async def get_metrics_prometheus():
    """
    Get metrics in Prometheus text format
    
    Returns:
        Metrics in Prometheus exposition format
    """
    collector = get_metrics_collector()
    prometheus_text = collector.to_prometheus_format()
    
    return Response(
        content=prometheus_text,
        media_type="text/plain; version=0.0.4"
    )


@router.get("/dashboard")
async def get_metrics_dashboard() -> Dict[str, Any]:
    """
    Get metrics in JSON format for dashboard
    
    Returns:
        Dictionary containing all metrics with statistics
    """
    collector = get_metrics_collector()
    return collector.get_all_metrics()
