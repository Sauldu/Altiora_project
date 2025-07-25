# src/security/encryption.py
"""Module d'utilitaires de chiffrement symétrique ultra-léger et sans configuration.

Ce module fournit une implémentation simple pour le chiffrement et le déchiffrement
de données en utilisant la cryptographie Fernet. La clé de chiffrement peut être
dérivée d'un mot de passe ou chargée depuis une variable d'environnement,
rendant le système flexible et sécurisé pour les champs PII (informations
personnelles identifiables) et les chaînes de caractères générales.
"""

import os
from typing import Optional, Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logger = logging.getLogger(__name__)


class DataEncryption:
    """Aide au chiffrement symétrique utilisant Fernet.

    La clé de chiffrement est obtenue soit à partir d'une clé Fernet brute,
    soit dérivée d'un mot de passe, soit lue depuis la variable d'environnement
    `ENCRYPTION_KEY`.
    """

    def __init__(
        self,
        password: Optional[str] = None,
        *,
        key: Optional[bytes] = None,
    ) -> None:
        """Initialise l'outil de chiffrement.

        Args:
            password: Un mot de passe à partir duquel la clé Fernet sera dérivée.
                      Si fourni, `ENCRYPTION_SALT` doit être défini dans l'environnement.
            key: Une clé Fernet brute (bytes) à utiliser directement. Prioritaire sur `password`.

        Raises:
            ValueError: Si aucune clé ou mot de passe n'est fourni et `ENCRYPTION_KEY` n'est pas défini.
        """
        if key:
            self.key = key
        elif password:
            self.key = self._derive_key(password)
        else:
            # Tente de charger la clé depuis la variable d'environnement.
            env_key = os.getenv("ENCRYPTION_KEY")
            if env_key:
                try:
                    self.key = base64.urlsafe_b64decode(env_key)
                except Exception as e:
                    raise ValueError(f"La clé ENCRYPTION_KEY dans l'environnement est invalide : {e}")
            else:
                # Si aucune clé n'est fournie, génère une nouvelle clé (pour la démo/dev).
                # En production, une clé doit toujours être fournie ou chargée.
                logger.warning("Aucune clé de chiffrement fournie ou trouvée dans ENCRYPTION_KEY. Génération d'une clé temporaire. NE PAS UTILISER EN PRODUCTION.")
                self.key = Fernet.generate_key()

        self._cipher = Fernet(self.key)

    # ------------------------------------------------------------------
    # Dérivation de clé
    # ------------------------------------------------------------------
    @staticmethod
    def _derive_key(password: str) -> bytes:
        """Dérive une clé Fernet à partir d'un mot de passe et d'un sel."

        Args:
            password: Le mot de passe en chaîne de caractères.

        Returns:
            La clé Fernet dérivée en bytes.
        """
        # Le sel doit être stable pour dériver la même clé à chaque fois.
        salt = os.getenv("ENCRYPTION_SALT", "altiora_default_salt").encode() # Utilise un sel par défaut si non défini.
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32, # Longueur de la clé Fernet.
            salt=salt,
            iterations=100_000, # Nombre d'itérations recommandé pour la sécurité.
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    # ------------------------------------------------------------------
    # Assistants publics
    # ------------------------------------------------------------------
    def encrypt_str(self, plaintext: str) -> str:
        """Chiffre une chaîne de caractères."

        Args:
            plaintext: La chaîne de caractères à chiffrer.

        Returns:
            La chaîne chiffrée (encodée en base64 URL-safe).
        """
        return self._cipher.encrypt(plaintext.encode('utf-8')).decode('utf-8')

    def decrypt_str(self, ciphertext: str) -> str:
        """Déchiffre une chaîne de caractères."

        Args:
            ciphertext: La chaîne de caractères chiffrée.

        Returns:
            La chaîne déchiffrée en texte clair.
        """
        return self._cipher.decrypt(ciphertext.encode('utf-8')).decode('utf-8')

    def encrypt_dict(self, data: Dict[str, str]) -> Dict[str, str]:
        """Chiffre uniquement les valeurs d'un dictionnaire."

        Args:
            data: Le dictionnaire dont les valeurs doivent être chiffrées.

        Returns:
            Un nouveau dictionnaire avec les valeurs chiffrées.
        """
        return {k: self.encrypt_str(v) for k, v in data.items()}

    def decrypt_dict(self, data: Dict[str, str]) -> Dict[str, str]:
        """Déchiffre les valeurs d'un dictionnaire."

        Args:
            data: Le dictionnaire dont les valeurs doivent être déchiffrées.

        Returns:
            Un nouveau dictionnaire avec les valeurs déchiffrées.
        """
        return {k: self.decrypt_str(v) for k, v in data.items()}


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n--- Démonstration du chiffrement avec clé générée ---")
    # Génère une clé Fernet pour la démonstration.
    generated_key = Fernet.generate_key()
    cipher_gen = DataEncryption(key=generated_key)

    original_text = "Ceci est un message très secret."
    encrypted_text = cipher_gen.encrypt_str(original_text)
    decrypted_text = cipher_gen.decrypt_str(encrypted_text)

    print(f"Original : {original_text}")
    print(f"Chiffré  : {encrypted_text}")
    print(f"Déchiffré: {decrypted_text}")
    assert original_text == decrypted_text

    print("\n--- Démonstration du chiffrement avec mot de passe ---")
    password = "MySuperSecurePassword123!"
    os.environ["ENCRYPTION_SALT"] = "unique_salt_for_altiora"
    cipher_pass = DataEncryption(password=password)

    original_text_2 = "Mes données personnelles: nom, adresse, téléphone."
    encrypted_text_2 = cipher_pass.encrypt_str(original_text_2)
    decrypted_text_2 = cipher_pass.decrypt_str(encrypted_text_2)

    print(f"Original : {original_text_2}")
    print(f"Chiffré  : {encrypted_text_2}")
    print(f"Déchiffré: {decrypted_text_2}")
    assert original_text_2 == decrypted_text_2

    print("\n--- Démonstration du chiffrement de dictionnaire ---")
    data_dict = {"email": "test@example.com", "phone": "0612345678"}
    encrypted_dict = cipher_pass.encrypt_dict(data_dict)
    decrypted_dict = cipher_pass.decrypt_dict(encrypted_dict)

    print(f"Original : {data_dict}")
    print(f"Chiffré  : {encrypted_dict}")
    print(f"Déchiffré: {decrypted_dict}")
    assert data_dict == decrypted_dict

    # Nettoyage de la variable d'environnement.
    del os.environ["ENCRYPTION_SALT"]
