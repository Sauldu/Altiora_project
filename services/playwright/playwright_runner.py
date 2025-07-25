# services/playwright/playwright_runner.py
"""Service d'exécution de tests Playwright.

Ce service permet d'exécuter des scripts de test Playwright de manière asynchrone,
avec des options de configuration avancées (navigateur, headless, timeout, retries).
Il gère la préparation des environnements de test, l'exécution parallèle,
la collecte des artefacts (screenshots, vidéos, traces) et la génération de rapports.
"""

import os
import asyncio
import json
import tempfile
import shutil
import subprocess
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from concurrent.futures import ProcessPoolExecutor
import traceback

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
import redis.asyncio as redis
from playwright.async_api import async_playwright
import pytest
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Modèles Pydantic --- #
class TestCode(BaseModel):
    """Représente un bloc de code de test à exécuter."""
    code: str = Field(..., description="Code Python/Playwright du test.")
    test_name: str = Field(default="test_generated", description="Nom unique du test.")
    test_type: str = Field(default="e2e", description="Type de test (ex: 'e2e', 'component').")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées supplémentaires associées au test.")


class ExecutionConfig(BaseModel):
    """Configuration des paramètres d'exécution des tests Playwright."""
    browser: str = Field(default="chromium", description="Navigateur à utiliser : 'chromium', 'firefox', 'webkit'.")
    headed: bool = Field(default=False, description="Exécuter le navigateur en mode visible (True) ou headless (False).")
    timeout: int = Field(default=30000, description="Timeout maximal par test en millisecondes.")
    retries: int = Field(default=0, description="Nombre de tentatives en cas d'échec du test.")
    parallel: bool = Field(default=True, description="Exécuter les tests en parallèle (True) ou séquentiellement (False).")
    workers: int = Field(default=4, description="Nombre de workers parallèles à utiliser si `parallel` est True.")
    screenshot: str = Field(default="on-failure", description="Quand prendre des captures d'écran : 'always', 'on-failure', 'never'.")
    video: str = Field(default="on-failure", description="Quand enregistrer des vidéos : 'always', 'on-failure', 'never'.")
    trace: str = Field(default="on-failure", description="Quand enregistrer des traces : 'always', 'on-failure', 'never'.")
    base_url: Optional[str] = Field(default=None, description="URL de base pour les tests (utilisé par `page.goto('/')`).")


class TestExecutionRequest(BaseModel):
    """Requête complète pour lancer une exécution de tests."""
    tests: List[TestCode] = Field(..., description="Liste des tests à exécuter.")
    config: ExecutionConfig = Field(default_factory=ExecutionConfig, description="Configuration d'exécution des tests.")
    save_artifacts: bool = Field(default=True, description="Sauvegarder les artefacts (screenshots, vidéos, traces).")
    generate_report: bool = Field(default=True, description="Générer un rapport HTML récapitulatif.")


class TestResult(BaseModel):
    """Résultat détaillé d'un test individuel."""
    test_name: str = Field(..., description="Nom du test.")
    status: str = Field(..., description="Statut de l'exécution du test : 'passed', 'failed', 'skipped', 'error'.")
    duration: float = Field(..., description="Durée d'exécution du test en secondes.")
    error_message: Optional[str] = Field(None, description="Message d'erreur si le test a échoué ou a rencontré une erreur.")
    error_trace: Optional[str] = Field(None, description="Trace de la pile d'appels en cas d'erreur.")
    screenshot: Optional[str] = Field(None, description="Chemin relatif vers la capture d'écran (si disponible).")
    video: Optional[str] = Field(None, description="Chemin relatif vers la vidéo (si disponible).")
    trace: Optional[str] = Field(None, description="Chemin relatif vers le fichier de trace (si disponible).")
    logs: List[str] = Field(default_factory=list, description="Logs de la console du test.")


class ExecutionResponse(BaseModel):
    """Réponse complète après l'exécution d'une suite de tests."""
    execution_id: str = Field(..., description="ID unique de cette exécution de tests.")
    status: str = Field(..., description="Statut global de l'exécution : 'completed', 'error', etc.")
    total_tests: int = Field(..., description="Nombre total de tests exécutés.")
    passed: int = Field(..., description="Nombre de tests réussis.")
    failed: int = Field(..., description="Nombre de tests échoués.")
    skipped: int = Field(..., description="Nombre de tests ignorés.")
    duration: float = Field(..., description="Durée totale de l'exécution en secondes.")
    results: List[TestResult] = Field(..., description="Liste détaillée des résultats de chaque test.")
    report_path: Optional[str] = Field(None, description="Chemin relatif vers le rapport HTML généré.")
    artifacts_path: Optional[str] = Field(None, description="Chemin relatif vers l'archive ZIP des artefacts.")


