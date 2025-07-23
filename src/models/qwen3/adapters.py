"""
Adaptateurs Qwen3 – Conversion & normalisation des données
Responsabilités :
- Parser la sortie brute de Qwen3
- Valider & transformer en structures internes
- Générer formats d’export (Excel, JSON, CSV)
"""

import datetime
import json
import re
from dataclasses import asdict
from typing import Dict, List, Any

from pydantic import BaseModel, Field, validator


# ------------------------------------------------------------------
# Modèles de sortie Qwen3
# ------------------------------------------------------------------

class QwenScenario(BaseModel):
    """Scénario de test extrait par Qwen3"""
    titre: str
    objectif: str
    criticite: str = Field(default="MOYENNE")
    preconditions: List[str] = Field(default_factory=list)
    etapes: List[str] = Field(default_factory=list)
    resultat_attendu: str
    donnees_test: Dict[str, Any] = Field(default_factory=dict)
    type_test: str = Field(default="FONCTIONNEL")

    @validator("criticite")
    def validate_criticite(cls, v):
        return v.upper() if v.upper() in {"HAUTE", "MOYENNE", "BASSE"} else "MOYENNE"


class QwenAnalysis(BaseModel):
    """Analyse complète d’un SFD"""
    scenarios: List[QwenScenario] = Field(default_factory=list)
    resume: str = ""
    tags: List[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Adapteurs de parsing
# ------------------------------------------------------------------

class QwenOutputAdapter:
    """Adapte la sortie brute de Qwen3 vers des objets typés"""

    @staticmethod
    def parse_json(raw: str) -> QwenAnalysis:
        """Parse une réponse JSON brute"""
        try:
            data = json.loads(raw.strip())
            return QwenAnalysis(**data)
        except json.JSONDecodeError as e:
            return QwenAnalysis(scenarios=[], resume=f"Erreur JSON : {e}")

    @staticmethod
    def parse_text(raw: str) -> QwenAnalysis:
        """Parse une réponse textuelle semi-structurée via regex"""
        scenarios = []
        blocks = re.split(r"\n##+ ", raw.strip())
        for block in blocks:
            match = re.search(r"### (.+?)\n(.+?)(?=\n##|$)", block, re.DOTALL)
            if match:
                titre, contenu = match.groups()
                scenarios.append(
                    QwenScenario(
                        titre=titre.strip(),
                        objectif=contenu.strip()[:100] + "...",
                        criticite="MOYENNE",
                        etapes=contenu.strip().splitlines()[:5],
                        resultat_attendu="À compléter",
                    )
                )
        return QwenAnalysis(scenarios=scenarios, resume="Parse textuel")

    @staticmethod
    def normalize(raw: str, format_hint: str = "json") -> QwenAnalysis:
        """Normalise n’importe quelle sortie"""
        if format_hint == "json":
            return QwenOutputAdapter.parse_json(raw)
        return QwenOutputAdapter.parse_text(raw)


# ------------------------------------------------------------------
# Adaptateurs d’export
# ------------------------------------------------------------------

class ExportAdapter:
    """Convertit les objets Qwen en formats d’export"""

    @staticmethod
    def to_excel_dict(analysis: QwenAnalysis) -> Dict[str, Any]:
        """Prépare les données pour ExcelFormatter"""
        return {
            "rows": [
                {
                    "ID": idx,
                    "Titre": s.titre,
                    "Objectif": s.objectif,
                    "Criticite": s.criticite,
                    "Preconditions": "\n".join(s.preconditions),
                    "Etapes": "\n".join(s.etapes),
                    "Resultat": s.resultat_attendu,
                    "Type": s.type_test,
                }
                for idx, s in enumerate(analysis.scenarios, 1)
            ],
            "metadata": {
                "total_scenarios": len(analysis.scenarios),
                "generated_at": str(datetime.utcnow()),
            },
        }

    @staticmethod
    def to_json_dict(analysis: QwenAnalysis) -> Dict[str, Any]:
        """Export JSON structuré"""
        return {
            "scenarios": [asdict(s) for s in analysis.scenarios],
            "summary": {
                "count": len(analysis.scenarios),
                "tags": analysis.tags,
            },
        }

    @staticmethod
    def to_csv_rows(analysis: QwenAnalysis) -> List[Dict[str, str]]:
        """Lignes CSV prêtes à l’emploi"""
        return [
            {
                "Titre": s.titre,
                "Objectif": s.objectif.replace("\n", " "),
                "Criticite": s.criticite,
                "Type": s.type_test,
            }
            for s in analysis.scenarios
        ]


# ------------------------------------------------------------------
# Utilitaires rapides
# ------------------------------------------------------------------

def validate_qwen_output(raw: str) -> bool:
    """Vérifie rapidement si la sortie est exploitable"""
    try:
        QwenOutputAdapter.parse_json(raw)
        return True
    except Exception:
        return False


def extract_scenarios_only(raw: str) -> List[Dict[str, Any]]:
    """Retourne uniquement la liste brute des scénarios"""
    analysis = QwenOutputAdapter.normalize(raw)
    return [asdict(s) for s in analysis.scenarios]
