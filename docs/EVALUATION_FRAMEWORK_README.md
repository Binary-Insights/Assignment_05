# Evaluation Framework - Complete Guide

## Overview

This evaluation framework provides a comprehensive system for comparing LLM-generated outputs from two pipelines:

1. **Structured Pipeline**: Uses structured JSON payload data with LLM for dashboard generation
2. **RAG Pipeline**: Uses Pinecone vector retrieval + LLM for dashboard generation

The framework includes:
- ✅ Evaluation metrics calculation (`src/evals/eval_metrics.py`)
- ✅ Evaluation runner with caching (`src/evals/eval_runner.py`)
- ✅ FastAPI endpoints for retrieving metrics (`/evals/{company_slug}`)
- ✅ Streamlit dashboard for visualization (`src/frontend/eval_dashboard.py`)
- ✅ Ground truth data management (`data/eval/ground_truth.json`)

## Directory Structure

```
src/evals/
├── __init__.py                 # Module initialization
├── eval_metrics.py             # Metrics calculation logic
└── eval_runner.py              # Evaluation execution and caching

data/eval/
├── ground_truth.json           # Reference data for evaluation
├── results.json                # Cached evaluation results
└── report.md                   # Generated comparison reports

src/frontend/
└── eval_dashboard.py           # Streamlit visualization page
```

## Evaluation Metrics

### 1. Factual Accuracy (0–3)
Measures correctness of information compared to ground truth.

| Score | Meaning |
|-------|---------|
| 3 | All critical facts accurate and verifiable |
| 2 | Facts mostly accurate with minor inconsistencies |
| 1 | Facts partially accurate with significant errors |
| 0 | Most facts incorrect or hallucinated |

**Evaluation Checklist:**
- [ ] Funding amounts match ground truth
- [ ] Investor names are correct
- [ ] Founding year is accurate
- [ ] Company location is correct
- [ ] Product descriptions are accurate

### 2. Schema Compliance (0–2)
Measures adherence to dashboard structure requirements.

| Score | Meaning |
|-------|---------|
| 2 | Complete schema with all sections properly formatted |
| 1 | Covers most sections but some data missing/poorly formatted |
| 0 | Missing multiple required sections |

**Required Sections:**
- Company Overview
- Products & Technology
- Market Position
- Financial Information
- Team & Organization
- Risk Assessment

### 3. Provenance Quality (0–2)
Measures inclusion and accuracy of source citations.

| Score | Meaning |
|-------|---------|
| 2 | Complete and accurate citations for key claims |
| 1 | Some citations provided but incomplete/partially incorrect |
| 0 | No provenance info or all citations incorrect |

**Evaluation Checklist:**
- [ ] Key facts have source citations
- [ ] URLs are valid and accessible
- [ ] Crawl dates are recent
- [ ] Citations support the claims

### 4. Hallucination Detection (0–2)
Measures absence of false information not in source data.

| Score | Meaning |
|-------|---------|
| 2 | No hallucinations detected |
| 1 | Few hallucinations (1-2 false claims) |
| 0 | Multiple hallucinations (3+ false claims) |

**Common Hallucinations to Watch For:**
- False acquisitions or partnerships
- Inflated headcount
- Incorrect funding round names
- Made-up product features
- False regulatory approvals

### 5. Readability (0–1)
Measures clarity and presentation quality.

| Score | Meaning |
|-------|---------|
| 1 | Clear formatting, well-organized, easy to read |
| 0 | Poor formatting, hard to read, confusing structure |

**Evaluation Checklist:**
- [ ] Text flows naturally
- [ ] Headers are descriptive
- [ ] Lists are properly formatted
- [ ] No redundancy
- [ ] Professional tone

### 6. Mean Reciprocal Ranking (MRR)
Measures quality of information ranking (how well important facts appear first).

$$\text{MRR} = \frac{1}{\text{rank of first relevant fact}}$$

| MRR Score | Meaning |
|-----------|---------|
| 1.0 | Most important fact appears first |
| 0.5 | Most important fact appears second |
| 0.33 | Most important fact appears third |
| 0.0 | No relevant facts in top ranked items |

**Why MRR is valuable:**
- Captures information ordering
- Sensitive to top-ranked items
- Standard in information retrieval
- Complements absolute accuracy
- Differentiates subtle quality differences

## Quick Start

### 1. Prepare Ground Truth Data

Edit `data/eval/ground_truth.json` to add companies:

```json
{
  "world-labs": {
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "reference_material": {
      "official_sources": [
        "https://www.linkedin.com/company/world-labs",
        "https://worldlabs.ai"
      ],
      "key_facts": [
        {
          "id": "fact_001",
          "claim": "Founded in 2023",
          "source_urls": ["https://..."],
          "confidence": "high"
        }
      ],
      "hallucination_examples": [
        "False claim 1",
        "False claim 2"
      ]
    }
  }
}
```

