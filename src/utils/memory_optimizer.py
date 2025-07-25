# src/utils/memory_optimizer.py
"""Optimiseur de mémoire pour Altiora.

Ce module fournit des utilitaires pour gérer l'utilisation de la mémoire,
particulièrement utile pour les applications gourmandes en ressources comme
les modèles d'IA. Il inclut des fonctionnalités de suivi de la mémoire,
de cache compressé et de mappage mémoire pour les grands fichiers.
"""

import gc
import mmap
import os
import pickle
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import lz4.frame
import psutil

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# API Publique
# ------------------------------------------------------------------

class MemoryOptimizer:
    """Aide centrale pour maintenir l'utilisation de la mémoire sous une limite définie."""

    def __init__(self, max_memory_gb: float = 25.0):
        """Initialise l'optimiseur de mémoire.

        Args:
            max_memory_gb: La limite maximale de mémoire en gigaoctets que le processus peut utiliser.
        """
        self.max_memory_bytes = max_memory_gb * 1024 ** 3
        self.process = psutil.Process() # Référence au processus courant.
        logger.info(f"MemoryOptimizer initialisé avec une limite de {max_memory_gb} Go.")

    # ------------------------------------------------------------------
    # Gestionnaire de contexte pour le suivi de la mémoire et le GC
    # ------------------------------------------------------------------
    class track:
        """Gestionnaire de contexte asynchrone pour suivre l'utilisation de la mémoire.

        Utilisation:
        ```python
        async with memory_optimizer.track("sfd_analysis"):
            # Code gourmand en mémoire ici.
            pass
        ```
        """
        def __init__(self, name: str, optimizer: "MemoryOptimizer"):
            """Initialise le traqueur de mémoire."

            Args:
                name: Un nom descriptif pour l'opération suivie.
                optimizer: L'instance de `MemoryOptimizer`.
            """
            self.name = name
            self.opt = optimizer
            self.start: int = 0

        async def __aenter__(self):
            """Entre dans le bloc `async with`. Collecte le garbage et enregistre l'utilisation initiale de la mémoire."""
            gc.collect() # Force le garbage collection avant de commencer.
            self.start = self.opt.process.memory_info().rss
            logger.debug(f"[MEM] Début du suivi pour '{self.name}'. Utilisation initiale : {self.start / (1024**2):.1f} MB")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            """Quitte le bloc `async with`. Collecte le garbage et enregistre le pic de mémoire."""
            gc.collect()
            peak = self.opt.process.memory_info().rss
            delta_mb = (peak - self.start) / 1024 ** 2
            if delta_mb > 100:  # Loggue seulement les augmentations significatives.
                logger.info(f"[MEM] {self.name}: Augmentation de {delta_mb:.1f} MB. Utilisation finale : {peak / (1024**2):.1f} MB")
            else:
                logger.debug(f"[MEM] {self.name}: Changement de {delta_mb:.1f} MB. Utilisation finale : {peak / (1024**2):.1f} MB")

    # ------------------------------------------------------------------
    # Cache compressé transparent
    # ------------------------------------------------------------------
    class CompressedCache:
        """Cache en mémoire/disque qui compresse les données volumineuses.

        Agit comme un remplacement pour un dictionnaire ou Redis lorsque les données
        sont très grandes. Les éléments sont compressés et stockés sur disque,
        avec une gestion LRU pour l'éviction.
        """

        def __init__(self, cache_dir: Path, max_items: int = 50):
            """Initialise le cache compressé."

            Args:
                cache_dir: Le répertoire où les fichiers compressés seront stockés.
                max_items: Le nombre maximal d'éléments à conserver dans le cache (LRU).
            """
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.max_items = max_items
            self._lru: Dict[str, Path] = {}  # key -> file path (pour la gestion LRU).
            logger.info(f"Cache compressé initialisé dans {self.cache_dir} avec {max_items} éléments max.")

        def _key_path(self, key: str) -> Path:
            """Génère un chemin de fichier sûr pour une clé donnée."""
            safe_key = "".join(c if c.isalnum() else "_" for c in key) # Assainit la clé pour le nom de fichier.
            return self.cache_dir / f"{safe_key}.lz4"

        def get(self, key: str) -> Optional[Any]:
            """Récupère un élément du cache."

            Args:
                key: La clé de l'élément à récupérer.

            Returns:
                L'élément décompressé si trouvé, sinon None.
            """
            path = self._key_path(key)
            if not path.exists():
                return None
            try:
                with lz4.frame.open(path, "rb") as f:
                    value = pickle.load(f)
                self._lru.pop(key, None) # Met à jour l'ordre LRU.
                self._lru[key] = path
                return value
            except (IOError, OSError, lz4.frame.LZ4FrameError, pickle.PickleError) as e:
                logger.warning(f"Erreur lors de la lecture du cache compressé {path}: {e}")
                path.unlink(missing_ok=True) # Supprime le fichier corrompu.
                return None

        def set(self, key: str, value: Any) -> None:
            """Stocke un élément dans le cache."

            Args:
                key: La clé de l'élément.
                value: La valeur à stocker.
            """
            path = self._key_path(key)
            try:
                with lz4.frame.open(path, "wb") as f:
                    pickle.dump(value, f)
                self._lru[key] = path
                # Éviction LRU si le cache dépasse la taille maximale.
                if len(self._lru) > self.max_items:
                    oldest_key = next(iter(self._lru)) # Récupère la clé la plus ancienne.
                    self._lru.pop(oldest_key).unlink(missing_ok=True) # Supprime l'élément le plus ancien.
            except (IOError, OSError, lz4.frame.LZ4FrameError, pickle.PickleError) as e:
                logger.error(f"Erreur lors de l'écriture dans le cache compressé {path}: {e}")

    # ------------------------------------------------------------------
    # Mappage mémoire pour les chaînes/fichiers volumineux
    # ------------------------------------------------------------------
    @staticmethod
    def mmap_file(file_path: Path) -> mmap.mmap:
        """Retourne un objet `mmap` en lecture seule pour une ingestion de fichier sans copie.

        Utile lorsque les fichiers (ex: SFD) sont très volumineux (> 50 Mo) et que la RAM est limitée.
        Permet de traiter le fichier directement depuis le disque sans le charger entièrement en mémoire.

        Args:
            file_path: Le chemin vers le fichier à mapper en mémoire.

        Returns:
            Un objet `mmap.mmap` représentant le fichier mappé en mémoire.

        Raises:
            IOError, OSError: En cas d'erreur lors du mappage du fichier.
        """
        try:
            fd = os.open(file_path, os.O_RDONLY)
            return mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
        except (IOError, OSError) as e:
            logger.error(f"Erreur lors du mappage mémoire du fichier {file_path}: {e}")
            raise

    # ------------------------------------------------------------------
    # Fonctions utilitaires
    # ------------------------------------------------------------------
    @staticmethod
    def force_gc():
        """Force explicitement la collecte des objets inutilisés (garbage collection)."""
        gc.collect()

    @staticmethod
    def current_usage_mb() -> float:
        """Retourne l'utilisation actuelle de la mémoire du processus en mégaoctets."""
        return psutil.Process().memory_info().rss / (1024 ** 2)

    @staticmethod
    def trim_cache(max_age_seconds: int = 3600):
        """Supprime les fichiers de cache sur disque plus anciens que `max_age_seconds`.

        Cette fonction devrait être appelée périodiquement par l'orchestrateur
        ou un processus de maintenance.

        Args:
            max_age_seconds: L'âge maximal en secondes pour les fichiers de cache.
        """
        cache_root = Path("cache/memory_optimizer")
        if not cache_root.exists():
            return
        cutoff = time.time() - max_age_seconds
        for file in cache_root.rglob("*.lz4"): # Recherche tous les fichiers compressés.
            if file.stat().st_mtime < cutoff:
                try:
                    file.unlink(missing_ok=True)
                    logger.info(f"Fichier de cache ancien supprimé : {file}")
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression du fichier de cache {file}: {e}")


