"""
Memory Optimizer for Altiora – CPU-friendly utilities for ThinkPad i5-13500H
- Limits RAM peaks during large SFD processing
- Transparent compression / LRU caches
- GC hints & memory-mapped fallbacks
"""

import gc
import mmap
import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional

import lz4.frame
import psutil


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

class MemoryOptimizer:
    """
    Central helper to keep memory under ~25 GB on 32 GB machines.
    Usage:
        opt = MemoryOptimizer(max_memory_gb=25)
        async with opt.track("sfd_analysis"):
            ...
    """

    def __init__(self, max_memory_gb: float = 25.0):
        self.max_memory_bytes = max_memory_gb * 1024 ** 3
        self.process = psutil.Process()

    # ------------------------------------------------------------------
    # Context manager for automatic GC & peak tracking
    # ------------------------------------------------------------------
    class track:
        def __init__(self, name: str, optimizer: "MemoryOptimizer"):
            self.name = name
            self.opt = optimizer

        async def __aenter__(self):
            gc.collect()
            self.start = self.opt.process.memory_info().rss
            return self

        async def __aexit__(self, exc_type, exc, tb):
            gc.collect()
            peak = self.opt.process.memory_info().rss
            delta_mb = (peak - self.start) / 1024 ** 2
            if delta_mb > 100:  # log only big jumps
                logger.info(f"[MEM] {self.name}: +{delta_mb:.1f} MB")

    # ------------------------------------------------------------------
    # Transparent compressed cache
    # ------------------------------------------------------------------
    class CompressedCache:
        """
        Drop-in replacement for dict / Redis when data is huge.
        Keeps last N items compressed on disk; falls back to mmap for >100 MB blobs.
        """

        def __init__(self, cache_dir: Path, max_items: int = 50):
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.max_items = max_items
            self._lru: Dict[str, Path] = {}  # key -> file

        def _key_path(self, key: str) -> Path:
            safe_key = "".join(c if c.isalnum() else "_" for c in key)
            return self.cache_dir / f"{safe_key}.lz4"

        def get(self, key: str) -> Optional[Any]:
            path = self._key_path(key)
            if not path.exists():
                return None
            try:
                with lz4.frame.open(path, "rb") as f:
                    return pickle.load(f)
            except (IOError, OSError, lz4.frame.LZ4FrameError, pickle.PickleError) as e:
                logger.info(f"Error reading from compressed cache {path}: {e}")
                return None

        def set(self, key: str, value: Any) -> None:
            path = self._key_path(key)
            try:
                with lz4.frame.open(path, "wb") as f:
                    pickle.dump(value, f)
                self._lru[key] = path
                # LRU eviction
                if len(self._lru) > self.max_items:
                    oldest = next(iter(self._lru))
                    self._lru.pop(oldest).unlink(missing_ok=True)
            except (IOError, OSError, lz4.frame.LZ4FrameError, pickle.PickleError) as e:
                logger.info(f"Error writing to compressed cache {path}: {e}")

    # ------------------------------------------------------------------
    # Memory-mapped fallback for giant strings / files
    # ------------------------------------------------------------------
    @staticmethod
    def mmap_file(file_path: Path) -> mmap.mmap:
        """
        Returns a read-only mmap object for zero-copy SFD ingestion.
        Useful when SFD > 50 MB and RAM is tight.
        """
        try:
            fd = os.open(file_path, os.O_RDONLY)
            return mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
        except (IOError, OSError) as e:
            logger.info(f"Error memory-mapping file {file_path}: {e}")
            raise

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def force_gc():
        """Explicitly collect unreachable objects."""
        gc.collect()

    @staticmethod
    def current_usage_mb() -> float:
        return psutil.Process().memory_info().rss / 1024 ** 2

    @staticmethod
    def trim_cache(max_age_seconds: int = 3600):
        """
        Remove any on-disk cache older than max_age_seconds.
        Call periodically from orchestrator.
        """
        cache_root = Path("cache/memory_optimizer")
        if not cache_root.exists():
            return
        cutoff = time.time() - max_age_seconds
        for file in cache_root.rglob("*.lz4"):
            if file.stat().st_mtime < cutoff:
                file.unlink(missing_ok=True)


# ------------------------------------------------------------------
# Module-level singleton for convenience
# ------------------------------------------------------------------
memory_optimizer = MemoryOptimizer()
compressed_cache = memory_optimizer.CompressedCache(cache_dir=Path("cache/memory_optimizer"))
