# src/utils/question_router.py
"""Module pour le routage des questions vers des modules de traitement appropriés.

Ce module contient une logique simple pour classifier les questions posées par
l'utilisateur et les diriger vers des fonctionnalités spécifiques de l'application,
comme la génération de code, l'explication de code ou la réponse à des questions textuelles.
"""

class QuestionRouter:
    """Classe responsable de la classification des questions utilisateur."""

    def classify(self, question: str) -> str:
        """Classifie une question donnée en fonction de son contenu.

        Args:
            question: La chaîne de caractères représentant la question de l'utilisateur.

        Returns:
            Une chaîne de caractères indiquant la catégorie de la question :
            - "code_generation" si la question semble demander la génération de code.
            - "code_explanation" si la question semble demander une explication de code.
            - "text_question" pour toutes les autres questions (par défaut).
        """
        # Implémentation de la classification de la question basée sur des mots-clés simples.
        # Cette logique peut être étendue avec des modèles de NLP plus sophistiqués.
        if "code" in question.lower() and ("générer" in question.lower() or "écrire" in question.lower()):
            return "code_generation"
        elif "explication" in question.lower() or "expliquer" in question.lower() and "code" in question.lower():
            return "code_explanation"
        else:
            return "text_question"


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    router = QuestionRouter()

    questions = [
        "Peux-tu générer du code Python pour une fonction de tri ?",
        "Explique-moi ce bloc de code JavaScript.",
        "Quelle est la capitale de la France ?",
        "Écris un test Playwright pour une page de connexion.",
        "Comment fonctionne l'algorithme de Dijkstra ?"
    ]

    print("\n--- Classification des questions ---")
    for q in questions:
        category = router.classify(q)
        print(f"Question: \"{q}\" -> Catégorie: {category}")
