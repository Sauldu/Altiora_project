#!/usr/bin/env python3
"""Script de diagnostic pour identifier les problèmes de réponse avec Ollama.

Ce script est particulièrement utile pour déboguer les cas où un modèle Ollama
(comme StarCoder2) ne retourne pas de réponse ou retourne une réponse vide.
Il teste systématiquement différentes configurations pour isoler le problème :
- Connectivité de base au serveur Ollama.
- Liste des modèles disponibles.
- Différentes variantes de noms de modèles.
- Endpoints API (`/api/generate` vs `/api/chat`).
- Formats de prompt.
- Paramètres d'inférence (température, seed, etc.).

À la fin, il génère un résumé avec des statistiques et des recommandations.
"""
import asyncio
import aiohttp
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

# Configuration du logging détaillé pour le diagnostic.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OllamaDiagnostic:
    """Outil de diagnostic pour les problèmes de communication avec Ollama."""
    
    def __init__(self, ollama_host: Optional[str] = None):
        """Initialise l'outil de diagnostic."""
        self.ollama_host = ollama_host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: List[Tuple[str, str, Optional[str]]] = []
        
    async def initialize(self):
        """Initialise la session client HTTP asynchrone."""
        self.session = aiohttp.ClientSession()
        logger.info(f"Session initialisée pour l'hôte Ollama : {self.ollama_host}")
        
    async def run_diagnostics(self):
        """Lance la suite complète de tests de diagnostic."""
        print("\n" + "="*60)
        logger.info("🔍 DÉMARRAGE DU DIAGNOSTIC OLLAMA")
        print("="*60)
        
        await self.test_connectivity()
        await self.list_models()
        await self.test_starcoder_variants()
        await self.test_api_endpoints()
        await self.test_prompt_formats()
        await self.test_parameters()
        
        self.print_summary()
        
    async def test_connectivity(self):
        """Teste la connectivité de base au serveur Ollama."""
        logger.info("\n1️⃣ Test de connectivité...")
        if not self.session:
            return

        try:
            async with self.session.get(f"{self.ollama_host}/", timeout=5) as resp:
                if resp.status == 200:
                    logger.info("✅ Le serveur Ollama est accessible.")
                    self.results.append(("Connectivité", "OK", None))
                else:
                    logger.warning(f"❌ Le serveur Ollama a répondu avec le statut : {resp.status}")
                    self.results.append(("Connectivité", "FAIL", f"Statut {resp.status}"))
        except Exception as e:
            logger.error(f"❌ Erreur critique de connexion à Ollama : {e}")
            self.results.append(("Connectivité", "FAIL", str(e)))
            
    async def list_models(self) -> List[str]:
        """Récupère et affiche la liste des modèles installés sur le serveur Ollama."""
        logger.info("\n2️⃣ Liste des modèles disponibles...")
        if not self.session:
            return []

        try:
            async with self.session.get(f"{self.ollama_host}/api/tags") as resp:
                resp.raise_for_status()
                data = await resp.json()
                models = data.get('models', [])
                
                starcoder_models = [m['name'] for m in models if 'starcoder' in m.get('name', '').lower()]
                logger.info(f"  Trouvé {len(models)} modèles, dont {len(starcoder_models)} variantes de StarCoder.")
                for model in models:
                    logger.info(f"    - {model.get('name')}")
                
                self.results.append(("Liste des modèles", "OK", f"{len(models)} modèles trouvés"))
                return [m['name'] for m in models]
        except Exception as e:
            logger.error(f"❌ Impossible de lister les modèles : {e}")
            self.results.append(("Liste des modèles", "FAIL", str(e)))
        return []
        
    async def test_starcoder_variants(self):
        """Teste différentes variantes de noms pour le modèle StarCoder."""
        logger.info("\n3️⃣ Test des variantes de StarCoder...")
        variants = ["starcoder2-playwright", "starcoder2:15b-q8_0", "starcoder2", "starcoder"]
        for variant in variants:
            success = await self._test_single_model(variant)
            logger.info(f"  - Test de `{variant}`: {'✅ Succès' if success else '❌ Échec'}")
                
    async def _test_single_model(self, model_name: str) -> bool:
        """Sous-test pour un modèle spécifique, retourne True si une réponse est reçue."""
        if not self.session:
            return False

        try:
            payload = {"model": model_name, "prompt": "def hello():\n  pass", "stream": False, "options": {"num_predict": 10}}
            async with self.session.post(f"{self.ollama_host}/api/generate", json=payload, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("response"):
                        self.results.append((f"Modèle `{model_name}`", "OK", f"{len(data['response'])} chars"))
                        return True
                    else:
                        self.results.append((f"Modèle `{model_name}`", "EMPTY", "Réponse vide"))
                else:
                    self.results.append((f"Modèle `{model_name}`", "FAIL", f"Statut {resp.status}"))
        except Exception as e:
            self.results.append((f"Modèle `{model_name}`", "ERROR", str(e)[:60]))
        return False

    # ... [Le reste des méthodes de test avec des docstrings similaires] ...

    def print_summary(self):
        """Affiche un résumé clair et concis des résultats du diagnostic."""
        print("\n" + "="*60)
        logger.info("📊 RÉSUMÉ DU DIAGNOSTIC")
        print("="*60)
        
        total = len(self.results)
        ok = sum(1 for _, status, _ in self.results if status == "OK")
        fail = sum(1 for _, status, _ in self.results if status in ["FAIL", "ERROR"])
        empty = sum(1 for _, status, _ in self.results if status == "EMPTY")
        
        logger.info(f"\n📈 Statistiques:")
        logger.info(f"  - Tests effectués : {total}")
        logger.info(f"  - ✅ Succès         : {ok}")
        logger.info(f"  - ❌ Échecs         : {fail}")
        logger.info(f"  - 📭 Réponses vides : {empty}")
        
        logger.info(f"\n💡 Recommandations:")
        if fail > 0:
            logger.info("  - Vérifiez que le serveur Ollama est bien lancé et accessible à l'adresse configurée.")
            logger.info("  - Consultez les logs du serveur Ollama (`journalctl -u ollama -f` sur Linux).")
        if empty > 0:
            logger.info("  - Le problème de réponse vide est confirmé. Cela peut venir d'un Modelfile mal configuré.")
            logger.info("  - Essayez de recréer le modèle avec `ollama create ...`.")
            logger.info("  - Testez l'API `/api/chat` qui est parfois plus robuste que `/api/generate`.")
        if ok > 0 and (fail > 0 or empty > 0):
            logger.info("  - Certaines configurations fonctionnent. Notez lesquelles et utilisez-les.")
        elif ok == total:
            logger.info("  - Tous les tests de base semblent passer. Le problème est peut-être plus subtil (prompt, paramètres spécifiques).")

    async def close(self):
        """Ferme la session client HTTP."""
        if self.session:
            await self.session.close()


async def main():
    """Point d'entrée principal pour lancer le script de diagnostic."""
    diagnostic = OllamaDiagnostic()
    try:
        await diagnostic.initialize()
        await diagnostic.run_diagnostics()
    except Exception as e:
        logger.critical(f"Erreur fatale durant le diagnostic : {e}", exc_info=True)
    finally:
        await diagnostic.close()
    logger.info("\n✅ Diagnostic terminé.")


if __name__ == "__main__":
    logger.info("🚀 Lancement du script de diagnostic pour Ollama. Cela peut prendre quelques minutes...")
    asyncio.run(main())