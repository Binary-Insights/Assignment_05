# Evaluation Metrics Implementation Guide

## Overview

The evaluation system now supports **two scoring modes**:
1. **PROGRAMMATIC** - Automatically calculates metrics from content
2. **MANUAL** - Uses hardcoded/predefined scores

## Scoring Modes

### PROGRAMMATIC Mode (Auto-Calculate)
Each metric is calculated based on the generated dashboard content and ground truth data.

**How to use:**
```bash
# Evaluate single company with programmatic scoring
python src/evals/eval_runner.py --company world-labs --mode programmatic

# Batch evaluate all companies
python src/evals/eval_runner.py --batch --mode programmatic

# Generate report with programmatic scores
python src/evals/eval_runner.py --batch --report --mode programmatic
```

### MANUAL Mode (Hardcoded)
Uses predefined scores (placeholders). Useful for testing UI/workflows before implementing scoring logic.

**How to use:**
```bash
# Evaluate with manual scoring
python src/evals/eval_runner.py --company world-labs --mode manual

# Batch evaluate with manual mode
python src/evals/eval_runner.py --batch --mode manual
```

### Default Mode
Set the default mode by modifying `SCORING_MODE` variable in `eval_runner.py`:

```python
# In src/evals/eval_runner.py, line ~38
SCORING_MODE = "programmatic"  # Change to "manual" for hardcoded scores
```

---

## Metric Scoring Details

### 1. Factual Accuracy (0-3)

**Logic:**
- Compares generated text against key facts from ground truth
- Counts how many key facts are mentioned in the output
- Calculates coverage percentage

**Scoring:**
| Score | Coverage | Condition |
|-------|----------|-----------|
| 3 | ≥ 90% | All key facts accurately represented |
| 2 | 70-89% | Most key facts present with minor gaps |
| 1 | 40-69% | Only basic facts present |
| 0 | < 40% | No relevant facts or severe inaccuracies |

**Implementation:**
```python
from eval_metrics import calculate_factual_accuracy

score = calculate_factual_accuracy(generated_text, ground_truth_data)
```

**Ground Truth Requirements:**
```json
{
  "key_facts": [
    {"text": "Founded in 2020"},
    {"text": "Headquarters in San Francisco"},
    "Series B funding raised"
  ]
}
```

---

### 2. Schema Compliance (0-2)

**Logic:**
- Checks for required sections and proper structure
- Looks for markdown headers and list formatting
- Verifies section coverage

**Scoring:**
| Score | Condition |
|-------|-----------|
| 2 | All required sections present + consistent structure (headers + lists) |
| 1 | Most sections present (≥50%) OR has structure |
| 0 | Missing required sections or no structure |

**Implementation:**
```python
from eval_metrics import calculate_schema_compliance

score = calculate_schema_compliance(generated_text, ground_truth_data)
```

**Ground Truth Requirements:**
```json
{
  "required_fields": ["overview", "mission", "products", "team", "funding"],
  "expected_sections": ["overview", "mission", "products", "team", "funding"]
}
```

---

### 3. Provenance Quality (0-2)

**Logic:**
- Detects citations, links, and source attribution
- Looks for citation patterns: `[link]()`, URLs, "Source:", etc.
- Counts unique sources

**Scoring:**
| Score | Condition |
|-------|-----------|
| 2 | ≥ 5 citations AND ≥ 2 unique sources |
| 1 | ≥ 2 citations OR ≥ 1 unique source |
| 0 | No citations or source references |

**Implementation:**
```python
from eval_metrics import calculate_provenance_quality

score = calculate_provenance_quality(generated_text, ground_truth_data)
```

**Citation Patterns Detected:**
- Markdown links: `[text](url)`
- URLs: `http://...`, `https://...`
- Source labels: `Source: ...`, `Reference: ...`
- Parenthetical sources: `(Source: ...)`
- Phrases: `According to ...`

---

### 4. Hallucination Detection (0-2)

**Logic:**
- Detects hallucination indicators and contradictions
- Checks for vague or unverifiable claims
- Compares against ground truth facts

**Scoring:**
| Score | Hallucinations | Condition |
|-------|---|-----------|
| 2 | 0 | No detectable hallucinations |
| 1 | 1-2 | Minor inconsistencies |
| 0 | ≥ 3 | Multiple errors or contradictions |

**Hallucination Indicators Checked:**
- "I don't have access to..."
- "I cannot provide..."
- "Unknown/not specified"
- "Approximately infinite"
- Vague intensifiers: "very large", "extremely small"

**Implementation:**
```python
from eval_metrics import calculate_hallucination_detection

score = calculate_hallucination_detection(generated_text, ground_truth_data)
```

**Ground Truth Requirements:**
```json
{
  "key_facts": [
    {
      "text": "Founded in 2020",
      "contradictory_phrases": ["Founded in 2019", "Started in 2021"]
    }
  ]
}
```

---

### 5. Readability (0-1)

**Logic:**
- Evaluates formatting quality and structure
- Counts formatting elements (headers, bold, lists, code blocks)
- Checks for reasonable line length

