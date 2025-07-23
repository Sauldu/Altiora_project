# altiora/utils/consent_manager_db.py
import asyncpg
from datetime import datetime
from typing import List

class ConsentManagerDB:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def save_consent(self, user_id: str, pii_types: List[str], granted: bool):
        expires_at = datetime.utcnow() # Ou une logique d'expiration
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_consents (user_id, pii_types, granted, expires_at, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                """,
                user_id, pii_types, granted, expires_at
            )

    async def is_valid(self, user_id: str, pii_type: str) -> bool:
        async with self.db_pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                SELECT granted, expires_at FROM user_consents
                WHERE user_id = $1 AND $2 = ANY(pii_types)
                ORDER BY created_at DESC LIMIT 1
                """,
                user_id, pii_type
            )
        if record and record['granted'] and record['expires_at'] > datetime.utcnow():
            return True
        return False