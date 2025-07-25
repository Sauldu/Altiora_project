# src/batch_processor.py
"""Module pour le traitement par lots de Spécifications Fonctionnelles Détaillées (SFD).

Ce processeur permet de traiter un grand nombre de documents SFD en mode batch,
enchaînant les étapes d'OCR (reconnaissance optique de caractères) et d'analyse
par des modèles de langage (LLM). Il utilise Redis pour la persistance de l'état
des jobs et Prometheus pour l'exposition des métriques.
"""

import asyncio
import json
import gc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Set, Dict, Any, Optional

import aiofiles
import redis.asyncio as redis
import zstandard as zstd
from dependency_injector.wiring import inject, Provide
from prometheus_client import Counter, Gauge

from src.core.container import Container
from src.core.model_pool import ModelPool
from src.models.sfd_models import SFDAnalysisRequest
from services.ocr.ocr_wrapper import OCRRequest, extract_text # Assurez-vous que extract_text est bien importable.

# --- Métriques Prometheus --- #
BATCH_DOCS_TOTAL = Gauge("altiora_batch_docs_total", "Nombre total de documents traités par lot.")
BATCH_SUCCESS_TOTAL = Counter("altiora_batch_success_total", "Nombre de documents traités avec succès par lot.")
BATCH_CHUNK_TIME = Gauge("altiora_batch_chunk_seconds", "Durée de traitement d'un chunk (OCR + LLM) en secondes.")

# --- Configuration des ressources --- #
MAX_WORKERS = 20        # Nombre maximal de workers pour les tâches CPU (ex: OCR).
LLM_CONCURRENCY = 6     # Nombre maximal d'appels LLM concurrents (limité par les ressources GPU/CPU).
CHUNK_SIZE = 16         # Nombre de SFD traitées par chunk (pour le traitement par lots).

# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------
@dataclass
class Job:
    """Représente un job de traitement de SFD dans le batch."""
    path: Path # Chemin du fichier SFD.
    ocr_text: str = "" # Texte extrait par l'OCR.
    status: str = "pending" # Statut du job (pending, ocr_ok, ocr_failed, llm_failed, done).
    error: str = "" # Message d'erreur si le job a échoué.
    result: Optional[Dict[str, Any]] = None # Résultat de l'analyse LLM.


