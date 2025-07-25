# src/qa_system/qa_system.py
"""Module implémentant le système de Question-Réponse (QA) pour l'application Altiora.

Ce module fournit une interface pour interagir avec les modèles de langage
afin de répondre aux questions des utilisateurs. Il est conçu pour être
asynchrone et peut être intégré dans une API FastAPI.
"""

import asyncio
import time
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QASystem:
    """Système de Question-Réponse (QA) pour interagir avec les modèles de langage."

    Cette classe est responsable de la logique d'appel aux modèles d'IA
    pour générer des réponses aux questions posées par l'utilisateur.
    """

    async def answer_async(self, question: str, context: Optional[str], model: str, temperature: float) -> Any:
        """Répond à une question de manière asynchrone en utilisant un modèle de langage."

        Args:
            question: La question posée par l'utilisateur.
            context: Un contexte optionnel pour aider le modèle à formuler la réponse.
            model: Le nom du modèle de langage à utiliser (ex: 'qwen', 'starcoder').
            temperature: La température de génération pour contrôler la créativité de la réponse.

        Returns:
            Un objet factice (`Any`) contenant `text` (la réponse) et `confidence`.
            Dans une implémentation réelle, cela appellerait une interface de modèle LLM.
        """
        logger.info(f"Réception de la question : '{question}' pour le modèle '{model}' avec température {temperature}.")
        # Simule un délai de traitement pour l'inférence du modèle.
        await asyncio.sleep(0.5)

        # Logique factice pour la réponse.
        mock_answer = f"Ceci est une réponse simulée à votre question : '{question}'."
        mock_confidence = 0.85

        # Dans une application réelle, vous appelleriez ici votre interface de modèle LLM.
        # Exemple: `response = await self.llm_interface.generate_answer(question, context, model, temperature)`

        # Retourne un objet dynamique pour simuler la réponse du modèle.
        return type('obj', (object,), {'text': mock_answer, 'confidence': mock_confidence})()


# Initialisation du système de QA.
qa_system = QASystem()

# Initialisation de l'application FastAPI.
app = FastAPI(title="Altiora QA API", description="API pour le système de Question-Réponse d'Altiora.")


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


# --- Points de terminaison (Endpoints) --- #
@app.post("/qa/answer", response_model=QAResponse)
async def answer_question(request: QARequest) -> QAResponse:
    """Point de terminaison principal pour poser une question au système QA."

    Args:
        request: L'objet `QARequest` contenant la question et les paramètres.

    Returns:
        Un objet `QAResponse` avec la réponse du modèle.

    Raises:
        HTTPException: En cas d'erreur interne du serveur lors du traitement de la question.
    """
    start_time = time.time()

    try:
        # Appelle la méthode asynchrone du système QA pour obtenir une réponse.
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
        raise HTTPException(status_code=500, detail=f"Erreur interne du service : {str(e)}")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def run_server():
        """Lance le serveur FastAPI pour la démonstration."""
        logger.info("Lancement du serveur QA API sur http://0.0.0.0:8000")
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info", reload=True)
        server = uvicorn.Server(config)
        await server.serve()

    async def run_client():
        """Simule des requêtes client vers l'API QA."""
        await asyncio.sleep(1) # Donne le temps au serveur de démarrer.
        import httpx

        print("\n--- Test de l'endpoint /qa/answer ---")
        qa_request = {
            "question": "Comment puis-je optimiser mon code Python ?",
            "context": "J'ai un script qui est lent.",
            "model": "qwen",
            "temperature": 0.5
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("http://localhost:8000/qa/answer", json=qa_request)
                response.raise_for_status()
                qa_response = response.json()
                print(f"Réponse du QA : {qa_response['answer']}")
                print(f"Confiance : {qa_response['confidence']:.2f}")
                print(f"Modèle utilisé : {qa_response['model_used']}")
                print(f"Temps de traitement : {qa_response['processing_time']:.2f}s")
        except httpx.HTTPStatusError as e:
            print(f"Erreur HTTP : {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Erreur lors de l'appel client : {e}")

    async def main_demo():
        # Lance le serveur et le client en parallèle.
        server_task = asyncio.create_task(run_server())
        client_task = asyncio.create_task(run_client())

        await asyncio.gather(server_task, client_task)

    asyncio.run(main_demo())