# ------------------------------------------------------------------
# Singleton au niveau du module pour la commodité
# ------------------------------------------------------------------
memory_optimizer = MemoryOptimizer()
compressed_cache = memory_optimizer.CompressedCache(cache_dir=Path("cache/memory_optimizer"))


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import numpy as np

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        print("\n--- Démonstration du MemoryOptimizer ---")
        current_mem = memory_optimizer.current_usage_mb()
        print(f"Utilisation mémoire initiale : {current_mem:.2f} MB")

        # Démonstration du suivi de la mémoire.
        print("\n--- Suivi de l'utilisation mémoire avec `track` ---")
        large_list = []
        async with memory_optimizer.track("large_list_creation"):
            for _ in range(1_000_000):
                large_list.append(np.random.rand(100)) # Crée une liste gourmande en mémoire.
            print(f"Taille de la liste : {len(large_list)} éléments.")
        del large_list # Libère la référence.
        memory_optimizer.force_gc() # Force le GC.
        print(f"Utilisation mémoire après GC : {memory_optimizer.current_usage_mb():.2f} MB")

        # Démonstration du cache compressé.
        print("\n--- Démonstration du CompressedCache ---")
        key = "my_large_data"
        data_to_cache = {"big_array": list(range(1_000_000)), "text": "Ceci est un très long texte qui sera compressé." * 100}

        print("Stockage de données dans le cache compressé...")
        compressed_cache.set(key, data_to_cache)
        print(f"Utilisation mémoire après stockage : {memory_optimizer.current_usage_mb():.2f} MB")

        print("Récupération de données depuis le cache compressé...")
        retrieved_data = compressed_cache.get(key)
        print(f"Données récupérées (taille de l'array) : {len(retrieved_data['big_array'])}")
        print(f"Utilisation mémoire après récupération : {memory_optimizer.current_usage_mb():.2f} MB")

        # Démonstration du mappage mémoire (nécessite un fichier existant).
        print("\n--- Démonstration du Mmap (nécessite un grand fichier) ---")
        temp_file_path = Path("temp_large_file.txt")
        try:
            # Crée un grand fichier temporaire.
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write("Ligne de texte.\n" * 100_000)
            
            print(f"Fichier temporaire créé : {temp_file_path} ({temp_file_path.stat().st_size / (1024**2):.2f} MB)")
            
            with memory_optimizer.mmap_file(temp_file_path) as mm:
                print(f"Fichier mappé en mémoire. Taille du mappage : {len(mm) / (1024**2):.2f} MB")
                # Accès aux données via le mappage sans charger tout en RAM.
                first_line = mm[:20].decode('utf-8')
                print(f"Première ligne mappée : {first_line}...")
            
            print(f"Utilisation mémoire après mappage : {memory_optimizer.current_usage_mb():.2f} MB")
        except Exception as e:
            print(f"Impossible de démontrer le mappage mémoire (créez un grand fichier ou vérifiez les permissions) : {e}")
        finally:
            if temp_file_path.exists():
                temp_file_path.unlink()

        # Démonstration du nettoyage du cache.
        print("\n--- Nettoyage du cache compressé ---")
        await asyncio.sleep(1) # Simule le passage du temps.
        memory_optimizer.trim_cache(max_age_seconds=0) # Supprime tout ce qui est plus vieux que 0 secondes.
        print("Cache nettoyé.")
        print(f"Utilisation mémoire après nettoyage : {memory_optimizer.current_usage_mb():.2f} MB")

    asyncio.run(demo())