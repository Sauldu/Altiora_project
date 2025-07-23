from cryptography.fernet import Fernet
import os
from pathlib import Path
import json

class SecretManager:
    """Gestionnaire centralisé des secrets."""
    def __init__(self, secrets_dir: Path):
        self.key_file = secrets_dir / "master.key"
        self.secrets_file = secrets_dir / "secrets.enc"
        self.cipher = self._load_or_create_cipher()
        self.secrets = self._load_secrets()

    def _load_or_create_cipher(self):
        """Charge la clé de chiffrement principale ou en crée une nouvelle."""
        if self.key_file.exists():
            key = self.key_file.read_bytes()
        else:
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
        return Fernet(key)

    def _load_secrets(self) -> dict:
        """Charge et déchiffre les secrets depuis le fichier."""
        if not self.secrets_file.exists():
            return {}
        encrypted_data = self.secrets_file.read_bytes()
        if not encrypted_data:
            return {}
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception:
            # Gère un fichier corrompu ou invalide
            return {}

    def get_secret(self, key: str, default: str = None) -> str | None:
        """
        Récupère un secret.
        Priorise les variables d'environnement si elles existent.
        """
        env_value = os.environ.get(key.upper())
        if env_value:
            return env_value
        return self.secrets.get(key, default)

    def set_secret(self, key: str, value: str):
        """Définit un secret et le sauvegarde de manière persistante."""
        self.secrets[key] = value
        self._save_secrets()

    def _save_secrets(self):
        """Chiffre et sauvegarde l'ensemble des secrets."""
        data = json.dumps(self.secrets).encode('utf-8')
        encrypted_data = self.cipher.encrypt(data)
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        self.secrets_file.write_bytes(encrypted_data)