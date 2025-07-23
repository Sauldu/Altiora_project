from typing import Dict, Any, List

from pydantic import BaseModel, Field


class TestScenario(BaseModel):
    id: str = Field(..., description="Unique identifier for the test scenario.")
    title: str = Field(..., min_length=5, description="Descriptive title of the test.")
    objective: str = Field(..., description="Purpose of the test.")
    criticality: str = Field("MEDIUM", description="Criticality of the test (HIGH, MEDIUM, LOW).")
    preconditions: List[str] = Field(default_factory=list, description="List of prerequisites for the test.")
    steps: List[str] = Field(..., min_items=1, description="Detailed steps to perform the test.")
    expected_result: str = Field(..., description="Expected outcome of the test.")
    test_data: Dict[str, Any] = Field(default_factory=dict, description="Data required for the test.")
    test_type: str = Field("FUNCTIONAL", description="Type of test (FUNCTIONAL, INTEGRATION, E2E, SECURITY, PERFORMANCE).")

    class Config:
        use_enum_values = True  # If using Enums for criticality/test_type
