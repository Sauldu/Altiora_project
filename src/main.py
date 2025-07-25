# src/main.py
"""
Point d'entrée FastAPI d'Altiora
- Routes REST
- Métriques Prometheus
- Cache hiérarchique
- Pools de modèles
- Logging structuré
"""

from __future__ import annotations

import time
import zoneinfo
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, FastAPI, HTTPException, Request, Body
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBearer
from prometheus_client import Counter, Gauge, generate_latest
from pydantic import BaseModel

from src.cache.intelligent_cache import IntelligentCache
from src.core.container import Container
from src.core.model_pool import ModelPool
from src.monitoring.health import health
from src.monitoring.structured_logger import logger
from src.monitoring.tracer import setup_tracing
from src.orchestrator import Orchestrator
from src.security.input_validator import SFDInput, validate_or_422


# ------------------------------------------------------------------
# Modèles Pydantic
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


UTC = zoneinfo.ZoneInfo("UTC")
security = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------
# Middleware de limitation de taille de corps
# ------------------------------------------------------------------
@app.middleware("http")
async def max_body_size_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        if int(content_length) > 1_000_000:
            raise HTTPException(status_code=413, detail="Corps de requête trop volumineux")
    response = await call_next(request)
    return response


# ------------------------------------------------------------------
# Middleware de métriques
# ------------------------------------------------------------------
REQUESTS = Counter(
    "altiora_requests_total",
    "Total des requêtes HTTP",
    ["method", "endpoint", "status_code"],
)
RESPONSE_TIME = Gauge("altiora_response_time_seconds", "Temps de réponse")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    REQUESTS.labels(request.method, str(request.url.path), response.status_code).inc()
    RESPONSE_TIME.set(duration)
    return response


# ------------------------------------------------------------------
# Authentification (stub)
# ------------------------------------------------------------------
async def authenticate_user(credentials=Depends(security)) -> User:
    if credentials and credentials.credentials:
        return User(id="demo", roles=["user"])
    return User(id="anonymous", roles=["guest"])


# ------------------------------------------------------------------
# Cache singleton
# ------------------------------------------------------------------
_cache: IntelligentCache | None = None


def get_cache() -> IntelligentCache:
    global _cache
    if _cache is None:
        _cache = IntelligentCache(
            redis_url="redis://localhost:6379",
            disk_cache_dir=Path("./cache/l3"),
            max_ram_items=1000,
        )
    return _cache


# ------------------------------------------------------------------
# Pools de modèles
# ------------------------------------------------------------------
_qwen3_pool: ModelPool | None = None


async def get_qwen3_pool() -> ModelPool:
    global _qwen3_pool
    if _qwen3_pool is None:
        _qwen3_pool = await ModelPool.create_qwen3_pool(
            pool_size=3,
            ollama_url="http://localhost:11434",
        )
    return _qwen3_pool


# ------------------------------------------------------------------
# Application FastAPI
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing(app=app)
    await startup_event()
    yield
    await shutdown_event()


app = FastAPI(
    title="Altiora API",
    version="1.2.0",
    docs_url=None,
    lifespan=lifespan
)

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
app.add_route("/docs", get_swagger_ui_html(openapi_url="/openapi.json", title="Altiora API"))


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/health")
async def health_check():
    return await health()


@app.post("/analyze")
async def analyze(body: Dict[str, Any] = Body(...)):
    payload = validate_or_422(SFDInput, body)
    return {"status": "analysé", "input_length": len(payload.content)}


@app.post("/tests", response_model=Test, tags=["tests"])
@inject
async def run_test(
        user: User = Depends(authenticate_user),
        orchestrator: Orchestrator = Depends(Provide[Container.orchestrator]),
):
    if "user" not in user.roles:
        raise HTTPException(status_code=403, detail="Accès interdit")
    test_result = await orchestrator.process_sfd_to_tests(
        SFDInput(content="dummy")
    )
    return Test(
        id="1",
        name="Test 1",
        status=test_result.get("status", "running"),
        created_at=datetime.now(UTC).isoformat(),
    )


@app.get("/reports", response_model=List[Report], tags=["reports"])
async def get_reports(
        user: User = Depends(authenticate_user),
        cache: IntelligentCache = Depends(get_cache),
):
    key = "reports"

    async def _generate():
        return [
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

    reports = await cache.get_or_compute(key, _generate, ttl=300)
    return reports


@app.post("/warm-cache")
async def warm_cache(
        keys: List[str],
        cache: IntelligentCache = Depends(get_cache),
):
    await cache.preload_keys(set(keys))
    return {"status": "ok", "warmed": keys}


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
async def dashboard():
    return HTMLResponse(
        "<h1>Tableau de bord Altiora</h1><p>Métriques, statistiques de cache, etc. à venir.</p>"
    )


# ------------------------------------------------------------------
# Gestionnaires de durée de vie
# ------------------------------------------------------------------
async def startup_event():
    pool = await get_qwen3_pool()
    await pool.preload_keys({"qwen3:32b", "starcoder2:15b"})
    logger.info("application_startup", extra={"event": "started"})


async def shutdown_event():
    if _qwen3_pool:
        await _qwen3_pool.close()
    logger.info("application_shutdown", extra={"event": "stopped"})
