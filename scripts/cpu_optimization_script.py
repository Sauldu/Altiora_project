#!/usr/bin/env python3
"""
CPU Optimization Script for LoRA Adapters
Optimizes quantization, batch size, and inference parameters for ThinkPad i5-13500H
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

# Add project root
sys.path.append(str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CPUOptimizationConfig:
    """Configuration optimale pour CPU Intel i5-13500H"""
    # CPU cores configuration
    p_cores: int = 6  # Performance cores
    e_cores: int = 8  # Efficiency cores
    total_threads: int = 20
    
    # Memory settings
    max_memory_gb: int = 28  # Laisser 4GB pour l'OS
    
    # Quantization settings
    quantization_bits: int = 4  # 4-bit pour Qwen3
    quantization_type: str = "q4_K_M"  # Meilleur rapport qualité/taille
    
    # Batch settings par modèle
    batch_configs = {
        "qwen3": {
            "batch_size": 1,
            "max_seq_length": 2048,
            "num_threads": 12,  # P-cores only
            "context_size": 8192
        },
        "starcoder2": {
            "batch_size": 2,
            "max_seq_length": 1024,
            "num_threads": 8,
            "context_size": 4096
        }
    }
    
    # Inference optimization
    inference_settings = {
        "use_mmap": True,
        "use_mlock": False,  # False pour éviter lock mémoire
        "n_batch": 512,
        "n_gpu_layers": 0,  # CPU only
        "rope_freq_base": 1000000,
        "rope_freq_scale": 1.0
    }


class CPUOptimizer:
    """Optimise les paramètres CPU pour les modèles LoRA"""
    
    def __init__(self):
        self.config = CPUOptimizationConfig()
        self.ollama_host = "http://localhost:11434"
        self.results = {}
        
    def get_cpu_info(self) -> Dict:
        """Collecte les informations CPU"""
        info = {
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "memory_total": psutil.virtual_memory().total / (1024**3),
            "memory_available": psutil.virtual_memory().available / (1024**3)
        }
        
        # Détection P-cores vs E-cores (Intel 12th gen+)
        try:
            # Linux : analyse /proc/cpuinfo
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                # Heuristique : P-cores ont généralement une fréquence plus élevée
                info["has_hybrid_arch"] = "Efficient" in cpuinfo or self.config.total_threads > 16
        except:
            info["has_hybrid_arch"] = False
            
        return info
    
    def optimize_thread_affinity(self, model_type: str) -> List[int]:
        """Optimise l'affinité des threads CPU"""
        if model_type == "qwen3":
            # Utiliser uniquement les P-cores (0-5 physiques = 0-11 logiques)
            return list(range(0, 12))
        else:
            # StarCoder2 : mix P-cores et E-cores
            return list(range(0, 8))
    
    def calculate_optimal_batch_size(self, model_type: str, available_memory_gb: float) -> int:
        """Calcule la taille de batch optimale selon la mémoire"""
        model_memory_requirements = {
            "qwen3": 8.0,  # GB pour 32B quantifié
            "starcoder2": 4.0  # GB pour 15B quantifié
        }
        
        base_memory = model_memory_requirements.get(model_type, 6.0)
        overhead = 2.0  # GB pour l'overhead
        
        available_for_batches = available_memory_gb - base_memory - overhead
        batch_memory = 0.5  # GB par batch estimé
        
        optimal_batch = max(1, int(available_for_batches / batch_memory))
        
        # Limites de sécurité
        max_batch = self.config.batch_configs[model_type]["batch_size"]
        return min(optimal_batch, max_batch)
    
    async def benchmark_configuration(self, model_name: str, config: Dict) -> Dict:
        """Benchmark une configuration spécifique"""
        logger.info(f"Benchmark {model_name} avec config: {config}")
        
        # Préparer le test
        test_prompts = [
            "Analyse cette spec: formulaire login avec validation email",
            "Génère un test Playwright pour bouton submit",
            "Extrais les cas limites d'un panier e-commerce"
        ]
        
        results = {
            "config": config,
            "latencies": [],
            "tokens_per_second": [],
            "memory_usage": []
        }
        
        async with aiohttp.ClientSession() as session:
            for prompt in test_prompts:
                start_time = time.time()
                start_memory = psutil.virtual_memory().used / (1024**3)
                
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "options": {
                        "num_thread": config["num_threads"],
                        "num_ctx": config["context_size"],
                        "num_batch": config.get("n_batch", 512),
                        "num_predict": 256
                    }
                }
                
                try:
                    async with session.post(
                        f"{self.ollama_host}/api/generate",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            latency = time.time() - start_time
                            end_memory = psutil.virtual_memory().used / (1024**3)
                            
                            eval_count = data.get("eval_count", 0)
                            eval_duration = data.get("eval_duration", 1) / 1e9
                            
                            results["latencies"].append(latency)
                            results["tokens_per_second"].append(eval_count / eval_duration)
                            results["memory_usage"].append(end_memory - start_memory)
                
                except aiohttp.ClientError as e:
                    logger.error(f"Erreur benchmark: {e}")
        
        # Calculer les moyennes
        results["avg_latency"] = np.mean(results["latencies"]) if results["latencies"] else 0
        results["avg_tokens_per_second"] = np.mean(results["tokens_per_second"]) if results["tokens_per_second"] else 0
        results["avg_memory_usage"] = np.mean(results["memory_usage"]) if results["memory_usage"] else 0
        
        return results
    
    async def optimize_model(self, model_type: str, model_name: str) -> Dict:
        """Optimise un modèle spécifique"""
        logger.info(f"\n🔧 Optimisation {model_type}")
        
        cpu_info = self.get_cpu_info()
        base_config = self.config.batch_configs[model_type]
        
        # Configurations à tester
        test_configs = []
        
        # Varier le nombre de threads
        thread_counts = [4, 8, 12, 16] if model_type == "qwen3" else [4, 6, 8]
        
        for threads in thread_counts:
            # Varier la taille du contexte
            for ctx_multiplier in [0.5, 1.0, 1.5]:
                context_size = int(base_config["context_size"] * ctx_multiplier)
                
                # Varier n_batch
                for n_batch in [256, 512, 1024]:
                    config = {
                        "num_threads": threads,
                        "context_size": context_size,
                        "n_batch": n_batch,
                        "batch_size": self.calculate_optimal_batch_size(
                            model_type, 
                            cpu_info["memory_available"]
                        )
                    }
                    test_configs.append(config)
        
        # Benchmarker chaque configuration
        best_config = None
        best_score = 0
        
        for config in test_configs[:5]:  # Limiter pour gagner du temps
            result = await self.benchmark_configuration(model_name, config)
            
            # Score composite : tokens/s - (latency * 10)
            score = result["avg_tokens_per_second"] - (result["avg_latency"] * 10)
            
            if score > best_score:
                best_score = score
                best_config = {
                    "config": config,
                    "performance": {
                        "tokens_per_second": result["avg_tokens_per_second"],
                        "latency": result["avg_latency"],
                        "memory_usage": result["avg_memory_usage"]
                    }
                }
        
        return best_config
    
    def generate_ollama_modelfile(self, model_type: str, optimal_config: Dict) -> str:
        """Génère un Modelfile optimisé pour Ollama"""
        base_models = {
            "qwen3": "qwen3:32b-q4_K_M",
            "starcoder2": "starcoder2:15b-q8_0"
        }
        
        adapter_paths = {
            "qwen3": "data/models/lora_adapters/qwen3-sfd-analyzer-lora",
            "starcoder2": "data/models/lora_adapters/starcoder2-playwright-lora"
        }
        
        config = optimal_config["config"]
        
        modelfile = f"""FROM {base_models[model_type]}
ADAPTER {adapter_paths[model_type]}

# Optimisations CPU Intel i5-13500H
PARAMETER num_thread {config['num_threads']}
PARAMETER num_ctx {config['context_size']}
PARAMETER num_batch {config['n_batch']}
PARAMETER num_gpu 0

# Paramètres mémoire
PARAMETER use_mmap true
PARAMETER use_mlock false

# Paramètres d'inférence
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"

# System prompt optimisé
SYSTEM Tu es un expert optimisé pour CPU avec adaptateur LoRA spécialisé.
"""
        
        return modelfile
    
    async def run_optimization(self):
        """Lance l'optimisation complète"""
        logger.info("🚀 Démarrage optimisation CPU pour adapters LoRA")
        
        # Info système
        cpu_info = self.get_cpu_info()
        logger.info(f"CPU: {cpu_info['cpu_cores']} cores, {cpu_info['cpu_count']} threads")
        logger.info(f"RAM: {cpu_info['memory_total']:.1f}GB total, {cpu_info['memory_available']:.1f}GB disponible")
        
        # Optimiser chaque modèle
        models_to_optimize = [
            ("qwen3", "qwen3-sfd-analyzer-lora"),
            ("starcoder2", "starcoder2-playwright-lora")
        ]
        
        for model_type, model_name in models_to_optimize:
            optimal = await self.optimize_model(model_type, model_name)
            self.results[model_type] = optimal
            
            # Générer le Modelfile optimisé
            modelfile = self.generate_ollama_modelfile(model_type, optimal)
            
            # Sauvegarder
            output_path = Path(f"configs/optimized_{model_type}_modelfile")
            output_path.parent.mkdir(exist_ok=True)
            
            try:
                with open(output_path, "w") as f:
                    f.write(modelfile)
            except (IOError, OSError) as e:
                logger.error(f"Error writing Modelfile to {output_path}: {e}")
            
            logger.info(f"✅ Modelfile optimisé sauvé: {output_path}")
        
        # Rapport final
        self._print_optimization_report()
    
    def _print_optimization_report(self):
        """Affiche le rapport d'optimisation"""
        print("\n" + "="*80)
        logger.info("📊 RAPPORT D'OPTIMISATION CPU")
        print("="*80)
        
        for model_type, result in self.results.items():
            logger.info(f"\n🔸 {model_type.upper()}")
            logger.info(f"   Configuration optimale:")
            
            config = result["config"]
            perf = result["performance"]
            
            logger.info(f"   - Threads: {config['num_threads']}")
            logger.info(f"   - Contexte: {config['context_size']} tokens")
            logger.info(f"   - Batch interne: {config['n_batch']}")
            logger.info(f"   - Batch size: {config['batch_size']}")
            
            logger.info(f"\n   Performance:")
            logger.info(f"   - Vitesse: {perf['tokens_per_second']:.1f} tokens/s")
            logger.info(f"   - Latence: {perf['latency']:.2f}s")
            logger.info(f"   - RAM utilisée: {perf['memory_usage']:.1f}GB")
        
        logger.info("\n💡 Recommandations:")
        logger.info("1. Utiliser les Modelfiles optimisés dans configs/")
        logger.info("2. Fermer les applications gourmandes en RAM")
        logger.info("3. Désactiver le turbo boost si surchauffe")
        logger.info("4. Monitorer avec htop pendant l'inférence")


async def main():
    optimizer = CPUOptimizer()
    await optimizer.run_optimization()


if __name__ == "__main__":
    asyncio.run(main())