### 2. Generate Dashboards

For each company, generate both pipeline outputs:

```bash
# Structured pipeline
curl http://localhost:8000/dashboard/structured?company_name=World%20Labs

# RAG pipeline  
curl http://localhost:8000/dashboard/rag?company_name=World%20Labs
```

Or use the Streamlit app to generate dashboards interactively.

### 3. Run Evaluations

```bash
# Evaluate single company
python src/evals/eval_runner.py --company world-labs --pipeline structured
python src/evals/eval_runner.py --company world-labs --pipeline rag

# Batch evaluate all companies
python src/evals/eval_runner.py --batch

# Generate comparison report
python src/evals/eval_runner.py --batch --report

# View results
python src/evals/eval_runner.py --view world-labs
```

### 4. View Evaluation Results

**Via API:**
```bash
# Get evaluation for specific company
curl http://localhost:8000/evals/world-labs

# List all evaluations
curl http://localhost:8000/evals
```

**Via Streamlit:**
1. Run: `streamlit run src/frontend/eval_dashboard.py`
2. Open browser to `http://localhost:8501`
3. Select company from dropdown
4. View metrics and visualizations

## Understanding the Results

### Comparison Response (API)

```json
{
  "company_name": "World Labs",
  "company_slug": "world-labs",
  "structured": {
    "factual_accuracy": 3,
    "schema_compliance": 2,
    "provenance_quality": 2,
    "hallucination_detection": 2,
    "readability": 1,
    "mrr_score": 0.95,
    "total_score": 13.9
  },
  "rag": {
    "factual_accuracy": 2,
    "schema_compliance": 2,
    "provenance_quality": 1,
    "hallucination_detection": 1,
    "readability": 1,
    "mrr_score": 0.75,
    "total_score": 10.5
  },
  "winners": {
    "factual_accuracy": "structured",
    "schema_compliance": "tie",
    "provenance_quality": "structured",
    "hallucination_detection": "structured",
    "readability": "tie",
    "mrr_score": "structured"
  }
}
```

### Interpretation

**Total Score (out of 14):**
- Structured: 13.9 → 99% (Excellent)
- RAG: 10.5 → 75% (Good)

**Winner by Metric:**
- Structured wins: 4 metrics
- RAG wins: 0 metrics
- Tie: 2 metrics

**MRR Comparison:**
- Structured (0.95): Highly relevant facts ranked near top
- RAG (0.75): Good ranking but some relevant facts appear lower
- Difference: 0.20 (Structured significantly better)

## Evaluation Report

After running `python src/evals/eval_runner.py --batch --report`, review `data/eval/report.md`:

```markdown
# Evaluation Report: Structured vs RAG Pipelines

## Summary Table

| Company | Method | Factual | Schema | Provenance | Hallucination | Readability | MRR | Total |
|---------|--------|---------|--------|------------|---------------|-------------|-----|-------|
| World Labs | Structured | 3 | 2 | 2 | 2 | 1 | 0.95 | 13.9 |
| World Labs | RAG | 2 | 2 | 1 | 1 | 1 | 0.75 | 10.5 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

## Summary Statistics

**Structured Pipeline**: Average Score = 12.5/14
**RAG Pipeline**: Average Score = 9.8/14

## MRR Analysis

**Structured Pipeline** Average MRR: 0.92
**RAG Pipeline** Average MRR: 0.71

> MRR measures how well important facts are ranked (higher is better, 1.0 is perfect)
```

## Implementation Details

### How MRR is Calculated

```python
from src.evals.eval_metrics import calculate_mrr

# Extract key facts with relevance scores
facts = [
    {"relevance_score": 0.95, "text": "Founded in 2023"},
    {"relevance_score": 0.5, "text": "Based in SF"},
    {"relevance_score": 0.85, "text": "Raised $230M"}
]

# Calculate MRR
mrr = calculate_mrr(facts, relevant_threshold=0.7)
# Returns: 1.0 (first fact has highest relevance)
```

**Algorithm:**
1. Sort facts by ranking position (as they appear in output)
2. Find first fact with relevance_score ≥ threshold (0.7)
3. Calculate MRR = 1 / rank
4. Return MRR (higher is better)

### Caching Strategy

Results are cached in `data/eval/results.json` to avoid redundant calculations:

```json
{
  "world-labs": {
    "structured": { /* metrics */ },
    "rag": { /* metrics */ }
  }
}
```

**To force re-evaluation:**
```bash
python src/evals/eval_runner.py --company world-labs --force
```

### Streamlit Caching

The Streamlit dashboard caches API calls for 5 minutes to improve performance:

