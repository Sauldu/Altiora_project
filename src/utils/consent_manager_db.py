# src/utils/consent_manager_db.py
"""Module pour la gestion du consentement utilisateur dans une base de données PostgreSQL.

Ce module fournit une classe `ConsentManagerDB` pour enregistrer et vérifier
le consentement des utilisateurs concernant le traitement de leurs données
personnelles. Il utilise `asyncpg` pour des opérations asynchrones avec
PostgreSQL, assurant la conformité avec les réglementations sur la protection
des données (ex: RGPD).
"""

import asyncpg
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class ConsentManagerDB:
    """Gère la persistance et la vérification du consentement utilisateur dans une base de données."""

    def __init__(self, db_pool: asyncpg.Pool):
        """Initialise le gestionnaire de consentement avec un pool de connexions à la base de données."

        Args:
            db_pool: Un pool de connexions `asyncpg.Pool` pour interagir avec la base de données.
        """
        self.db_pool = db_pool

    async def create_table(self):
        """Crée la table `user_consents` si elle n'existe pas."

        Cette méthode doit être appelée au démarrage de l'application pour s'assurer
        que la structure de la base de données est prête.
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_consents (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    pii_types TEXT[] NOT NULL, -- Tableau de types de PII (ex: 'email', 'phone')
                    granted BOOLEAN NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
        logger.info("Table 'user_consents' vérifiée/créée.")

    async def save_consent(self, user_id: str, pii_types: List[str], granted: bool, expiry_days: int = 365):
        """Enregistre une décision de consentement pour un utilisateur."

        Args:
            user_id: L'identifiant de l'utilisateur.
            pii_types: Une liste de chaînes de caractères représentant les types de PII concernés (ex: ["email", "phone"]).
            granted: True si le consentement est accordé, False sinon.
            expiry_days: La durée de validité du consentement en jours.
        """
        expires_at = datetime.utcnow() + timedelta(days=expiry_days)
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_consents (user_id, pii_types, granted, expires_at, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ""
                ,
                user_id, pii_types, granted, expires_at
            )
        logger.info(f"Consentement enregistré pour l'utilisateur {user_id} : {granted} pour {pii_types}.")

    async def is_valid(self, user_id: str, pii_type: str) -> bool:
        """Vérifie si un consentement valide est actif pour un utilisateur et un type de PII donné."

        Args:
            user_id: L'identifiant de l'utilisateur.
            pii_type: Le type de PII à vérifier (ex: "email").

        Returns:
            True si un consentement valide et non expiré est trouvé, False sinon.
        """
        async with self.db_pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                SELECT granted, expires_at FROM user_consents
                WHERE user_id = $1 AND $2 = ANY(pii_types)
                ORDER BY created_at DESC LIMIT 1
                ""
                ,
                user_id, pii_type
            )
        
        if record:
            # Vérifie si le consentement a été accordé et n'a pas expiré.
            if record['granted'] and record['expires_at'] > datetime.utcnow():
                logger.debug(f"Consentement valide trouvé pour {user_id} et {pii_type}.")
                return True
            else:
                logger.debug(f"Consentement non valide ou expiré pour {user_id} et {pii_type}.")
        else:
            logger.debug(f"Aucun enregistrement de consentement trouvé pour {user_id} et {pii_type}.")
        return False


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import os

    async def demo():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Configuration de la connexion à la base de données PostgreSQL.
        # Assurez-vous que ces variables d'environnement sont définies ou adaptez l'URL.
        DB_USER = os.getenv("PG_USER", "postgres")
        DB_PASS = os.getenv("PG_PASSWORD", "password")
        DB_HOST = os.getenv("PG_HOST", "localhost")
        DB_PORT = os.getenv("PG_PORT", "5432")
        DB_NAME = os.getenv("PG_DB", "altiora_db")
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        print("\n--- Démonstration du ConsentManagerDB ---")
        pool = None
        try:
            # Crée un pool de connexions à la base de données.
            pool = await asyncpg.create_pool(DATABASE_URL)
            manager = ConsentManagerDB(pool)
            await manager.create_table() # S'assure que la table existe.

            user_id = "test_user_123"

            print("\n--- Enregistrement du consentement (accordé) ---")
            await manager.save_consent(user_id, ["email", "phone"], True, expiry_days=30)
            print(f"Consentement pour {user_id} enregistré.")

            print("\n--- Vérification du consentement ---")
            has_email_consent = await manager.is_valid(user_id, "email")
            print(f"L'utilisateur {user_id} a-t-il le consentement pour l'email ? {has_email_consent}")

            has_address_consent = await manager.is_valid(user_id, "address")
            print(f"L'utilisateur {user_id} a-t-il le consentement pour l'adresse ? {has_address_consent}")

            print("\n--- Enregistrement du consentement (refusé) ---")
            await manager.save_consent(user_id, ["phone"], False, expiry_days=1)
            print(f"Consentement pour {user_id} (téléphone) refusé.")

            has_phone_consent_after_refusal = await manager.is_valid(user_id, "phone")
            print(f"L'utilisateur {user_id} a-t-il le consentement pour le téléphone après refus ? {has_phone_consent_after_refusal}")

            print("\n--- Test de l'expiration du consentement ---")
            await manager.save_consent(user_id, ["temp_data"], True, expiry_days=0) # Expire immédiatement.
            print("Consentement temporaire enregistré (expire immédiatement).")
            await asyncio.sleep(1) # Attend 1 seconde pour s'assurer que le temps passe.
            has_temp_consent = await manager.is_valid(user_id, "temp_data")
            print(f"L'utilisateur {user_id} a-t-il le consentement pour les données temporaires (expiré) ? {has_temp_consent}")

        except asyncpg.exceptions.PostgresError as e:
            logging.error(f"Erreur PostgreSQL : {e}. Assurez-vous que la base de données est lancée et accessible.")
            print("Veuillez vérifier votre configuration PostgreSQL et les identifiants.")
        except Exception as e:
            logging.error(f"Erreur inattendue lors de la démonstration : {e}")
        finally:
            if pool:
                await pool.close()
                print("Pool de connexions à la base de données fermé.")

    asyncio.run(demo())