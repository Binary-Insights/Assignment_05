"""Pydantic models for ground truth evaluation data."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, RootModel


class KeyFact(BaseModel):
    """Individual ground truth fact."""
    
    id: str = Field(..., description="Unique fact identifier")
    claim: str = Field(..., description="The factual claim")
    source_urls: List[str] = Field(..., description="List of source URLs")
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level in the fact"
    )
    date: datetime = Field(..., description="Date the fact was recorded")
    category: str = Field(
        ..., 
        description="Category of the fact (e.g., 'funding', 'company_focus', 'investors', 'headquarters', 'founding', 'product', 'partnerships')"
    )


class ReferenceMaterial(BaseModel):
    """Reference material and key facts for a company."""
    
    official_sources: List[str] = Field(
        ..., description="Official sources (LinkedIn, company website, Crunchbase, etc.)"
    )
    key_facts: List[KeyFact] = Field(
        ..., description="List of verified key facts about the company"
    )
    hallucination_examples: List[str] = Field(
        ..., description="Examples of common hallucinations or false claims"
    )


class EvaluationNotes(BaseModel):
    """Evaluation-specific notes for a company."""
    
    structured_pipeline_notes: str = Field(
        ..., description="Notes for structured pipeline evaluation"
    )
    rag_pipeline_notes: str = Field(
        ..., description="Notes for RAG pipeline evaluation"
    )
    common_issues: List[str] = Field(
        ..., description="Common issues to watch for during evaluation"
    )


class CompanyGroundTruth(BaseModel):
    """Complete ground truth data for a single company."""
    
    company_name: str = Field(..., description="Official company name")
    company_slug: str = Field(..., description="URL-friendly company identifier")
    reference_material: ReferenceMaterial = Field(
        ..., description="Reference material and verified facts"
    )
    evaluation_notes: EvaluationNotes = Field(
        ..., description="Notes for evaluation"
    )


class GroundTruthCollection(RootModel):
    """Collection of ground truth data for multiple companies."""
    
    root: Dict[str, CompanyGroundTruth] = Field(
        ...,
        description="Dictionary mapping company slugs to their ground truth data"
    )

    class Config:
        title = "Ground Truth Collection"
        description = "Complete collection of ground truth data for AI company evaluations"


# Alternative direct dictionary approach for easier usage
class GroundTruthDict(BaseModel):
    """Alternative schema using RootModel-like behavior."""
    
    class Config:
        title = "Ground Truth Data"
        extra = "allow"
