# src/infrastructure/encryption.py
"""Module de chiffrement transparent pour l'application Altiora.

Ce module fournit des utilitaires de chiffrement robustes pour diverses
utilisations : chiffrement de fichiers (AES-256-GCM), chiffrement de
dictionnaires (pour les données structurées comme les PII), et chiffrement
de secrets utilisateur (libsodium SealedBox). Il est conçu pour être
compatible avec différents systèmes d'exploitation.
"""

import base64
import json
import os
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Importations conditionnelles pour libsodium (PyNaCl).
# PyNaCl est une dépendance optionnelle pour le chiffrement de secrets utilisateur.
try:
    from nacl.encoding import Base64Encoder
    from nacl.public import PrivateKey, SealedBox
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False
    logging.warning("PyNaCl (libsodium) non installé. Le chiffrement de secrets utilisateur ne sera pas disponible.")

logger = logging.getLogger(__name__)


class AltioraEncryption:
    """Façade unifiée pour les opérations de chiffrement dans Altiora."""

    def __init__(self, key_env_var: str = "ALTIORA_MASTER_KEY"):
        """Initialise la classe de chiffrement.

        La clé maîtresse est chargée depuis une variable d'environnement.
        Si la variable n'est pas définie, une clé est dérivée d'un mot de passe par défaut.

        Args:
            key_env_var: Le nom de la variable d'environnement contenant la clé maîtresse.
        """
        self._key_env_var = key_env_var
        self._master_key = self._get_master_key()
        # AES-GCM nécessite une clé de 32 octets (256 bits).
        self._aes_gcm = AESGCM(self._master_key[:32])

    def _get_master_key(self) -> bytes:
        """Récupère la clé maîtresse depuis l'environnement ou la dérive."

        Returns:
            La clé maîtresse en bytes.
        """
        env_key = os.getenv(self._key_env_var)
        if env_key:
            try:
                # La clé de l'environnement doit être encodée en base64 URL-safe.
                return base64.urlsafe_b64decode(env_key)
            except Exception as e:
                logger.error(f"La clé maîtresse dans l'environnement ({self._key_env_var}) est invalide : {e}. Dérivation d'une clé par défaut.")
        
        # Dérive une clé si aucune n'est trouvée ou si elle est invalide.
        logger.warning(f"Variable d'environnement {self._key_env_var} non définie ou invalide. Dérivation d'une clé à partir d'un mot de passe par défaut. NE PAS UTILISER EN PRODUCTION.")
        return self._derive_from_password("default_altiora_password").encode()

    @staticmethod
    def _derive_from_password(password: str) -> str:
        """Dérive une clé de chiffrement à partir d'un mot de passe."

        Args:
            password: Le mot de passe en chaîne de caractères.

        Returns:
            La clé dérivée encodée en base64 URL-safe.
        """
        salt = os.getenv("ALTIORA_SALT", "some_fixed_salt").encode() # Utilise un sel fixe pour la reproductibilité.
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32, # Longueur de la clé dérivée.
            salt=salt,
            iterations=100_000, # Nombre d'itérations pour la sécurité.
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode())).decode()

    # ---------- AES-256-GCM (pour les fichiers et les données structurées) ----------
    def encrypt_file(self, path: Path) -> bytes:
        """Chiffre le contenu d'un fichier en utilisant AES-256-GCM."

        Args:
            path: Le chemin vers le fichier à chiffrer.

        Returns:
            Les données chiffrées (nonce + ciphertext) en bytes.
        """
        nonce = secrets.token_bytes(12) # Nonce de 12 octets pour AES-GCM.
        plaintext = path.read_bytes()
        ciphertext = self._aes_gcm.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt_file(self, path: Path) -> bytes:
        """Déchiffre le contenu d'un fichier chiffré avec AES-256-GCM."

        Args:
            path: Le chemin vers le fichier chiffré.

        Returns:
            Les données déchiffrées en bytes.
        """
        blob = path.read_bytes()
        nonce, ciphertext = blob[:12], blob[12:]
        return self._aes_gcm.decrypt(nonce, ciphertext, None)

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Chiffre un dictionnaire en JSON puis avec AES-256-GCM."

        Args:
            data: Le dictionnaire à chiffrer.

        Returns:
            La chaîne chiffrée (base64 encodée).
        """
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
        ciphertext = self._aes_gcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext).decode('utf-8')

    def decrypt_dict(self, b64_ciphertext: str) -> Dict[str, Any]:
        """Déchiffre une chaîne chiffrée (base64) en un dictionnaire."

        Args:
            b64_ciphertext: La chaîne chiffrée encodée en base64.

        Returns:
            Le dictionnaire déchiffré.
        """
        blob = base64.b64decode(b64_ciphertext)
        nonce, ciphertext = blob[:12], blob[12:]
        plaintext = self._aes_gcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))

    # ---------- libsodium SealedBox (pour les secrets utilisateur) ----------
    def encrypt_user_secret(self, secret: str, user_public_key_b64: str) -> str:
        """Chiffre un secret pour un utilisateur en utilisant sa clé publique (SealedBox).

        Nécessite l'installation de PyNaCl (`pip install PyNaCl`).

        Args:
            secret: Le secret en texte clair à chiffrer.
            user_public_key_b64: La clé publique de l'utilisateur encodée en base64.

        Returns:
            Le secret chiffré encodé en base64.

        Raises:
            RuntimeError: Si PyNaCl n'est pas installé.
        """
        if not _HAS_NACL:
            raise RuntimeError("PyNaCl n'est pas installé. Impossible d'utiliser SealedBox.")
        
        pub_key = SealedBox(Base64Encoder.decode(user_public_key_b64))
        return base64.b64encode(pub_key.encrypt(secret.encode('utf-8'))).decode('utf-8')

    def decrypt_user_secret(self, cipher_b64: str, user_private_key_b64: str) -> str:
        """Déchiffre un secret chiffré avec SealedBox en utilisant la clé privée de l'utilisateur."

        Nécessite l'installation de PyNaCl (`pip install PyNaCl`).

        Args:
            cipher_b64: Le secret chiffré encodé en base64.
            user_private_key_b64: La clé privée de l'utilisateur encodée en base64.

        Returns:
            Le secret déchiffré en texte clair.

        Raises:
            RuntimeError: Si PyNaCl n'est pas installé.
        """
        if not _HAS_NACL:
            raise RuntimeError("PyNaCl n'est pas installé. Impossible d'utiliser SealedBox.")

        priv_key = PrivateKey(Base64Encoder.decode(user_private_key_b64), encoder=Base64Encoder)
        box = SealedBox(priv_key)
        return box.decrypt(base64.b64decode(cipher_b64)).decode('utf-8')


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Définir une clé maîtresse dans l'environnement pour la démo.
    # En production, cette clé devrait être gérée de manière sécurisée (ex: HashiCorp Vault).
    os.environ["ALTIORA_MASTER_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()

    print("\n--- Démonstration du chiffrement de fichiers (AES-GCM) ---")
    encryptor = AltioraEncryption()
    temp_file = Path("temp_secret.txt")
    temp_file.write_text("Ceci est un contenu de fichier très confidentiel.")

    encrypted_bytes = encryptor.encrypt_file(temp_file)
    temp_file.write_bytes(encrypted_bytes) # Écrit le contenu chiffré dans le même fichier.
    print(f"Fichier chiffré : {temp_file}")

    decrypted_content = encryptor.decrypt_file(temp_file).decode('utf-8')
    print(f"Contenu déchiffré : {decrypted_content}")
    assert decrypted_content == "Ceci est un contenu de fichier très confidentiel."
    temp_file.unlink()

    print("\n--- Démonstration du chiffrement de dictionnaires (AES-GCM) ---")
    data_to_encrypt = {"user_id": "alice", "email": "alice@example.com", "age": 30}
    encrypted_data_str = encryptor.encrypt_dict(data_to_encrypt)
    print(f"Données originales : {data_to_encrypt}")
    print(f"Données chiffrées : {encrypted_data_str}")

    decrypted_data_dict = encryptor.decrypt_dict(encrypted_data_str)
    print(f"Données déchiffrées : {decrypted_data_dict}")
    assert data_to_encrypt == decrypted_data_dict

    if _HAS_NACL:
        print("\n--- Démonstration du chiffrement de secrets utilisateur (SealedBox) ---")
        # Génère une paire de clés pour l'utilisateur (en production, ce serait stocké de manière sécurisée).
        user_private_key = PrivateKey.generate()
        user_public_key = user_private_key.public_key

        user_private_key_b64 = user_private_key.encode(Base64Encoder).decode()
        user_public_key_b64 = user_public_key.encode(Base64Encoder).decode()

        secret_to_share = "Mon API Key pour le service X"
        
        # Chiffre le secret avec la clé publique de l'utilisateur.
        encrypted_secret = encryptor.encrypt_user_secret(secret_to_share, user_public_key_b64)
        print(f"Secret original : {secret_to_share}")
        print(f"Secret chiffré (pour l'utilisateur) : {encrypted_secret}")

        # Déchiffre le secret avec la clé privée de l'utilisateur.
        decrypted_secret = encryptor.decrypt_user_secret(encrypted_secret, user_private_key_b64)
        print(f"Secret déchiffré : {decrypted_secret}")
        assert secret_to_share == decrypted_secret
    else:
        print("\n--- Démonstration SealedBox ignorée : PyNaCl non installé. ---")

    print("Démonstration du chiffrement terminée.")
    del os.environ["ALTIORA_MASTER_KEY"]