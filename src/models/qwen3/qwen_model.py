# src/models/qwen_model.py
from transformers import AutoModelForCausalLM, AutoTokenizer

def load_qwen_model():
    model_name = "Qwen/Qwen3-32B-q4_K_M"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    return model, tokenizer

class QwenModel:
    def __init__(self):
        self.model, self.tokenizer = load_qwen_model()

    def answer(self, question, context=None):
        # Implémentation de la réponse à une question
        return "Réponse du modèle texte"

    def explain(self, code):
        # Implémentation de l'explication de code
        return "Explication du code"