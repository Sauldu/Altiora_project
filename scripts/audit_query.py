# scripts/audit_query.py
"""Script pour interroger les journaux d'audit compressés.

Ce script parcourt les fichiers de log d'audit (`.jsonl.zst`) dans le répertoire `logs/audit`,
les décompresse à la volée et affiche les événements qui se sont produits au cours
de la dernière heure.

Utilisation :
    python -m scripts.audit_query
"""

import zstandard
import json
import glob
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def query_last_hour():
    """Interroge et affiche les événements d'audit de la dernière heure."""
    # Recherche tous les fichiers d'audit compressés.
    files = glob.glob("logs/audit/*.jsonl.zst")
    if not files:
        print("Aucun fichier d'audit trouvé dans `logs/audit/`.")
        return

    # Définit la limite de temps pour la requête.
    cutoff = datetime.utcnow() - timedelta(hours=1)
    print(f"Recherche des événements d'audit depuis {cutoff.isoformat()}Z...")

    event_found = False
    for path in files:
        try:
            with open(path, "rb") as f:
                # Décompresse le contenu du fichier.
                data = zstandard.ZstdDecompressor().decompress(f.read())
            
            # Traite chaque ligne comme un objet JSON distinct.
            for line in data.decode('utf-8').splitlines():
                try:
                    event = json.loads(line)
                    # Vérifie si l'horodatage de l'événement est dans la fenêtre de temps.
                    if datetime.fromisoformat(event["ts"]) > cutoff:
                        print(json.dumps(event, indent=2, ensure_ascii=False))
                        event_found = True
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Erreur de décodage JSON ou clé manquante dans {path}: {e}")
        except (IOError, OSError, zstandard.ZstdError) as e:
            logger.error(f"Erreur lors du traitement du fichier {path}: {e}")

    if not event_found:
        print("Aucun événement trouvé dans la dernière heure.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    query_last_hour()
