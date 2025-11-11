"""
Example Usage of the Result Evaluator

Demonstrates how to use the evaluator in different scenarios.
"""

# Example 1: Evaluate a single company
# ====================================

from src.evals.result_evaluator import evaluate_company
from src.evals.eval_results_models import EvaluationResultsCollection
import json

# Evaluate Anthropic
evaluation = evaluate_company(
    company_slug="anthropic",
    company_name="Anthropic",
    ground_truth_path="data/eval/ground_truth.json",
    structured_response_path="data/llm_response/structured_responses.json",
    rag_response_path="data/llm_response/rag_responses.json"
)

if evaluation:
    print("=" * 60)
    print(f"EVALUATION RESULTS FOR ANTHROPIC")
    print("=" * 60)
    
    print("\n📋 STRUCTURED PIPELINE")
    print(f"  Factual Accuracy:      {evaluation.structured.factual_accuracy}/3")
    print(f"  Schema Compliance:     {evaluation.structured.schema_compliance}/2")
    print(f"  Provenance Quality:    {evaluation.structured.provenance_quality}/2")
    print(f"  Hallucination Detection: {evaluation.structured.hallucination_detection}/2")
    print(f"  Readability:           {evaluation.structured.readability}/1")
    print(f"  MRR Score:             {evaluation.structured.mrr_score:.3f}/1.0")
    print(f"  {'─' * 40}")
    print(f"  TOTAL SCORE:           {evaluation.structured.total_score:.1f}/11")
    
    print("\n🔄 RAG PIPELINE")
    print(f"  Factual Accuracy:      {evaluation.rag.factual_accuracy}/3")
    print(f"  Schema Compliance:     {evaluation.rag.schema_compliance}/2")
    print(f"  Provenance Quality:    {evaluation.rag.provenance_quality}/2")
    print(f"  Hallucination Detection: {evaluation.rag.hallucination_detection}/2")
    print(f"  Readability:           {evaluation.rag.readability}/1")
    print(f"  MRR Score:             {evaluation.rag.mrr_score:.3f}/1.0")
    print(f"  {'─' * 40}")
    print(f"  TOTAL SCORE:           {evaluation.rag.total_score:.1f}/11")
    
    # Determine winner
    diff = evaluation.structured.total_score - evaluation.rag.total_score
    if diff > 0:
        print(f"\n✅ STRUCTURED PIPELINE WINS by {diff:.1f} points")
    elif diff < 0:
        print(f"\n✅ RAG PIPELINE WINS by {abs(diff):.1f} points")
    else:
        print(f"\n🤝 TIE: Both pipelines scored {evaluation.structured.total_score:.1f}/11")


# Example 2: Batch evaluate all companies and save results
# ========================================================

from src.evals.result_evaluator import evaluate_batch, get_evaluation_summary

print("\n" + "=" * 60)
print("BATCH EVALUATION")
print("=" * 60)

results = evaluate_batch(
    ground_truth_path="data/eval/ground_truth.json",
    structured_response_path="data/llm_response/structured_responses.json",
    rag_response_path="data/llm_response/rag_responses.json",
    output_path="data/eval/results.json"
)

summary = get_evaluation_summary(results)

print(f"\n📊 SUMMARY STATISTICS")
print(f"  Total Companies Evaluated: {summary.get('total_companies', 0)}")
print(f"  Structured Avg Score:      {summary.get('structured_avg_score', 0):.2f}/11")
print(f"  RAG Avg Score:             {summary.get('rag_avg_score', 0):.2f}/11")
print(f"  Structured Avg MRR:        {summary.get('structured_avg_mrr', 0):.3f}")
print(f"  RAG Avg MRR:               {summary.get('rag_avg_mrr', 0):.3f}")
print(f"  Structured Better:         {summary.get('structured_better_count', 0)} companies")
print(f"  RAG Better:                {summary.get('rag_better_count', 0)} companies")


# Example 3: Load and analyze results
# ===================================

print("\n" + "=" * 60)
print("ANALYZING RESULTS")
print("=" * 60)

with open("data/eval/results.json") as f:
    data = json.load(f)

results_collection = EvaluationResultsCollection(root=data)

print("\n🔍 DETAILED COMPARISON")
print(f"{'Company':<20} {'Struct':<10} {'RAG':<10} {'Winner':<15} {'Diff':<8}")
print("─" * 63)

for slug, company_data in results_collection.root.items():
    struct_score = company_data.structured.total_score
    rag_score = company_data.rag.total_score
    diff = struct_score - rag_score
    
    if diff > 0:
        winner = "📋 Structured"
    elif diff < 0:
        winner = "🔄 RAG"
    else:
        winner = "🤝 Tie"
    
    company_name = company_data.structured.company_name[:17]
    print(f"{company_name:<20} {struct_score:<10.1f} {rag_score:<10.1f} {winner:<15} {abs(diff):<8.1f}")


# Example 4: Compare specific metrics across pipelines
# ===================================================

