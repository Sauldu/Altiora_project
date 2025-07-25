# src/main.py
"""Point d'entrée principal de l'application FastAPI Altiora.

Ce module configure et lance l'API REST d'Altiora, intégrant diverses
fonctionnalités clés telles que :
- La gestion des routes API pour les opérations principales (analyse SFD, tests, rapports).
- L'exposition de métriques Prometheus pour la surveillance.
- Un cache hiérarchique pour optimiser les performances.
- Des pools de modèles pour une gestion efficace des LLMs.
- Un logging structuré pour une meilleure traçabilité.
- Des mécanismes de sécurité (limitation de taille de corps, authentification).
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
from pydantic import BaseModel, Field

from src.cache.intelligent_cache import IntelligentCache
from src.core.container import Container
from src.core.model_pool import ModelPool
from src.monitoring.health import health
from src.monitoring.structured_logger import logger
from src.monitoring.tracer import setup_tracing
from src.orchestrator import Orchestrator
from src.security.input_validator import SFDInput, validate_or_422


# ------------------------------------------------------------------
# Modèles Pydantic pour les données de l'API
# ------------------------------------------------------------------
class Test(BaseModel):
    """Modèle Pydantic pour représenter un résultat de test."""
    id: str = Field(..., description="Identifiant unique du test.")
    name: str = Field(..., description="Nom du test.")
    status: str = Field(..., description="Statut du test (ex: 'passed', 'failed', 'running').")
    created_at: str = Field(..., description="Date et heure de création du test (ISO format).")


class Report(BaseModel):
    """Modèle Pydantic pour représenter un rapport généré."""
    id: str = Field(..., description="Identifiant unique du rapport.")
    title: str = Field(..., description="Titre du rapport.")
    content: str = Field(..., description="Contenu textuel du rapport.")
    created_at: str = Field(..., description="Date et heure de création du rapport (ISO format).")


class User(BaseModel):
    """Modèle Pydantic pour représenter un utilisateur authentifié (simplifié)."""
    id: str = Field(..., description="Identifiant unique de l'utilisateur.")
    roles: List[str] = Field(..., description="Liste des rôles de l'utilisateur.")


# Définition du fuseau horaire UTC pour la cohérence des horodatages.
UTC = zoneinfo.ZoneInfo("UTC")

# Schéma de sécurité HTTP Bearer pour l'authentification.
security = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------
# Middlewares FastAPI
# ------------------------------------------------------------------
@app.middleware("http")
async def max_body_size_middleware(request: Request, call_next):
    """Middleware pour limiter la taille maximale du corps des requêtes HTTP."

    Args:
        request: L'objet `Request` de FastAPI.
        call_next: La fonction pour passer la requête au prochain middleware ou à l'endpoint.

    Raises:
        HTTPException: Si la taille du corps de la requête dépasse la limite (413 Payload Too Large).
    """
    content_length = request.headers.get("content-length")
    if content_length:
        # Limite la taille du corps à 1 Mo (1_000_000 octets).
        if int(content_length) > 1_000_000:
            raise HTTPException(status_code=413, detail="Corps de requête trop volumineux (max 1 Mo).")
    response = await call_next(request)
    return response


# Métriques Prometheus pour le suivi des requêtes.
REQUESTS = Counter(
    "altiora_requests_total",
    "Total des requêtes HTTP",
    ["method", "endpoint", "status_code"],
)
RESPONSE_TIME = Gauge("altiora_response_time_seconds", "Temps de réponse des requêtes HTTP en secondes.")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware pour collecter les métriques de performance des requêtes HTTP."

    Args:
        request: L'objet `Request` de FastAPI.
        call_next: La fonction pour passer la requête au prochain middleware ou à l'endpoint.
    """
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    # Incrémente le compteur de requêtes avec les labels appropriés.
    REQUESTS.labels(request.method, str(request.url.path), response.status_code).inc()
    # Met à jour la jauge du temps de réponse.
    RESPONSE_TIME.set(duration)
    
    return response


# ------------------------------------------------------------------
# Authentification (stub pour la démonstration)
# ------------------------------------------------------------------
async def authenticate_user(credentials=Depends(security)) -> User:
    """Fonction d'authentification factice."

    Dans une application réelle, cette fonction validerait les jetons JWT
    et récupérerait les informations de l'utilisateur depuis une base de données.

    Args:
        credentials: Les informations d'identification extraites de l'en-tête Authorization.

    Returns:
        Un objet `User` factice avec des rôles.
    """
    if credentials and credentials.credentials:
        # Ici, la logique de validation du jeton JWT serait implémentée.
        # Pour la démo, tout jeton non vide est considéré comme valide.
        return User(id="demo_user", roles=["user"])
    return User(id="anonymous", roles=["guest"])


