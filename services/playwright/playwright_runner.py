"""
Playwright Runner Service
Service d'exécution de tests Playwright avec gestion parallèle et reporting
"""

import os
import asyncio
import json
import tempfile
import shutil
import subprocess
import uuid
from pathlib import Path
from datetime import datetime
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modèles Pydantic
class TestCode(BaseModel):
    """Code de test à exécuter"""
    code: str = Field(..., description="Code Python/Playwright du test")
    test_name: str = Field(default="test_generated", description="Nom du test")
    test_type: str = Field(default="e2e", description="Type de test")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionConfig(BaseModel):
    """Configuration d'exécution des tests"""
    browser: str = Field(default="chromium", description="Navigateur: chromium, firefox, webkit")
    headed: bool = Field(default=False, description="Mode headed (avec interface)")
    timeout: int = Field(default=30000, description="Timeout par test en ms")
    retries: int = Field(default=2, description="Nombre de tentatives")
    parallel: bool = Field(default=True, description="Exécution parallèle")
    workers: int = Field(default=4, description="Nombre de workers parallèles")
    screenshot: str = Field(default="on-failure", description="Screenshots: always, on-failure, never")
    video: str = Field(default="on-failure", description="Videos: always, on-failure, never")
    trace: str = Field(default="on-failure", description="Traces: always, on-failure, never")
    base_url: Optional[str] = Field(default=None, description="URL de base pour les tests")


class TestExecutionRequest(BaseModel):
    """Requête d'exécution de tests"""
    tests: List[TestCode] = Field(..., description="Liste des tests à exécuter")
    config: ExecutionConfig = Field(default_factory=ExecutionConfig)
    save_artifacts: bool = Field(default=True, description="Sauvegarder screenshots/videos")
    generate_report: bool = Field(default=True, description="Générer un rapport HTML")


class TestResult(BaseModel):
    """Résultat d'un test"""
    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    error_message: Optional[str] = None
    error_trace: Optional[str] = None
    screenshot: Optional[str] = None
    video: Optional[str] = None
    trace: Optional[str] = None
    logs: List[str] = Field(default_factory=list)


class ExecutionResponse(BaseModel):
    """Réponse d'exécution des tests"""
    execution_id: str
    status: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration: float
    results: List[TestResult]
    report_path: Optional[str] = None
    artifacts_path: Optional[str] = None


# Application FastAPI
app = FastAPI(
    title="Playwright Runner Service",
    description="Service d'exécution de tests Playwright",
    version="1.0.0"
)

# État global
redis_client: Optional[redis.Redis] = None
execution_queue: Dict[str, Any] = {}
executor = ProcessPoolExecutor(max_workers=4)


# ------------------------------------------------------------------
# Lifecycle events
# ------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage"""
    global redis_client
    
    # Connexion Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Redis connecté")
    except Exception as e:
        logger.warning(f"⚠️ Redis non disponible: {e}")
        redis_client = None
    
    # Créer les répertoires nécessaires
    for dir_path in ["workspace", "reports", "screenshots", "videos", "traces"]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Installer les navigateurs Playwright si nécessaire
    await ensure_playwright_browsers()


@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt"""
    if redis_client:
        await redis_client.close()
    
    executor.shutdown(wait=True)


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Endpoint de santé du service"""
    redis_ok = False
    if redis_client:
        try:
            await redis_client.ping()
            redis_ok = True
        except:
            pass
    
    # Vérifier Playwright
    playwright_ok = await check_playwright_health()
    
    return {
        "status": "healthy",
        "service": "playwright-runner",
        "timestamp": datetime.now().isoformat(),
        "redis": "connected" if redis_ok else "disconnected",
        "playwright": "ready" if playwright_ok else "not_ready",
        "active_executions": len(execution_queue)
    }


# ------------------------------------------------------------------
# Main execution endpoints
# ------------------------------------------------------------------

