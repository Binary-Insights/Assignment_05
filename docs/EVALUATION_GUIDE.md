# Evaluation Framework Guide

## Overview

This document describes the evaluation framework for comparing LLM-generated outputs from two pipelines:
1. **Structured Pipeline**: Uses structured payload data with LLM for dashboard generation
2. **RAG Pipeline**: Uses Pinecone vector retrieval + LLM for dashboard generation

## Evaluation Metrics

### 1. Factual Accuracy (0–3)
Measures how accurate the generated information is compared to ground truth.
- **0**: Most facts are incorrect or hallucinated
- **1**: Facts are partially accurate but contain significant errors
- **2**: Facts are mostly accurate with minor inconsistencies
- **3**: All critical facts are accurate and verifiable

### 2. Schema Compliance (0–2)
Measures how well the output follows the required dashboard schema.
- **0**: Missing multiple required sections
- **1**: Covers most sections but some data is missing or poorly formatted
- **2**: Complete schema with all required sections properly formatted

### 3. Provenance Quality (0–2)
Measures the inclusion and accuracy of source citations.
- **0**: No provenance information or all citations are incorrect
- **1**: Some citations provided but incomplete or partially incorrect
- **2**: Complete and accurate citations for key claims

### 4. Hallucination Detection (0–2)
Measures the presence of false information not found in source data.
- **0**: Multiple hallucinations present (3+ false claims)
- **1**: Few hallucinations (1-2 false claims)
- **2**: No hallucinations detected

### 5. Readability (0–1)
Measures clarity and presentation quality.
- **0**: Poor formatting, hard to read, confusing structure
- **1**: Clear formatting, well-organized, easy to read

### 6. Mean Reciprocal Ranking (MRR)
Measures the ranking quality of extracted facts and information.
- Calculates: 1/rank of first relevant fact
- Range: 0.0 to 1.0
- Average MRR across all facts for overall ranking quality

**Why MRR is good for this evaluation:**
- ✓ Captures the order/ranking of information quality
- ✓ Sensitive to highly relevant information appearing early
- ✓ Standard metric in information retrieval
- ✓ Works well for comparing pipeline ranking strategies
- ✓ Complements absolute accuracy metrics

## Ground Truth Dataset Structure

### Ground Truth File Format

**Location**: `data/eval/ground_truth.json`

```json
{
  "world-labs": {
    "company_name": "World Labs",
    "reference_material": {
      "official_sources": ["https://www.linkedin.com/company/world-labs", "https://worldlabs.ai"],
      "key_facts": [
        {
          "claim": "World Labs raised $230M in Series Unknown",
          "source_url": "https://www.crunchbase.com/organization/world-labs",
          "confidence": "high"
        }
      ]
    },
    "structured_pipeline": {
      "factual_accuracy": 3,
      "schema_compliance": 2,
      "provenance_quality": 2,
      "hallucination_detection": 2,
      "readability": 1,
      "mrr_score": 0.95,
      "notes": "Excellent structured output with clear provenance"
    },
    "rag_pipeline": {
      "factual_accuracy": 2,
      "schema_compliance": 2,
      "provenance_quality": 1,
      "hallucination_detection": 1,
      "readability": 1,
      "mrr_score": 0.75,
      "notes": "Good content but some hallucinations in funding details"
    }
  }
}
```

## Preparing Ground Truth Data

### Step 1: Collect Reference Material
Gather authoritative sources for each company:
- LinkedIn company page
- Official website
- Crunchbase profile
- Press releases
- SEC filings (if applicable)

### Step 2: Extract Key Facts
Document critical claims with sources:
- Founding year and location
- Total funding and rounds
- Key products and features
- Leadership and headcount
- Recent announcements

### Step 3: Manual Evaluation
For each pipeline output (Structured & RAG):
1. Compare claims against reference material
2. Score each metric (0-2 or 0-3)
3. Document hallucinations
4. Calculate MRR based on fact ordering

### Step 4: Store Results
Save evaluation in `data/eval/ground_truth.json` for reproducibility.

## Running Evaluations

### Single Company Evaluation
```bash
python src/evals/eval_runner.py --company world-labs --pipeline structured
python src/evals/eval_runner.py --company world-labs --pipeline rag
```

### Batch Evaluation (All Companies)
```bash
python src/evals/eval_runner.py --batch
```

### Generate Comparison Report
```bash
python src/evals/eval_runner.py --batch --report
```

## Evaluation Results Storage

**Location**: `data/eval/results.json`

Results are cached to avoid re-evaluation. Structure:
```json
{
  "world-labs": {
    "timestamp": "2025-11-06T10:30:00Z",
    "structured": { /* metrics */ },
    "rag": { /* metrics */ }
  }
}
```

## API Integration

### Fetch Evaluation Results
```bash
curl http://localhost:8000/evals/world-labs
```

Response:
```json
{
  "company_slug": "world-labs",
  "structured": { /* metrics */ },
  "rag": { /* metrics */ }
}
```

## Streamlit Dashboard

Access evaluation metrics at: `http://localhost:8501`

Features:
- Comparison table: Structured vs RAG across all metrics
- Individual company metrics view
- MRR scoring and analysis
- Trend analysis over time (if multiple evaluations)
- Export evaluation reports

## Best Practices

1. **Use authoritative sources** for ground truth
2. **Be consistent** in scoring across companies
3. **Document hallucinations** with specific examples
4. **Update regularly** as new dashboards are generated
5. **Cache results** to avoid re-evaluation costs
6. **Review periodically** to catch evaluation drift

## Example Evaluation Workflow

1. Generate dashboard: `POST /dashboard/structured?company_name=World%20Labs`
2. Generate dashboard: `POST /dashboard/rag?company_name=World%20Labs`
3. Review outputs against ground truth
4. Score metrics (1-5 minutes per company)
5. Save in `data/eval/ground_truth.json`
6. Run evaluator: `python src/evals/eval_runner.py --company world-labs`
7. View results in Streamlit or via API

## Troubleshooting

**Q: MRR score is very low (< 0.5)**
- Check if relevant facts are appearing late in output
- Review fact ordering logic in pipeline
- Consider adjusting retrieval ranking

**Q: Hallucination scores vary widely**
- Ensure consistent reference material
- Double-check against multiple sources
- Document controversial claims

**Q: Schema compliance is low**
- Verify dashboard template includes all sections
- Check LLM prompt for schema requirements
- Review output for missing fields

## References

- Mean Reciprocal Ranking: https://en.wikipedia.org/wiki/Mean_reciprocal_rank
- Evaluation Metrics for LLM: https://openreview.net/pdf/2024
- RAG Evaluation: https://arxiv.org/abs/2310.01852
