# src/monitoring/healthcheck.py
from fastapi import FastAPI, Response
import aioredis
import httpx

app = FastAPI()


@app.get("/health")
async def health_check():
    """Vérification santé complète"""
    checks = {
        "redis": await check_redis(),
        "ollama": await check_ollama(),
        "services": await check_services()
    }

    if all(checks.values()):
        return {"status": "healthy", "checks": checks}
    else:
        return Response(
            content={"status": "unhealthy", "checks": checks},
            status_code=503
        )


async def check_redis():
    try:
        redis = await aioredis.from_url("redis://redis:6379")
        await redis.ping()
        return True
    except:
        return False