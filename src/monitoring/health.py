# src/monitoring/health.py
import json

from fastapi import FastAPI, Response
import redis.asyncio as redis
import httpx

app = FastAPI()


@app.get("/health")
async def health():
    status = {"status": "healthy", "checks": {}}
    code = 200

    # Redis
    try:
        r = redis.from_url("redis://localhost:6379")
        await r.ping()
        status["checks"]["redis"] = True
    except Exception as e:
        status["checks"]["redis"] = str(e)
        code = 503

    # Ollama
    async with httpx.AsyncClient(timeout=2) as client:
        try:
            await client.get("http://localhost:11434/health")
            status["checks"]["ollama"] = True
        except Exception as e:
            status["checks"]["ollama"] = str(e)
            code = 503

    return Response(content=json.dumps(status), status_code=code)