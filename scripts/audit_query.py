# scripts/audit_query.py
import zstandard, json, glob
from datetime import datetime, timedelta

def query_last_hour():
    files = glob.glob("logs/audit/*.jsonl.zst")
    cutoff = datetime.utcnow() - timedelta(hours=1)
    for path in files:
        try:
            with open(path, "rb") as f:
                data = zstandard.ZstdDecompressor().decompress(f.read())
            for line in data.decode().splitlines():
                try:
                    ev = json.loads(line)
                    if datetime.fromisoformat(ev["ts"]) > cutoff:
                        print(ev)
                except json.JSONDecodeError as e:
                    logger.info(f"Error decoding JSON from line in {path}: {e}")
        except (IOError, OSError, zstandard.ZstdError) as e:
            logger.info(f"Error processing file {path}: {e}")