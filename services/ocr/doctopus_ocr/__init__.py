# services/ocr/doctopus_ocr/__init__.py
"""
Stub OCR engine – never crashes if the real one is missing
"""

class DoctoplusWrapper:
    """
    Minimal mock that returns plausible OCR results
    """

    def __init__(self, config_path: str):
        self.config_path = config_path

    @staticmethod
    async def extract_text(
            *,
        file_path: str,
        language: str = "fra",
        preprocess: bool = True,
        confidence_threshold: float = 0.8,
        output_format: str = "text",
    ) -> dict:
        """Return mock data"""
        import asyncio
        await asyncio.sleep(0.2)  # Simulate work
        return {
            "text": f"Mock OCR text for {file_path}",
            "confidence": 0.92,
            "pages": 1,
        }