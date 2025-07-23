# src/ensemble/multi_model.py
class MultiModelEnsemble:
    def __init__(self, models: List[str]):
        self.models = self.load_models(models)
        self.voting_strategy = WeightedVoting()

    async def generate(self, prompt: str) -> str:
        """Génère une réponse en utilisant plusieurs modèles"""
        responses = await asyncio.gather(*[
            model.generate(prompt) for model in self.models
        ])

        # Vote pondéré basé sur la confiance
        best_response = self.voting_strategy.select(
            responses,
            weights=self.calculate_confidence_weights(responses)
        )

        return best_response