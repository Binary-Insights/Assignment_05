# LLM Result Evaluator

This module provides LLM-based evaluation of RAG and Structured pipeline responses against ground truth data using Claude and Instructor with Pydantic models.

## Overview

The evaluator compares LLM-generated company information extractions against verified ground truth facts and scores them across multiple dimensions:

- **Factual Accuracy** (0-3): How accurate the extracted information is
- **Schema Compliance** (0-2): Following required data structure
- **Provenance Quality** (0-2): Quality of citations and source attribution
- **Hallucination Detection** (0-2): Freedom from false/unverifiable claims
- **Readability** (0-1): Clarity and formatting of output
- **Mean Reciprocal Ranking** (0-1): How well important facts are prioritized
- **Total Score**: Sum of all metrics (0-11)

## Installation

```bash
# Install required packages
pip install anthropic instructor pydantic fastapi
```

## Configuration

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Data Structure

### Ground Truth (`data/eval/ground_truth.json`)

```json
{
  "company-slug": {
    "company_name": "Company Name",
    "company_slug": "company-slug",
    "reference_material": {
      "official_sources": ["https://..."],
      "key_facts": [
        {
          "id": "fact_001",
          "claim": "Fact claim",
          "source_urls": ["https://..."],
          "confidence": "high",
          "date": "2024-01-01",
          "category": "funding"
        }
      ],
      "hallucination_examples": ["False claim 1", "False claim 2"]
    },
    "evaluation_notes": {
      "structured_pipeline_notes": "...",
      "rag_pipeline_notes": "...",
      "common_issues": ["..."]
    }
  }
}
```

### LLM Responses (`data/llm_response/structured_responses.json` and `rag_responses.json`)

```json
{
  "company-slug": {
    "structured": {...},
    "rag": {...}
  }
}
```

### Evaluation Results (`data/eval/results.json`)

```json
{
  "company-slug": {
    "structured": {
      "company_name": "...",
      "company_slug": "...",
      "pipeline_type": "structured",
      "timestamp": "2025-11-09T...",
      "factual_accuracy": 2,
      "schema_compliance": 1,
      "provenance_quality": 2,
      "hallucination_detection": 1,
      "readability": 0,
      "mrr_score": 1.0,
      "notes": "...",
      "total_score": 8.0
    },
    "rag": {...}
  }
}
```

## Usage

### Python API

#### Evaluate a Single Company

```python
from result_evaluator import evaluate_company

evaluation = evaluate_company(
    company_slug="anthropic",
    company_name="Anthropic",
    ground_truth_path="data/eval/ground_truth.json",
    structured_response_path="data/llm_response/structured_responses.json",
    rag_response_path="data/llm_response/rag_responses.json"
)

print(f"Structured Score: {evaluation.structured.total_score}")
print(f"RAG Score: {evaluation.rag.total_score}")
```

#### Batch Evaluate All Companies

```python
from result_evaluator import evaluate_batch, get_evaluation_summary

results = evaluate_batch(
    ground_truth_path="data/eval/ground_truth.json",
    structured_response_path="data/llm_response/structured_responses.json",
    rag_response_path="data/llm_response/rag_responses.json",
    output_path="data/eval/results.json"
)

summary = get_evaluation_summary(results)
print(f"Structured Avg Score: {summary['structured_avg_score']:.2f}")
print(f"RAG Avg Score: {summary['rag_avg_score']:.2f}")
```

### Command Line

#### Evaluate Specific Company

```bash
python src/evals/result_evaluator.py \
  --company anthropic \
  --ground-truth data/eval/ground_truth.json \
  --structured-responses data/llm_response/structured_responses.json \
  --rag-responses data/llm_response/rag_responses.json
```

#### Batch Evaluate All Companies

```bash
python src/evals/result_evaluator.py \
  --batch \
  --ground-truth data/eval/ground_truth.json \
  --structured-responses data/llm_response/structured_responses.json \
  --rag-responses data/llm_response/rag_responses.json \
  --output data/eval/results.json
```

### FastAPI Endpoints

#### Evaluate Single Company

```bash
curl -X POST http://localhost:8000/api/evals/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "company_slug": "anthropic",
    "company_name": "Anthropic"
  }'
```

