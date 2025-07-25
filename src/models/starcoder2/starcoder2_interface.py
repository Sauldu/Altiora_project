# src/models/starcoder2/starcoder2_interface.py
"""Interface pour interagir avec le modèle StarCoder2 via Ollama.

Cette interface est spécialisée dans la génération de tests Playwright.
Elle est conçue pour être asynchrone, robuste (avec un disjoncteur) et
peut gérer le chargement de modèles optimisés (quantifiés) via un gestionnaire
de mémoire.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import aiohttp
import torch
from transformers import BitsAndBytesConfig, AutoModelForCausalLM, AutoTokenizer

from configs.config_module import ModelConfig
from src.core.model_memory_manager import ModelMemoryManager
from src.utils.retry_handler import CircuitBreaker

# ------------------------------------------------------------------
# Configuration du Logger
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Énumérations et DTO (Data Transfer Objects)
# ------------------------------------------------------------------
class TestType(Enum):
    """Types de tests supportés par le générateur de code."""
    E2E = "e2e"
    API = "api"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    COMPONENT = "component"


@dataclass
class PlaywrightTestConfig:
    """Configuration spécifique pour la génération de tests Playwright."""
    use_page_object: bool = True
    use_fixtures: bool = True
    include_screenshots: bool = True
    include_videos: bool = False
    browser: str = "chromium"
    timeout: int = 30000
    retry_count: int = 2
    use_data_testid: bool = True
    include_accessibility: bool = True
    include_performance_metrics: bool = False


# ------------------------------------------------------------------
# Interface StarCoder2
# ------------------------------------------------------------------
class StarCoder2OllamaInterface:
    """Wrapper asynchrone pour interagir avec StarCoder2 via Ollama ou en local."""

    def __init__(
            self,
            *,
            config: ModelConfig,
            model_memory_manager: ModelMemoryManager,
            failure_threshold: int = 5,
            recovery_timeout: int = 60,
    ) -> None:
        """Initialise l'interface StarCoder2.

        Args:
            config: L'objet de configuration du modèle (nom, température, etc.).
            model_memory_manager: Le gestionnaire de mémoire pour charger/décharger les modèles.
            failure_threshold: Nombre d'échecs consécutifs avant que le disjoncteur ne s'ouvre.
            recovery_timeout: Temps en secondes avant que le disjoncteur ne tente de se refermer.
        """
        self.config = config
        self.model_memory_manager = model_memory_manager
        self.model_name = config.name
        self.ollama_host = "http://localhost:11434"  # Supposons qu'Ollama tourne localement.
        self.timeout = config.timeout
        self.use_chat_api = config.api_mode == "chat"
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        self.model: Optional[AutoModelForCausalLM] = None
        self.tokenizer: Optional[AutoTokenizer] = None

        # Paramètres par défaut pour l'inférence du modèle.
        self.default_params = {
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "repeat_penalty": self.config.repeat_penalty,
            "num_predict": self.config.max_tokens,
            "num_ctx": self.config.num_ctx,
            "seed": self.config.seed,
            "stop": self.config.stop,
        }

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """Initialise le modèle StarCoder2 en le chargeant via le gestionnaire de mémoire."""
        # Le gestionnaire de mémoire décidera s'il faut charger le modèle complet ou quantifié.
        self.model = await self.model_memory_manager.get_model(self.model_name)
        # Récupère le tokenizer associé au modèle chargé.
        self.tokenizer = self.model_memory_manager.loaded_models[self.model_name]['tokenizer']
        logger.info(f"Interface StarCoder2 prête avec le modèle local : {self.model_name}.")

    async def close(self) -> None:
        """Ferme la session HTTP si elle est ouverte."""
        if self.session and not self.session.closed:
            await self.session.close()

    # ------------------------------------------------------------------
    # API Publique
    # ------------------------------------------------------------------
    async def generate_playwright_test(
            self,
            scenario: Dict[str, Any],
            config: Optional[PlaywrightTestConfig] = None,
            test_type: TestType = TestType.E2E,
    ) -> Dict[str, Any]:
        """Génère un script de test Playwright à partir d'un scénario donné.

        Args:
            scenario: Un dictionnaire décrivant le scénario de test.
            config: Configuration spécifique pour la génération du test Playwright.
            test_type: Le type de test à générer (E2E par défaut).

        Returns:
            Un dictionnaire contenant le code du test généré et ses métadonnées.

        Raises:
            RuntimeError: Si le modèle ou le tokenizer ne sont pas initialisés.
            Exception: En cas d'échec de la génération ou de validation du code.
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Le modèle ou le tokenizer StarCoder2 n'est pas initialisé.")

        config = config or PlaywrightTestConfig()

        prompt = self._build_prompt(scenario, config, test_type)
        start_time = asyncio.get_event_loop().time()

        async def _do() -> Dict[str, Any]:
            """Fonction interne pour l'exécution de la génération de code via le disjoncteur."""
            try:
                # Encode le prompt et génère la réponse du modèle.
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    top_k=self.config.top_k,
                    repetition_penalty=self.config.repeat_penalty,
                    do_sample=True if self.config.temperature > 0 else False,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
                raw_generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                # Extrait et valide le code généré.
                code = self._extract_code(raw_generated_text)
                code = self._validate_code(code)

                result = {
                    "code": code,
                    "test_type": test_type.value,
                    "uses_page_object": config.use_page_object,
                    "metadata": {
                        "generation_time": asyncio.get_event_loop().time() - start_time,
                        "model": self.model_name,
                        "scenario_title": scenario.get("titre", "Inconnu"),
                        "timestamp": datetime.now().isoformat(),
                        "api_mode": "local_inference",
                    },
                }
                return result
            except (RuntimeError, ValueError) as e:
                logger.error(f"Erreur de modèle lors de la génération du test Playwright : {e}")
                raise
            except Exception as e:
                logger.error(f"Erreur inattendue lors de la génération du test Playwright : {e}")
                raise

        return await self.circuit_breaker.call(_do)

    # ------------------------------------------------------------------
    # Extraction et validation du code
    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(
            scenario: Dict[str, Any], config: PlaywrightTestConfig, test_type: TestType
    ) -> str:
        """Construit le prompt pour StarCoder2 basé sur le scénario et la configuration."""
        title = scenario.get("titre", "Test").replace(" ", "_").lower()
        objective = scenario.get("objectif", "Vérifier la fonctionnalité.")
        steps = scenario.get("etapes", [])
        formatted_steps = "\n".join([f"    {i + 1}. {s}" for i, s in enumerate(steps)])

        # Le prompt est structuré pour guider le modèle à générer du code Playwright.
        return f"""
Generate a complete Playwright test in Python.

Scenario: {title}
Objective: {objective}
Steps:
{formatted_steps}
Browser: {config.browser}
Use Page Objects: {config.use_page_object}
```python
# Votre code de test Playwright ici
"""

    @staticmethod
    def _extract_code(raw: str) -> str:
        """Extrait le bloc de code Python d'une chaîne de texte brute générée par le LLM."""
        start_marker = "```python"
        end_marker = "```"
        start_index = raw.find(start_marker)
        if start_index == -1:
            return raw.strip() # Retourne le texte brut si aucun bloc de code n'est trouvé.
        
        start = start_index + len(start_marker)
        end = raw.find(end_marker, start)
        
        if end == -1:
            return raw[start:].strip() # Si pas de marqueur de fin, prend tout jusqu'à la fin.
        
        return raw[start:end].strip()

    @staticmethod
    def _validate_code(code: str) -> str:
        """Valide et potentiellement formate le code généré."

        Cette méthode peut intégrer des outils comme `ruff` ou `black` pour
        assurer la conformité du code. Pour l'instant, elle retourne le code tel quel.
        """
        # Exemple: Intégration future avec un validateur de code.
        # from post_processing.code_validator import CodeValidator
        # validator = CodeValidator()
        # validation_result = await validator.validate(code, code_type="playwright")
        # if not validation_result.passed:
        #     logger.warning(f"Code Playwright généré avec des avertissements/erreurs: {validation_result.playwright_warnings}")
        #     # Vous pouvez choisir de lever une erreur, de corriger, ou de simplement logguer.
        return code


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Assurez-vous qu'Ollama est lancé et que le modèle StarCoder2 est pull.
        # ollama pull starcoder2:15b-q8_0

        # Crée une instance factice de ModelConfig et ModelMemoryManager pour la démo.
        @dataclass
        class MockModelConfig:
            name: str = "starcoder2:15b-q8_0"
            temperature: float = 0.2
            top_p: float = 0.95
            top_k: int = 40
            repeat_penalty: float = 1.1
            max_tokens: int = 512
            num_ctx: int = 4096
            seed: int = 42
            stop: List[str] = Field(default_factory=lambda: ["```", "\n\n\n"])
            api_mode: str = "generate"

        class MockModelMemoryManager:
            def __init__(self):
                self.loaded_models = {
                    "starcoder2:15b-q8_0": {
                        'model': AutoModelForCausalLM.from_pretrained("bigcode/starcoder2-15b", quantization_config=BitsAndBytesConfig(load_in_4bit=True), device_map="auto"),
                        'tokenizer': AutoTokenizer.from_pretrained("bigcode/starcoder2-15b"),
                        'last_used': datetime.now().timestamp(),
                        'size': 1.0 # Taille factice
                    }
                }
            async def get_model(self, model_name: str):
                return self.loaded_models[model_name]['model']

        mock_config = MockModelConfig()
        mock_memory_manager = MockModelMemoryManager()

        interface = StarCoder2OllamaInterface(
            config=mock_config,
            model_memory_manager=mock_memory_manager
        )
        try:
            await interface.initialize()

            sample_scenario = {
                "titre": "Connexion utilisateur",
                "objectif": "Vérifier la connexion réussie avec des identifiants valides.",
                "etapes": [
                    "Naviguer vers la page de connexion",
                    "Saisir l'email et le mot de passe",
                    "Cliquer sur le bouton de connexion"
                ]
            }
            sample_config = PlaywrightTestConfig(browser="chromium", use_page_object=True)

            print("\n--- Génération d'un test Playwright ---")
            generated_test = await interface.generate_playwright_test(
                scenario=sample_scenario,
                config=sample_config,
                test_type=TestType.E2E
            )
            print(f"Code généré :\n{generated_test['code']}")
            print(f"Métadonnées : {generated_test['metadata']}")

        except RuntimeError as e:
            logging.error(f"Erreur d'initialisation de l'interface StarCoder2 : {e}")
        except Exception as e:
            logging.error(f"Erreur lors de la génération du test Playwright : {e}")
        finally:
            await interface.close()

    # Vérifie si PyTorch et Transformers sont disponibles avant de lancer la démo.
    if torch is None or AutoModelForCausalLM is None or AutoTokenizer is None:
        print("PyTorch ou Transformers ne sont pas installés. Impossible d'exécuter la démo de StarCoder2.")
    else:
        asyncio.run(demo())