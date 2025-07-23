# src/encryption.py
"""
Chiffrement transparent pour Altiora
- AES-256-GCM pour les fichiers & Redis
- libsodium SealedBox pour les secrets utilisateur
- Compatible Windows / macOS / Linux
"""

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Dict, Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from nacl.encoding import Base64Encoder
from nacl.public import PrivateKey, SealedBox


class AltioraEncryption:
    """Facade unifiée"""

    def __init__(self, key_env: str = "ALTIORA_MASTER_KEY"):
        self._key = os.getenv(key_env) or self._derive_from_password()
        self._aes = AESGCM(self._key.encode()[:32])  # 256 bits

    # ---------- AES-256-GCM (fichiers & Redis) ----------
    def encrypt_file(self, path: Path) -> None:
        nonce = secrets.token_bytes(12)
        ct = self._aes.encrypt(nonce, path.read_bytes(), None)
        path.write_bytes(nonce + ct)

    def decrypt_file(self, path: Path) -> bytes:
        blob = path.read_bytes()
        nonce, ct = blob[:12], blob[12:]
        return self._aes.decrypt(nonce, ct, None)

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        nonce = secrets.token_bytes(12)
        ct = self._aes.encrypt(nonce, json.dumps(data).encode(), None)
        return base64.b64encode(nonce + ct).decode()

    def decrypt_dict(self, b64: str) -> Dict[str, Any]:
        blob = base64.b64decode(b64)
        nonce, ct = blob[:12], blob[12:]
        return json.loads(self._aes.decrypt(nonce, ct, None))

    # ---------- libsodium SealedBox (secrets) ----------
    @staticmethod
    def encrypt_user_secret(secret: str, user_public_key_b64: str) -> str:
        pub_key = SealedBox(Base64Encoder.decode(user_public_key_b64))
        return base64.b64encode(pub_key.encrypt(secret.encode())).decode()

    @staticmethod
    def decrypt_user_secret(cipher_b64: str, user_private_key_b64: str) -> str:
        priv_key = PrivateKey(Base64Encoder.decode(user_private_key_b64), encoder=Base64Encoder)
        box = SealedBox(priv_key)
        return box.decrypt(base64.b64decode(cipher_b64)).decode()

    # ---------- Helpers ----------
    @staticmethod
    def _derive_from_password(pw: str = None) -> str:
        pw = pw or os.getenv("ALTIORA_PW", "default")
        kdf = PBKDF2HMAC(hashes.SHA256(), 32, b"salty_salt", 100_000)
        return base64.urlsafe_b64encode(kdf.derive(pw.encode())).decode()