Response:
```json
{
  "status": "success",
  "message": "Successfully evaluated Anthropic",
  "company_slug": "anthropic",
  "company_name": "Anthropic",
  "structured": {...},
  "rag": {...},
  "winners": {
    "factual_accuracy": "structured",
    "schema_compliance": "rag",
    ...
  },
  "timestamp": "2025-11-09T..."
}
```

#### Get Evaluation (On-Demand)

```bash
curl http://localhost:8000/api/evals/evaluate/anthropic
```

#### Batch Evaluate

```bash
curl -X POST http://localhost:8000/api/evals/evaluate/batch \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Streamlit Dashboard Integration

The evaluation dashboard includes:

1. **Run LLM Evaluation Button** - Run evaluation for the selected company
2. **Batch Evaluate Button** - Run evaluation for all companies
3. **Evaluation Results Display** - Shows scores and comparisons
4. **Winners Badge** - Indicates which pipeline performed better

#### Dashboard Features

- Compare structured vs RAG pipelines
- View detailed score breakdowns
- Radar chart visualization
- Bar chart for total score comparison
- MRR analysis
- Batch comparison across all companies

## Scoring Logic

The LLM evaluator uses Claude with detailed prompts to score each metric:

### Factual Accuracy (0-3)
- **3**: All verifiable facts are accurate and match ground truth
- **2**: Most facts are accurate with minor discrepancies
- **1**: Some facts are accurate but notable errors exist
- **0**: Multiple factual errors or hallucinations detected

### Schema Compliance (0-2)
- **2**: Response perfectly follows expected structure/format
- **1**: Response mostly follows structure with minor deviations
- **0**: Response poorly structured or non-compliant

### Provenance Quality (0-2)
- **2**: All claims have proper citations/sources
- **1**: Most claims have sources but some missing
- **0**: Few or no proper source citations

### Hallucination Detection (0-2)
- **2**: No hallucinations; all claims are verifiable
- **1**: Minor unverifiable claims but no major hallucinations
- **0**: Contains known false claims or significant hallucinations

### Readability (0-1)
- **1**: Clear, well-organized, and easy to understand
- **0**: Confusing, poorly formatted, or hard to parse

### Mean Reciprocal Ranking (0-1)
- **1.0**: Most important facts appear first
- **0.5**: Most important facts appear second position
- **0.0**: Important facts missing or ranked poorly

## Architecture

```
src/evals/
├── eval_results_models.py    # Pydantic models for evaluation results
├── ground_truth_models.py    # Pydantic models for ground truth
└── result_evaluator.py       # LLM evaluation logic

src/backend/routes/
└── eval_routes.py            # FastAPI endpoints

src/frontend/pages/
└── 01_evaluation_dashboard.py # Streamlit dashboard with evaluation UI
```

## Error Handling

The evaluator handles various error scenarios:

- Missing ground truth files
- Missing LLM responses
- API failures
- Invalid JSON
- Timeout errors

All errors are logged and reported to the user interface.

## Performance

- Single company evaluation: ~30-60 seconds (depends on Claude response time)
- Batch evaluation: ~1-2 minutes per company
- Caching: Results are cached for 5 minutes in Streamlit

## Future Enhancements

- [ ] Support for additional LLM models
- [ ] Custom scoring templates
- [ ] Result export to CSV/Excel
- [ ] Evaluation history tracking
- [ ] Partial evaluation (skip specific metrics)
- [ ] Custom evaluation criteria per company
- [ ] A/B testing framework

## Troubleshooting

### API Key Error
```
ValueError: ANTHROPIC_API_KEY not found in environment variables
```
**Solution**: Set the API key in your environment:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### File Not Found
```
Ground truth file not found: data/eval/ground_truth.json
```
**Solution**: Ensure the file exists at the specified path.

### Timeout Error
```
Evaluation timed out. The LLM evaluation is taking longer than expected.
```
**Solution**: Increase the timeout in the dashboard or run via CLI.

### Import Error
```
ModuleNotFoundError: No module named 'instructor'
```
**Solution**: Install required packages:
```bash
pip install anthropic instructor pydantic fastapi
```

## References

- [Instructor Documentation](https://python.useinstructor.com/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
