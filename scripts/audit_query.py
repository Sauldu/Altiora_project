# scripts/audit_query.py
import zstandard, json, glob
from datetime import datetime, timedelta

def query_last_hour():
    files = glob.glob("logs/audit/*.jsonl.zst")
    cutoff = datetime.utcnow() - timedelta(hours=1)
    for path in files:
        with open(path, "rb") as f:
            data = zstandard.ZstdDecompressor().decompress(f.read())
        for line in data.decode().splitlines():
            ev = json.loads(line)
            if datetime.fromisoformat(ev["ts"]) > cutoff:
                print(ev)