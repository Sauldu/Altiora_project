# src/batch_processor.py
import asyncio
import json
import gc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Set

import aiofiles
import redis.asyncio as redis
import zstandard as zstd
from dependency_injector.wiring import inject, Provide
from prometheus_client import Counter, Gauge

from src.core.container import Container
from src.core.model_pool import ModelPool
from src.models.sfd_models import SFDAnalysisRequest
from services.ocr.ocr_wrapper import OCRRequest, extract_text

# Métriques
BATCH_DOCS_TOTAL = Gauge("altiora_batch_docs_total", "Nombre de documents")
BATCH_SUCCESS_TOTAL = Counter("altiora_batch_success_total", "Succès")
BATCH_CHUNK_TIME = Gauge("altiora_batch_chunk_seconds", "Durée chunk OCR+LLM")

MAX_WORKERS = 20        # CPU OCR
LLM_CONCURRENCY = 6     # Slots GPU/VRAM
CHUNK_SIZE = 16         # SFD par chunk

# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------
@dataclass
class Job:
    path: Path
    ocr_text: str = ""
    status: str = "pending"
    error: str = ""
    result: dict | None = None


class BatchProcessor:
    def __init__(self, redis_url: str, qwen3_pool: ModelPool):
        self.redis = redis.from_url(redis_url, decode_responses=False)
        self.qwen3_pool = qwen3_pool
        self.limiter = asyncio.Semaphore(LLM_CONCURRENCY)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    @inject
    async def run(
        self,
        input_dir: Path,
        output_dir: Path,
        resume: bool = False,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        job_key = f"batch:{input_dir.name}"

        jobs = await self._load_or_create_jobs(job_key, input_dir, resume)
        BATCH_DOCS_TOTAL.set(len(jobs))

        # Pipeline OCR → LLM
        await self._pipeline(jobs)
        await self._dump_results(output_dir, jobs)

    # --------------------------------------------------
    # Pipeline OCR puis LLM
    # --------------------------------------------------
    async def _pipeline(self, jobs: List[Job]) -> None:
        # 1. OCR (CPU-bound)
        ocr_tasks = [self._ocr_one(job) for job in jobs if job.status == "pending"]
        await asyncio.gather(*ocr_tasks)

        # 2. LLM (GPU-bound, limité)
        llm_tasks = [self._llm_one(job) for job in jobs if job.ocr_text]
        await asyncio.gather(*llm_tasks)

    async def _ocr_one(self, job: Job) -> None:
        try:
            req = OCRRequest(file_path=str(job.path), language="fra", preprocess=True)
            job.ocr_text = await asyncio.to_thread(extract_text, req)
            job.status = "ocr_ok"
        except Exception as e:
            job.status, job.error = "ocr_failed", str(e)

    async def _llm_one(self, job: Job) -> None:
        async with self.limiter:
            try:
                async with self.qwen3_pool.context() as model:
                    req = SFDAnalysisRequest(content=job.ocr_text)
                    job.result = await model.analyze_sfd(req)
                    job.status = "done"
                    BATCH_SUCCESS_TOTAL.inc()
            except Exception as e:
                job.status, job.error = "llm_failed", str(e)

    # --------------------------------------------------
    # Persistence Redis
    # --------------------------------------------------
    async def _load_or_create_jobs(
        self, key: str, input_dir: Path, resume: bool
    ) -> List[Job]:
        if resume and await self.redis.exists(key):
            raw = await self.redis.get(key)
            return [Job(**j) for j in json.loads(zstd.decompress(raw).decode())]

        files = [p for p in input_dir.iterdir() if p.suffix.lower() in {".pdf", ".txt", ".docx"}]
        jobs = [Job(p) for p in files]
        await self._save_jobs(key, jobs)
        return jobs

    async def _save_jobs(self, key: str, jobs: List[Job]) -> None:
        await self.redis.set(
            key, zstd.compress(json.dumps([asdict(j) for j in jobs]).encode()), ex=3600
        )

    async def _dump_results(self, output_dir: Path, jobs: List[Job]) -> None:
        summary = {
            "total": len(jobs),
            "success": sum(1 for j in jobs if j.status == "done"),
            "failed": sum(1 for j in jobs if j.status.endswith("failed")),
        }
        async with aiofiles.open(output_dir / "summary.json", "w") as f:
            await f.write(json.dumps(summary, indent=2))
        for job in jobs:
            if job.result:
                async with aiofiles.open(output_dir / f"{job.path.stem}.json", "w") as f:
                    await f.write(json.dumps(job.result, indent=2))
        gc.collect()

# ------------------------------------------------------------------
# Entry-point
# ------------------------------------------------------------------
@inject
async def main(
    input_dir: Path,
    output_dir: Path,
    resume: bool = False,
    qwen3_pool: ModelPool = Provide[Container.qwen3_pool],
) -> None:
    await BatchProcessor("redis://localhost:6379", qwen3_pool).run(
        input_dir, output_dir, resume
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch SFD processing")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    from dependency_injector.wiring import inject, Provide
    from src.core.container import Container

    container = Container()
    container.wire(modules=[__name__])
    asyncio.run(main(**vars(args)))