@app.post("/execute", response_model=ExecutionResponse)
async def execute_tests(request: TestExecutionRequest):
    """
    Exécute une suite de tests Playwright
    """
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    start_time = asyncio.get_event_loop().time()
    
    # Créer un workspace pour cette exécution
    workspace_dir = Path("workspace") / execution_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Préparer les fichiers de test
        test_files = await prepare_test_files(request.tests, workspace_dir)
        
        # Configuration pytest
        pytest_config = generate_pytest_config(request.config, workspace_dir)
        
        # Exécuter les tests
        if request.config.parallel and len(test_files) > 1:
            results = await run_tests_parallel(
                test_files, 
                pytest_config, 
                request.config,
                workspace_dir
            )
        else:
            results = await run_tests_sequential(
                test_files, 
                pytest_config, 
                request.config,
                workspace_dir
            )
        
        # Calculer les statistiques
        total_duration = asyncio.get_event_loop().time() - start_time
        stats = calculate_stats(results)
        
        # Générer le rapport si demandé
        report_path = None
        if request.generate_report:
            report_path = await generate_html_report(
                execution_id,
                results,
                stats,
                workspace_dir
            )
        
        # Gérer les artifacts
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
        
        # Sauvegarder en cache si Redis disponible
        if redis_client:
            await save_execution_result(execution_id, response)
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur exécution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur exécution: {str(e)}")
    
    finally:
        # Nettoyer le workspace après un délai
        asyncio.create_task(cleanup_workspace(workspace_dir, delay=300))


