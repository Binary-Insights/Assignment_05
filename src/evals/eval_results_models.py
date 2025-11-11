"""Pydantic models for evaluation results."""

from datetime import datetime
from typing import Dict, Literal
from pydantic import BaseModel, Field, validator, RootModel


class EvaluationResult(BaseModel):
    """Schema for individual evaluation result entry.
    
    Scoring ranges:
    - factual_accuracy: 0–3
    - schema_compliance: 0–2
    - provenance_quality: 0–2
    - hallucination_detection: 0–2
    - readability: 0–1
    - mrr_score: 0–1
    - total_score: Sum of all metrics (0–11)
    """
    
    company_name: str
    company_slug: str
    pipeline_type: Literal["structured", "rag"]
    timestamp: datetime
    factual_accuracy: int = Field(..., ge=0, le=3, description="Factual accuracy score (0–3)")
    schema_compliance: int = Field(..., ge=0, le=2, description="Schema compliance score (0–2)")
    provenance_quality: int = Field(..., ge=0, le=2, description="Provenance quality score (0–2)")
    hallucination_detection: int = Field(..., ge=0, le=2, description="Hallucination detection score (0–2)")
    readability: int = Field(..., ge=0, le=1, description="Readability score (0–1)")
    mrr_score: float = Field(..., ge=0.0, le=1.0, description="MRR score (0–1)")
    notes: str
    total_score: float = Field(..., ge=0, le=11, description="Total score - sum of all metrics (0–11)")
    
    @validator("total_score")
    def validate_total_score(cls, v, values):
        """Validate that total_score equals the sum of individual scores."""
        if not values:  # Skip if other fields not yet validated
            return v
        
        expected_total = (
            values.get("factual_accuracy", 0) +
            values.get("schema_compliance", 0) +
            values.get("provenance_quality", 0) +
            values.get("hallucination_detection", 0) +
            values.get("readability", 0) +
            values.get("mrr_score", 0)
        )
        
        if abs(v - expected_total) > 0.01:  # Allow small floating point differences
            raise ValueError(
                f"total_score ({v}) must equal sum of individual scores ({expected_total}). "
                f"Expected: {expected_total}, Got: {v}"
            )
        return v


class CompanyEvaluations(BaseModel):
    """Schema for a company with both structured and rag evaluations."""
    
    structured: EvaluationResult
    rag: EvaluationResult


class EvaluationResultsCollection(RootModel):
    """Root schema for the complete evaluation results collection."""
    
    root: Dict[str, CompanyEvaluations] = Field(
        ...,
        description="Dictionary mapping company slugs to their evaluation results"
    )

    class Config:
        title = "Evaluation Results Collection"
        description = "Complete collection of RAG vs Structured pipeline evaluation results"


# Alternative simpler approach using a Dict wrapper
class EvaluationResultsDict(BaseModel):
    """Alternative schema using direct dictionary approach."""
    
    class Config:
        title = "Evaluation Results"
        extra = "allow"  # Allow arbitrary company keys
    
    def __getitem__(self, key: str) -> CompanyEvaluations:
        """Allow dictionary-like access."""
        return getattr(self, key)
