# src/models/starcoder_model.py
from transformers import AutoModelForCausalLM, AutoTokenizer

def load_starcoder_model():
    model_name = "bigcode/starcoder"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    return model, tokenizer

class StarcoderModel:
    def __init__(self):
        self.model, self.tokenizer = load_starcoder_model()

    def generate(self, question, context=None):
        # Implémentation de la génération de code
        return "Code généré"

    def extract_code(self, context):
        # Implémentation de l'extraction de code
        return "Code extrait"