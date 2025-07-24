# src/utils/question_router.py

class QuestionRouter:
    def classify(self, question):
        # Implémentation de la classification de la question
        if "code" in question:
            return "code_generation"
        elif "explication" in question:
            return "code_explanation"
        else:
            return "text_question"