# --- Application FastAPI --- #
app = FastAPI(
    title="Playwright Runner Service",
    description="Service d'exécution de tests Playwright à la demande.",
    version="1.0.0"
)

# --- État global du service --- #
redis_client: Optional[redis.Redis] = None
execution_queue: Dict[str, Any] = {} # Pour suivre les exécutions asynchrones.
executor = ProcessPoolExecutor(max_workers=4) # Pool de processus pour les tâches bloquantes.


# ------------------------------------------------------------------
# Événements de cycle de vie (Lifespan events)
# ------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Initialisation du service au démarrage de l'application."""
    global redis_client
    
    # Tente de se connecter à Redis pour la mise en cache des résultats.
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Connexion Redis établie.")
    except Exception as e:
        logger.warning(f"⚠️ Redis non disponible – cache désactivé : {e}")
        redis_client = None
    
    # Crée les répertoires nécessaires pour les workspaces et les artefacts.
    for dir_path in ["workspace", "reports", "screenshots", "videos", "traces", "artifacts"]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # S'assure que les navigateurs Playwright sont installés.
    await ensure_playwright_browsers()


@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage du service à l'arrêt de l'application."""
    if redis_client:
        await redis_client.close()
    
    # Arrête le pool de processus.
    executor.shutdown(wait=True)


# ------------------------------------------------------------------
# Points de terminaison de santé
# ------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Point de terminaison pour vérifier l'état de santé du service."""
    redis_ok = False
    if redis_client:
        try:
            await redis_client.ping()
            redis_ok = True
        except redis.exceptions.ConnectionError:
            redis_ok = False
    
    # Vérifie si Playwright est opérationnel.
    playwright_ok = await check_playwright_health()
    
    return {
        "status": "healthy",
        "service": "playwright-runner",
        "timestamp": datetime.now().isoformat(),
        "redis": "connecté" if redis_ok else "déconnecté",
        "playwright": "prêt" if playwright_ok else "non_prêt",
        "active_executions": len(execution_queue)
    }


# ------------------------------------------------------------------
# Points de terminaison d'exécution principaux
# ------------------------------------------------------------------

@app.post("/execute", response_model=ExecutionResponse)
async def execute_tests(request: TestExecutionRequest) -> ExecutionResponse:
    """Exécute une suite de tests Playwright de manière synchrone (bloquant l'appel API)."""
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    start_time = asyncio.get_event_loop().time()
    
    # Crée un répertoire de travail temporaire pour cette exécution.
    workspace_dir = Path("workspace") / execution_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Prépare les fichiers de test à partir du code fourni.
        test_files = await prepare_test_files(request.tests, workspace_dir)
        
        # Génère les arguments pytest basés sur la configuration d'exécution.
        pytest_config_args = generate_pytest_config(request.config, workspace_dir)
        
        # Exécute les tests en parallèle ou séquentiellement.
        if request.config.parallel and len(test_files) > 1:
            results = await run_tests_parallel(
                test_files,
                pytest_config_args,
                request.config,
                workspace_dir
            )
        else:
            results = await run_tests_sequential(
                test_files,
                pytest_config_args,
                request.config,
                workspace_dir
            )
        
        # Calcule les statistiques globales de l'exécution.
        total_duration = asyncio.get_event_loop().time() - start_time
        stats = calculate_stats(results)
        
        # Génère le rapport HTML si demandé.
        report_path = None
        if request.generate_report:
            report_path = await generate_html_report(
                execution_id,
                results,
                stats,
                workspace_dir
            )
        
        # Collecte et archive les artefacts si demandé.
        artifacts_path = None
        if request.save_artifacts:
            artifacts_path = await collect_artifacts(execution_id, workspace_dir)
        
        response = ExecutionResponse(
            execution_id=execution_id,
            status="completed",
            total_tests=len(results),
            passed=stats["passed"],
            failed=stats["failed"],
            skipped=stats["skipped"],
            duration=total_duration,
            results=results,
            report_path=report_path,
            artifacts_path=artifacts_path
        )
        
        # Sauvegarde le résultat complet de l'exécution dans Redis.
        if redis_client:
            await save_execution_result(execution_id, response)
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution des tests : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne du service : {str(e)}")
    
    finally:
        # Planifie le nettoyage du répertoire de travail après un délai.
        asyncio.create_task(cleanup_workspace(workspace_dir, delay=300))


