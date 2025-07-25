# src/audit/rotation.py
"""Module pour la rotation et l'archivage sécurisé des journaux d'audit.

Ce module gère la rotation mensuelle des fichiers de log d'audit.
Les logs sont compressés, archivés dans un fichier `.tar.gz`,
puis chiffrés avant d'être stockés dans un répertoire d'archive.
Les fichiers originaux sont ensuite supprimés.
"""

import datetime
import logging
import tarfile
from pathlib import Path

from src.infrastructure.encryption import AltioraEncryption

logger = logging.getLogger(__name__)


def rotate_monthly():
    """Effectue la rotation mensuelle des journaux d'audit.

    Cette fonction est conçue pour être exécutée périodiquement (ex: via un cron job).
    Elle collecte tous les fichiers `.jsonl.zst` du répertoire `logs/audit`,
    les archive dans un fichier `.tar.gz` chiffré, et supprime les originaux.
    """
    current_month_str = datetime.datetime.utcnow().strftime("%Y%m")
    audit_log_dir = Path("logs/audit")
    archive_dir = Path("logs/archive")
    
    # Crée le répertoire d'archive s'il n'existe pas.
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Chemin du fichier d'archive temporaire (non chiffré).
    temp_archive_path = archive_dir / f"audit_{current_month_str}.tar"
    # Chemin du fichier d'archive final (chiffré).
    final_encrypted_archive_path = archive_dir / f"audit_{current_month_str}.tar.gz.enc"

    logger.info(f"Démarrage de la rotation des logs d'audit pour le mois {current_month_str}...")

    try:
        # 1. Crée une archive tarball des fichiers de log.
        with tarfile.open(temp_archive_path, "w") as tar:
            # Parcourt tous les fichiers de log compressés dans le répertoire d'audit.
            for log_file in audit_log_dir.glob("*.jsonl.zst"):
                tar.add(log_file, arcname=log_file.name) # Ajoute le fichier à l'archive.
                log_file.unlink() # Supprime le fichier original après l'avoir ajouté à l'archive.
        logger.info(f"Fichiers de log archivés dans {temp_archive_path}.")

        # 2. Chiffre l'archive.
        # La clé de chiffrement est gérée par AltioraEncryption (probablement via variables d'environnement).
        cipher = AltioraEncryption("AUDIT_BACKUP_KEY") # Utilise une clé spécifique pour l'audit.
        encrypted_data = cipher.encrypt_file(temp_archive_path)
        final_encrypted_archive_path.write_bytes(encrypted_data)
        logger.info(f"Archive chiffrée et sauvegardée : {final_encrypted_archive_path}.")

        # 3. Supprime l'archive temporaire non chiffrée.
        temp_archive_path.unlink()
        logger.info(f"Archive temporaire {temp_archive_path} supprimée.")

    except (IOError, OSError, tarfile.ReadError) as e:
        logger.error(f"Erreur lors de la rotation des logs d'audit : {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Erreur inattendue lors de la rotation des logs d'audit : {e}", exc_info=True)


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import time
    import zstandard

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Crée quelques fichiers de log factices pour la démonstration.
    audit_log_dir = Path("logs/audit")
    audit_log_dir.mkdir(parents=True, exist_ok=True)

    print("\n--- Création de fichiers de log factices ---")
    for i in range(3):
        log_file_path = audit_log_dir / f"test_audit_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{i}.jsonl.zst"
        with open(log_file_path, "wb") as f:
            compressor = zstandard.ZstdCompressor(level=1)
            f.write(compressor.compress(f"Log entry {i}\n".encode()))
        print(f"Créé : {log_file_path}")
        time.sleep(0.1) # Pour avoir des horodatages différents.

    print("\n--- Lancement de la rotation mensuelle ---")
    rotate_monthly()

    print("\n--- Vérification du répertoire d'audit ---")
    remaining_logs = list(audit_log_dir.glob("*.jsonl.zst"))
    if not remaining_logs:
        print("✅ Tous les fichiers de log ont été archivés et supprimés du répertoire d'audit.")
    else:
        print("❌ Des fichiers de log sont restés :", remaining_logs)

    print("\n--- Vérification du répertoire d'archive ---")
    archive_dir = Path("logs/archive")
    encrypted_archives = list(archive_dir.glob("*.tar.gz.enc"))
    if encrypted_archives:
        print(f"✅ Archive chiffrée trouvée : {encrypted_archives[0]}")
        # Pour déchiffrer et vérifier, il faudrait la clé et la logique de déchiffrement.
    else:
        print("❌ Aucune archive chiffrée trouvée.")

    print("Démonstration de la rotation des logs terminée.")