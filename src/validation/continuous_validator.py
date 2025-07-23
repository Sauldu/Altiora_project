# src/validation/continuous_validator.py
class ContinuousValidator:
    def __init__(self):
        self.validators = [
            CodeQualityValidator(),
            SecurityValidator(),
            PerformanceValidator(),
            AIModelValidator()
        ]

    async def validate_commit(self, commit_hash: str):
        """Valide un commit avant merge"""
        results = {}

        for validator in self.validators:
            result = await validator.validate(commit_hash)
            results[validator.name] = result

            if result.is_blocking and not result.passed:
                raise ValidationError(f"{validator.name} failed: {result.message}")

        return ValidationReport(results)