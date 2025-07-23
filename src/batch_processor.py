# src/batch_processor.py
import asyncio
import gc
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path

import redis.asyncio as redis
import zstandard as zstd
from prometheus_client import Counter, Gauge
from tqdm.asyncio import tqdm

from orchestrator import Orchestrator
from services.ocr.ocr_wrapper import OCRRequest
from services.ocr.ocr_wrapper import extract_text

# Métriques Prometheus
BATCH_DOCS_TOTAL = Gauge("altiora_batch_docs_total", "Nombre de documents")
BATCH_SUCCESS_TOTAL = Counter("altiora_batch_success_total", "Succès")

CHUNK_SIZE = 50
MAX_WORKERS = 20
REDIS_TTL = 24 * 3600


@dataclass
class Job:
    path: Path
    status: str = "pending"
    error: str = ""
    result: dict = None


class BatchProcessor:
    def __init__(self, redis_url: str, llm_semaphore: asyncio.Semaphore):
        self.redis = redis.from_url(redis_url, decode_responses=False)
        self.executor = ProcessPoolExecutor(max_workers=MAX_WORKERS)
        self.sem_llm = llm_semaphore

    async def run(self, input_dir: Path, output_dir: Path, resume: bool):
        output_dir.mkdir(parents=True, exist_ok=True)
        job_key = f"batch:{input_dir.name}"

        # Scan ou reprise
        if resume and await self.redis.exists(job_key):
            jobs = await self._load_jobs(job_key)
        else:
            jobs = [Job(p) for p in input_dir.iterdir() if p.suffix.lower() in {".pdf", ".txt", ".docx"}]
            await self._save_jobs(job_key, jobs)
            BATCH_DOCS_TOTAL.set(len(jobs))

        todo = [j for j in jobs if j.status == "pending"]
        async with tqdm(total=len(todo), desc="Batch") as pbar:
            coros = [self._process_one(job, pbar) for job in todo]
            await asyncio.gather(*coros, return_exceptions=True)

        await self._dump_results(output_dir, jobs)
        self.executor.shutdown(wait=True)

    # --------------------------------------------------
    # I/O-bound OCR + LLM-bound génération
    # --------------------------------------------------
    async def _process_one(self, job: Job, pbar: tqdm):
        try:
            job.status = "running"
            await self._save_jobs(job_key_suffix(job), await self._load_jobs(job_key_suffix(job)))

            # OCR (CPU-bound)
            ocr_req = OCRRequest(file_path=str(job.path), language="fra", preprocess=True)
            await asyncio.get_running_loop().run_in_executor(
                self.executor, extract_text, ocr_req
            )

            # Génération (I/O-bound + LLM)
            async with self.sem_llm:
                orch = Orchestrator()
                await orch.initialize()
                job.result = await orch.process_sfd_to_tests(
                    str(job.path),

                )
                await orch.close()
                job.status = "done"
                BATCH_SUCCESS_TOTAL.inc()
        except Exception as e:
            job.status, job.error = "failed", str(e)
        finally:
            await self._save_jobs(job_key_suffix(job), await self._load_jobs(job_key_suffix(job)))
            pbar.update(1)
            gc.collect()

    # --------------------------------------------------
    # Utils
    # --------------------------------------------------
    async def _load_jobs(self, key):
        raw = await self.redis.get(key)
        return [Job(**j) for j in json.loads(zstd.decompress(raw).decode())]

    async def _save_jobs(self, key, jobs):
        data = zstd.compress(json.dumps([asdict(j) for j in jobs]).encode())
        await self.redis.set(key, data, ex=REDIS_TTL)

    @staticmethod
    async def _dump_results(output_dir: Path, jobs):
        summary = {"total": len(jobs), "success": sum(1 for j in jobs if j.status == "done")}
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        for job in jobs:
            if job.result:
                (output_dir / f"{job.path.stem}.json").write_text(json.dumps(job.result, indent=2))


def job_key_suffix(job: Job) -> str:
    return f"batch:{job.path.parent.name}"


# --------------------------------------------------
# Point d’entrée
# --------------------------------------------------
if __name__ == "__main__":
    import argparse, asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    llm_sem = asyncio.Semaphore(12)
    asyncio.run(BatchProcessor("redis://localhost:6379", llm_sem).run(
        args.input_dir, args.output_dir, args.resume
    ))
