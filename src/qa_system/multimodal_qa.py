# src/qa_system/multimodal_qa.py
from src.models.qwen_model import QwenModel
from src.models.starcoder_model import StarcoderModel
from src.utils.question_router import QuestionRouter


class MultiModalQASystem:
    def __init__(self):
        self.text_model = QwenModel()
        self.code_model = StarcoderModel()
        self.router = QuestionRouter()

    def answer_question(self, question, context=None):
        """Route vers le bon modèle selon le type de question"""
        question_type = self.router.classify(question)

        if question_type == "code_generation":
            return self.code_model.generate(question, context)
        elif question_type == "code_explanation":
            # Utiliser les deux modèles
            code = self.code_model.extract_code(context)
            explanation = self.text_model.explain(code)
            return explanation
        else:
            return self.text_model.answer(question, context)