# src/main.py
from __future__ import annotations

import json
import time
import zoneinfo
from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer  # 1️⃣  imported correctly
from prometheus_client import Counter, Gauge, generate_latest
from pydantic import BaseModel

from infrastructure.redis_config import get_redis_client
from middleware.cache_middleware import cache_middleware
from middleware.rbac_middleware import verify_permission
from src.core.container import Container


# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------
class Test(BaseModel):
    id: str
    name: str
    status: str
    created_at: str


class Report(BaseModel):
    id: str
    title: str
    content: str
    created_at: str


class User(BaseModel):
    id: str
    roles: List[str]


# ------------------------------------------------------------------
# Globals
# ------------------------------------------------------------------
UTC = zoneinfo.ZoneInfo("UTC")
security = HTTPBearer(auto_error=False)

app = FastAPI(title="Altiora API", version="1.0.0", docs_url=None)
container = Container()

app.add_route("/docs", get_swagger_ui_html(openapi_url="/openapi.json", title="Altiora API"), include_in_schema=False)

# ------------------------------------------------------------------
# Prometheus
# ------------------------------------------------------------------
REQUESTS = Counter(
    "altiora_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
RESPONSE_TIME = Gauge("altiora_response_time_seconds", "Response time")


# ------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    REQUESTS.labels(request.method, str(request.url.path), response.status_code).inc()
    RESPONSE_TIME.set(duration)
    return response


app.middleware("http")(cache_middleware)


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------
async def authenticate_user(
        credentials=Depends(security),
) -> User:
    """Return stub user (replace with real JWT)."""
    if credentials and credentials.credentials:
        return User(id="demo", roles=["user"])
    return User(id="anonymous", roles=["guest"])


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


@app.post("/tests", response_model=Test, tags=["tests"])
@inject
async def run_test(
    user: User = Depends(authenticate_user),
    orchestrator: Orchestrator = Depends(Provide[Container.orchestrator]),
):
    await verify_permission(user, resource="test", action="execute")
    return Test(
        id="1",
        name="Test 1",
        status="running",
        created_at=datetime.now(UTC).isoformat(),
    )


@app.get("/reports", response_model=List[Report], tags=["reports"])
async def get_reports(user: User = Depends(authenticate_user)):  # 3️⃣ default added
    await verify_permission(user, resource="report", action="read")

    redis = await get_redis_client()
    try:
        key = "reports"
        cached = await redis.get(key)
        if cached:
            return [Report(**item) for item in json.loads(decompress_data(cached))]

        reports = [
            Report(
                id="1",
                title="Rapport 1",
                content="Contenu",
                created_at=datetime.now(UTC).isoformat(),
            ),
            Report(
                id="2",
                title="Rapport 2",
                content="Contenu",
                created_at=datetime.now(UTC).isoformat(),
            ),
        ]
        compressed = compress_data(json.dumps([r.model_dump() for r in reports]))
        await redis.set(key, compressed, ex=300)
        return reports
    finally:
        await redis.aclose()


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
async def dashboard():
    return HTMLResponse(
        "<h1>Altiora Dashboard</h1><p>Install <code>plotly</code> for charts.</p>"
    )
