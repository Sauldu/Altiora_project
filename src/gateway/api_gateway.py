# src/gateway/api_gateway.py
import time

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
# Import pour le système de QA
from src.qa_system.qa_system import QASystem

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)


class QARequest(BaseModel):
    question: str
    context: str = None
    model: str = "qwen"
    temperature: float = 0.7


class QAResponse(BaseModel):
    answer: str
    confidence: float
    model_used: str
    processing_time: float


qa_system = QASystem()


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.post("/api/v1/qa/answer", response_model=QAResponse)
@limiter.limit("10/minute")
async def answer_question(request: QARequest):
    """Endpoint principal pour Q&A avec rate limiting"""
    start_time = time.time()

    try:
        # Inférence asynchrone
        answer = await qa_system.answer_async(
            question=request.question,
            context=request.context,
            model=request.model,
            temperature=request.temperature
        )

        return QAResponse(
            answer=answer.text,
            confidence=answer.confidence,
            model_used=request.model,
            processing_time=time.time() - start_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze")
@limiter.limit("10/minute")
async def analyze_sfd(request: Request, sfd_content: str):
    """Analyse un SFD avec rate limiting"""
    # Logique d'analyse du SFD
    pass