@app.post("/execute_async")
async def execute_tests_async(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks
):
    """Lance l'exécution des tests en arrière-plan et retourne immédiatement un ID d'exécution."""
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    
    # Enregistre l'exécution dans la queue avec un statut initial.
    execution_queue[execution_id] = {
        "status": "queued",
        "started_at": datetime.now().isoformat(),
        "config": request.config.model_dump() # Utilise model_dump pour Pydantic v2
    }
    
    # Lance la fonction d'exécution en arrière-plan.
    background_tasks.add_task(
        run_tests_background,
        execution_id,
        request
    )
    
    return JSONResponse(
        {
            "execution_id": execution_id,
            "status": "queued",
            "message": "Tests en cours d'exécution en arrière-plan.",
            "check_status_url": f"/status/{execution_id}"
        },
        status_code=202 # Accepted
    )


@app.get("/status/{execution_id}", response_model=Union[ExecutionResponse, Dict[str, str]])
async def get_execution_status(execution_id: str):
    """Récupère le statut et les résultats d'une exécution de tests par son ID."""
    # Vérifie d'abord dans la queue des exécutions en cours.
    if execution_id in execution_queue:
        return execution_queue[execution_id]
    
    # Sinon, vérifie dans le cache Redis.
    if redis_client:
        result = await get_execution_result(execution_id)
        if result:
            return result
    
    raise HTTPException(status_code=404, detail="Exécution non trouvée.")


@app.get("/report/{execution_id}", response_class=FileResponse)
async def get_report(execution_id: str):
    """Récupère le rapport HTML généré pour une exécution donnée."""
    report_path = Path("reports") / f"{execution_id}_report.html"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Rapport non trouvé.")
    
    return FileResponse(
        report_path,
        media_type="text/html",
        filename=f"report_{execution_id}.html"
    )


@app.get("/artifacts/{execution_id}", response_class=FileResponse)
async def get_artifacts(execution_id: str):
    """Télécharge une archive ZIP contenant tous les artefacts (screenshots, vidéos, traces) d'une exécution."""
    artifacts_path = Path("artifacts") / f"{execution_id}.zip"
    
    if not artifacts_path.exists():
        raise HTTPException(status_code=404, detail="Artefacts non trouvés.")
    
    return FileResponse(
        artifacts_path,
        media_type="application/zip",
        filename=f"artifacts_{execution_id}.zip"
    )


# ------------------------------------------------------------------
# Fonctions d'exécution principales
# ------------------------------------------------------------------

async def prepare_test_files(tests: List[TestCode], workspace_dir: Path) -> List[Path]:
    """Prépare les fichiers de test Python dans le répertoire de travail temporaire."""
    test_files = []
    
    for i, test in enumerate(tests):
        test_name = test.test_name or f"test_{i}"
        file_name = f"{test_name}.py"
        file_path = workspace_dir / file_name
        
        # S'assure que le code de test contient les imports et décorateurs nécessaires.
        code = ensure_test_imports(test.code)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            test_files.append(file_path)
            logger.info(f"Fichier de test préparé : {file_path}")
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors de l'écriture du fichier de test {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Échec de l'écriture du fichier de test : {file_path}")
    
    # Crée le fichier `conftest.py` nécessaire pour la configuration de pytest-playwright.
    await create_conftest(workspace_dir)
    
    return test_files


def ensure_test_imports(code: str) -> str:
    """Ajoute les imports et décorateurs pytest-playwright nécessaires au code de test."""
    required_imports = [
        "import pytest",
        "from playwright.async_api import Page, expect",
    ]
    
    # Ajoute les imports manquants au début du code.
    for imp in required_imports:
        if imp not in code:
            code = f"{imp}\n{code}"
    
    # Ajoute le décorateur `@pytest.mark.asyncio` si la fonction de test est asynchrone.
    if "@pytest.mark.asyncio" not in code and "async def test_" in code:
        code = code.replace("async def test_", "@pytest.mark.asyncio\nasync def test_")
    
    return code


