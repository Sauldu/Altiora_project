# src/security/encryption.py
"""
Ultra-light, zero-config encryption utilities
– Fernet based, safe and key from env-vars.
"""

import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class DataEncryption:
    """
    Symmetric encryption helper using Fernet.
    - key from env `ENCRYPTION_KEY` or password + salt
    - safe for PII fields & general strings
    """

    def __init__(
        self,
        password: Optional[str] = None,
        *,
        key: Optional[bytes] = None,
    ) -> None:
        if key:
            self.key = key
        elif password:
            self.key = self._derive_key(password)
        else:
            # Use pre-shared key from env (hex/base64)
            env_key = os.getenv("ENCRYPTION_KEY")
            if env_key:
                self.key = base64.urlsafe_b64decode(env_key)
            else:
                self.key = Fernet.generate_key()

        self._cipher = Fernet(self.key)

    # ------------------------------------------------------------------
    # key derivation
    # ------------------------------------------------------------------
    @staticmethod
    def _derive_key(password: str) -> bytes:
        salt = os.getenv("ENCRYPTION_SALT", "default_salt").encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------
    def encrypt_str(self, plaintext: str) -> str:
        """Encrypt a single string."""
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt_str(self, ciphertext: str) -> str:
        """Decrypt a single string."""
        return self._cipher.decrypt(ciphertext.encode()).decode()

    def encrypt_dict(self, data: dict[str, str]) -> dict[str, str]:
        """Encrypt only the values of a dict (useful for PII)."""
        return {k: self.encrypt_str(v) for k, v in data.items()}

    def decrypt_dict(self, data: dict[str, str]) -> dict[str, str]:
        """Decrypt the values of a dict."""
        return {k: self.decrypt_str(v) for k, v in data.items()}