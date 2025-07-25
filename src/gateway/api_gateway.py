# src/gateway/api_gateway.py
"""Passerelle API principale pour l'application Altiora.

Ce module implémente une passerelle API basée sur FastAPI qui expose
des points de terminaison pour interagir avec les fonctionnalités
de l'assistant QA. Il intègre des mesures de sécurité comme la limitation
de débit (rate limiting) et l'ajout d'en-têtes de sécurité HTTP.
"""

import time
import logging

from fastapi import FastAPI, Request, HTTPException, status
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

# Importation du système de QA (Question Answering).
from src.qa_system.qa_system import QASystem

logger = logging.getLogger(__name__)

# Initialisation du limiteur de débit.
limiter = Limiter(key_func=get_remote_address)

# Initialisation de l'application FastAPI.
app = FastAPI(
    title="Altiora API Gateway",
    description="Passerelle API pour l'assistant QA Altiora.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)


# --- Modèles Pydantic pour les requêtes et réponses --- #
class QARequest(BaseModel):
    """Modèle de requête pour le système de Question-Réponse (QA)."""
    question: str = Field(..., description="La question posée par l'utilisateur.")
    context: Optional[str] = Field(None, description="Contexte optionnel pour aider à répondre à la question.")
    model: str = Field("qwen", description="Le modèle d'IA à utiliser pour la réponse (ex: 'qwen', 'starcoder').")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Température pour la génération de la réponse (contrôle la créativité).")


class QAResponse(BaseModel):
    """Modèle de réponse du système de Question-Réponse (QA)."""
    answer: str = Field(..., description="La réponse générée par le modèle.")
    confidence: float = Field(..., description="Le niveau de confiance de la réponse (entre 0 et 1).")
    model_used: str = Field(..., description="Le nom du modèle d'IA utilisé pour générer la réponse.")
    processing_time: float = Field(..., description="Le temps de traitement de la requête en secondes.")


# Initialisation du système de QA.
qa_system = QASystem()


# --- Middlewares --- #
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Middleware pour ajouter des en-têtes de sécurité HTTP aux réponses."

    Ces en-têtes aident à protéger l'application contre certaines vulnérabilités
    web courantes comme le Cross-Site Scripting (XSS) et le Clickjacking.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# --- Points de terminaison (Endpoints) --- #
@app.post("/api/v1/qa/answer", response_model=QAResponse)
@limiter.limit("10/minute") # Limite à 10 requêtes par minute par adresse IP.
async def answer_question(request: QARequest) -> QAResponse:
    """Point de terminaison principal pour poser une question au système QA."

    Args:
        request: L'objet `QARequest` contenant la question et les paramètres.

    Returns:
        Un objet `QAResponse` avec la réponse du modèle.

    Raises:
        HTTPException: En cas d'erreur interne du serveur.
    """
    start_time = time.time()

    try:
        # Appelle le système de QA pour obtenir une réponse.
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
        logger.error(f"Erreur lors de la réponse à la question : {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/v1/analyze")
@limiter.limit("5/minute") # Limite à 5 requêtes par minute pour l'analyse SFD.
async def analyze_sfd(request: Request, sfd_content: str):
    """Point de terminaison pour analyser une Spécification Fonctionnelle Détaillée (SFD)."

    Args:
        request: L'objet `Request` de FastAPI.
        sfd_content: Le contenu de la SFD à analyser.

    Returns:
        Un dictionnaire avec le résultat de l'analyse (actuellement un placeholder).

    Raises:
        HTTPException: En cas d'erreur interne du serveur.
    """
    logger.info(f"Requête d'analyse SFD reçue. Contenu : {sfd_content[:100]}...")
    # TODO: Implémenter la logique réelle d'analyse SFD ici.
    # Cela impliquerait d'appeler l'orchestrateur ou un service dédié.
    return {"message": "Analyse SFD en cours de développement.", "received_content_length": len(sfd_content)}


# ------------------------------------------------------------------
# Point d'entrée Uvicorn
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("Lancement de la passerelle API sur http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)