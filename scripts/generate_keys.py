# scripts/generate_keys.py
#!/usr/bin/env python3
from infrastructure.encryption import AltioraEncryption
import getpass
pw = getpass.getpass("Mot de passe maître : ")
key = AltioraEncryption._derive_from_password(pw)
print("ALTIORA_MASTER_KEY=", key)