from pydantic import BaseModel, Field, validator


class SFDAnalysisRequest(BaseModel):
    """Modèle de requête pour l'analyse d'une Spécification Fonctionnelle Détaillée (SFD).

    Ce modèle Pydantic valide les données entrantes pour une demande d'analyse de SFD.

    Attributes:
        content: Le contenu textuel brut de la SFD à analyser.
        extraction_type: Le type d'extraction à effectuer. Peut être 'complete',
                         'summary', ou 'critical_only'.
        language: La langue du document (ex: 'fr', 'en').
    """
    content: str = Field(..., min_length=10, description="Contenu textuel du SFD à analyser.")
    extraction_type: str = Field(default="complete", description="Type d'extraction souhaité (complete, summary, critical_only).")
    language: str = Field(default="fr", description="Langue du SFD (ex: 'fr', 'en').")

    @validator('extraction_type')
    def validate_extraction_type(cls, v):
        """Valide que le type d'extraction est une des valeurs autorisées."""
        allowed = ["complete", "summary", "critical_only"]
        if v not in allowed:
            raise ValueError(f"Le type d'extraction doit être l'un des suivants : {allowed}")
        return v

    @validator('language')
    def validate_language(cls, v):
        """Valide que la langue est une des valeurs autorisées."""
        allowed = ["fr", "en"]
        if v not in allowed:
            raise ValueError(f"La langue doit être l'une des suivantes : {allowed}")
        return v