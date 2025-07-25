# src/core/workflow_engine.py
"""Moteur de workflow pour l'orchestration de bout en bout des tâches de QA.

Ce module gère l'exécution séquentielle des étapes d'un pipeline complexe,
comme l'analyse d'une Spécification Fonctionnelle Détaillée (SFD) jusqu'à
la génération de tests. Il intègre le suivi de la progression et la gestion
des erreurs à chaque étape.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from post_processing.excel_formatter import ExcelFormatter
from src.core.state_manager import get_state_manager
from src.core.strategies.sfd_analysis_strategy import SFDAnalysisStrategy
from src.models.qwen3.qwen3_interface import Qwen3OllamaInterface
from src.models.starcoder2.starcoder2_interface import (
    PlaywrightTestConfig,
    StarCoder2OllamaInterface,
    TestType,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Orchestrateur de workflow de QA avec suivi de la progression.

    Cette classe coordonne les différentes étapes d'un processus complexe,
    comme la transformation d'une SFD en suite de tests automatisés.
    """

    def __init__(self) -> None:
        """Initialise le moteur de workflow. Les composants sont initialisés de manière asynchrone."""
        self.qwen3: Optional[Qwen3OllamaInterface] = None
        self.starcoder2: Optional[StarCoder2OllamaInterface] = None
        self.excel_formatter = ExcelFormatter()
        self.state = None # Sera initialisé par get_state_manager.
        self.strategies: Dict[str, Any] = {} # Registre des stratégies de workflow.

    async def initialize(self) -> None:
        """Initialise de manière asynchrone les interfaces des modèles et le gestionnaire d'état."""
        self.qwen3 = Qwen3OllamaInterface()
        await self.qwen3.initialize()

        self.starcoder2 = StarCoder2OllamaInterface()
        await self.starcoder2.initialize()

        self.state = await get_state_manager()
        # Enregistre les stratégies disponibles.
        self.strategies["sfd_analysis"] = SFDAnalysisStrategy(self.qwen3)

    async def close(self) -> None:
        """Ferme proprement les connexions des modèles et le gestionnaire d'état."""
        if self.qwen3:
            await self.qwen3.close()
        if self.starcoder2:
            await self.starcoder2.close()
        if self.state:
            await self.state.close()

    async def run_sfd_to_test_suite(self, sfd_path: str, session_id: str) -> Dict[str, Any]:
        """Exécute le pipeline complet de l'analyse SFD à la génération de la suite de tests.

        Args:
            sfd_path: Le chemin vers le fichier de spécifications fonctionnelles détaillées.
            session_id: L'identifiant unique de la session pour le suivi de la progression.

        Returns:
            Un dictionnaire contenant le statut du workflow, le chemin du rapport final,
            et l'horodatage de la génération.

        Raises:
            RuntimeError: Si une étape du workflow échoue.
            FileNotFoundError: Si le fichier SFD n'est pas trouvé.
        """
        # Définit les étapes du pipeline avec leurs fonctions associées.
        steps = [
            ("load_sfd", self._load_sfd), # La fonction _load_sfd prend le sfd_path directement.
            ("analyze_sfd", self._analyze_sfd), # Prend le contenu de la SFD.
            ("generate_tests", self._generate_tests), # Prend les scénarios analysés.
            ("export_report", self._export_report), # Prend les tests générés.
        ]

        context: Dict[str, Any] = {}
        for step_name, step_func in steps:
            # Met à jour la progression de l'étape dans le gestionnaire d'état.
            if self.state:
                await self.state.set_pipeline_progress(session_id, step_name, 0.0)
            try:
                # Exécute l'étape avec un timeout.
                # La fonction `step_func` est appelée avec le `context` actuel.
                # Les résultats de l'étape sont mis à jour dans le `context`.
                if step_name == "load_sfd":
                    result = await asyncio.wait_for(step_func(sfd_path), timeout=300)
                else:
                    result = await asyncio.wait_for(step_func(context), timeout=300)
                context.update(result);
                if self.state:
                    await self.state.set_pipeline_progress(session_id, step_name, 1.0)
            except asyncio.TimeoutError:
                logger.error(f"L'étape '{step_name}' a dépassé le temps imparti.")
                if self.state:
                    await self.state.set_pipeline_progress(session_id, step_name, -1.0)
                raise RuntimeError(f"L'étape du workflow '{step_name}' a dépassé le temps imparti.")
            except Exception as e:
                logger.error(f"L'étape '{step_name}' a échoué : {e}", exc_info=True)
                if self.state:
                    await self.state.set_pipeline_progress(session_id, step_name, -1.0)
                raise RuntimeError(f"L'étape du workflow '{step_name}' a échoué.") from e

        return {
            "session_id": session_id,
            "workflow_status": "completed",
            "final_report": context.get("report_path"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def _load_sfd(path: str) -> Dict[str, Any]:
        """Charge le contenu textuel d'un fichier SFD."

        Args:
            path: Le chemin d'accès au fichier SFD.

        Returns:
            Un dictionnaire contenant le contenu du fichier et sa taille.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            RuntimeError: Si une erreur de lecture du fichier survient.
        """
        sfd_file = Path(path).resolve()
        if not sfd_file.exists():
            raise FileNotFoundError(f"Le fichier SFD n'a pas été trouvé : {sfd_file}")

        try:
            async with aiofiles.open(sfd_file, encoding="utf-8") as f:
                content = await f.read()
            return {"content": content, "file_size": sfd_file.stat().st_size}
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors du chargement du fichier SFD {sfd_file}: {e}")
            raise RuntimeError(f"Échec du chargement du fichier SFD : {e}")

    async def _analyze_sfd(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse le contenu d'une SFD pour en extraire les scénarios de test."""
        sfd_content = context.get("content")
        if not sfd_content:
            raise ValueError("Le contenu de la SFD est manquant dans le contexte.")

        strategy = self.strategies.get("sfd_analysis")
        if not strategy:
            raise ValueError("La stratégie d'analyse SFD n'est pas initialisée.")

        # La stratégie d'analyse SFD attend un objet SFDAnalysisRequest.
        # Ici, nous passons le contenu directement, la stratégie doit le gérer.
        result = await strategy.execute({"sfd_request": sfd_content}) # Adapte l'appel à la stratégie.
        return result

    async def _generate_tests(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Génère les tests Playwright à partir des scénarios extraits."""
        scenarios = context.get("scenarios")
        if not scenarios:
            raise ValueError("Les scénarios sont manquants dans le contexte.")

        if not self.starcoder2:
            raise RuntimeError("L'interface StarCoder2 n'est pas initialisée.")

        generated: List[Dict[str, Any]] = []
        config = PlaywrightTestConfig(browser="chromium", use_page_object=False)
        for scenario in scenarios:
            # Génère le code de test pour chaque scénario.
            code = await self.starcoder2.generate_playwright_test(
                scenario=scenario, config=config, test_type=TestType.E2E
            )
            generated.append({"scenario": scenario, "test": code})
        return {"tests": generated}

    async def _export_report(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Génère le rapport Excel final à partir des tests générés."""
        tests = context.get("tests")
        if not tests:
            raise ValueError("Les tests générés sont manquants dans le contexte.")

        # L'excel_formatter attend une liste de dictionnaires pour les scénarios et les tests.
        report_path = await self.excel_formatter.format_test_matrix(
            test_cases=[
                {
                    "id": t["scenario"].get("id", ""), # Assurez-vous que l'ID est présent
                    "description": t["scenario"].get("description", ""),
                    "type": t["scenario"].get("type", "CP"),
                    "generated_code": t["test"],
                }
                for t in tests
            ],
            output_path=f"reports/test_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )
        return {"report_path": str(report_path)}

    async def get_progress(self, session_id: str) -> Dict[str, Any]:
        """Récupère la progression actuelle d'un workflow par son ID de session."""
        if not self.state:
            raise RuntimeError("Le gestionnaire d'état n'est pas initialisé.")
        return await self.state.get_pipeline_progress(session_id)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        engine = WorkflowEngine()
        await engine.initialize()

        session_id = "demo_session_123"
        sfd_content = """
        Spécification Fonctionnelle Détaillée: Module de Connexion

        1. Scénario: Connexion réussie
        - ID: CU01_SB01_CP001
        - Description: L'utilisateur doit pouvoir se connecter avec des identifiants valides.
        - Type: CP
        - Étapes: Entrer email et mot de passe valides, cliquer sur 'Se connecter'.
        - Résultat attendu: Redirection vers le tableau de bord.

        2. Scénario: Mot de passe incorrect
        - ID: CU01_SB01_CE001
        - Description: L'utilisateur ne doit pas pouvoir se connecter avec un mot de passe incorrect.
        - Type: CE
        - Étapes: Entrer email valide et mot de passe incorrect, cliquer sur 'Se connecter'.
        - Résultat attendu: Message d'erreur 'Mot de passe incorrect'.
        """
        # Crée un fichier SFD temporaire pour la démo.
        temp_sfd_path = Path("temp_sfd_demo.txt")
        async with aiofiles.open(temp_sfd_path, "w", encoding="utf-8") as f:
            await f.write(sfd_content)

        print(f"\n--- Lancement du workflow pour la session : {session_id} ---")
        try:
            # Simule l'analyse SFD et la génération de tests.
            # Note: Les interfaces Qwen3 et Starcoder2 doivent être fonctionnelles (Ollama).
            result = await engine.run_sfd_to_test_suite(str(temp_sfd_path), session_id)
            print(f"\nWorkflow terminé avec succès. Rapport final : {result['final_report']}")
            print(f"Statut de progression : {await engine.get_progress(session_id)}")
        except Exception as e:
            print(f"\nErreur lors de l'exécution du workflow : {e}")
            print(f"Statut de progression : {await engine.get_progress(session_id)}")
        finally:
            await engine.close()
            if temp_sfd_path.exists():
                temp_sfd_path.unlink()

    asyncio.run(demo())