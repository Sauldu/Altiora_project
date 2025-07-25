#!/usr/bin/env python3
"""Script d'optimisation des performances CPU pour les adaptateurs LoRA.

Ce script est spécifiquement conçu pour optimiser les paramètres d'inférence
des modèles de langage (comme Qwen3 et StarCoder2) avec des adaptateurs LoRA
sur un CPU Intel i5-13500H. Il benchmarke différentes configurations de threads,
de taille de contexte et de batch pour trouver le meilleur compromis entre
vitesse (tokens/s) et latence.

Le script génère ensuite des `Modelfile` pour Ollama contenant les paramètres
optimaux.
"""

import os
import sys
import json
import time
import psutil
import torch
import asyncio
import aiohttp
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor

# Ajoute la racine du projet au path pour permettre les imports relatifs.
sys.path.append(str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class CPUOptimizationConfig:
    """Configuration de base pour l'optimisation sur un CPU Intel i5-13500H."""
    # Configuration des cœurs CPU
    p_cores: int = 6  # Performance-cores
    e_cores: int = 8  # Efficiency-cores
    total_threads: int = 20
    
    # Paramètres mémoire
    max_memory_gb: int = 28  # Laisse 4GB pour le système d'exploitation
    
    # Paramètres de quantification
    quantization_bits: int = 4
    quantization_type: str = "q4_K_M"  # Bon compromis qualité/taille
    
    # Configurations de batch par défaut par modèle
    batch_configs = {
        "qwen3": {
            "batch_size": 1,
            "max_seq_length": 2048,
            "num_threads": 12,  # P-cores uniquement par défaut
            "context_size": 8192
        },
        "starcoder2": {
            "batch_size": 2,
            "max_seq_length": 1024,
            "num_threads": 8,
            "context_size": 4096
        }
    }
    
    # Paramètres d'inférence généraux
    inference_settings = {
        "use_mmap": True,
        "use_mlock": False,  # False pour éviter de "locker" la mémoire
        "n_batch": 512,
        "n_gpu_layers": 0,  # CPU uniquement
        "rope_freq_base": 1000000,
        "rope_freq_scale": 1.0
    }


class CPUOptimizer:
    """Optimise les paramètres d'inférence des modèles LoRA pour le CPU."""
    
    def __init__(self):
        self.config = CPUOptimizationConfig()
        self.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.results = {}
        
    def get_cpu_info(self) -> Dict:
        """Collecte et retourne les informations sur le CPU et la mémoire."""
        info = {
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "memory_total": psutil.virtual_memory().total / (1024**3),
            "memory_available": psutil.virtual_memory().available / (1024**3)
        }
        return info
    
    async def benchmark_configuration(self, model_name: str, config: Dict) -> Dict:
        """Benchmark une configuration spécifique en envoyant des requêtes à Ollama."""
        logger.info(f"Benchmark de {model_name} avec config: {config}")
        
        test_prompts = [
            "Analyse cette spec: formulaire login avec validation email",
            "Génère un test Playwright pour un bouton submit",
            "Extrais les cas limites d'un panier e-commerce"
        ]
        
        results = {
            "config": config,
            "latencies": [],
            "tokens_per_second": [],
            "memory_usage_gb": []
        }
        
        async with aiohttp.ClientSession() as session:
            for prompt in test_prompts:
                start_time = time.time()
                start_memory_gb = psutil.virtual_memory().used / (1024**3)
                
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_thread": config['num_threads'],
                        "num_ctx": config['context_size'],
                        "num_batch": config.get('n_batch', 512),
                        "num_predict": 256
                    }
                }
                
                try:
                    async with session.post(
                        f"{self.ollama_host}/api/generate",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=120) # Timeout plus long
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            latency = time.time() - start_time
                            end_memory_gb = psutil.virtual_memory().used / (1024**3)
                            
                            eval_count = data.get("eval_count", 0)
                            eval_duration_ns = data.get("eval_duration", 1)
                            tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0
                            
                            results["latencies"].append(latency)
                            results["tokens_per_second"].append(tps)
                            results["memory_usage_gb"].append(end_memory_gb - start_memory_gb)
                        else:
                            logger.warning(f"Erreur de benchmark (status {resp.status}) pour {model_name}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout lors du benchmark de {model_name} avec prompt: {prompt[:30]}...")
                except aiohttp.ClientError as e:
                    logger.error(f"Erreur de client AIOHTTP durant le benchmark: {e}")
        
        # Calcule les moyennes pour le rapport.
        results["avg_latency"] = np.mean(results["latencies"]) if results["latencies"] else 0
        results["avg_tokens_per_second"] = np.mean(results["tokens_per_second"]) if results["tokens_per_second"] else 0
        results["avg_memory_usage_gb"] = np.mean(results["memory_usage_gb"]) if results["memory_usage_gb"] else 0
        
        return results
    
    async def optimize_model(self, model_type: str, model_name: str) -> Optional[Dict]:
        """Teste plusieurs configurations pour un modèle et retourne la meilleure."""
        logger.info(f"\n🔧 Optimisation de {model_type} ({model_name})...")
        
        base_config = self.config.batch_configs[model_type]
        
        # Grille de recherche pour les hyperparamètres.
        test_configs = []
        thread_counts = [4, 8, 12, 16] if model_type == "qwen3" else [4, 6, 8]
        for threads in thread_counts:
            for ctx_multiplier in [0.5, 1.0]:
                for n_batch in [256, 512, 1024]:
                    config = {
                        "num_threads": threads,
                        "context_size": int(base_config["context_size"] * ctx_multiplier),
                        "n_batch": n_batch,
                    }
                    test_configs.append(config)
        
        best_config = None
        best_score = -float('inf')
        
        # Limite le nombre de benchmarks pour un test rapide.
        for config in test_configs[:5]:
            result = await self.benchmark_configuration(model_name, config)
            
            # Score composite: tokens/s pondérés, pénalisé par la latence.
            score = result["avg_tokens_per_second"] - (result["avg_latency"] * 5)
            
            if score > best_score:
                best_score = score
                best_config = {
                    "config": config,
                    "performance": {
                        "tokens_per_second": result["avg_tokens_per_second"],
                        "latency": result["avg_latency"],
                        "memory_usage_gb": result["avg_memory_usage_gb"]
                    }
                }
        
        return best_config
    
    def generate_ollama_modelfile(self, model_type: str, optimal_config: Dict) -> str:
        """Génère un contenu de `Modelfile` optimisé pour Ollama."""
        base_models = {
            "qwen3": "qwen3:32b-q4_K_M",
            "starcoder2": "starcoder2:15b-q8_0"
        }
        adapter_paths = {
            "qwen3": "./data/models/lora_adapters/qwen3-sfd-analyzer-lora",
            "starcoder2": "./data/models/lora_adapters/starcoder2-playwright-lora"
        }
        
        config = optimal_config["config"]
        
        modelfile_content = f"""FROM {base_models[model_type]}
ADAPTER {adapter_paths[model_type]}

# --- Paramètres optimisés pour CPU Intel i5-13500H ---
PARAMETER num_thread {config['num_threads']}
PARAMETER num_ctx {config['context_size']}
PARAMETER num_batch {config['n_batch']}
PARAMETER num_gpu 0

# Paramètres mémoire
PARAMETER use_mmap true
PARAMETER use_mlock false

# Paramètres d'inférence standards
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"

SYSTEM Tu es un expert en génération de code et analyse de spécifications, optimisé pour tourner sur CPU avec un adaptateur LoRA.
"""
        return modelfile_content
    
    async def run_optimization(self):
        """Lance le processus d'optimisation complet."""
        logger.info("🚀 Démarrage de l'optimisation CPU pour les adaptateurs LoRA")
        
        cpu_info = self.get_cpu_info()
        logger.info(f"CPU: {cpu_info['cpu_cores']} cœurs, {cpu_info['cpu_count']} threads")
        logger.info(f"RAM: {cpu_info['memory_total']:.1f}GB total, {cpu_info['memory_available']:.1f}GB disponible")
        
        models_to_optimize = [
            ("qwen3", "qwen3-sfd-analyzer-lora"),
            ("starcoder2", "starcoder2-playwright-lora")
        ]
        
        for model_type, model_name in models_to_optimize:
            optimal_config = await self.optimize_model(model_type, model_name)
            if not optimal_config:
                logger.error(f"Échec de l'optimisation pour {model_type}. Passage au suivant.")
                continue

            self.results[model_type] = optimal_config
            modelfile_str = self.generate_ollama_modelfile(model_type, optimal_config)
            
            output_path = Path(f"configs/ollama_optimized_{model_type}.yaml")
            output_path.parent.mkdir(exist_ok=True)
            
            try:
                output_path.write_text(modelfile_str, encoding='utf-8')
                logger.info(f"✅ Modelfile optimisé sauvegardé : {output_path}")
            except (IOError, OSError) as e:
                logger.error(f"Erreur lors de l'écriture du Modelfile sur {output_path}: {e}")
        
        self._print_optimization_report()
    
    def _print_optimization_report(self):
        """Affiche un rapport final avec les résultats de l'optimisation."""
        print("\n" + "="*80)
        logger.info("📊 RAPPORT FINAL D'OPTIMISATION CPU")
        print("="*80)
        
        for model_type, result in self.results.items():
            logger.info(f"\n🔸 MODÈLE : {model_type.upper()}")
            config = result["config"]
            perf = result["performance"]
            
            logger.info(f"   Configuration Optimale:")
            logger.info(f"   - Threads CPU       : {config['num_threads']}")
            logger.info(f"   - Taille du contexte: {config['context_size']} tokens")
            logger.info(f"   - Batch interne (n_batch): {config['n_batch']}")
            
            logger.info(f"\n   Performance Estimée:")
            logger.info(f"   - Vitesse (tokens/s): {perf['tokens_per_second']:.1f}")
            logger.info(f"   - Latence par requête: {perf['latency']:.2f}s")
            logger.info(f"   - Utilisation RAM   : {perf['memory_usage_gb']:.2f}GB")
        
        logger.info("\n💡 Recommandations:")
        logger.info("1. Utilisez les Modelfiles générés dans `configs/` pour créer vos modèles Ollama.")
        logger.info("   (ex: `ollama create mon-qwen3-optimise -f configs/ollama_optimized_qwen3.yaml`)")
        logger.info("2. Assurez-vous de fermer les applications gourmandes en RAM avant l'inférence.")
        logger.info("3. Surveillez la température du CPU avec `htop` ou un outil similaire.")


async def main():
    optimizer = CPUOptimizer()
    await optimizer.run_optimization()


if __name__ == "__main__":
    asyncio.run(main())