```python
@st.cache_data(ttl=300)
def fetch_company_evaluation(company_slug):
    # API call cached for 5 minutes
    ...
```

Click "🔄 Refresh" button to clear cache immediately.

## Best Practices

### For Manual Scoring

1. **Use authoritative sources**
   - Official company website
   - LinkedIn company page
   - Crunchbase profile
   - SEC filings (if public)

2. **Be consistent**
   - Same evaluation criteria for all companies
   - Document scoring rationale in `notes`
   - Use examples for disputed scores

3. **Document hallucinations**
   - Include specific false claims
   - Cite correct information
   - Note severity (critical vs minor)

4. **Track evaluation history**
   - Include timestamp
   - Note pipeline/model version
   - Update as new data emerges

### For Batch Evaluation

1. **Check pipeline consistency**
   - Same LLM model used for both pipelines?
   - Same prompts and temperature settings?
   - Same retrieval parameters for RAG?

2. **Review outliers**
   - Unusually low/high scores
   - Verify evaluation accuracy
   - Check for systematic biases

3. **Monitor trends**
   - Track metrics over time
   - Identify improving/degrading areas
   - Correlate with pipeline changes

## Troubleshooting

### No evaluation results found

**Problem:** API returns 404 for `/evals/{company_slug}`

**Solutions:**
1. Check if evaluation has been run:
   ```bash
   python src/evals/eval_runner.py --company world-labs
   ```
2. Verify `data/eval/results.json` exists
3. Check file permissions

### MRR score very low (< 0.3)

**Possible causes:**
- Important facts appear late in output
- Fact extraction not capturing best information
- Retrieval ranking needs tuning

**Debug:**
```python
from src.evals.eval_runner import EvaluationRunner
runner = EvaluationRunner()
facts = runner._extract_facts_from_markdown(dashboard_text)
print(facts)  # Review fact ordering
```

### Inconsistent scores between runs

**Problem:** Same dashboard scores differently on second evaluation

**Causes:**
- Non-deterministic LLM outputs
- Cache not being used
- Different reference data

**Solution:**
```bash
# Use cache
python src/evals/eval_runner.py --company world-labs  # Uses cache

# Force re-evaluation
python src/evals/eval_runner.py --company world-labs --force  # Recalculates
```

### Streamlit dashboard not loading

**Problem:** "Failed to fetch evaluations"

**Debug steps:**
1. Check API is running: `curl http://localhost:8000/health`
2. Check eval file exists: `ls data/eval/results.json`
3. View browser console for errors
4. Check environment variables: `echo $FASTAPI_URL`

## Examples

### Excellent Structured Output (13.9/14)

Typical characteristics:
- All key facts accurate and properly sourced
- Complete dashboard schema
- Detailed provenance with URL citations
- No hallucinations detected
- Well-formatted and readable
- MRR: 0.95+ (important facts appear first)

### Good RAG Output (10.5/14)

Typical characteristics:
- Most facts accurate (minor inconsistencies)
- Complete schema
- Some citations provided
- Few minor hallucinations
- Good readability
- MRR: 0.70-0.85 (some info buried)

### Needs Improvement (< 8/14)

Warning signs:
- Multiple factual errors
- Missing required schema sections
- No citations or invalid sources
- Significant hallucinations
- Poor formatting or confusing structure
- MRR: < 0.5 (relevant info appears late)

## Next Steps

1. **Customize evaluation logic** in `src/evals/eval_runner.py`:
   - Implement auto-scoring instead of templates
   - Add domain-specific metrics
   - Integrate with fact-checking APIs

2. **Expand ground truth** in `data/eval/ground_truth.json`:
   - Add more companies
   - Include more key facts
   - Document edge cases

3. **Advanced MRR analysis**:
   - Analyze fact categories (funding, products, team, etc.)
   - Category-specific MRR scores
   - Identify weak areas by category

4. **Multi-model comparison**:
   - Compare different LLM models
   - Track model improvements over time
   - Cost vs quality analysis

## References

- **RAGAS Framework**: Retrieval-Augmented Generation Automated Evaluation
  - https://github.com/explodinggradients/ragas
  
- **Mean Reciprocal Ranking**: Information Retrieval Metric
  - https://en.wikipedia.org/wiki/Mean_reciprocal_rank
  
- **LLM Evaluation**: Survey of evaluation methods
  - https://arxiv.org/abs/2310.01852
  
- **RAG Evaluation**: Specialized metrics for retrieval-augmented systems
  - https://github.com/run-llama/llama_index/tree/main/llama-index-legacy/llama_index/evaluation

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review examples in `src/evals/eval_metrics.py`
3. Check logs in `data/logs/`
4. Run in verbose mode: `VERBOSE=1 python src/evals/eval_runner.py --company world-labs`
