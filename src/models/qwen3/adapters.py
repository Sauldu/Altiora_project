# src/models/qwen3/adapters.py
"""Module pour l'adaptation et la normalisation des données de sortie de Qwen3.

Ce module fournit des adaptateurs pour :
- Parser la sortie brute de Qwen3 (JSON ou texte semi-structuré).
- Valider et transformer ces données en structures internes typées (Pydantic).
- Générer des formats d'exportation standardisés (Excel, JSON, CSV).
"""

import datetime
import json
import re
from dataclasses import asdict
from typing import Dict, List, Any

from pydantic import BaseModel, Field, validator


# ------------------------------------------------------------------
# Modèles de sortie Qwen3 (structures de données internes)
# ------------------------------------------------------------------

class QwenScenario(BaseModel):
    """Représente un scénario de test extrait par Qwen3.

    Attributes:
        titre: Le titre du scénario de test.
        objectif: L'objectif principal du scénario.
        criticite: Le niveau de criticité du scénario (HAUTE, MOYENNE, BASSE).
        preconditions: Liste des conditions préalables à l'exécution du scénario.
        etapes: Liste des étapes détaillées du scénario.
        resultat_attendu: Le résultat attendu après l'exécution des étapes.
        donnees_test: Données spécifiques nécessaires pour l'exécution du test.
        type_test: Le type de test (ex: FONCTIONNEL, INTÉGRATION).
    """
    titre: str
    objectif: str
    criticite: str = Field(default="MOYENNE")
    preconditions: List[str] = Field(default_factory=list)
    etapes: List[str] = Field(default_factory=list)
    resultat_attendu: str
    donnees_test: Dict[str, Any] = Field(default_factory=dict)
    type_test: str = Field(default="FONCTIONNEL")

    @validator("criticite")
    def validate_criticite(cls, v: str) -> str:
        """Valide et normalise le niveau de criticité."""
        normalized_v = v.upper()
        if normalized_v in {"HAUTE", "MOYENNE", "BASSE"}:
            return normalized_v
        return "MOYENNE" # Valeur par défaut si invalide.


class QwenAnalysis(BaseModel):
    """Représente l'analyse complète d'une SFD par Qwen3."""
    scenarios: List[QwenScenario] = Field(default_factory=list)
    resume: str = Field("", description="Résumé textuel de l'analyse.")
    tags: List[str] = Field(default_factory=list, description="Tags ou mots-clés pertinents extraits.")


# ------------------------------------------------------------------
# Adaptateurs de parsing (conversion de la sortie brute de Qwen3)
# ------------------------------------------------------------------

class QwenOutputAdapter:
    """Adapte la sortie brute de Qwen3 (JSON ou texte) en objets typés `QwenAnalysis`."""

    @staticmethod
    def parse_json(raw: str) -> QwenAnalysis:
        """Parse une réponse JSON brute de Qwen3 en `QwenAnalysis`."

        Args:
            raw: La chaîne JSON brute.

        Returns:
            Une instance de `QwenAnalysis`.

        Raises:
            json.JSONDecodeError: Si la chaîne n'est pas un JSON valide.
        """
        try:
            data = json.loads(raw.strip())
            return QwenAnalysis(**data)
        except json.JSONDecodeError as e:
            # Retourne une analyse vide avec l'erreur pour faciliter le débogage.
            return QwenAnalysis(scenarios=[], resume=f"Erreur de parsing JSON : {e}")

    @staticmethod
    def parse_text(raw: str) -> QwenAnalysis:
        """Parse une réponse textuelle semi-structurée de Qwen3 via des expressions régulières."

        Args:
            raw: La chaîne de texte brute.

        Returns:
            Une instance de `QwenAnalysis` avec les scénarios extraits.
        """
        scenarios = []
        # Divise le texte en blocs de scénarios.
        blocks = re.split(r"\n##+ ", raw.strip())
        for block in blocks:
            # Extrait le titre et le contenu de chaque scénario.
            match = re.search(r"### (.+?)\n(.+?)(?=\n##|$)", block, re.DOTALL)
            if match:
                titre, contenu = match.groups()
                # Crée un QwenScenario avec les informations extraites.
                scenarios.append(
                    QwenScenario(
                        titre=titre.strip(),
                        objectif=contenu.strip()[:100] + "...", # Extrait un aperçu de l'objectif.
                        criticite="MOYENNE", # Valeur par défaut pour le parsing texte.
                        etapes=contenu.strip().splitlines()[:5], # Extrait les premières lignes comme étapes.
                        resultat_attendu="À compléter",
                    )
                )
        return QwenAnalysis(scenarios=scenarios, resume="Analyse textuelle partielle.")

    @staticmethod
    def normalize(raw: str, format_hint: str = "json") -> QwenAnalysis:
        """Normalise n'importe quelle sortie brute de Qwen3 en `QwenAnalysis`.

        Args:
            raw: La chaîne de sortie brute.
            format_hint: Une indication sur le format attendu ('json' ou 'text').

        Returns:
            Une instance de `QwenAnalysis`.
        """
        if format_hint == "json":
            return QwenOutputAdapter.parse_json(raw)
        return QwenOutputAdapter.parse_text(raw)