async def create_conftest(workspace_dir: Path):
    """Crée le fichier `conftest.py` avec la configuration de base pour pytest-playwright."""
    conftest_content = '''"""
Configuration Playwright pour les tests
"""
import pytest
from playwright.async_api import async_playwright
import os

@pytest.fixture(scope="session")
async def browser_type_launch_args():
    """Arguments de lancement du navigateur."""
    return {
        "headless": not bool(os.getenv("HEADED", "false").lower() == "true"),
        "timeout": 30000,
    }

@pytest.fixture(scope="session")
async def browser_context_args(browser_type_launch_args):
    """Arguments du contexte navigateur."""
    base_url = os.getenv("BASE_URL")
    context_args = {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }
    if base_url:
        context_args["base_url"] = base_url
    return context_args

@pytest.fixture(scope="function")
async def page(browser, browser_context_args):
    """Fixture de page avec configuration."""
    context = await browser.new_context(**browser_context_args)
    page = await context.new_page()
    yield page
    await context.close()
'''
    
    conftest_path = workspace_dir / "conftest.py"
    try:
        with open(conftest_path, 'w', encoding='utf-8') as f:
            f.write(conftest_content)
    except (IOError, OSError) as e:
        logger.error(f"Erreur lors de l'écriture de conftest.py sur {conftest_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Échec de l'écriture de conftest.py : {conftest_path}")


def generate_pytest_config(config: ExecutionConfig, workspace_dir: Path) -> List[str]:
    """Génère la liste des arguments de ligne de commande pour pytest en fonction de la configuration."""
    args = [
        str(workspace_dir), # Indique à pytest où trouver les tests.
        "-v", # Mode verbeux.
        "--tb=short", # Traceback courte pour une meilleure lisibilité.
        f"--maxfail={config.retries + 1}", # Arrête après N échecs (retries + 1).
        "--json-report", # Active le rapport JSON.
        f"--json-report-file={workspace_dir}/report.json", # Chemin du rapport JSON.
    ]
    
    # Ajoute les arguments spécifiques au navigateur.
    args.extend([
        f"--browser={config.browser}",
        "--browser-channel=chromium" if config.browser == "chromium" else "", # Spécifique à Chromium
    ])
    
    if config.headed:
        args.append("--headed") # Lance le navigateur en mode visible.
    
    # Options de capture d'écran.
    if config.screenshot == "always":
        args.append("--screenshot=on")
    elif config.screenshot == "on-failure":
        args.append("--screenshot=only-on-failure")
    
    # Options d'enregistrement vidéo.
    if config.video == "always":
        args.append("--video=on")
    elif config.video == "on-failure":
        args.append("--video=retain-on-failure")
    
    # Options de trace Playwright.
    if config.trace == "always":
        args.append("--tracing=on")
    elif config.trace == "on-failure":
        args.append("--tracing=retain-on-failure")
    
    # Parallélisation avec pytest-xdist.
    if config.parallel and config.workers > 1:
        args.extend(["-n", str(config.workers)])
    
    # Timeout global pour l'exécution des tests.
    args.append(f"--timeout={config.timeout // 1000}") # Convertit ms en secondes.
    
    return [arg for arg in args if arg] # Filtre les arguments vides.


async def run_tests_sequential(
    test_files: List[Path],
    pytest_args: List[str],
    config: ExecutionConfig,
    workspace_dir: Path
) -> List[TestResult]:
    """Exécute les tests séquentiellement, un fichier à la fois."""
    results = []
    
    for test_file in test_files:
        result = await run_single_test(
            test_file,
            pytest_args,
            config,
            workspace_dir
        )
        results.append(result)
    
    return results


