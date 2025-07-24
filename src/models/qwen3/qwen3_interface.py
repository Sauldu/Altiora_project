#!/usr/bin/env python3
"""
Interface Qwen3 avec Ollama pour l'analyse de SFD
Optimisée pour génération de scénarios de test sur CPU
Support du context 32K tokens pour documents longs
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import aiohttp

# Import pour l'évolution de la personnalité
from psychodesign.personality_evolution import PersonalityEvolution
from src.models.sfd_models import SFDAnalysisRequest
from src.utils.retry_handler import CircuitBreaker

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
        self.cache_enabled = cache_enabled
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
        except aiohttp.ClientError as e:
            logger.error(f"Erreur lors de la vérification du modèle: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la vérification du modèle: {e}")
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
        except aiohttp.ClientError as e:
            logger.warning(f"Préchargement échoué (non critique): {e}")
        except Exception as e:
            logger.warning(f"Préchargement échoué (non critique): {e}")

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
        cache_key = self._generate_cache_key(request.content, request.extraction_type)

        # Vérifier le cache si activé
        if use_cache and self.cache_enabled and cache_key in self.cache:
            logger.info("Résultat trouvé dans le cache")
            return self.cache[cache_key]

        # Construire le prompt selon le type d'extraction
        prompt = self._build_prompt(request)

        try:
            async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json={"model": self.model_name, "prompt": prompt, **self.default_params}
            ) as resp:
                resp.raise_for_status()  # Lève une exception pour les codes d'état HTTP 4xx/5xx
                data = await resp.json()
                result = self._parse_response(data)
                if use_cache and self.cache_enabled:
                    self.cache[cache_key] = result
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Erreur lors de la génération de texte: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la génération de texte: {e}")
            raise

    @staticmethod
    def _generate_cache_key(content: str, extraction_type: str) -> str:
        """Génère une clé de cache basée sur le contenu et le type d'extraction"""
        return f"{hash(content)}_{extraction_type}"

    @staticmethod
    def _build_prompt(request: SFDAnalysisRequest) -> str:
        """Construit le prompt en fonction du type d'extraction"""
        # Logique de construction du prompt
        return f"Analyse SFD: {request.content}"

    @staticmethod
    def _parse_response(data: Dict) -> Dict:
        """Analyse la réponse JSON en scénarios de test"""
        # Logique de parsing de la réponse
        return {"scenarios": data.get("scenarios", [])}
