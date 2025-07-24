# src/audit/rotation.py
import datetime
from pathlib import Path
import tarfile

from infrastructure.encryption import AltioraEncryption


def rotate_monthly():
    month = datetime.utcnow().strftime("%Y%m")
    src = Path("logs/audit")
    dst = Path("logs/archive") / f"{month}.tar.gz.enc"
    dst.parent.mkdir(exist_ok=True)

    try:
        with tarfile.open(dst.with_suffix(".tar"), "w") as tar:
            for f in src.glob("*.jsonl.zst"):
                tar.add(f, arcname=f.name)
                f.unlink()

        cipher = AltioraEncryption("AUDIT_BACKUP_KEY")
        dst.write_bytes(cipher.encrypt_file(dst.with_suffix(".tar")))
        dst.with_suffix(".tar").unlink()
    except (IOError, OSError, tarfile.ReadError) as e:
        print(f"Error during audit log rotation: {e}")
