# src/models/hybrid_engine.py
class HybridEngine:
    """Utilise GPU quand disponible, CPU sinon"""
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.cpu_fallback = CPUOptimizedModel()