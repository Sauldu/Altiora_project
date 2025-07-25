#!/usr/bin/env python3
"""
Script de diagnostic pour identifier le problème de réponse vide avec StarCoder2
Teste différentes configurations et approches
"""
import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Configuration du logging détaillé
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OllamaDiagnostic:
    """Outil de diagnostic pour les problèmes Ollama"""
    
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.session = None
        self.results = []
        
    async def initialize(self):
        """Initialise la session HTTP"""
        self.session = aiohttp.ClientSession()
        logger.info(f"Session initialisée pour {self.ollama_host}")
        
    async def run_diagnostics(self):
        """Lance tous les tests de diagnostic"""
        print("\n" + "="*60)
        logger.info("🔍 DIAGNOSTIC OLLAMA - STARCODER2")
        print("="*60)
        
        # 1. Test de connectivité
        await self.test_connectivity()
        
        # 2. Lister les modèles disponibles
        await self.list_models()
        
        # 3. Tester différents modèles StarCoder
        await self.test_starcoder_variants()
        
        # 4. Tester différentes APIs
        await self.test_api_endpoints()
        
        # 5. Tester différents formats de prompt
        await self.test_prompt_formats()
        
        # 6. Tester les paramètres
        await self.test_parameters()
        
        # 7. Afficher le résumé
        self.print_summary()
        
    async def test_connectivity(self):
        """Test de base de la connectivité Ollama"""
        logger.info("\n1️⃣ Test de connectivité")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{self.ollama_host}/") as resp:
                if resp.status == 200:
                    logger.info("✅ Ollama accessible")
                    self.results.append(("Connectivité", "OK", None))
                else:
                    logger.info(f"❌ Status: {resp.status}")
                    self.results.append(("Connectivité", "FAIL", f"Status {resp.status}"))
        except Exception as e:
            logger.info(f"❌ Erreur de connexion: {e}")
            self.results.append(("Connectivité", "FAIL", str(e)))
            
    async def list_models(self):
        """Liste tous les modèles disponibles"""
        logger.info("\n2️⃣ Modèles disponibles")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{self.ollama_host}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = data.get('models', [])
                    
                    starcoder_models = []
                    for model in models:
                        name = model.get('name', '')
                        if 'starcoder' in name.lower() or 'star' in name.lower():
                            starcoder_models.append(name)
                            logger.info(f"  🌟 {name} ({model.get('size', 'N/A')})")
                        else:
                            logger.info(f"  • {name}")
                    
                    self.results.append(("Modèles trouvés", f"{len(models)}", 
                                       f"StarCoder: {len(starcoder_models)}"))
                    return starcoder_models
        except Exception as e:
            logger.info(f"❌ Erreur: {e}")
            self.results.append(("Liste modèles", "FAIL", str(e)))
        return []
        
    async def test_starcoder_variants(self):
        """Teste différentes variantes de StarCoder"""
        logger.info("\n3️⃣ Test des variantes StarCoder")
        print("-" * 40)
        
        variants = [
            "starcoder2-playwright",
            "starcoder2:15b-q8_0",
            "starcoder:3b",
            "starcoder2",
            "starcoder"
        ]
        
        for variant in variants:
            success = await self.test_single_model(variant)
            if success:
                logger.info(f"  ✅ {variant} - Fonctionne")
            else:
                logger.info(f"  ❌ {variant} - Échec")
                
    async def test_single_model(self, model_name: str) -> bool:
        """Teste un modèle spécifique"""
        try:
            # Test simple avec /api/generate
            payload = {
                "model": model_name,
                "prompt": "def hello():\n    return",
                "stream": False,
                "options": {"num_predict": 20}
            }
            
            async with self.session.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", "")
                    if response:
                        self.results.append((f"Modèle {model_name}", "OK", 
                                           f"{len(response)} chars"))
                        return True
                    else:
                        self.results.append((f"Modèle {model_name}", "EMPTY", 
                                           "Réponse vide"))
                else:
                    self.results.append((f"Modèle {model_name}", "FAIL", 
                                       f"Status {resp.status}"))
        except asyncio.TimeoutError:
            self.results.append((f"Modèle {model_name}", "TIMEOUT", "10s"))
        except Exception as e:
            self.results.append((f"Modèle {model_name}", "ERROR", str(e)[:50]))
        return False
        
    async def test_api_endpoints(self):
        """Teste les différents endpoints API"""
        logger.info("\n4️⃣ Test des endpoints API")
        print("-" * 40)
        
        # Trouver un modèle qui marche
        test_model = "starcoder2:15b-q8_0"  # Par défaut
        
        # Test /api/generate
        logger.info("\n  📍 Test /api/generate:")
        response_gen = await self.test_generate_api(test_model)
        
        # Test /api/chat
        logger.info("\n  📍 Test /api/chat:")
        response_chat = await self.test_chat_api(test_model)
        
        # Comparer les résultats
        if response_gen and response_chat:
            logger.info(f"\n  📊 Comparaison:")
            logger.info(f"     Generate: {len(response_gen)} caractères")
            logger.info(f"     Chat: {len(response_chat)} caractères")
            
    async def test_generate_api(self, model: str) -> Optional[str]:
        """Teste l'API /generate"""
        payloads = [
            # Format basique
            {
                "model": model,
                "prompt": "Generate a simple Playwright test:\n```python\n",
                "stream": False
            },
            # Avec system
            {
                "model": model,
                "prompt": "Generate a simple Playwright test",
                "system": "You are a Python test automation expert.",
                "stream": False
            },
            # Avec options complètes
            {
                "model": model,
                "prompt": "# Playwright test for login\ndef test_login(page):\n",
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 200,
                    "stop": ["```", "\n\n\n"]
                }
            }
        ]
        
        for i, payload in enumerate(payloads):
            try:
                logger.debug(f"Test payload {i+1}: {json.dumps(payload, indent=2)}")
                
                async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    raw = await resp.text()
                    logger.debug(f"Raw response: {raw[:200]}")
                    
                    if resp.status == 200:
                        data = json.loads(raw)
                        response = data.get("response", "")
                        if response:
                            logger.info(f"    ✅ Format {i+1}: {len(response)} chars")
                            self.results.append((f"Generate format {i+1}", "OK", 
                                               f"{len(response)} chars"))
                            return response
                        else:
                            logger.info(f"    ❌ Format {i+1}: Réponse vide")
                            logger.debug(f"Clés disponibles: {list(data.keys())}")
                    else:
                        logger.info(f"    ❌ Format {i+1}: Status {resp.status}")
            except Exception as e:
                logger.info(f"    ❌ Format {i+1}: {type(e).__name__}")
                logger.error(f"Erreur: {e}")
        
        return None
        
    async def test_chat_api(self, model: str) -> Optional[str]:
        """Teste l'API /chat"""
        payloads = [
            # Format simple
            {
                "model": model,
                "messages": [
                    {"role": "user", "content": "Generate a Playwright test for login"}
                ],
                "stream": False
            },
            # Avec system message
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a test automation expert."},
                    {"role": "user", "content": "Write a Playwright test"}
                ],
                "stream": False
            },
            # Avec options
            {
                "model": model,
                "messages": [
                    {"role": "user", "content": "Create async def test_example(page):"}
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 200}
            }
        ]
        
        for i, payload in enumerate(payloads):
            try:
                async with self.session.post(
                    f"{self.ollama_host}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("message", {}).get("content", "")
                        if content:
                            logger.info(f"    ✅ Format {i+1}: {len(content)} chars")
                            self.results.append((f"Chat format {i+1}", "OK", 
                                               f"{len(content)} chars"))
                            return content
                        else:
                            logger.info(f"    ❌ Format {i+1}: Contenu vide")
                    else:
                        logger.info(f"    ❌ Format {i+1}: Status {resp.status}")
            except Exception as e:
                logger.info(f"    ❌ Format {i+1}: {type(e).__name__}")
                
        return None
        
    async def test_prompt_formats(self):
        """Teste différents formats de prompts"""
        logger.info("\n5️⃣ Test des formats de prompt")
        print("-" * 40)
        
        model = "starcoder2:15b-q8_0"  # Utiliser le modèle de base
        
        prompts = [
            # Code completion style
            ("Code completion", "def test_login(page):\n    # Test login functionality\n    "),
            
            # Instruction style
            ("Instruction", "Write a Playwright test function that checks if a button is clickable"),
            
            # Markdown style
            ("Markdown", "```python\n# Playwright test\nasync def test_"),
            
            # Comment style
            ("Comment", "# TODO: Create a Playwright test for form submission\n# The test should:\n# 1. Navigate to /form\n# 2. Fill the form\n# 3. Submit\n\ndef test_"),
            
            # Template style
            ("Template", "[INST] Generate a Playwright test [/INST]\n"),
        ]
        
        for name, prompt in prompts:
            logger.info(f"\n  🧪 Test: {name}")
            response = await self.test_prompt_response(model, prompt)
            if response:
                logger.info(f"    ✅ Réponse: {len(response)} caractères")
                logger.info(f"    📝 Extrait: {response[:100]}...")
            else:
                logger.info(f"    ❌ Pas de réponse")
                
    async def test_prompt_response(self, model: str, prompt: str) -> Optional[str]:
        """Teste un prompt spécifique"""
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 100
                }
            }
            
            async with self.session.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "")
        except Exception as e:
            logger.error(f"Erreur test prompt: {e}")
        return None
        
    async def test_parameters(self):
        """Teste différentes combinaisons de paramètres"""
        logger.info("\n6️⃣ Test des paramètres")
        print("-" * 40)
        
        model = "starcoder2:15b-q8_0"
        base_prompt = "def calculate_sum(a, b):\n    "
        
        param_sets = [
            {"name": "Default", "params": {}},
            {"name": "Low temp", "params": {"temperature": 0.1}},
            {"name": "High predict", "params": {"num_predict": 500}},
            {"name": "With seed", "params": {"seed": 42, "temperature": 0.2}},
            {"name": "Full context", "params": {"num_ctx": 4096, "num_predict": 200}},
        ]
        
        for param_set in param_sets:
            logger.info(f"\n  ⚙️ {param_set['name']}: ", end="")
            
            try:
                payload = {
                    "model": model,
                    "prompt": base_prompt,
                    "stream": False,
                    "options": param_set['params']
                }
                
                async with self.session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response = data.get("response", "")
                        if response:
                            logger.info(f"✅ {len(response)} chars")
                            self.results.append((f"Params: {param_set['name']}", 
                                               "OK", f"{len(response)} chars"))
                        else:
                            logger.info("❌ Réponse vide")
                            self.results.append((f"Params: {param_set['name']}", 
                                               "EMPTY", "0 chars"))
                    else:
                        logger.info(f"❌ Status {resp.status}")
            except Exception as e:
                logger.info(f"❌ {type(e).__name__}")
                
    def print_summary(self):
        """Affiche un résumé des résultats"""
        print("\n" + "="*60)
        logger.info("📊 RÉSUMÉ DU DIAGNOSTIC")
        print("="*60)
        
        # Statistiques
        total_tests = len(self.results)
        successful = sum(1 for _, status, _ in self.results if status == "OK")
        failed = sum(1 for _, status, _ in self.results if status in ["FAIL", "ERROR"])
        empty = sum(1 for _, status, _ in self.results if status == "EMPTY")
        
        logger.info(f"\n📈 Statistiques:")
        logger.info(f"  • Tests totaux: {total_tests}")
        logger.info(f"  • ✅ Réussis: {successful}")
        logger.info(f"  • ❌ Échoués: {failed}")
        logger.info(f"  • 📭 Vides: {empty}")
        
        # Recommandations
        logger.info(f"\n💡 Recommandations:")
        
        if empty > 0:
            logger.info("  1. Le problème de réponse vide est confirmé")
            logger.info("  2. Essayer l'API /chat au lieu de /generate")
            logger.info("  3. Vérifier les logs Ollama: journalctl -u ollama -f")
            
        if successful > 0:
            logger.info("  4. Certaines configurations fonctionnent")
            logger.info("  5. Utiliser les paramètres qui ont réussi")
            
        # Détails des échecs
        if failed > 0 or empty > 0:
            logger.info(f"\n⚠️ Détails des problèmes:")
            for test, status, detail in self.results:
                if status in ["FAIL", "ERROR", "EMPTY"]:
                    logger.info(f"  • {test}: {status} - {detail}")
                    
    async def close(self):
        """Ferme la session"""
        if self.session:
            await self.session.close()


# Fonction principale
async def main():
    """Lance le diagnostic complet"""
    diagnostic = OllamaDiagnostic()
    
    try:
        await diagnostic.initialize()
        await diagnostic.run_diagnostics()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
    finally:
        await diagnostic.close()
        
    logger.info("\n✅ Diagnostic terminé")
    logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    logger.info("🚀 Lancement du diagnostic Ollama/StarCoder2")
    logger.info("Cela peut prendre quelques minutes...")
    asyncio.run(main())
