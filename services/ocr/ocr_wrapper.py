# services/ocr/ocr_wrapper.py
"""Service web pour l'extraction de texte via OCR (Optical Character Recognition).

Ce service fournit une API pour extraire du texte à partir de fichiers image et PDF.
Il intègre des fonctionnalités de mise en cache (via Redis) et de gestion des
fichiers temporaires. Il peut utiliser une implémentation OCR réelle (Doctopus) ou une maquette.
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
# Gestion du cycle de vie (Lifespan manager)
# ------------------------------------------------------------------

# Clients globaux pour Redis et la gestion des tâches.
redis_client: Optional[redis.Redis] = None
processing_queue: Dict[str, Any] = {} # Utilisé pour suivre les tâches en cours (non implémenté ici)

# Répertoires pour les fichiers téléchargés et temporaires.
UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "/app/uploads")).resolve()
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True) # S'assure que le répertoire temporaire existe.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gère le cycle de vie de l'application (démarrage et arrêt).

    Tente de se connecter à Redis au démarrage et ferme la connexion à l'arrêt.
    Nettoie également les fichiers temporaires.
    """
    global redis_client
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping() # Teste la connexion.
        logger.info("✅ Connexion Redis établie.")
    except Exception as e:
        logger.warning("⚠️ Redis non disponible – cache désactivé (%s)", e)
        redis_client = None # Désactive le cache si Redis n'est pas accessible.
    yield # L'application démarre ici.
    if redis_client:
        await redis_client.close() # Ferme la connexion Redis à l'arrêt.
    
    # Nettoie les fichiers temporaires à l'arrêt.
    if TEMP_DIR.exists():
        for p in TEMP_DIR.iterdir():
            p.unlink(missing_ok=True) # Supprime les fichiers, ignore s'ils n'existent plus.


app = FastAPI(title="Service OCR Doctoplus", version="1.0.0", lifespan=lifespan)

# ------------------------------------------------------------------
# Schémas Pydantic
# ------------------------------------------------------------------
class OCRRequest(BaseModel):
    """Modèle de requête pour l'extraction OCR."""
    file_path: str = Field(..., description="Chemin absolu du fichier à traiter.")
    language: str = Field("fra", description="Langue du document (code ISO 639-2/T, ex: 'fra', 'eng').")
    preprocess: bool = Field(True, description="Appliquer des étapes de pré-traitement de l'image.")
    cache: bool = Field(True, description="Utiliser le cache Redis pour les résultats.")
    output_format: str = Field("text", description="Format de sortie (ex: 'text', 'hocr').")
    confidence_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Seuil de confiance pour l'extraction.")


class OCRResponse(BaseModel):
    """Modèle de réponse pour l'extraction OCR."""
    text: str = Field(..., description="Texte extrait du document.")
    confidence: float = Field(..., description="Niveau de confiance global de l'extraction.")
    processing_time: float = Field(..., description="Temps de traitement en secondes.")
    cached: bool = Field(False, description="Indique si le résultat provient du cache.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées supplémentaires sur le traitement.")


class OCRBatchRequest(BaseModel):
    """Modèle de requête pour le traitement OCR par lots (non implémenté)."""
    files: List[str] = Field(..., description="Liste des chemins de fichiers à traiter.")
    language: str = Field("fra", description="Langue pour le traitement par lots.")
    parallel: bool = Field(True, description="Exécuter les traitements en parallèle.")
    max_workers: int = Field(4, ge=1, le=10, description="Nombre maximal de workers parallèles.")


# ------------------------------------------------------------------
# Fonctions utilitaires
# ------------------------------------------------------------------
def _doctoplus_available() -> bool:
    """Vérifie si la bibliothèque Doctopus OCR est disponible."""
    try:
        import doctopus_ocr  # type: ignore
        return True
    except ImportError:
        return False


def _cache_key(req: OCRRequest) -> str:
    """Génère une clé de cache unique basée sur les paramètres de la requête et les métadonnées du fichier."""
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
    # Utilise un hachage MD5 du JSON sérialisé pour garantir une clé unique et stable.
    digest = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return f"ocr:{digest}"


async def _get_cache(key: str) -> Optional[Dict[str, Any]]:
    """Récupère un résultat depuis le cache Redis."""
    if not redis_client:
        return None
    try:
        cached = await redis_client.get(key)
        return json.loads(cached) if cached else None
    except Exception as e:
        logger.warning("Erreur de lecture du cache Redis : %s", e)
        return None