**Scoring:**
| Score | Condition |
|-------|-----------|
| 1 | Good structure (headers + lists) AND reasonable line length (30-120 chars) |
| 0 | Poor formatting or no structure |

**Formatting Elements Analyzed:**
- Markdown headers: `# Title`
- Bold text: `**bold**`
- Italic text: `*italic*`
- Lists: `- item`
- Code blocks: `` ` `` or `` ``` ``

**Implementation:**
```python
from eval_metrics import calculate_readability

score = calculate_readability(generated_text, ground_truth_data)
```

---

### 6. Mean Reciprocal Ranking (MRR) - Already Implemented

**Logic:**
- Measures how well important facts are ranked
- Finds first relevant fact (relevance ≥ 0.7)
- Returns 1/rank

**Scoring:**
- Rank 1 (first): MRR = 1.0 (perfect)
- Rank 2 (second): MRR = 0.5
- No relevant facts: MRR = 0.0

**Implementation:**
```python
from eval_metrics import calculate_mrr

mrr = calculate_mrr(facts, relevant_threshold=0.7)
```

---

## Total Score Calculation

```
Total = Factual (0-3) 
      + Schema (0-2) 
      + Provenance (0-2) 
      + Hallucination (0-2) 
      + Readability (0-1) 
      + MRR*2 (0-2, scaled from 0-1)
      = Maximum 14 points
```

---

## Ground Truth Data Format

Create a `data/eval/ground_truth.json` file:

```json
{
  "world-labs": {
    "company_name": "World Labs",
    "key_facts": [
      "Founded in 2020",
      "Series B funding",
      "Computer vision AI"
    ],
    "required_fields": [
      "overview",
      "mission",
      "products",
      "team",
      "funding"
    ],
    "expected_sections": [
      "overview",
      "mission",
      "products",
      "team",
      "funding"
    ]
  },
  "another-company": {
    "company_name": "Another Company",
    "key_facts": [...],
    "required_fields": [...]
  }
}
```

---

## Usage Examples

### Example 1: Single Company Evaluation (Programmatic)
```bash
python src/evals/eval_runner.py --company world-labs --pipeline structured --mode programmatic
```

Output:
```
Evaluating world-labs/structured (mode: programmatic)
Using PROGRAMMATIC scoring for world-labs/structured
✓ Evaluated world-labs/structured: total=11.2/14

✓ Evaluation successful
  Company: World Labs
  Pipeline: structured
  Scoring Mode: programmatic
  Factual Accuracy: 3/3
  Schema Compliance: 2/2
  Provenance Quality: 1/2
  Hallucination Detection: 2/2
  Readability: 1/1
  MRR: 0.850
  Total Score: 11.2/14
```

### Example 2: Batch Evaluation (Both Modes)
```bash
# Programmatic
python src/evals/eval_runner.py --batch --mode programmatic --report

# Manual
python src/evals/eval_runner.py --batch --mode manual --report
```

### Example 3: Force Re-evaluation
```bash
# Ignore cache and recalculate
python src/evals/eval_runner.py --batch --force --mode programmatic
```

### Example 4: View Cached Results
```bash
python src/evals/eval_runner.py --view world-labs
```

---

## Customizing Scoring Logic

### Modify Thresholds

Edit `eval_metrics.py` to change scoring thresholds:

```python
def calculate_factual_accuracy(generated_text, ground_truth_data):
    # Change these thresholds
    if coverage >= 0.9:  # ← Modify these
        return 3
    elif coverage >= 0.7:  # ← Modify these
        return 2
    # ...
```

### Add Custom Metrics

Extend the scoring functions:

```python
# In eval_metrics.py
def calculate_custom_metric(generated_text, ground_truth_data):
    """Your custom scoring logic."""
    # Calculate score 0-X
    return score

# In eval_runner.py
custom_score = calculate_custom_metric(dashboard_markdown, gt)

# Add to EvaluationMetrics
metrics = EvaluationMetrics(
    # ... existing metrics
    custom_metric=custom_score
)
```

### Switch Between Modes Dynamically

```python
from eval_runner import EvaluationRunner

runner = EvaluationRunner()

# Programmatic mode
metrics_prog = runner.evaluate_company_pipeline(
    "world-labs",
    "structured",
    scoring_mode="programmatic"
)

# Manual mode
metrics_manual = runner.evaluate_company_pipeline(
    "world-labs",
    "structured",
    scoring_mode="manual"
)
```

---

## Results Caching

Results are automatically cached in:
```
data/eval/results.json
```

To clear cache and force re-evaluation:
```bash
python src/evals/eval_runner.py --batch --force --mode programmatic
```

---

## Testing the Implementation

Run the example in `eval_metrics.py`:
```bash
python src/evals/eval_metrics.py
```

This demonstrates:
- MRR calculation
- Metrics comparison
- Winner determination

---

## Troubleshooting

### No results found
- Ensure `data/eval/ground_truth.json` exists
- Check company slug format

### Low scores for programmatic mode
- Ground truth data may be incomplete
- Adjust scoring thresholds
- Check regex patterns for detection

### Switching between modes
- Delete `data/eval/results.json` to force recalculation
- Use `--force` flag
- Change `SCORING_MODE` in `eval_runner.py`
