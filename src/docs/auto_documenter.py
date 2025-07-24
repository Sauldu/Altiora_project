from src.docs.helpers import CodeAnalyzer, DocGenerator

# src/docs/auto_documenter.py
class AutoDocumenter:
    def __init__(self):
        self.code_analyzer = CodeAnalyzer()
        self.doc_generator = DocGenerator()

    def generate_project_docs(self):
        """Génère la documentation complète du projet"""
        # Analyse de l'architecture
        architecture = self.code_analyzer.analyze_architecture()

        # Génération des diagrammes
        diagrams = self.generate_diagrams(architecture)

        # Documentation API
        api_docs = self.generate_api_docs()

        # Guide utilisateur
        user_guide = self.generate_user_guide()

        return {
            'architecture': architecture,
            'diagrams': diagrams,
            'api': api_docs,
            'guide': user_guide
        }