async def _save_cache(key: str, value: Dict[str, Any], ttl: int = 86400) -> None:
    """Sauvegarde un résultat dans le cache Redis avec une durée de vie (TTL)."""
    if redis_client:
        try:
            await redis_client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("Erreur d'écriture dans le cache Redis : %s", e)


# ------------------------------------------------------------------
# Extracteurs OCR (réel et maquette)
# ------------------------------------------------------------------
async def _extract_mock(req: OCRRequest) -> Dict[str, Any]:
    """Implémentation de maquette pour l'extraction OCR (pour le développement/test)."""
    await asyncio.sleep(0.5) # Simule un délai de traitement.
    text = f"Résultat OCR simulé pour {Path(req.file_path).name}"
    return {"text": text, "confidence": 0.95, "metadata": {"mode": "mock"}}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
async def _extract_doctoplus(req: OCRRequest) -> Dict[str, Any]:
    """Extrait le texte en utilisant la bibliothèque Doctopus OCR (implémentation réelle)."""
    from doctopus_ocr import DoctopusWrapper  # type: ignore

    wrapper = DoctopusWrapper(
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
# Points de terminaison (Endpoints)
# ------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Point de terminaison pour la vérification de l'état de santé du service OCR."""
    redis_ok = redis_client and await redis_client.ping() or False
    return {
        "status": "healthy",
        "redis": "connecté" if redis_ok else "déconnecté",
        "doctoplus": "disponible" if _doctoplus_available() else "maquette",
    }


@app.post("/extract", response_model=OCRResponse)
async def extract_text(request: OCRRequest):
    """Extrait le texte d'un fichier spécifié par son chemin.

    Args:
        request: L'objet `OCRRequest` contenant les détails de l'extraction.

    Returns:
        Un `OCRResponse` avec le texte extrait et les métadonnées.

    Raises:
        HTTPException: Si le chemin du fichier n'est pas autorisé ou si le fichier n'est pas trouvé.
    """
    path = Path(request.file_path).resolve()
    # Mesure de sécurité: s'assurer que le chemin est dans le répertoire autorisé.
    if not path.is_relative_to(UPLOAD_ROOT):
        raise HTTPException(403, "Accès au chemin non autorisé.")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Fichier non trouvé.")

    start = asyncio.get_event_loop().time()
    cache_key = _cache_key(request) if request.cache and redis_client else None
    cached = await _get_cache(cache_key) if cache_key else None
    if cached:
        return OCRResponse(**cached, cached=True)

    # Choisit l'extracteur (réel ou maquette) en fonction de la disponibilité de Doctopus.
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
    """Extrait le texte d'un fichier téléchargé directement via l'API.

    Le fichier est d'abord sauvegardé temporairement, puis traité par l'OCR.
    Le fichier temporaire est supprimé après le traitement.

    Args:
        file: Le fichier téléchargé.
        language: Langue du document.
        preprocess: Appliquer le pré-traitement.
        cache: Utiliser le cache.

    Returns:
        Un `OCRResponse` avec le texte extrait.

    Raises:
        HTTPException: Si une erreur survient lors de la sauvegarde ou du traitement du fichier.
    """
    # Crée un chemin temporaire unique pour le fichier téléchargé.
    temp_path = TEMP_DIR / f"{datetime.now().timestamp()}_{file.filename}"
    try:
        # Écrit le contenu du fichier téléchargé dans le fichier temporaire.
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(await file.read())
        
        # Crée une requête OCR à partir du fichier temporaire et la traite.
        request = OCRRequest(
            file_path=str(temp_path),
            language=language,
            preprocess=preprocess,
            cache=cache,
        )
        return await extract_text(request)
    except (IOError, OSError) as e:
        logger.error(f"Erreur lors de l'écriture du fichier téléchargé sur {temp_path}: {e}")
        raise HTTPException(status_code=500, detail="Échec de la sauvegarde du fichier téléchargé.")
    finally:
        # S'assure que le fichier temporaire est supprimé, même en cas d'erreur.
        temp_path.unlink(missing_ok=True)


# ------------------------------------------------------------------
# Point d'entrée Uvicorn
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("ocr_wrapper:app", host="0.0.0.0", port=8001, reload=False)
