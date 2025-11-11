"""
Evaluation module for LLM dashboard comparison.

Provides metrics calculation and evaluation runners for comparing
Structured vs RAG pipeline outputs.

Main components:
- eval_metrics: Core metrics and scoring logic
- eval_runner: Evaluation pipeline and caching
"""

from .eval_metrics import (
    EvaluationMetrics,
    ComparisonResult,
    calculate_mrr,
    calculate_aggregate_mrr,
)

__all__ = [
    "EvaluationMetrics",
    "ComparisonResult",
    "calculate_mrr",
    "calculate_aggregate_mrr",
]