print("\n" + "=" * 60)
print("METRIC BREAKDOWN")
print("=" * 60)

metrics = [
    ("Factual Accuracy", "factual_accuracy", "3"),
    ("Schema Compliance", "schema_compliance", "2"),
    ("Provenance Quality", "provenance_quality", "2"),
    ("Hallucination Detection", "hallucination_detection", "2"),
    ("Readability", "readability", "1"),
    ("MRR", "mrr_score", "1.0"),
]

print(f"\n{'Metric':<25} {'Struct Avg':<15} {'RAG Avg':<15} {'Winner':<12}")
print("─" * 67)

for metric_name, field_name, max_val in metrics:
    struct_values = []
    rag_values = []
    
    for slug, company_data in results_collection.root.items():
        struct_val = getattr(company_data.structured, field_name)
        rag_val = getattr(company_data.rag, field_name)
        struct_values.append(struct_val)
        rag_values.append(rag_val)
    
    struct_avg = sum(struct_values) / len(struct_values) if struct_values else 0
    rag_avg = sum(rag_values) / len(rag_values) if rag_values else 0
    
    if struct_avg > rag_avg:
        winner = "📋 Structured"
    elif rag_avg > struct_avg:
        winner = "🔄 RAG"
    else:
        winner = "🤝 Tie"
    
    print(f"{metric_name:<25} {struct_avg:<15.3f} {rag_avg:<15.3f} {winner:<12}")


# Example 5: Using with Pydantic validation
# ==========================================

print("\n" + "=" * 60)
print("PYDANTIC VALIDATION EXAMPLES")
print("=" * 60)

from src.evals.eval_results_models import EvaluationResult
from datetime import datetime

# Valid evaluation
print("\n✅ Creating valid evaluation...")
valid_eval = EvaluationResult(
    company_name="Test Company",
    company_slug="test-company",
    pipeline_type="structured",
    timestamp=datetime.now(),
    factual_accuracy=2,
    schema_compliance=1,
    provenance_quality=2,
    hallucination_detection=1,
    readability=0,
    mrr_score=1.0,
    notes="Valid evaluation",
    total_score=7.0  # 2+1+2+1+0+1 = 7
)
print(f"✓ Total Score: {valid_eval.total_score}")

# Invalid evaluation - will raise error
print("\n❌ Attempting invalid evaluation (factual_accuracy=4)...")
try:
    invalid_eval = EvaluationResult(
        company_name="Test",
        company_slug="test",
        pipeline_type="structured",
        timestamp=datetime.now(),
        factual_accuracy=4,  # ❌ Max is 3
        schema_compliance=1,
        provenance_quality=2,
        hallucination_detection=1,
        readability=0,
        mrr_score=1.0,
        notes="Invalid",
        total_score=9.0
    )
except ValueError as e:
    print(f"✓ Caught validation error: {str(e)[:50]}...")

# Invalid total score
print("\n❌ Attempting invalid evaluation (total_score mismatch)...")
try:
    invalid_total = EvaluationResult(
        company_name="Test",
        company_slug="test",
        pipeline_type="structured",
        timestamp=datetime.now(),
        factual_accuracy=2,
        schema_compliance=1,
        provenance_quality=2,
        hallucination_detection=1,
        readability=0,
        mrr_score=1.0,
        notes="Invalid total",
        total_score=10.0  # ❌ Should be 7.0
    )
except ValueError as e:
    print(f"✓ Caught validation error: {str(e)[:50]}...")


# Example 6: Export results to CSV
# ================================

print("\n" + "=" * 60)
print("EXPORTING RESULTS")
print("=" * 60)

import csv

csv_file = "evaluation_results.csv"
with open(csv_file, 'w', newline='') as f:
    writer = csv.writer(f)
    
    # Header
    writer.writerow([
        "Company",
        "Structured Score",
        "RAG Score",
        "Struct Factual",
        "RAG Factual",
        "Struct Schema",
        "RAG Schema",
        "Struct Provenance",
        "RAG Provenance",
        "Struct Hallucination",
        "RAG Hallucination",
        "Struct Readability",
        "RAG Readability",
        "Struct MRR",
        "RAG MRR"
    ])
    
    # Data rows
    for slug, company_data in results_collection.root.items():
        writer.writerow([
            company_data.structured.company_name,
            company_data.structured.total_score,
            company_data.rag.total_score,
            company_data.structured.factual_accuracy,
            company_data.rag.factual_accuracy,
            company_data.structured.schema_compliance,
            company_data.rag.schema_compliance,
            company_data.structured.provenance_quality,
            company_data.rag.provenance_quality,
            company_data.structured.hallucination_detection,
            company_data.rag.hallucination_detection,
            company_data.structured.readability,
            company_data.rag.readability,
            company_data.structured.mrr_score,
            company_data.rag.mrr_score,
        ])

print(f"✓ Results exported to {csv_file}")


print("\n" + "=" * 60)
print("EXAMPLES COMPLETE")
print("=" * 60)
