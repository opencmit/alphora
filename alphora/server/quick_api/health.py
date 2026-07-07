import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from importlib.metadata import PackageNotFoundError, version as pkg_version

from alphora.agent.base_agent import BaseAgent
from alphora.server.quick_api.config import APIPublisherConfig
from alphora.server.quick_api.memory_pool import MemoryPool


def build_health_path(path: str) -> str:
    base = path.rstrip("/")
    return f"{base}/health"


def get_framework_version() -> str:
    try:
        return pkg_version("alphora")
    except PackageNotFoundError:
        return "unknown"


def register_health_router(
        agent: BaseAgent,
        method_name: str,
        memory_pool: MemoryPool,
        config: APIPublisherConfig,
        state: Dict[str, Any],
) -> APIRouter:
    router = APIRouter()
    health_path = build_health_path(config.path)

    @router.get(health_path)
    async def health_check():
        now = time.time()
        started_at = state.get("started_at")
        uptime_seconds = int(now - started_at) if started_at else 0

        pool_size = memory_pool.size
        max_items = config.max_memory_items
        usage_ratio = pool_size / max_items if max_items > 0 else 0.0

        status = "ok"
        if usage_ratio >= 0.9:
            status = "degraded"
        if config.sandbox_workspace and not os.path.isdir(config.sandbox_workspace):
            status = "degraded"

        body = {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
            "service": {
                "agent_class": agent.__class__.__name__,
                "method": method_name,
                "version": config.service_version,
            },
            "framework": {
                "name": "alphora",
                "version": get_framework_version(),
            },
            "runtime": {
                "memory_pool": {
                    "size": pool_size,
                    "max_items": max_items,
                    "usage_ratio": round(usage_ratio, 4),
                },
                "file_server_enabled": bool(config.sandbox_workspace),
            },
        }

        http_status = 200 if status in ("ok", "degraded") else 503
        return JSONResponse(content=body, status_code=http_status)

    return router