# ------------------------------------------------------------------
# Cache singleton
# ------------------------------------------------------------------
_cache: IntelligentCache | None = None


def get_cache() -> IntelligentCache:
    """Retourne l'instance singleton du cache intelligent."

    Initialise le cache si ce n'est pas déjà fait.

    Returns:
        L'instance de `IntelligentCache`.
    """
    global _cache
    if _cache is None:
        _cache = IntelligentCache(
            redis_url="redis://localhost:6379", # URL Redis pour le cache.
            disk_cache_dir=Path("./cache/l3"), # Répertoire pour le cache disque.
            max_ram_items=1000, # Nombre maximal d'éléments en RAM.
        )
    return _cache


# ------------------------------------------------------------------
# Pools de modèles (singleton)
# ------------------------------------------------------------------
_qwen3_pool: ModelPool | None = None


async def get_qwen3_pool() -> ModelPool:
    """Retourne l'instance singleton du pool de modèles Qwen3."

    Initialise le pool si ce n'est pas déjà fait.

    Returns:
        L'instance de `ModelPool` configurée pour Qwen3.
    """
    global _qwen3_pool
    if _qwen3_pool is None:
        _qwen3_pool = await ModelPool.create_qwen3_pool(
            pool_size=3, # Nombre d'instances Qwen3 dans le pool.
            ollama_url="http://localhost:11434", # URL du serveur Ollama.
        )
    return _qwen3_pool


