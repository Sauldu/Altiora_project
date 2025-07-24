# src/audit/writer.py
import asyncio
from pathlib import Path
import logging
from datetime import datetime
from src.audit.ring_buffer import RingBuffer
from src.audit.models import AuditEvent

import aiofiles
import zstandard as zstd


class AsyncAuditWriter:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        self._ctx = zstd.ZstdCompressor(level=3)  # très rapide
        self._buffer = RingBuffer()

    async def start(self):
        asyncio.create_task(self._periodic_flush())

    def log(self, event: AuditEvent) -> None:
        self._buffer.push(event)

    async def _periodic_flush(self):
        while True:
            await asyncio.sleep(5)  # flush toutes les 5 s
            batch = self._buffer.flush()
            if batch:
                path = self.log_dir / f"audit_{datetime.utcnow():%Y%m%d_%H%M%S}.jsonl.zst"
                try:
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(self._ctx.compress("\n".join(batch).encode()))
                except (IOError, OSError, zstd.ZstdError) as e:
                    logger.error(f"Error writing audit log to {path}: {e}"
)