async def run_tests_parallel(
    test_files: List[Path],
    pytest_args: List[str],
    config: ExecutionConfig,
    workspace_dir: Path
) -> List[TestResult]:
    """Exécute les tests en parallèle en utilisant pytest-xdist."""
    # pytest-xdist est utilisé via les arguments passés à pytest.
    cmd = [sys.executable, "-m", "pytest"] + pytest_args
    
    # Configure les variables d'environnement pour le sous-processus pytest.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace_dir) # Ajoute le workspace au PYTHONPATH.
    if config.base_url:
        env["BASE_URL"] = config.base_url
    if config.headed:
        env["HEADED"] = "true"
    
    logger.info(f"Lancement de pytest en parallèle : {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(workspace_dir) # Exécute pytest dans le répertoire de travail.
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"Pytest a échoué (code {process.returncode}):\n{stderr.decode()}")

    # Parse le rapport JSON généré par pytest.
    report_path = workspace_dir / "report.json"
    if report_path.exists():
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            return parse_pytest_report(report, workspace_dir)
        except (IOError, OSError, json.JSONDecodeError) as e:
            logger.error(f"Erreur lors de la lecture ou du parsing du rapport pytest {report_path}: {e}")
            return [TestResult(
                test_name="suite_complete",
                status="error",
                duration=0,
                error_message=f"Échec de la lecture/parsing du rapport : {e}",
                error_trace=stderr.decode() if stderr else None
            )]
    else:
        logger.error(f"Le rapport JSON n'a pas été généré à {report_path}. Stdout: {stdout.decode()}, Stderr: {stderr.decode()}")
        return [TestResult(
            test_name="suite_complete",
            status="error",
            duration=0,
            error_message="Rapport JSON non trouvé.",
            error_trace=stderr.decode() if stderr else None
        )]


async def run_single_test(
    test_file: Path,
    base_pytest_args: List[str],
    config: ExecutionConfig,
    workspace_dir: Path
) -> TestResult:
    """Exécute un seul fichier de test Playwright via pytest."""
    # Construit les arguments pytest spécifiques à ce fichier.
    pytest_args = [str(test_file)] + [arg for arg in base_pytest_args if arg not in [str(workspace_dir), '-n', str(config.workers)]]
    
    cmd = [sys.executable, "-m", "pytest"] + pytest_args
    
    # Configure les variables d'environnement.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace_dir)
    if config.base_url:
        env["BASE_URL"] = config.base_url
    
    start_time = asyncio.get_event_loop().time()
    
    logger.info(f"Lancement du test : {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(workspace_dir)
    )
    
    stdout, stderr = await process.communicate()
    duration = asyncio.get_event_loop().time() - start_time
    
    # Détermine le statut du test basé sur le code de retour.
    if process.returncode == 0:
        status = "passed"
    elif process.returncode == 1: # pytest retourne 1 pour les échecs de test.
        status = "failed"
    else:
        status = "error"
    
    # Collecte les artefacts générés par ce test.
    artifacts = collect_test_artifacts(test_file.stem, workspace_dir)
    
    return TestResult(
        test_name=test_file.stem,
        status=status,
        duration=duration,
        error_message=stderr.decode() if status != "passed" and stderr else None,
        logs=stdout.decode().split('\n') if stdout else [],
        **artifacts
    )


def parse_pytest_report(report: Dict, workspace_dir: Path) -> List[TestResult]:
    """Parse le rapport JSON généré par pytest et le convertit en liste de `TestResult`."""
    results = []
    
    for test_data in report.get("tests", []):
        test_name = test_data.get("nodeid", "unknown").split("::")[-1]
        outcome = test_data.get("outcome", "unknown")
        
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "skipped": "skipped",
            "error": "error"
        }
        status = status_map.get(outcome, "error")
        
        error_message = None
        error_trace = None
        if status == "failed" or status == "error":
            # Tente d'extraire le message d'erreur et la trace.
            if "call" in test_data and "longrepr" in test_data["call"]:
                error_message = str(test_data["call"]["longrepr"])
            elif "setup" in test_data and "longrepr" in test_data["setup"]:
                error_message = str(test_data["setup"]["longrepr"])
            # Une trace complète peut être extraite si nécessaire.
            # error_trace = test_data.get("longrepr", {}).get("reprcrash", {}).get("message")
        
        duration = test_data.get("duration", 0)
        
        artifacts = collect_test_artifacts(test_name, workspace_dir)
        
        results.append(TestResult(
            test_name=test_name,
            status=status,
            duration=duration,
            error_message=error_message,
            error_trace=error_trace,
            **artifacts
        ))
    
    return results


