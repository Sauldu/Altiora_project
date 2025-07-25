# src/audit/writer.py
"""Writer asynchrone pour les événements d'audit.

Ce module fournit une classe `AsyncAuditWriter` qui collecte les événements
d'audit dans un tampon circulaire en mémoire et les écrit périodiquement
sur disque dans des fichiers compressés (Zstandard). Cela permet de réduire
la fréquence des opérations d'écriture sur disque et d'améliorer les performances.
"""

import asyncio
from pathlib import Path
import logging
from datetime import datetime
from src.audit.ring_buffer import RingBuffer
from src.audit.models import AuditEvent

import aiofiles
import zstandard as zstd

logger = logging.getLogger(__name__)


class AsyncAuditWriter:
    """Écrit les événements d'audit de manière asynchrone et par lots sur disque."""

    def __init__(self, log_dir: Path, buffer_size: int = 10_000, flush_interval: int = 5):
        """Initialise le writer d'audit asynchrone.

        Args:
            log_dir: Le répertoire où les fichiers de log d'audit seront stockés.
            buffer_size: La taille maximale du tampon circulaire en mémoire.
            flush_interval: L'intervalle en secondes entre chaque écriture sur disque.
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True) # Crée le répertoire si nécessaire.
        self._ctx = zstd.ZstdCompressor(level=3)  # Compresseur Zstandard (niveau 3 pour un bon équilibre).
        self._buffer = RingBuffer(size=buffer_size)
        self._flush_interval = flush_interval
        self._flush_task: asyncio.Task | None = None

    async def start(self):
        """Démarre la tâche de flush périodique en arrière-plan."""
        if self._flush_task === None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._periodic_flush())
            logger.info(f"AsyncAuditWriter démarré. Flush toutes les {self._flush_interval} secondes.")

    async def stop(self):
        """Arrête la tâche de flush périodique et force un dernier flush."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task # Attend que la tâche se termine (gère l'exception CancelledError).
            except asyncio.CancelledError:
                pass
            logger.info("AsyncAuditWriter arrêté. Exécution du flush final...")
        await self._flush_to_disk() # Force un dernier flush pour s'assurer que toutes les données sont écrites.
        logger.info("Flush final terminé.")

    def log(self, event: AuditEvent) -> None:
        """Ajoute un événement d'audit au tampon en mémoire."

        Args:
            event: L'objet `AuditEvent` à enregistrer.
        """
        self._buffer.push(event)

    async def _periodic_flush(self):
        """Tâche asynchrone qui vide périodiquement le tampon sur disque."""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush_to_disk()
            except asyncio.CancelledError:
                break # La tâche a été annulée, sort de la boucle.
            except Exception as e:
                logger.error(f"Erreur lors du flush périodique des logs d'audit : {e}", exc_info=True)

    async def _flush_to_disk(self):
        """Vide le contenu du tampon en mémoire vers un fichier compressé sur disque."""
        batch = self._buffer.flush()
        if batch:
            # Génère un nom de fichier unique basé sur l'horodatage.
            path = self.log_dir / f"audit_{datetime.utcnow():%Y%m%d_%H%M%S_%f}.jsonl.zst"
            try:
                async with aiofiles.open(path, "wb") as f:
                    # Compresse le lot d'événements et l'écrit dans le fichier.
                    await f.write(self._ctx.compress("\n".join(batch).encode('utf-8')))
                logger.info(f"Logs d'audit écrits sur disque : {path} ({len(batch)} événements).")
            except (IOError, OSError, zstd.ZstdError) as e:
                logger.error(f"Erreur lors de l'écriture des logs d'audit sur {path}: {e}")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        log_directory = Path("temp_audit_logs")
        # S'assure que le répertoire de démonstration est propre.
        if log_directory.exists():
            import shutil
            shutil.rmtree(log_directory)
        log_directory.mkdir()

        writer = AsyncAuditWriter(log_directory, buffer_size=3, flush_interval=2) # Petit buffer et intervalle pour la démo.
        await writer.start()

        print("\n--- Enregistrement d'événements d'audit ---")
        for i in range(10):
            event = AuditEvent(
                ts=datetime.utcnow(),
                actor=f"user_{i}",
                action="demo_action",
                meta={"event_id": i, "data": f"some_data_{i}"}
            )
            writer.log(event)
            print(f"Loggué événement {i}.")
            await asyncio.sleep(0.5) # Simule l'arrivée des événements.

        print("\n--- Arrêt du writer et flush final ---")
        await writer.stop()

        print("\n--- Vérification des fichiers générés ---")
        generated_files = list(log_directory.glob("*.jsonl.zst"))
        for f in generated_files:
            print(f"Fichier généré : {f}")
            with open(f, "rb") as fb:
                decompressor = zstd.ZstdDecompressor()
                content = decompressor.decompress(fb.read()).decode('utf-8')
                print(f"Contenu:\n{content[:200]}...")

        print("Démonstration de AsyncAuditWriter terminée.")
        # Nettoyage du répertoire temporaire.
        import shutil
        shutil.rmtree(log_directory)

    import asyncio
    asyncio.run(demo())