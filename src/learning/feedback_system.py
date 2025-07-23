# src/learning/feedback_system.py
class FeedbackLearningSystem:
    def __init__(self):
        self.feedback_store = FeedbackStore()
        self.model_updater = ModelUpdater()

    async def collect_feedback(self,
                               query: str,
                               response: str,
                               user_rating: int,
                               corrections: Optional[str] = None):
        """Collecte le feedback utilisateur pour amélioration continue"""
        feedback = {
            'timestamp': datetime.utcnow(),
            'query': query,
            'response': response,
            'rating': user_rating,
            'corrections': corrections
        }

        await self.feedback_store.save(feedback)

        # Déclenche le fine-tuning si suffisamment de feedback
        if await self.should_trigger_retraining():
            await self.model_updater.schedule_retraining()