def collect_test_artifacts(test_name: str, workspace_dir: Path) -> Dict[str, Optional[str]]:
    """Collecte les chemins relatifs des artefacts (screenshots, vidéos, traces) pour un test donné."""
    artifacts = {
        "screenshot": None,
        "video": None,
        "trace": None
    }
    
    # Patterns de recherche pour les artefacts générés par Playwright/pytest.
    # Note: Les chemins peuvent varier légèrement en fonction de la configuration de pytest-playwright.
    patterns = {
        "screenshot": [f"**/{test_name}*.png"],
        "video": [f"**/{test_name}*.webm"],
        "trace": [f"**/{test_name}*.zip"]
    }
    
    for artifact_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            # Recherche les fichiers correspondants dans le répertoire de travail.
            files = list(workspace_dir.glob(pattern))
            if files:
                # Prend le premier fichier trouvé et stocke son chemin relatif.
                artifacts[artifact_type] = str(files[0].relative_to(workspace_dir))
                break
    
    return artifacts


def calculate_stats(results: List[TestResult]) -> Dict[str, int]:
    """Calcule les statistiques récapitulatives d'une liste de résultats de tests."""
    stats = {
        "passed": sum(1 for r in results if r.status == "passed"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
        "error": sum(1 for r in results if r.status == "error")
    }
    return stats


# ------------------------------------------------------------------
# Tâches de fond
# ------------------------------------------------------------------

async def run_tests_background(execution_id: str, request: TestExecutionRequest):
    """Fonction exécutée en arrière-plan pour lancer les tests et mettre à jour leur statut."""
    try:
        # Met à jour le statut de l'exécution dans la queue.
        execution_queue[execution_id]["status"] = "running"
        
        # Exécute les tests en appelant la fonction principale synchrone.
        response = await execute_tests(request)
        
        # Met à jour la queue avec les résultats complets.
        execution_queue[execution_id] = response.model_dump() # Utilise model_dump pour Pydantic v2
        execution_queue[execution_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        # Gère les erreurs survenues pendant l'exécution en arrière-plan.
        logger.error(f"Erreur lors de l'exécution en arrière-plan pour {execution_id}: {e}", exc_info=True)
        execution_queue[execution_id].update({
            "status": "error",
            "error": str(e),
            "error_trace": traceback.format_exc(),
            "completed_at": datetime.now().isoformat()
        })


async def cleanup_workspace(workspace_dir: Path, delay: int = 300):
    """Nettoie le répertoire de travail temporaire après un délai spécifié."""
    await asyncio.sleep(delay)
    
    try:
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
            logger.info(f"Répertoire de travail nettoyé : {workspace_dir}")
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage du répertoire de travail {workspace_dir}: {e}")


# ------------------------------------------------------------------
# Génération de rapports
# ------------------------------------------------------------------

async def generate_html_report(
    execution_id: str,
    results: List[TestResult],
    stats: Dict[str, int],
    workspace_dir: Path
) -> str:
    """Génère un rapport HTML récapitulatif des résultats de l'exécution des tests."""
    report_path = Path("reports") / f"{execution_id}_report.html"
    
    # Template HTML pour le rapport.
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Rapport de Test - {execution_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ padding: 10px 20px; border-radius: 5px; color: white; }}
        .passed {{ background: #4CAF50; }} /* Vert */
        .failed {{ background: #f44336; }} /* Rouge */
        .skipped {{ background: #ff9800; }} /* Orange */
        .error {{ background: #9c27b0; }} /* Violet */
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f2f2f2; }}
        .status-passed {{ color: #4CAF50; font-weight: bold; }}
        .status-failed {{ color: #f44336; font-weight: bold; }}
        .status-skipped {{ color: #ff9800; font-weight: bold; }}
        .status-error {{ color: #9c27b0; font-weight: bold; }}
        .error-details {{ background: #ffebee; color: #c62828; padding: 10px; margin: 5px 0; border-radius: 3px; font-family: monospace; white-space: pre-wrap; word-break: break-all; }}
        .artifact-link {{ margin-left: 10px; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Rapport d'Exécution des Tests Playwright</h1>
        <p>ID d'Exécution : <strong>{execution_id}</strong></p>
        <p>Généré le : {timestamp}</p>
        <p>Durée totale : {total_duration:.2f} secondes</p>
    </div>
    
    <div class="stats">
        <div class="stat passed">Réussis : {passed}</div>
        <div class="stat failed">Échoués : {failed}</div>
        <div class="stat skipped">Ignorés : {skipped}</div>
        <div class="stat error">Erreurs : {error}</div>
    </div>
    
    <h2>Résultats Détaillés des Tests</h2>
    <table>
        <thead>
            <tr>
                <th>Nom du Test</th>
                <th>Statut</th>
                <th>Durée</th>
                <th>Détails / Artefacts</th>
            </tr>
        </thead>
        <tbody>
            {test_rows}
        </tbody>
    </table>
</body>
</html>
"""
    
    # Génère les lignes du tableau pour chaque résultat de test.
    test_rows = []
    for result in results:
        error_section = ""
        if result.error_message:
            error_section = f'<div class="error-details"><pre>{result.error_message}</pre></div>'
        
        artifact_links = []
        if result.screenshot:
            artifact_links.append(f'<a href="../artifacts/{execution_id}/{result.screenshot}" target="_blank" class="artifact-link">Screenshot</a>')
        if result.video:
            artifact_links.append(f'<a href="../artifacts/{execution_id}/{result.video}" target="_blank" class="artifact-link">Vidéo</a>')
        if result.trace:
            artifact_links.append(f'<a href="../artifacts/{execution_id}/{result.trace}" target="_blank" class="artifact-link">Trace</a>')
        
        test_rows.append(f"""
        <tr>
            <td>{result.test_name}</td>
            <td class="status-{result.status}">{result.status.upper()}</td>
            <td>{result.duration:.2f}s</td>
            <td>
                {error_section}
                {' '.join(artifact_links)}
            </td>
        </tr>
        """
        )
    
    # Remplit le template HTML avec les données et les lignes de test.
    html_content = html_template.format(
        execution_id=execution_id,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_duration=sum(r.duration for r in results),
        passed=stats["passed"],
        failed=stats["failed"],
        skipped=stats["skipped"],
        error=stats.get("error", 0),
        test_rows="\n".join(test_rows)
    )
    
    # Écrit le rapport HTML dans le fichier.
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except (IOError, OSError) as e:
        logger.error(f"Erreur lors de l'écriture du rapport HTML sur {report_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Échec de l'écriture du rapport HTML : {report_path}")
    
    return str(report_path)


async def collect_artifacts(execution_id: str, workspace_dir: Path) -> str:
    """Collecte tous les artefacts générés (screenshots, vidéos, traces) et les archive dans un fichier ZIP."""
    import zipfile
    
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True) # S'assure que le répertoire des artefacts existe.
    
    zip_path = artifacts_dir / f"{execution_id}.zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Ajoute tous les fichiers pertinents du workspace à l'archive ZIP.
            for pattern in ["**/*.png", "**/*.webm", "**/*.zip", "**/*.json", "**/trace.zip"]:
                for file_path in workspace_dir.glob(pattern):
                    if file_path.is_file():
                        # Ajoute le fichier à l'archive en conservant sa structure de répertoire relative.
                        arcname = file_path.relative_to(workspace_dir)
                        zipf.write(file_path, arcname)
    except (IOError, OSError) as e:
        logger.error(f"Erreur lors de la création de l'archive ZIP des artefacts {zip_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Échec de la création de l'archive des artefacts : {zip_path}")
    
    return str(zip_path)


# ------------------------------------------------------------------
# Fonctions utilitaires
# ------------------------------------------------------------------

async def ensure_playwright_browsers():
    """S'assure que les navigateurs Playwright nécessaires sont installés."""
    logger.info("Vérification de l'installation des navigateurs Playwright...")
    try:
        # Tente de lancer chaque navigateur pour vérifier son installation.
        async with async_playwright() as p:
            for browser_name in ["chromium", "firefox", "webkit"]:
                try:
                    browser = await getattr(p, browser_name).launch(headless=True)
                    await browser.close()
                    logger.info(f"  ✅ Navigateur {browser_name} est disponible.")
                except Exception:
                    logger.warning(f"  ⚠️ Navigateur {browser_name} non disponible. Tentative d'installation...")
                    # Tente d'installer le navigateur manquant.
                    try:
                        subprocess.run(["playwright", "install", browser_name], check=True)
                        logger.info(f"  ✅ Navigateur {browser_name} installé avec succès.")
                    except Exception as install_e:
                        logger.error(f"  ❌ Impossible d'installer le navigateur {browser_name}: {install_e}")
    except Exception as e:
        logger.error(f"Erreur lors de la vérification/installation des navigateurs Playwright: {e}")


async def check_playwright_health() -> bool:
    """Vérifie si l'environnement Playwright est opérationnel en lançant un navigateur simple."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
            return True
    except Exception as e:
        logger.error(f"Playwright n'est pas opérationnel : {e}")
        return False


async def save_execution_result(execution_id: str, result: ExecutionResponse):
    """Sauvegarde le résultat complet d'une exécution de tests dans Redis."""
    if not redis_client:
        logger.warning("Redis n'est pas connecté, le résultat de l'exécution ne sera pas mis en cache.")
        return
    
    try:
        key = f"execution:{execution_id}"
        # Convertit l'objet Pydantic en dictionnaire, puis en JSON.
        await redis_client.setex(
            key,
            86400,  # Durée de vie du cache : 24 heures.
            json.dumps(result.model_dump(), default=str) # Utilise model_dump pour Pydantic v2
        )
        logger.info(f"Résultat de l'exécution {execution_id} sauvegardé dans Redis.")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du résultat dans Redis pour {execution_id}: {e}")


async def get_execution_result(execution_id: str) -> Optional[Dict]:
    """Récupère un résultat d'exécution depuis Redis par son ID."""
    if not redis_client:
        return None
    
    try:
        key = f"execution:{execution_id}"
        data = await redis_client.get(key)
        if data:
            logger.info(f"Résultat de l'exécution {execution_id} récupéré depuis Redis.")
            return json.loads(data)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du résultat depuis Redis pour {execution_id}: {e}")
    
    return None


# ------------------------------------------------------------------
# Points de terminaison additionnels
# ------------------------------------------------------------------

@app.delete("/cleanup")
async def cleanup_old_executions(days: int = 7):
    """Nettoie les anciens répertoires de travail, rapports et artefacts.

    Args:
        days: Nombre de jours après lesquels les fichiers sont considérés comme anciens et supprimés.

    Returns:
        Un dictionnaire récapitulatif des éléments nettoyés.
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    cleaned = {
        "workspaces": 0,
        "reports": 0,
        "artifacts": 0
    }
    
    logger.info(f"Démarrage du nettoyage des fichiers de plus de {days} jours...")

    # Nettoie les workspaces.
    for workspace in Path("workspace").iterdir():
        if workspace.is_dir() and workspace.stat().st_mtime < cutoff_date.timestamp():
            try:
                shutil.rmtree(workspace)
                cleaned["workspaces"] += 1
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du workspace {workspace}: {e}")
    
    # Nettoie les rapports HTML.
    for report in Path("reports").glob("*.html"):
        if report.stat().st_mtime < cutoff_date.timestamp():
            try:
                report.unlink()
                cleaned["reports"] += 1
            except Exception as e:
                logger.error(f"Erreur lors de la suppression du rapport {report}: {e}")
    
    # Nettoie les archives d'artefacts.
    for artifact in Path("artifacts").glob("*.zip"):
        if artifact.stat().st_mtime < cutoff_date.timestamp():
            try:
                artifact.unlink()
                cleaned["artifacts"] += 1
            except Exception as e:
                logger.error(f"Erreur lors de la suppression de l'artefact {artifact}: {e}")
    
    logger.info(f"Nettoyage terminé. Résumé : {cleaned}")
    return {
        "status": "success",
        "cleaned": cleaned,
        "message": f"Nettoyage des fichiers de plus de {days} jours effectué."
    }


@app.get("/stats")
async def get_stats():
    """Retourne des statistiques sur l'utilisation actuelle du service."""
    stats = {
        "service": "playwright-runner",
        "timestamp": datetime.now().isoformat(),
        "active_executions": len(execution_queue), # Nombre d'exécutions en cours.
        "workspace_count": len(list(Path("workspace").iterdir())),
        "report_count": len(list(Path("reports").glob("*.html"))),
        "artifact_count": len(list(Path("artifacts").glob("*.zip")))
    }
    
    # Ajoute des statistiques sur le cache Redis si disponible.
    if redis_client:
        try:
            exec_count = 0
            async for _ in redis_client.scan_iter("execution:*"):
                exec_count += 1
            stats["cached_executions"] = exec_count
        except redis.exceptions.ConnectionError:
            stats["cached_executions"] = "erreur de connexion Redis"
    
    return stats


# --- Point d'entrée Uvicorn --- #
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "playwright_runner:app", # Nom du module:objet FastAPI
        host="0.0.0.0",
        port=8004,
        log_level="info",
        reload=True # Utile pour le développement
    )
