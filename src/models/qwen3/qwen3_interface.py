#!/usr/bin/env python3
"""
Interface Qwen3 avec Ollama pour l'analyse de SFD
Optimisée pour génération de scénarios de test sur CPU
Support du context 32K tokens pour documents longs
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
import aiohttp





# Import pour l'évolution de la personnalité
from psychodesign.personality_evolution import PersonalityEvolution
from src.models.sfd_models import SFDAnalysisRequest
from src.utils.circuit_breaker import CircuitBreaker



logger = logging.getLogger(__name__)


class Qwen3OllamaInterface:
    """
    Interface pour communiquer avec Qwen3 via Ollama
    Spécialisée dans l'analyse de spécifications fonctionnelles
    """

    def __init__(self,
                 model_name: str = "qwen3-sfd-analyzer",
                 ollama_host: str = "http://localhost:11434",
                 timeout: int = 120,
                 cache_enabled: bool = True,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60):
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.timeout = timeout
        self.cache_enabled: bool = cache_enabled
        self.session = None
        self.adapter_path: Optional[str] = None
        self.personality_evolver = PersonalityEvolution()
        self.circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)

        # Cache en mémoire pour éviter les re-analyses
        self.cache: Dict[str, Dict] = {}

        # Configuration spécifique Qwen3
        self.default_params = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.1,
            "num_ctx": 32768,  # Context 32K
            "num_predict": 4096
        }

    async def initialize(self):
        """Initialise la session HTTP et vérifie le modèle"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )

        # Vérifier que le modèle est disponible
        if not await self._check_model():
            raise RuntimeError(f"Modèle {self.model_name} non disponible dans Ollama")

        # Précharger le modèle pour éviter la latence au premier appel
        await self._preload_model()

        # Charger le dernier adaptateur de personnalité LoRA
        self.load_latest_adapter()

        logger.info(f"Interface Qwen3 initialisée avec modèle {self.model_name}")

    async def _check_model(self) -> bool:
        """Vérifie la disponibilité du modèle via le circuit breaker"""
        async def _do_check():
            async with self.session.get(f"{self.ollama_host}/api/tags") as resp:
                resp.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
                data = await resp.json()
                models = [m['name'] for m in data.get('models', [])]
                return any(self.model_name in model for model in models)

        try:
            return await self.circuit_breaker.call(_do_check)
        except Exception as e:
            logger.error(f"Erreur vérification modèle (via circuit breaker): {e}")
            return False

    async def _preload_model(self):
        """Précharge le modèle en mémoire pour réduire la latence via le circuit breaker"""
        logger.info("Préchargement du modèle Qwen3...")

        async def _do_preload():
            payload = {
                "model": self.model_name,
                "prompt": "Bonjour",
                "stream": False,
                "options": {"num_predict": 1}
            }
            async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload
            ) as resp:
                resp.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
                await resp.json()

        try:
            await self.circuit_breaker.call(_do_preload)
            logger.info("Modèle préchargé avec succès")
        except Exception as e:
            logger.warning(f"Préchargement échoué (non critique, via circuit breaker): {e}")

    def load_latest_adapter(self):
        """Charge le chemin du dernier adaptateur LoRA disponible."""
        latest_adapter_path = self.personality_evolver.get_latest_adapter()
        if latest_adapter_path and latest_adapter_path.exists():
            self.adapter_path = str(latest_adapter_path)
            logger.info(f"🧠 Adaptateur de personnalité LoRA chargé : {self.adapter_path}")
        else:
            logger.info("🧠 Aucun adaptateur de personnalité trouvé, utilisation du modèle de base.")

    async def analyze_sfd(self,
                          request: SFDAnalysisRequest,
                          use_cache: bool = True) -> Dict:
        """
        Analyse un SFD et extrait les scénarios de test via le circuit breaker

        Args:
            request: Objet SFDAnalysisRequest contenant le contenu et le type d'extraction.
            use_cache: Utiliser le cache si disponible

        Returns:
            Dict contenant les scénarios extraits et métadonnées
        """
        # CORRECTION 2: Initialiser cache_key avant utilisation
        cache_key = self._generate_cache_key(request.content, request.extraction_type)

        # Vérifier le cache si activé
        if use_cache and self.cache_enabled and cache_key in self.cache:
            logger.info("Résultat trouvé dans le cache")
            return self.cache[cache_key]

        # Construire le prompt selon le type d'extraction
        prompt = self._build_analysis_prompt(request.content, request.extraction_type)

        # Paramètres optimisés pour l'analyse
        params = self.default_params.copy()
        if request.extraction_type == "critical":
            params["temperature"] = 0.3  # Plus déterministe pour les cas critiques

        # Appel au modèle
        start_time = asyncio.get_event_loop().time()

        async def _do_analyze():
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",  # Force la sortie JSON
                "options": params
            }

            # Ajouter l'adaptateur LoRA si disponible
            if self.adapter_path:
                payload["adapter"] = self.adapter_path

            async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload
            ) as resp:
                resp.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
                data = await resp.json()

                # CORRECTION 3: Vérifier la réponse vide
                if not data or not data.get("response"):
                    logger.error("Réponse vide d'Ollama")
                    return {"scenarios": [], "error": "empty_response"}

                response = data.get("response", "{}")

                # Parser et valider la réponse JSON
                result = self._parse_analysis_response(response)

                # Ajouter les métadonnées
                result["metadata"] = {
                    "processing_time": asyncio.get_event_loop().time() - start_time,
                    "model": self.model_name,
                    "adapter": self.adapter_path,
                    "extraction_type": request.extraction_type,
                    "content_length": len(request.content),
                    "timestamp": datetime.now().isoformat()
                }

                # Mettre en cache si activé
                if use_cache and self.cache_enabled:
                    self.cache[cache_key] = result

                return result

        try:
            return await self.circuit_breaker.call(_do_analyze)
        except asyncio.TimeoutError:
            raise Exception(f"Timeout après {self.timeout}s - Document trop long?")
        except Exception as e:
            logger.error(f"Erreur analyse SFD (via circuit breaker): {e}")
            raise

    @staticmethod
    def _generate_cache_key(content: str, extraction_type: str) -> str:
        """Génère une clé de cache unique"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"qwen3_analysis_{extraction_type}_{content_hash}"

    @staticmethod
    def _build_analysis_prompt(content: str, extraction_type: str) -> str:
        """Construit le prompt selon le type d'extraction demandé"""

        # Limiter la taille du contenu si nécessaire (32K tokens max)
        # Approximation : 1 token ≈ 4 caractères
        max_chars = 120000  # ~30K tokens pour garder de la marge
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... [Document tronqué]"

        prompts = {
            "complete": """En tant qu'expert en test logiciel, analyse cette spécification fonctionnelle et extrais TOUS les scénarios de test possibles.\n\nPour chaque scénario, fournis au format JSON:\n- titre: Nom descriptif du test\n- objectif: But du test\n- criticite: HAUTE/MOYENNE/BASSE\n- preconditions: Liste des prérequis\n- etapes: Liste détaillée des étapes\n- resultat_attendu: Description du résultat\n- donnees_test: Données nécessaires\n- type_test: FONCTIONNEL/INTEGRATION/E2E/SECURITE/PERFORMANCE\n\nSpécification:\n{content}\n\nGénère la réponse au format JSON valide avec une structure "scenarios": []""",

            "summary": """Analyse cette spécification et identifie les 10 scénarios de test les plus importants.\nFocus sur les fonctionnalités critiques et les cas d'usage principaux.\n\nSpécification:\n{content}\n\nFormat JSON avec "scenarios": [] contenant les 10 tests prioritaires.""",

            "critical": """Identifie UNIQUEMENT les scénarios de test CRITIQUES pour la sécurité, les données sensibles et les processus métier essentiels.\n\nSpécification:\n{content}\n\nFormat JSON avec "scenarios": [] contenant uniquement les tests de criticité HAUTE."""
        }

        prompt_template = prompts.get(extraction_type, prompts["complete"])
        return prompt_template.format(content=content)

    @staticmethod
    def _parse_analysis_response(response: str) -> Dict:
        """Parse et valide la réponse JSON du modèle"""
        try:
            # Nettoyer la réponse si nécessaire
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]

            # Parser le JSON
            data = json.loads(response)

            # Valider la structure
            if "scenarios" not in data:
                data = {"scenarios": []}

            # Enrichir les scénarios avec des valeurs par défaut
            for scenario in data["scenarios"]:
                scenario.setdefault("criticite", "MOYENNE")
                scenario.setdefault("type_test", "FONCTIONNEL")
                scenario.setdefault("preconditions", [])
                scenario.setdefault("donnees_test", {})

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON: {e}. Réponse brute: {response}")
            # Retourner une structure vide en cas d'erreur
            return {
                "scenarios": [],
                "error": "Erreur de parsing de la réponse",
                "raw_response": response
            }

    async def generate_test_matrix(self, scenarios: List[Dict]) -> Dict:
        """
        Génère une matrice de tests structurée à partir des scénarios via le circuit breaker
        Optimisé pour export Excel
        """
        prompt = f"""Crée une matrice de tests structurée pour Excel à partir de ces scénarios:\n\n{json.dumps(scenarios, ensure_ascii=False, indent=2)}\n\nLa matrice doit inclure:\n- ID unique par test\n- Module/Fonctionnalité\n- Scénario\n- Priorité (P1/P2/P3)\n- Complexité (Simple/Moyenne/Complexe)\n- Effort estimé (heures)\n- Dépendances\n- Automatisable (Oui/Non/Partiel)\n\nFormat JSON avec structure "test_matrix": []"""

        async def _do_generate():
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    **self.default_params,
                    "temperature": 0.5  # Plus structuré
                }
            }

            async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload
            ) as resp:
                resp.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
                data = await resp.json()

                # Vérifier la réponse vide ici aussi
                if not data or not data.get("response"):
                    logger.error("Réponse vide d'Ollama pour la matrice")
                    return {"test_matrix": [], "error": "empty_response"}

                return self._parse_analysis_response(data.get("response", "{}"))

        try:
            return await self.circuit_breaker.call(_do_generate)
        except Exception as e:
            logger.error(f"Erreur génération matrice (via circuit breaker): {e}")
            raise

    async def close(self):
        """Ferme la session HTTP"""
        if self.session:
            await self.session.close()
        logger.info("Interface Qwen3 fermée")


# Exemple d'utilisation
async def main():
    """Démonstration de l'interface Qwen3"""
    interface = Qwen3OllamaInterface()

    try:
        await interface.initialize()

        # Exemple d'analyse de SFD
        sfd_example = """
        Spécification Fonctionnelle: Module de Paiement

        1. Authentification sécurisée
        - L'utilisateur doit s'authentifier avec email/mot de passe
        - Support de l'authentification à deux facteurs

        2. Processus de paiement
        - Sélection du mode de paiement (CB, PayPal, virement)
        - Validation des informations
        - Confirmation avec code OTP
        """

        # Analyse complète
        sfd_request = SFDAnalysisRequest(content=sfd_example, extraction_type="complete")
        result = await interface.analyze_sfd(
            request=sfd_request
        )

        print(f"Analyse terminée en {result['metadata']['processing_time']:.2f}s")
        print(f"Scénarios extraits: {len(result['scenarios'])}")

        for scenario in result['scenarios']:
            print(f"  - {scenario['titre']} [{scenario['criticite']}]")

    finally:
        await interface.close()


if __name__ == "__main__":
    asyncio.run(main())
