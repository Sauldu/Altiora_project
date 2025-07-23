from pydantic import BaseModel, Field, validator


class SFDAnalysisRequest(BaseModel):
    content: str = Field(..., min_length=10, description="Contenu textuel du SFD à analyser.")
    extraction_type: str = Field(default="complete", description="Type d'extraction souhaité (complete, summary, critical_only).")
    language: str = Field(default="fr", description="Langue du SFD (ex: 'fr', 'en').")

    @validator('extraction_type')
    def validate_extraction_type(cls, v):
        allowed = ["complete", "summary", "critical_only"]
        if v not in allowed:
            raise ValueError(f"extraction_type must be one of {allowed}")
        return v

    @validator('language')
    def validate_language(cls, v):
        allowed = ["fr", "en"]
        if v not in allowed:
            raise ValueError(f"language must be one of {allowed}")
        return v
