# services/ocr/ocr_wrapper.py
"""
OCR Service Wrapper (FastAPI)
Fallback-safe, mock-ready, lifespan-compatible
"""

import asyncio
import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiofiles
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Lifespan manager
# ------------------------------------------------------------------
redis_client: Optional[redis.Redis] = None
processing_queue: Dict[str, Any] = {}
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "/app/uploads")).resolve()
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning("⚠️ Redis unavailable – cache disabled (%s)", e)
        redis_client = None
    yield
    if redis_client:
        await redis_client.close()
    if TEMP_DIR.exists():
        for p in TEMP_DIR.iterdir():
            p.unlink(missing_ok=True)


app = FastAPI(title="Doctoplus OCR Service", version="1.0.0", lifespan=lifespan)

# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------
class OCRRequest(BaseModel):
    file_path: str
    language: str = "fra"
    preprocess: bool = True
    cache: bool = True
    output_format: str = "text"
    confidence_threshold: float = Field(0.8, ge=0.0, le=1.0)


class OCRResponse(BaseModel):
    text: str
    confidence: float
    processing_time: float
    cached: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRBatchRequest(BaseModel):
    files: List[str]
    language: str = "fra"
    parallel: bool = True
    max_workers: int = Field(4, ge=1, le=10)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------
def _doctoplus_available() -> bool:
    try:
        import doctopus_ocr  # type: ignore
        return True
    except ImportError:
        return False


def _cache_key(req: OCRRequest) -> str:
    path = Path(req.file_path)
    data = {
        "name": path.name,
        "size": path.stat().st_size if path.exists() else 0,
        "mtime": path.stat().st_mtime if path.exists() else 0,
        "lang": req.language,
        "pre": req.preprocess,
        "fmt": req.output_format,
        "thr": req.confidence_threshold,
    }
    digest = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return f"ocr:{digest}"


async def _get_cache(key: str) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None
    try:
        cached = await redis_client.get(key)
        return json.loads(cached) if cached else None
    except Exception as e:
        logger.warning("cache read error: %s", e)
        return None


async def _save_cache(key: str, value: Dict[str, Any], ttl: int = 86400) -> None:
    if redis_client:
        try:
            await redis_client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("cache write error: %s", e)


# ------------------------------------------------------------------
# mock extractor
# ------------------------------------------------------------------
async def _extract_mock(req: OCRRequest) -> Dict[str, Any]:
    await asyncio.sleep(0.5)
    text = f"Mock OCR result for {Path(req.file_path).name}"
    return {"text": text, "confidence": 0.95, "metadata": {"mode": "mock"}}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
async def _extract_doctoplus(req: OCRRequest) -> Dict[str, Any]:
    from doctopus_ocr import DoctoplusWrapper  # type: ignore

    wrapper = DoctoplusWrapper(
        config_path=os.getenv("DOCTOPLUS_CONFIG", "/app/config/config.json")
    )
    result = await wrapper.extract_text(
        file_path=req.file_path,
        language=req.language,
        preprocess=req.preprocess,
        confidence_threshold=req.confidence_threshold,
        output_format=req.output_format,
    )
    return {
        "text": result.get("text", ""),
        "confidence": result.get("confidence", 0.0),
        "metadata": {
            "pages": result.get("pages", 0),
            "language": req.language,
            "file_type": Path(req.file_path).suffix,
            "file_size": Path(req.file_path).stat().st_size,
        },
    }


# ------------------------------------------------------------------
# endpoints
# ------------------------------------------------------------------
@app.get("/health")
async def health_check():
    redis_ok = redis_client and await redis_client.ping() or False
    return {
        "status": "healthy",
        "redis": "connected" if redis_ok else "disconnected",
        "doctoplus": "available" if _doctoplus_available() else "mock",
    }


@app.post("/extract", response_model=OCRResponse)
async def extract_text(request: OCRRequest):
    path = Path(request.file_path).resolve()
    if not path.is_relative_to(UPLOAD_ROOT):
        raise HTTPException(403, "Path not allowed")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "File not found")

    start = asyncio.get_event_loop().time()
    cache_key = _cache_key(request) if request.cache and redis_client else None
    cached = await _get_cache(cache_key) if cache_key else None
    if cached:
        return OCRResponse(**cached, cached=True)

    extractor = _extract_doctoplus if _doctoplus_available() else _extract_mock
    result = await extractor(request)

    processing_time = asyncio.get_event_loop().time() - start
    result["processing_time"] = processing_time

    if cache_key:
        await _save_cache(cache_key, result)
    return OCRResponse(**result)


@app.post("/extract_upload")
async def extract_upload(
    file: UploadFile = File(...),
    language: str = "fra",
    preprocess: bool = True,
    cache: bool = True,
):
    temp_path = TEMP_DIR / f"{datetime.now().timestamp()}_{file.filename}"
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(await file.read())
        request = OCRRequest(
            file_path=str(temp_path),
            language=language,
            preprocess=preprocess,
            cache=cache,
        )
        return await extract_text(request)
    except (IOError, OSError) as e:
        logger.error(f"Error writing uploaded file to {temp_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    finally:
        temp_path.unlink(missing_ok=True)


# ------------------------------------------------------------------
# uvicorn entry
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("ocr_wrapper:app", host="0.0.0.0", port=8001, reload=False)