# ------------------------------------------------------------------
# Application FastAPI et gestion du cycle de vie
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de durée de vie de l'application FastAPI."

    Cette fonction est appelée au démarrage et à l'arrêt de l'application.
    Elle est utilisée pour initialiser et nettoyer les ressources globales.
    """
    logger.info("Démarrage de l'application Altiora...")
    setup_tracing(app=app) # Initialise le traçage OpenTelemetry.
    await startup_event() # Exécute les tâches de démarrage personnalisées.
    yield # L'application est prête à recevoir des requêtes.
    logger.info("Arrêt de l'application Altiora...")
    await shutdown_event() # Exécute les tâches d'arrêt personnalisées.


app = FastAPI(
    title="Altiora API",
    version="1.2.0",
    docs_url=None, # Désactive l'URL par défaut pour utiliser une route personnalisée.
    lifespan=lifespan # Associe le gestionnaire de durée de vie à l'application.
)

# ------------------------------------------------------------------
# Routes de l'API
# ------------------------------------------------------------------
# Route personnalisée pour la documentation Swagger UI.
app.add_route("/docs", get_swagger_ui_html(openapi_url="/openapi.json", title="Altiora API"))


@app.get("/metrics", summary="Expose les métriques Prometheus.")
async def metrics() -> Response:
    """Retourne les métriques de l'application au format Prometheus."

    Ces métriques peuvent être collectées par un serveur Prometheus.
    """
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/health", summary="Vérifie l'état de santé de l'application et de ses dépendances.")
async def health_check() -> Dict[str, Any]:
    """Retourne l'état de santé de l'application."

    Délègue la vérification au module `src.monitoring.health`.
    """
    return await health()


@app.post("/analyze", summary="Analyse une Spécification Fonctionnelle Détaillée (SFD).", status_code=200)
async def analyze(body: Dict[str, Any] = Body(...)):
    """Analyse le contenu d'une SFD et retourne un statut."

    Args:
        body: Le corps de la requête contenant le contenu de la SFD.

    Returns:
        Un dictionnaire indiquant le statut de l'analyse.

    Raises:
        HTTPException: Si le corps de la requête est invalide (422 Unprocessable Entity).
    """
    # Valide le corps de la requête en utilisant le modèle SFDInput.
    payload = validate_or_422(SFDInput, body)
    # TODO: Intégrer l'orchestrateur pour lancer l'analyse réelle de la SFD.
    logger.info(f"Analyse SFD reçue. Longueur du contenu : {len(payload.content)}.")
    return {"status": "analysé", "input_length": len(payload.content)}


@app.post("/tests", response_model=Test, tags=["tests"], summary="Lance l'exécution d'un test.")
@inject
async def run_test(
        user: User = Depends(authenticate_user),
        orchestrator: Orchestrator = Depends(Provide[Container.orchestrator]),
) -> Test:
    """Lance l'exécution d'un test (exemple simplifié).

    Args:
        user: L'utilisateur authentifié (injecté par `authenticate_user`).
        orchestrator: L'instance de l'orchestrateur (injectée par `dependency_injector`).

    Returns:
        Un objet `Test` représentant le résultat du test.

    Raises:
        HTTPException: Si l'utilisateur n'a pas les permissions requises (403 Forbidden).
    """
    # Vérification des rôles (exemple RBAC simplifié).
    if "user" not in user.roles:
        raise HTTPException(status_code=403, detail="Accès interdit. Rôle 'user' requis.")
    
    # Appelle l'orchestrateur pour traiter une SFD factice et simuler un test.
    test_result = await orchestrator.process_sfd_to_tests(
        SFDInput(content="Contenu SFD factice pour le test.")
    )
    return Test(
        id="1",
        name="Test de démonstration",
        status=test_result.get("status", "running"),
        created_at=datetime.now(UTC).isoformat(),
    )


@app.get("/reports", response_model=List[Report], tags=["reports"], summary="Récupère la liste des rapports.")
async def get_reports(
        user: User = Depends(authenticate_user),
        cache: IntelligentCache = Depends(get_cache),
) -> List[Report]:
    """Récupère une liste de rapports, en utilisant le cache intelligent."

    Args:
        user: L'utilisateur authentifié.
        cache: L'instance du cache intelligent.

    Returns:
        Une liste d'objets `Report`.
    """
    key = "reports_list"

    async def _generate_reports_data():
        """Fonction interne pour générer les données des rapports (simulée)."""
        logger.info("Génération des données de rapports (non mis en cache)...")
        await asyncio.sleep(0.5) # Simule un délai de génération.
        return [
            Report(
                id="1",
                title="Rapport d'Analyse SFD Q1",
                content="Résumé des analyses SFD du premier trimestre.",
                created_at=datetime.now(UTC).isoformat(),
            ),
            Report(
                id="2",
                title="Rapport de Tests E2E",
                content="Résultats des campagnes de tests End-to-End.",
                created_at=datetime.now(UTC).isoformat(),
            ),
        ]

    # Tente de récupérer les rapports du cache, sinon les génère et les met en cache.
    reports = await cache.get_or_compute(_generate_reports_data, key, ttl=300) # Cache pendant 5 minutes.
    return reports


@app.post("/warm-cache", summary="Préchauffe le cache avec des clés spécifiques.")
async def warm_cache(
        keys: List[str],
        cache: IntelligentCache = Depends(get_cache),
):
    """Préchauffe le cache en chargeant des éléments spécifiques."

    Args:
        keys: Une liste de clés à précharger dans le cache.
        cache: L'instance du cache intelligent.

    Returns:
        Un dictionnaire indiquant le statut de l'opération.
    """
    await cache.preload_keys(set(keys))
    logger.info(f"Cache préchauffé avec les clés : {keys}")
    return {"status": "ok", "warmed": keys}


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"], summary="Affiche le tableau de bord de monitoring.")
async def dashboard():
    """Affiche une page HTML simple pour le tableau de bord."

    Dans une implémentation complète, cela redirigerait vers une application Dash/Grafana.
    """
    return HTMLResponse(
        "<h1>Tableau de bord Altiora</h1><p>Métriques, statistiques de cache, etc. à venir.</p>"
    )


# ------------------------------------------------------------------
# Gestionnaires de durée de vie (Lifespan handlers)
# ------------------------------------------------------------------
async def startup_event():
    """Fonction exécutée au démarrage de l'application."

    Initialise les pools de modèles et effectue d'autres tâches de démarrage.
    """
    logger.info("Exécution des tâches de démarrage de l'application...")
    # Initialise le pool de modèles Qwen3.
    pool = await get_qwen3_pool()
    # Précharge des modèles spécifiques dans Ollama (si nécessaire).
    # Note: Les noms de modèles doivent correspondre à ceux configurés dans Ollama.
    # await pool.preload_keys({"qwen3:32b", "starcoder2:15b"}) # Exemple de préchargement.
    logger.info("application_startup", extra={"event": "started"})


async def shutdown_event():
    """Fonction exécutée à l'arrêt de l'application."

    Ferme les pools de modèles et effectue d'autres tâches de nettoyage.
    """
    logger.info("Exécution des tâches d'arrêt de l'application...")
    if _qwen3_pool:
        await _qwen3_pool.close()
    # Ferme le client Redis du cache si nécessaire.
    if _cache:
        await _cache.close()
    logger.info("application_shutdown", extra={"event": "stopped"})


# ------------------------------------------------------------------
# Point d'entrée de l'application (pour Uvicorn)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    import logging

    # Configure le logging de base pour la démonstration.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logger.info("Lancement du serveur FastAPI Altiora...")
    uvicorn.run(
        "src.main:app", # Module et objet FastAPI à exécuter.
        host="0.0.0.0",
        port=8000,
        reload=True, # Active le rechargement automatique pour le développement.
        log_level="info",
    )