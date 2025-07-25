# tests/test_ocr_wrapper.py
"""Tests unitaires pour le wrapper du service OCR (`ocr_wrapper.py`).

Ce module contient des tests pour vérifier la fonctionnalité de base du
service OCR, y compris la génération de clés de cache et le comportement
de l'extracteur en mode mock.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Importe les fonctions et classes du module ocr_wrapper.
from services.ocr.ocr_wrapper import OCRRequest, _cache_key, _extract_mock, _extract_doctoplus # Assurez-vous d'importer les fonctions internes si elles sont testées.


@pytest.mark.asyncio
async def test_ocr_cache_key_generation():
    """Teste la génération de clés de cache uniques et déterministes pour les requêtes OCR."

    La clé de cache doit être la même pour des requêtes identiques et différente
    pour des requêtes différentes.
    """
    # Crée une requête OCR factice.
    request1 = OCRRequest(
        file_path='/test/sample.pdf',
        language='fra',
        preprocess=True,
        output_format='text'
    )

    # Génère la clé de cache.
    cache_key1 = _cache_key(request1)
    assert cache_key1.startswith('ocr:'), "La clé de cache devrait commencer par 'ocr:'."
    assert len(cache_key1) == 39, "La clé de cache devrait avoir une longueur fixe (ocr: + 32 caractères MD5)."

    # Teste la déterministe de la clé.
    request2 = OCRRequest(
        file_path='/test/sample.pdf',
        language='fra',
        preprocess=True,
        output_format='text'
    )
    cache_key2 = _cache_key(request2)
    assert cache_key1 == cache_key2, "Des requêtes identiques devraient générer la même clé de cache."

    # Teste la différence de la clé pour des requêtes différentes.
    request3 = OCRRequest(
        file_path='/test/another.pdf',
        language='fra',
        preprocess=True,
        output_format='text'
    )
    cache_key3 = _cache_key(request3)
    assert cache_key1 != cache_key3, "Des requêtes différentes devraient générer des clés de cache différentes."


@pytest.mark.asyncio
async def test_mock_ocr_extraction():
    """Teste l'extraction OCR en mode mock (`_extract_mock`)."

    Vérifie que l'extracteur mock retourne un résultat simulé avec les champs attendus.
    """
    # Crée une requête OCR factice pour le mock.
    mock_request = OCRRequest(
        file_path="test.pdf",
        language="fra",
        preprocess=True,
        output_format="text"
    )

    # Appelle la fonction d'extraction mock.
    result = await _extract_mock(mock_request)

    # Assertions sur le résultat du mock.
    assert "mock" in result["text"].lower(), "Le texte extrait devrait contenir 'mock'."
    assert result["confidence"] > 0, "La confiance devrait être supérieure à 0."
    assert "metadata" in result, "Le résultat devrait contenir des métadonnées."
    assert result["metadata"]["mode"] == "mock", "Le mode des métadonnées devrait être 'mock'."


@pytest.mark.asyncio
@patch('services.ocr.ocr_wrapper.DoctopusWrapper', autospec=True)
async def test_doctoplus_ocr_extraction(MockDoctopusWrapper: MagicMock):
    """Teste l'extraction OCR avec le wrapper Doctopus (`_extract_doctoplus`)."

    Mocke la bibliothèque `DoctopusWrapper` pour simuler son comportement
    sans dépendre d'une installation réelle.
    """
    # Configure le mock de DoctopusWrapper.
    mock_instance = MockDoctopusWrapper.return_value
    mock_instance.extract_text.return_value = {
        "text": "Texte extrait par Doctopus.",
        "confidence": 0.98,
        "pages": 2
    }

    # Crée une requête OCR.
    request = OCRRequest(
        file_path="/path/to/real_doc.pdf",
        language="eng",
        preprocess=True,
        output_format="text"
    )

    # Appelle la fonction d'extraction Doctopus.
    result = await _extract_doctoplus(request)

    # Assertions sur le résultat.
    assert result["text"] == "Texte extrait par Doctopus.", "Le texte devrait correspondre à la sortie mockée."
    assert result["confidence"] == 0.98, "La confiance devrait correspondre à la sortie mockée."
    assert result["metadata"]["pages"] == 2, "Les métadonnées devraient inclure le nombre de pages."
    assert mock_instance.extract_text.called_once_with(
        file_path=request.file_path,
        language=request.language,
        preprocess=request.preprocess,
        confidence_threshold=request.confidence_threshold,
        output_format=request.output_format,
    )


@pytest.mark.asyncio
@patch('services.ocr.ocr_wrapper.redis_client', new_callable=AsyncMock)
async def test_ocr_caching(mock_redis_client: AsyncMock):
    """Teste la fonctionnalité de mise en cache du service OCR."

    Vérifie que les résultats sont stockés et récupérés du cache Redis.
    """
    # Configure le mock Redis pour simuler un cache vide puis une valeur.
    mock_redis_client.get.return_value = None # Pas de cache au premier appel.
    mock_redis_client.setex.return_value = True

    # Mocke l'extracteur réel pour qu'il retourne une valeur connue.
    with patch('services.ocr.ocr_wrapper._extract_doctoplus', new_callable=AsyncMock) as mock_extractor:
        mock_extractor.return_value = {"text": "Contenu non mis en cache.", "confidence": 0.9}

        # Crée une requête OCR.
        request = OCRRequest(
            file_path="/path/to/doc.pdf",
            language="fra",
            preprocess=True,
            output_format="text",
            cache=True
        )

        # Premier appel (devrait être un MISS et mettre en cache).
        from services.ocr.ocr_wrapper import extract_text as ocr_extract_text_func # Importe la fonction de l'endpoint.
        result1 = await ocr_extract_text_func(request)
        mock_redis_client.get.assert_called_once() # Vérifie l'appel à get.
        mock_redis_client.setex.assert_called_once() # Vérifie l'appel à setex.
        assert result1.cached is False
        assert result1.text == "Contenu non mis en cache."

        # Réinitialise les mocks pour le deuxième appel.
        mock_redis_client.get.reset_mock()
        mock_redis_client.setex.reset_mock()
        mock_extractor.reset_mock()

        # Configure le mock Redis pour simuler un cache HIT.
        cached_data = {"text": "Contenu depuis le cache.", "confidence": 0.95, "processing_time": 0.01}
        mock_redis_client.get.return_value = json.dumps(cached_data)

        # Deuxième appel (devrait être un HIT).
        result2 = await ocr_extract_text_func(request)
        mock_redis_client.get.assert_called_once()
        mock_redis_client.setex.assert_not_called() # setex ne devrait pas être appelé.
        mock_extractor.assert_not_called() # L'extracteur ne devrait pas être appelé.
        assert result2.cached is True
        assert result2.text == "Contenu depuis le cache."