# ------------------------------------------------------------------
# Adaptateurs d'export (conversion des objets Qwen vers d'autres formats)
# ------------------------------------------------------------------

class ExportAdapter:
    """Convertit les objets `QwenAnalysis` et `QwenScenario` en différents formats d'exportation."""

    @staticmethod
    def to_excel_dict(analysis: QwenAnalysis) -> Dict[str, Any]:
        """Prépare les données d'analyse pour l'exportation via `ExcelFormatter`."

        Args:
            analysis: L'objet `QwenAnalysis` à convertir.

        Returns:
            Un dictionnaire formaté pour être utilisé par `ExcelFormatter`.
        """
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
                "generated_at": str(datetime.datetime.utcnow()),
            },
        }

    @staticmethod
    def to_json_dict(analysis: QwenAnalysis) -> Dict[str, Any]:
        """Convertit une `QwenAnalysis` en un dictionnaire JSON structuré."""
        return {
            "scenarios": [asdict(s) for s in analysis.scenarios],
            "summary": {
                "count": len(analysis.scenarios),
                "tags": analysis.tags,
            },
        }

    @staticmethod
    def to_csv_rows(analysis: QwenAnalysis) -> List[Dict[str, str]]:
        """Convertit une `QwenAnalysis` en une liste de dictionnaires prêts pour l'export CSV."""
        return [
            {
                "Titre": s.titre,
                "Objectif": s.objectif.replace("\n", " "), # Supprime les retours à la ligne pour le CSV.
                "Criticite": s.criticite,
                "Type": s.type_test,
            }
            for s in analysis.scenarios
        ]


# ------------------------------------------------------------------
# Utilitaires rapides
# ------------------------------------------------------------------

def validate_qwen_output(raw: str) -> bool:
    """Vérifie rapidement si la sortie brute de Qwen3 est un JSON exploitable."""
    try:
        QwenOutputAdapter.parse_json(raw)
        return True
    except Exception:
        return False


def extract_scenarios_only(raw: str) -> List[Dict[str, Any]]:
    """Extrait et retourne uniquement la liste brute des scénarios d'une sortie Qwen3."""
    analysis = QwenOutputAdapter.normalize(raw)
    return [asdict(s) for s in analysis.scenarios]


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Exemple de sortie JSON brute de Qwen3
    json_output = '''
    {
      "scenarios": [
        {
          "titre": "Connexion réussie",
          "objectif": "Vérifier la connexion avec des identifiants valides.",
          "criticite": "HAUTE",
          "preconditions": ["Utilisateur enregistré"],
          "etapes": ["1. Ouvrir la page de connexion", "2. Entrer email et mot de passe", "3. Cliquer sur 'Se connecter'"],
          "resultat_attendu": "Redirection vers le tableau de bord.",
          "donnees_test": {"email": "test@example.com", "password": "password123"},
          "type_test": "FONCTIONNEL"
        }
      ],
      "resume": "Analyse des fonctionnalités de connexion.",
      "tags": ["connexion", "authentification"]
    }
    '''

    # Exemple de sortie texte brute de Qwen3
    text_output = '''
## Scénario: Inscription utilisateur
### Titre: Inscription réussie
Objectif: Vérifier que l'utilisateur peut s'inscrire avec des informations valides.
Étapes:
1. Naviguer vers la page d'inscription.
2. Remplir tous les champs obligatoires.
3. Cliquer sur le bouton 'S'inscrire'.
Résultat attendu: L'utilisateur est redirigé vers la page de confirmation.
    '''

    print("\n--- Parsing de sortie JSON ---")
    analysis_json = QwenOutputAdapter.normalize(json_output, format_hint="json")
    logging.info(f"Scénarios JSON extraits : {len(analysis_json.scenarios)}")
    logging.info(f"Résumé JSON : {analysis_json.resume}")

    print("\n--- Parsing de sortie Texte ---")
    analysis_text = QwenOutputAdapter.normalize(text_output, format_hint="text")
    logging.info(f"Scénarios Texte extraits : {len(analysis_text.scenarios)}")
    logging.info(f"Titre du premier scénario texte : {analysis_text.scenarios[0].titre}")

    print("\n--- Exportation vers Excel (format dict) ---")
    excel_data = ExportAdapter.to_excel_dict(analysis_json)
    logging.info(f"Données Excel préparées : {excel_data['rows'][0]}")

    print("\n--- Exportation vers JSON (format dict) ---")
    json_data = ExportAdapter.to_json_dict(analysis_json)
    logging.info(f"Données JSON exportées : {json.dumps(json_data, indent=2, ensure_ascii=False)}")

    print("\n--- Vérification rapide de la sortie ---")
    is_valid = validate_qwen_output(json_output)
    logging.info(f"La sortie JSON est-elle valide ? {is_valid}")

    print("\n--- Extraction des scénarios uniquement ---")
    scenarios_only = extract_scenarios_only(json_output)
    logging.info(f"Scénarios extraits (liste brute) : {scenarios_only}")