@app.post("/execute_async")
async def execute_tests_async(
    request: TestExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    Lance l'exécution des tests en arrière-plan
    """
    execution_id = f"exec_{uuid.uuid4().hex[:8]}"
    
    # Enregistrer dans la queue
    execution_queue[execution_id] = {
        "status": "queued",
        "started_at": datetime.now().isoformat(),
        "config": request.config.dict()
    }
    
    # Lancer en arrière-plan
    background_tasks.add_task(
        run_tests_background,
        execution_id,
        request
    )
    
    return {
        "execution_id": execution_id,
        "status": "queued",
        "message": "Tests en cours d'exécution",
        "check_status_url": f"/status/{execution_id}"
    }


@app.get("/status/{execution_id}")
async def get_execution_status(execution_id: str):
    """
    Récupère le statut d'une exécution
    """
    # Vérifier dans la queue
    if execution_id in execution_queue:
        return execution_queue[execution_id]
    
    # Vérifier dans Redis
    if redis_client:
        result = await get_execution_result(execution_id)
        if result:
            return result
    
    raise HTTPException(status_code=404, detail="Exécution non trouvée")


@app.get("/report/{execution_id}")
async def get_report(execution_id: str):
    """
    Récupère le rapport HTML d'une exécution
    """
    report_path = Path("reports") / f"{execution_id}_report.html"
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Rapport non trouvé")
    
    return FileResponse(
        report_path,
        media_type="text/html",
        filename=f"report_{execution_id}.html"
    )


@app.get("/artifacts/{execution_id}")
async def get_artifacts(execution_id: str):
    """
    Télécharge les artifacts d'une exécution (ZIP)
    """
    artifacts_path = Path("artifacts") / f"{execution_id}.zip"
    
    if not artifacts_path.exists():
        raise HTTPException(status_code=404, detail="Artifacts non trouvés")
    
    return FileResponse(
        artifacts_path,
        media_type="application/zip",
        filename=f"artifacts_{execution_id}.zip"
    )


# ------------------------------------------------------------------
# Core execution functions
# ------------------------------------------------------------------

async def prepare_test_files(tests: List[TestCode], workspace_dir: Path) -> List[Path]:
    """
    Prépare les fichiers de test dans le workspace
    """
    test_files = []
    
    for i, test in enumerate(tests):
        # Générer un nom de fichier unique
        test_name = test.test_name or f"test_{i}"
        file_name = f"{test_name}.py"
        file_path = workspace_dir / file_name
        
        # Ajouter les imports nécessaires si manquants
        code = ensure_test_imports(test.code)
        
        # Écrire le fichier
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        test_files.append(file_path)
        logger.info(f"Test préparé: {file_path}")
    
    # Créer conftest.py pour la configuration Playwright
    await create_conftest(workspace_dir)
    
    return test_files


def ensure_test_imports(code: str) -> str:
    """
    S'assure que le code a les imports nécessaires
    """
    required_imports = [
        "import pytest",
        "from playwright.async_api import Page, expect",
    ]
    
    # Vérifier et ajouter les imports manquants
    for imp in required_imports:
        if imp not in code:
            code = f"{imp}\n{code}"
    
    # S'assurer que les tests async ont le décorateur
    if "@pytest.mark.asyncio" not in code and "async def test_" in code:
        code = code.replace("async def test_", "@pytest.mark.asyncio\nasync def test_")
    
    return code


async def create_conftest(workspace_dir: Path):
    """
    Crée un conftest.py avec la configuration Playwright
    """
    conftest_content = '''"""
Configuration Playwright pour les tests
"""
import pytest
from playwright.async_api import async_playwright
import os

@pytest.fixture(scope="session")
async def browser_type_launch_args():
    """Arguments de lancement du navigateur"""
    return {
        "headless": not bool(os.getenv("HEADED", "false").lower() == "true"),
        "timeout": 30000,
    }

@pytest.fixture(scope="session")
async def browser_context_args(browser_type_launch_args):
    """Arguments du contexte navigateur"""
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
    """Fixture de page avec configuration"""
    context = await browser.new_context(**browser_context_args)
    page = await context.new_page()
    yield page
    await context.close()
'''
    
    conftest_path = workspace_dir / "conftest.py"
    with open(conftest_path, 'w', encoding='utf-8') as f:
        f.write(conftest_content)


def generate_pytest_config(config: ExecutionConfig, workspace_dir: Path) -> List[str]:
    """
    Génère les arguments pytest selon la configuration
    """
    args = [
        str(workspace_dir),
        "-v",
        "--tb=short",
        f"--maxfail={config.retries}",
        "--json-report",
        f"--json-report-file={workspace_dir}/report.json",
    ]
    
    # Configuration du navigateur
    args.extend([
        f"--browser={config.browser}",
        "--browser-channel=chromium" if config.browser == "chromium" else "",
    ])
    
    if config.headed:
        args.append("--headed")
    
    # Screenshots et vidéos
    if config.screenshot == "always":
        args.append("--screenshot=on")
    elif config.screenshot == "on-failure":
        args.append("--screenshot=only-on-failure")
    
    if config.video == "always":
        args.append("--video=on")
    elif config.video == "on-failure":
        args.append("--video=retain-on-failure")
    
    if config.trace == "always":
        args.append("--tracing=on")
    elif config.trace == "on-failure":
        args.append("--tracing=retain-on-failure")
    
    # Parallélisation
    if config.parallel and config.workers > 1:
        args.extend(["-n", str(config.workers)])
    
    # Timeout
    args.append(f"--timeout={config.timeout // 1000}")
    
    return args


async def run_tests_sequential(
    test_files: List[Path],
    pytest_args: List[str],
    config: ExecutionConfig,
    workspace_dir: Path
) -> List[TestResult]:
    """
    Exécute les tests séquentiellement
    """
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
    """
    Exécute les tests en parallèle
    """
    # Utiliser pytest-xdist pour la parallélisation
    cmd = ["pytest"] + pytest_args
    
    # Variables d'environnement
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace_dir)
    if config.base_url:
        env["BASE_URL"] = config.base_url
    if config.headed:
        env["HEADED"] = "true"
    
    # Exécuter pytest
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(workspace_dir)
    )
    
    stdout, stderr = await process.communicate()
    
    # Parser le rapport JSON
    report_path = workspace_dir / "report.json"
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        
        return parse_pytest_report(report, workspace_dir)
    else:
        # Fallback si pas de rapport
        return [TestResult(
            test_name="all_tests",
            status="error",
            duration=0,
            error_message="Pas de rapport généré",
            error_trace=stderr.decode() if stderr else None
        )]


async def run_single_test(
    test_file: Path,
    base_pytest_args: List[str],
    config: ExecutionConfig,
    workspace_dir: Path
) -> TestResult:
    """
    Exécute un seul fichier de test
    """
    # Arguments spécifiques pour ce test
    pytest_args = [str(test_file)] + base_pytest_args[1:]  # Skip workspace dir
    
    cmd = ["pytest"] + pytest_args
    
    # Variables d'environnement
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace_dir)
    if config.base_url:
        env["BASE_URL"] = config.base_url
    
    start_time = asyncio.get_event_loop().time()
    
    # Exécuter le test
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(workspace_dir)
    )
    
    stdout, stderr = await process.communicate()
    duration = asyncio.get_event_loop().time() - start_time
    
    # Déterminer le statut
    if process.returncode == 0:
        status = "passed"
    elif process.returncode == 1:
        status = "failed"
    else:
        status = "error"
    
    # Collecter les artifacts
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
    """
    Parse le rapport JSON de pytest
    """
    results = []
    
    for test in report.get("tests", []):
        # Extraire le nom du test
        test_name = test.get("nodeid", "unknown").split("::")[-1]
        
        # Déterminer le statut
        outcome = test.get("outcome", "unknown")
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "skipped": "skipped",
            "error": "error"
        }
        status = status_map.get(outcome, "error")
        
        # Collecter les informations d'erreur
        error_message = None
        error_trace = None
        if status == "failed":
            if "call" in test and "longrepr" in test["call"]:
                error_message = test["call"]["longrepr"]
            elif "setup" in test and "longrepr" in test["setup"]:
                error_message = test["setup"]["longrepr"]
        
        # Durée
        duration = test.get("duration", 0)
        
        # Artifacts
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
    """
    Collecte les artifacts d'un test (screenshots, videos, traces)
    """
    artifacts = {
        "screenshot": None,
        "video": None,
        "trace": None
    }
    
    # Patterns de recherche
    patterns = {
        "screenshot": ["**/test-results/**/*{test_name}*.png", "**/screenshots/**/*{test_name}*.png"],
        "video": ["**/test-results/**/*{test_name}*.webm", "**/videos/**/*{test_name}*.webm"],
        "trace": ["**/test-results/**/*{test_name}*.zip", "**/traces/**/*{test_name}*.zip"]
    }
    
    for artifact_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            files = list(workspace_dir.glob(pattern.format(test_name=test_name)))
            if files:
                artifacts[artifact_type] = str(files[0].relative_to(workspace_dir))
                break
    
    return artifacts


def calculate_stats(results: List[TestResult]) -> Dict[str, int]:
    """
    Calcule les statistiques des tests
    """
    stats = {
        "passed": sum(1 for r in results if r.status == "passed"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
        "error": sum(1 for r in results if r.status == "error")
    }
    return stats


# ------------------------------------------------------------------
# Background tasks
# ------------------------------------------------------------------

async def run_tests_background(execution_id: str, request: TestExecutionRequest):
    """
    Exécute les tests en arrière-plan
    """
    try:
        # Mettre à jour le statut
        execution_queue[execution_id]["status"] = "running"
        
        # Exécuter les tests
        response = await execute_tests(request)
        
        # Mettre à jour avec les résultats
        execution_queue[execution_id] = response.dict()
        execution_queue[execution_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        # En cas d'erreur
        execution_queue[execution_id].update({
            "status": "error",
            "error": str(e),
            "error_trace": traceback.format_exc(),
            "completed_at": datetime.now().isoformat()
        })


async def cleanup_workspace(workspace_dir: Path, delay: int = 300):
    """
    Nettoie le workspace après un délai
    """
    await asyncio.sleep(delay)
    
    try:
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)
            logger.info(f"Workspace nettoyé: {workspace_dir}")
    except Exception as e:
        logger.error(f"Erreur nettoyage workspace: {e}")


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

async def generate_html_report(
    execution_id: str,
    results: List[TestResult],
    stats: Dict[str, int],
    workspace_dir: Path
) -> str:
    """
    Génère un rapport HTML des résultats
    """
    report_path = Path("reports") / f"{execution_id}_report.html"
    
    # Template HTML
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Report - {execution_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat {{ padding: 10px 20px; border-radius: 5px; color: white; }}
        .passed {{ background: #4CAF50; }}
        .failed {{ background: #f44336; }}
        .skipped {{ background: #ff9800; }}
        .error {{ background: #9c27b0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f2f2f2; }}
        .status-passed {{ color: #4CAF50; }}
        .status-failed {{ color: #f44336; }}
        .status-skipped {{ color: #ff9800; }}
        .status-error {{ color: #9c27b0; }}
        .error-details {{ background: #fee; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        pre {{ white-space: pre-wrap; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Test Execution Report</h1>
        <p>Execution ID: {execution_id}</p>
        <p>Generated: {timestamp}</p>
    </div>
    
    <div class="stats">
        <div class="stat passed">Passed: {passed}</div>
        <div class="stat failed">Failed: {failed}</div>
        <div class="stat skipped">Skipped: {skipped}</div>
        <div class="stat error">Errors: {error}</div>
    </div>
    
    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Test Name</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Details</th>
        </tr>
        {test_rows}
    </table>
</body>
</html>
"""
    
    # Générer les lignes de test
    test_rows = []
    for result in results:
        error_section = ""
        if result.error_message:
            error_section = f'<div class="error-details"><pre>{result.error_message}</pre></div>'
        
        test_rows.append(f"""
        <tr>
            <td>{result.test_name}</td>
            <td class="status-{result.status}">{result.status.upper()}</td>
            <td>{result.duration:.2f}s</td>
            <td>{error_section}</td>
        </tr>
        """)
    
    # Remplir le template
    html_content = html_template.format(
        execution_id=execution_id,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        passed=stats["passed"],
        failed=stats["failed"],
        skipped=stats["skipped"],
        error=stats.get("error", 0),
        test_rows="\n".join(test_rows)
    )
    
    # Écrire le rapport
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return str(report_path)


async def collect_artifacts(execution_id: str, workspace_dir: Path) -> str:
    """
    Collecte et archive tous les artifacts
    """
    import zipfile
    
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    
    zip_path = artifacts_dir / f"{execution_id}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Ajouter tous les fichiers d'artifacts
        for pattern in ["**/*.png", "**/*.webm", "**/*.zip", "**/*.json"]:
            for file_path in workspace_dir.glob(pattern):
                if file_path.is_file():
                    arcname = file_path.relative_to(workspace_dir)
                    zipf.write(file_path, arcname)
    
    return str(zip_path)


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------

async def ensure_playwright_browsers():
    """
    S'assure que les navigateurs Playwright sont installés
    """
    try:
        # Vérifier si les navigateurs sont installés
        async with async_playwright() as p:
            # Tenter de lancer chaque navigateur
            for browser_name in ["chromium", "firefox", "webkit"]:
                try:
                    browser = await getattr(p, browser_name).launch(headless=True)
                    await browser.close()
                except Exception:
                    logger.warning(f"Navigateur {browser_name} non disponible")
    except Exception as e:
        logger.error(f"Erreur vérification Playwright: {e}")
        # Tenter d'installer les navigateurs
        try:
            subprocess.run(["playwright", "install"], check=True)
            logger.info("Navigateurs Playwright installés")
        except Exception:
            logger.error("Impossible d'installer les navigateurs Playwright")


async def check_playwright_health() -> bool:
    """
    Vérifie que Playwright est opérationnel
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
            return True
    except Exception:
        return False


async def save_execution_result(execution_id: str, result: ExecutionResponse):
    """
    Sauvegarde le résultat d'exécution dans Redis
    """
    if not redis_client:
        return
    
    try:
        key = f"execution:{execution_id}"
        await redis_client.setex(
            key,
            86400,  # 24 heures
            json.dumps(result.dict(), default=str)
        )
    except Exception as e:
        logger.error(f"Erreur sauvegarde Redis: {e}")


async def get_execution_result(execution_id: str) -> Optional[Dict]:
    """
    Récupère un résultat d'exécution depuis Redis
    """
    if not redis_client:
        return None
    
    try:
        key = f"execution:{execution_id}"
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Erreur lecture Redis: {e}")
    
    return None


# ------------------------------------------------------------------
# Additional endpoints
# ------------------------------------------------------------------

@app.delete("/cleanup")
async def cleanup_old_executions(days: int = 7):
    """
    Nettoie les anciennes exécutions
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    cleaned = {
        "workspaces": 0,
        "reports": 0,
        "artifacts": 0
    }
    
    # Nettoyer les workspaces
    for workspace in Path("workspace").iterdir():
        if workspace.is_dir() and workspace.stat().st_mtime < cutoff_date.timestamp():
            shutil.rmtree(workspace)
            cleaned["workspaces"] += 1
    
    # Nettoyer les rapports
    for report in Path("reports").glob("*.html"):
        if report.stat().st_mtime < cutoff_date.timestamp():
            report.unlink()
            cleaned["reports"] += 1
    
    # Nettoyer les artifacts
    for artifact in Path("artifacts").glob("*.zip"):
        if artifact.stat().st_mtime < cutoff_date.timestamp():
            artifact.unlink()
            cleaned["artifacts"] += 1
    
    return {
        "status": "success",
        "cleaned": cleaned,
        "message": f"Nettoyage des fichiers de plus de {days} jours"
    }


@app.get("/stats")
async def get_stats():
    """
    Statistiques du service
    """
    stats = {
        "service": "playwright-runner",
        "timestamp": datetime.now().isoformat(),
        "active_executions": len(execution_queue),
        "workspace_count": len(list(Path("workspace").iterdir())),
        "report_count": len(list(Path("reports").glob("*.html"))),
        "artifact_count": len(list(Path("artifacts").glob("*.zip")))
    }
    
    # Statistiques Redis
    if redis_client:
        try:
            exec_count = 0
            async for _ in redis_client.scan_iter("execution:*"):
                exec_count += 1
            stats["cached_executions"] = exec_count
        except:
            stats["cached_executions"] = "error"
    
    return stats


# Point d'entrée
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8004,
        log_level="info"
    )