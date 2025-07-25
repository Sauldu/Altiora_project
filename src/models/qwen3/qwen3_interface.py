# src/models/qwen3/qwen3_interface.py
"""Interface pour interagir avec le modèle Qwen3 via Ollama.

Cette interface est spécialisée dans l'analyse de Spécifications Fonctionnelles Détaillées (SFD)
avec un support pour un grand contexte (32K tokens), optimisée pour la génération
de scénarios de test sur CPU. Elle intègre un disjoncteur (circuit breaker)
pour gérer les défaillances temporaires d'Ollama et un cache en mémoire.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional, Any

import aiohttp

from src.modules.psychodesign.personality_evolution import PersonalityEvolution
from src.models.sfd_models import SFDAnalysisRequest
from src.utils.retry_handler import CircuitBreaker

logger = logging.getLogger(__name__)


class Qwen3OllamaInterface:
    """Interface asynchrone pour communiquer avec Qwen3 via Ollama."""

    def __init__(self,
                 model_name: str = "qwen3-sfd-analyzer",
                 ollama_host: str = "http://localhost:11434",
                 timeout: int = 120,
                 cache_enabled: bool = True,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60):
        """Initialise l'interface Qwen3.

        Args:
            model_name: Le nom du modèle Qwen3 à utiliser dans Ollama.
            ollama_host: L'URL de l'hôte Ollama.
            timeout: Le délai d'attente maximal pour les requêtes HTTP en secondes.
            cache_enabled: Active ou désactive le cache en mémoire pour les résultats d'analyse.
            failure_threshold: Nombre d'échecs consécutifs avant que le disjoncteur ne s'ouvre.
            recovery_timeout: Temps en secondes avant que le disjoncteur ne tente de se refermer.
        """
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.timeout = timeout
        self.cache_enabled = cache_enabled
        self.session: Optional[aiohttp.ClientSession] = None
        self.adapter_path: Optional[str] = None
        self.personality_evolver = PersonalityEvolution()
        self.circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        # Cache en mémoire pour éviter les re-analyses coûteuses.
        self.cache: Dict[str, Dict] = {}

        # Configuration spécifique à Qwen3 pour l'inférence.
        self.default_params = {
            "temperature": 0.7, # Contrôle la créativité de la réponse.
            "top_p": 0.9,       # Contrôle la diversité de la réponse.
            "top_k": 40,        # Limite le nombre de jetons considérés pour la prédiction.
            "repeat_penalty": 1.1, # Pénalise la répétition de jetons.
            "num_ctx": 32768,   # Taille du contexte en jetons (pour les documents longs).
            "num_predict": 4096 # Nombre maximal de jetons à générer.
        }

    async def initialize(self):
        """Initialise la session HTTP et vérifie la disponibilité du modèle dans Ollama."

        Raises:
            RuntimeError: Si le modèle n'est pas disponible dans Ollama après vérification.
        """
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )

        # Vérifie que le modèle est disponible avant de continuer.
        if not await self._check_model():
            raise RuntimeError(f"Le modèle `{self.model_name}` n'est pas disponible dans Ollama.")

        # Précharge le modèle en mémoire pour réduire la latence au premier appel.
        await self._preload_model()

        # Charge le chemin du dernier adaptateur de personnalité LoRA si disponible.
        self.load_latest_adapter()

        logger.info(f"Interface Qwen3 initialisée avec le modèle `{self.model_name}`.")

    async def _check_model(self) -> bool:
        """Vérifie la disponibilité du modèle Qwen3 dans Ollama via le circuit breaker."""

        async def _do_check():
            """Fonction interne pour la vérification du modèle."""
            async with self.session.get(f"{self.ollama_host}/api/tags") as resp:
                resp.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx.
                data = await resp.json()
                models = [m['name'] for m in data.get('models', [])]
                return any(self.model_name in model for model in models)

        try:
            return await self.circuit_breaker.call(_do_check)
        except aiohttp.ClientError as e:
            logger.error(f"Erreur réseau lors de la vérification du modèle : {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la vérification du modèle : {e}")
            return False

    async def _preload_model(self):
        """Précharge le modèle en mémoire Ollama pour réduire la latence des requêtes futures."""
        logger.info(f"Préchargement du modèle Qwen3 ({self.model_name})...")

        async def _do_preload():
            """Fonction interne pour le préchargement du modèle."""
            payload = {
                "model": self.model_name,
                "prompt": "Bonjour", # Un prompt minimal pour déclencher le chargement.
                "stream": False,
                "options": {"num_predict": 1}
            }
            async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload
            ) as resp:
                resp.raise_for_status()
                await resp.json()

        try:
            await self.circuit_breaker.call(_do_preload)
            logger.info("Modèle Qwen3 préchargé avec succès.")
        except aiohttp.ClientError as e:
            logger.warning(f"Échec du préchargement du modèle (non critique) : {e}")
        except Exception as e:
            logger.warning(f"Échec inattendu du préchargement du modèle (non critique) : {e}")

    def load_latest_adapter(self):
        """Charge le chemin du dernier adaptateur LoRA de personnalité disponible."

        Si un adaptateur est trouvé, son chemin est stocké pour être utilisé
        lors de la construction des prompts.
        """
        latest_adapter_path = self.personality_evolver.get_latest_adapter()
        if latest_adapter_path and latest_adapter_path.exists():
            self.adapter_path = str(latest_adapter_path)
            logger.info(f"🧠 Adaptateur de personnalité LoRA chargé : {self.adapter_path}")
        else:
            logger.info("🧠 Aucun adaptateur de personnalité trouvé, utilisation du modèle de base Qwen3.")

    async def analyze_sfd(
        self,
        request: SFDAnalysisRequest,
        use_cache: bool = True
    ) -> Dict:
        """Analyse une Spécification Fonctionnelle Détaillée (SFD) et extrait les scénarios de test.

        Args:
            request: Un objet `SFDAnalysisRequest` contenant le contenu de la SFD
                     et le type d'extraction souhaité.
            use_cache: Si True, le résultat sera récupéré du cache si disponible et mis en cache après traitement.

        Returns:
            Un dictionnaire contenant les scénarios extraits et d'autres métadonnées d'analyse.

        Raises:
            aiohttp.ClientError: En cas d'erreur de communication avec Ollama.
            Exception: En cas d'erreur inattendue lors de l'analyse.
        """
        cache_key = self._generate_cache_key(request.content, request.extraction_type)

        # Vérifie le cache en mémoire si activé.
        if use_cache and self.cache_enabled and cache_key in self.cache:
            logger.info("Résultat d'analyse SFD trouvé dans le cache en mémoire.")
            return self.cache[cache_key]

        # Construit le prompt pour Qwen3 en fonction du type d'extraction demandé.
        prompt = self._build_prompt(request)

        try:
            # Utilise le circuit breaker pour l'appel à l'API Ollama.
            async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        **self.default_params
                    }
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                result = self._parse_response(data)
                
                # Met en cache le résultat si activé.
                if use_cache and self.cache_enabled:
                    self.cache[cache_key] = result
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Erreur réseau lors de la génération de texte par Qwen3 : {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la génération de texte par Qwen3 : {e}")
            raise

    async def close(self) -> None:
        """Ferme la session HTTP asynchrone."""
        if self.session and not self.session.closed:
            await self.session.close()

    @staticmethod
    def _generate_cache_key(content: str, extraction_type: str) -> str:
        """Génère une clé de cache unique basée sur le contenu de la SFD et le type d'extraction."""
        # Utilise un hachage du contenu pour une clé compacte et unique.
        return f"{hash(content)}_{extraction_type}"

    @staticmethod
    def _build_prompt(request: SFDAnalysisRequest) -> str:
        """Construit le prompt pour Qwen3 en fonction du type d'extraction demandé."""
        # Ce prompt est un exemple et devrait être affiné pour Qwen3.
        # Il devrait inclure des instructions claires sur le format de sortie attendu (JSON).
        if request.extraction_type == "complete":
            instruction = "Extrayez tous les scénarios de test détaillés de la spécification suivante, incluant titre, objectif, criticité, préconditions, étapes, résultat attendu et données de test. Retournez le tout au format JSON."
        elif request.extraction_type == "summary":
            instruction = "Fournissez un résumé des principaux scénarios de test de la spécification suivante. Retournez le tout au format JSON."
        elif request.extraction_type == "critical_only":
            instruction = "Identifiez et extrayez uniquement les scénarios de test critiques de la spécification suivante. Retournez le tout au format JSON."
        else:
            instruction = "Extrayez les scénarios de test de la spécification suivante au format JSON."

        return f"""
Vous êtes un expert en analyse de spécifications fonctionnelles. Votre tâche est d'analyser la SFD fournie et d'en extraire les scénarios de test.

Instruction: {instruction}

Spécification Fonctionnelle Détaillée:
```
{request.content}
```

Réponse JSON:
"""

    @staticmethod
    def _parse_response(data: Dict) -> Dict:
        """Analyse la réponse JSON brute d'Ollama et extrait les scénarios de test."

        Args:
            data: Le dictionnaire de réponse brut d'Ollama.

        Returns:
            Un dictionnaire contenant les scénarios extraits et d'autres informations.
        """
        # La réponse d'Ollama est dans `data["response"]`.
        # Il faut ensuite parser cette chaîne qui devrait être du JSON.
        raw_response_text = data.get("response", "{}")
        try:
            parsed_json = json.loads(raw_response_text)
            # Assurez-vous que la structure correspond à ce que vous attendez.
            return {"scenarios": parsed_json.get("scenarios", []), "raw_output": raw_response_text}
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON de la réponse Qwen3 : {e}. Réponse brute : {raw_response_text[:200]}...")
            return {"scenarios": [], "error": f"Parsing JSON échoué: {e}", "raw_output": raw_response_text}


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Assurez-vous qu'Ollama est lancé et que le modèle 'qwen3-sfd-analyzer' est pull.
        # ollama pull qwen3-sfd-analyzer

        interface = Qwen3OllamaInterface()
        try:
            await interface.initialize()

            sfd_content = """
            Spécification Fonctionnelle: Module de Connexion

            1. Scénario: Connexion réussie
            - Étapes: Entrer un email et un mot de passe valides, cliquer sur 'Se connecter'.
            - Résultat attendu: Redirection vers le tableau de bord.

            2. Scénario: Mot de passe incorrect
            - Étapes: Entrer un email valide et un mot de passe incorrect, cliquer sur 'Se connecter'.
            - Résultat attendu: Message d'erreur 'Mot de passe incorrect'.
            """
            sfd_request = SFDAnalysisRequest(content=sfd_content, extraction_type="complete")

            print("\n--- Analyse de la SFD (complète) ---")
            analysis_result = await interface.analyze_sfd(sfd_request)
            print(f"Résultat de l'analyse : {json.dumps(analysis_result, indent=2, ensure_ascii=False)}")

            # Démonstration du cache.
            print("\n--- Analyse de la SFD (depuis le cache) ---")
            analysis_result_cached = await interface.analyze_sfd(sfd_request, use_cache=True)
            print(f"Résultat de l'analyse (depuis cache) : {json.dumps(analysis_result_cached, indent=2, ensure_ascii=False)}")

        except RuntimeError as e:
            logging.error(f"Erreur d'initialisation de l'interface Qwen3 : {e}")
        except Exception as e:
            logging.error(f"Erreur lors de l'analyse de la SFD : {e}")
        finally:
            await interface.close()

    asyncio.run(demo())