class BatchProcessor:
    """Processeur de SFD par lots, gérant les étapes OCR et LLM."""

    def __init__(self, redis_url: str, qwen3_pool: ModelPool):
        """Initialise le processeur de lots."

        Args:
            redis_url: L'URL de connexion au serveur Redis pour la persistance de l'état.
            qwen3_pool: Un pool de modèles Qwen3 pour l'analyse LLM.
        """
        self.redis = redis.from_url(redis_url, decode_responses=False) # `decode_responses=False` pour stocker des bytes compressés.
        self.qwen3_pool = qwen3_pool
        self.limiter = asyncio.Semaphore(LLM_CONCURRENCY) # Limiteur de concurrence pour les appels LLM.

    # ------------------------------------------------------------------
    # API Publique
    # ------------------------------------------------------------------
    @inject
    async def run(
        self,
        input_dir: Path,
        output_dir: Path,
        resume: bool = False,
    ) -> None:
        """Lance le traitement par lots des SFD."

        Args:
            input_dir: Le répertoire contenant les fichiers SFD à traiter.
            output_dir: Le répertoire où les résultats seront sauvegardés.
            resume: Si True, tente de reprendre un job précédent depuis Redis.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        job_key = f"batch:{input_dir.name}"

        jobs = await self._load_or_create_jobs(job_key, input_dir, resume)
        BATCH_DOCS_TOTAL.set(len(jobs))

        # Exécute le pipeline OCR → LLM.
        await self._pipeline(jobs)
        await self._dump_results(output_dir, jobs)

    # ------------------------------------------------------------------
    # Pipeline OCR puis LLM
    # ------------------------------------------------------------------
    async def _pipeline(self, jobs: List[Job]) -> None:
        """Exécute le pipeline de traitement (OCR puis LLM) pour une liste de jobs."

        Args:
            jobs: La liste des objets `Job` à traiter.
        """
        # 1. Étape OCR (CPU-bound).
        # `asyncio.gather` exécute les tâches en parallèle.
        ocr_tasks = [self._ocr_one(job) for job in jobs if job.status == "pending"]
        await asyncio.gather(*ocr_tasks)

        # 2. Étape LLM (GPU-bound, limitée par le sémaphore).
        llm_tasks = [self._llm_one(job) for job in jobs if job.ocr_text and job.status == "ocr_ok"]
        await asyncio.gather(*llm_tasks)

    async def _ocr_one(self, job: Job) -> None:
        """Effectue l'extraction OCR pour un seul job."

        Args:
            job: L'objet `Job` à traiter.
        """
        try:
            req = OCRRequest(file_path=str(job.path), language="fra", preprocess=True)
            # `asyncio.to_thread` est utilisé pour exécuter la fonction synchrone `extract_text`
            # dans un thread séparé, évitant ainsi de bloquer l'event loop.
            job.ocr_text = await asyncio.to_thread(extract_text, req)
            job.status = "ocr_ok"
        except Exception as e:
            job.status, job.error = "ocr_failed", str(e)
            logger.error(f"Échec de l'OCR pour {job.path.name}: {e}")

    async def _llm_one(self, job: Job) -> None:
        """Effectue l'analyse LLM pour un seul job."

        Args:
            job: L'objet `Job` à traiter.
        """
        async with self.limiter: # Acquis un jeton du sémaphore pour limiter la concurrence.
            try:
                async with self.qwen3_pool.context() as model: # Récupère un modèle du pool.
                    req = SFDAnalysisRequest(content=job.ocr_text)
                    job.result = await model.analyze_sfd(req)
                    job.status = "done"
                    BATCH_SUCCESS_TOTAL.inc() # Incrémente le compteur de succès.
            except Exception as e:
                job.status, job.error = "llm_failed", str(e)
                logger.error(f"Échec de l'analyse LLM pour {job.path.name}: {e}")

    # ------------------------------------------------------------------
    # Persistance Redis
    # ------------------------------------------------------------------
    async def _load_or_create_jobs(
        self, key: str, input_dir: Path, resume: bool
    ) -> List[Job]:
        """Charge les jobs depuis Redis ou les crée à partir des fichiers du répertoire d'entrée."

        Args:
            key: La clé Redis pour stocker l'état du batch.
            input_dir: Le répertoire d'entrée.
            resume: Si True, tente de reprendre un job précédent.

        Returns:
            Une liste d'objets `Job`.
        """
        if resume and await self.redis.exists(key):
            raw = await self.redis.get(key)
            # Décompresse et décode les jobs depuis Redis.
            return [Job(**j) for j in json.loads(zstd.decompress(raw).decode('utf-8'))]

        # Crée de nouveaux jobs à partir des fichiers du répertoire d'entrée.
        files = [p for p in input_dir.iterdir() if p.suffix.lower() in {".pdf", ".txt", ".docx"}]
        jobs = [Job(p) for p in files]
        await self._save_jobs(key, jobs)
        return jobs

    async def _save_jobs(self, key: str, jobs: List[Job]) -> None:
        """Sauvegarde l'état actuel des jobs dans Redis."

        Args:
            key: La clé Redis pour stocker l'état du batch.
            jobs: La liste des objets `Job` à sauvegarder.
        """
        # Compresse et encode les jobs en JSON avant de les stocker dans Redis avec un TTL.
        await self.redis.set(
            key, zstd.compress(json.dumps([asdict(j) for j in jobs], ensure_ascii=False).encode('utf-8')), ex=3600
        )

    async def _dump_results(self, output_dir: Path, jobs: List[Job]) -> None:
        """Sauvegarde les résultats finaux des jobs dans le répertoire de sortie."

        Args:
            output_dir: Le répertoire de sortie.
            jobs: La liste des objets `Job` avec leurs résultats.
        """
        summary = {
            "total": len(jobs),
            "success": sum(1 for j in jobs if j.status == "done"),
            "failed": sum(1 for j in jobs if j.status.endswith("failed")),
        }
        # Sauvegarde le résumé du traitement.
        async with aiofiles.open(output_dir / "summary.json", "w", encoding='utf-8') as f:
            await f.write(json.dumps(summary, indent=2, ensure_ascii=False))
        
        # Sauvegarde les résultats individuels des jobs réussis.
        for job in jobs:
            if job.result:
                async with aiofiles.open(output_dir / f"{job.path.stem}.json", "w", encoding='utf-8') as f:
                    await f.write(json.dumps(job.result, indent=2, ensure_ascii=False))
        gc.collect() # Force le garbage collection pour libérer la mémoire.

# ------------------------------------------------------------------
# Point d'entrée
# ------------------------------------------------------------------
@inject
async def main(
    input_dir: Path,
    output_dir: Path,
    resume: bool = False,
    qwen3_pool: ModelPool = Provide[Container.qwen3_pool], # Injection de dépendance pour le pool Qwen3.
) -> None:
    """Fonction principale pour exécuter le processeur de lots via la CLI."

    Args:
        input_dir: Répertoire d'entrée.
        output_dir: Répertoire de sortie.
        resume: Reprendre le traitement.
        qwen3_pool: Pool de modèles Qwen3 (injecté).
    """
    await BatchProcessor("redis://localhost:6379", qwen3_pool).run(
        input_dir, output_dir, resume
    )


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Batch SFD processing")
    parser.add_argument("--input-dir", type=Path, required=True, help="Répertoire contenant les fichiers SFD à traiter.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Répertoire où sauvegarder les résultats.")
    parser.add_argument("--resume", action="store_true", help="Reprendre le traitement à partir du dernier état sauvegardé.")
    args = parser.parse_args()

    # Configuration du conteneur de dépendances.
    container = Container()
    container.config.from_yaml("configs/master_config.yaml") # Charge la configuration.
    container.wire(modules=[__name__]) # Connecte les dépendances.

    # Crée des répertoires factices pour la démonstration si nécessaire.
    if not args.input_dir.exists():
        args.input_dir.mkdir(parents=True, exist_ok=True)
        (args.input_dir / "sfd_doc_1.pdf").write_text("Contenu du document 1.")
        (args.input_dir / "sfd_doc_2.txt").write_text("Contenu du document 2.")
        logger.info(f"Répertoire d'entrée factice créé : {args.input_dir}")

    asyncio.run(main(**vars(args)))
