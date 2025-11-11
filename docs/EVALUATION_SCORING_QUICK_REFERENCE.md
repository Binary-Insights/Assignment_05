# Evaluation Metrics - Quick Reference

## 🚀 Quick Start

### Single Company Evaluation
```bash
# Programmatic mode (auto-calculate)
python src/evals/eval_runner.py --company world-labs --mode programmatic

# Manual mode (hardcoded scores)
python src/evals/eval_runner.py --company world-labs --mode manual
```

### Batch Evaluation
```bash
# Evaluate all companies
python src/evals/eval_runner.py --batch --mode programmatic

# Generate report
python src/evals/eval_runner.py --batch --report --mode programmatic

# Force re-evaluation (ignore cache)
python src/evals/eval_runner.py --batch --force --mode programmatic
```

### View Results
```bash
# View cached results
python src/evals/eval_runner.py --view world-labs

# View all results with report
python src/evals/eval_runner.py --batch --report
```

---

## 📊 Scoring Summary

| Metric | Scale | Logic |
|--------|-------|-------|
| **Factual Accuracy** | 0-3 | Coverage of key_facts |
| **Schema Compliance** | 0-2 | Required sections + structure |
| **Provenance Quality** | 0-2 | Citations and sources |
| **Hallucination Detection** | 0-2 | Contradiction detection |
| **Readability** | 0-1 | Formatting and line length |
| **MRR Score** | 0-1 | Fact ranking (scaled to 0-2) |
| **TOTAL** | **0-14** | Sum of all metrics |

---

## 🔧 Configuration

### Change Default Mode
Edit `src/evals/eval_runner.py` line ~50:
```python
SCORING_MODE = "programmatic"  # Change to "manual"
```

### Add/Modify Thresholds
Edit `src/evals/eval_metrics.py`:
- Factual accuracy thresholds (lines ~90-110)
- Schema compliance thresholds (lines ~150-170)
- Citation count thresholds (lines ~200-215)
- Hallucination indicators (lines ~250-270)

---

## 📁 Data Files

**Ground Truth** (required for programmatic scoring):
```
data/eval/ground_truth.json
```

Example structure:
```json
{
  "world-labs": {
    "company_name": "World Labs",
    "key_facts": ["Founded 2020", "Series B funding", "Computer vision"],
    "required_fields": ["overview", "mission", "products", "team"],
    "expected_sections": ["overview", "mission", "products"]
  }
}
```

**Results Cache** (auto-created):
```
data/eval/results.json
```

---

## 🎯 Metric Details

### Factual Accuracy (0-3)
- **3**: ≥90% facts covered
- **2**: 70-89% facts covered
- **1**: 40-69% facts covered
- **0**: <40% facts covered

### Schema Compliance (0-2)
- **2**: All required sections + good structure
- **1**: Most sections OR has structure
- **0**: Missing sections OR no structure

### Provenance Quality (0-2)
- **2**: ≥5 citations + ≥2 unique sources
- **1**: ≥2 citations OR ≥1 unique source
- **0**: No citations

### Hallucination Detection (0-2)
- **2**: No hallucinations
- **1**: 1-2 minor inconsistencies
- **0**: ≥3 errors/contradictions

### Readability (0-1)
- **1**: Good structure + 30-120 char lines
- **0**: Poor formatting

---

## 📈 Example Output

```
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

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "No ground truth" | Create `data/eval/ground_truth.json` |
| Low scores | Adjust thresholds in `eval_metrics.py` |
| Wrong mode being used | Check `SCORING_MODE` or pass `--mode` |
| Cache issues | Use `--force` flag to re-evaluate |
| Missing results | Ensure ground truth data is complete |

---

## 🔄 Switching Modes

### Programmatic → Manual
```bash
python src/evals/eval_runner.py --batch --mode manual
```

### Manual → Programmatic
```bash
python src/evals/eval_runner.py --batch --force --mode programmatic
```

### Use Default (from settings)
```bash
python src/evals/eval_runner.py --batch
# Uses SCORING_MODE from eval_runner.py
```

---

## 📚 Documentation Files

- `EVALUATION_METRICS_GUIDE.md` - Full implementation guide
- `src/evals/eval_metrics.py` - Metric implementations
- `src/evals/eval_runner.py` - Evaluation runner with CLI

---

## ✅ Validation Checklist

Before using programmatic mode:
- [ ] `data/eval/ground_truth.json` exists
- [ ] Ground truth has `key_facts` array
- [ ] Ground truth has `required_fields` array
- [ ] Ground truth has `expected_sections` array
- [ ] SCORING_MODE set to "programmatic" (or use `--mode programmatic`)
- [ ] All metrics implemented in `eval_metrics.py`

---

## 💡 Tips

1. **Start with Manual**: Test UI/workflow with `--mode manual`
2. **Then Test Programmatic**: Switch to `--mode programmatic`
3. **Adjust Thresholds**: Fine-tune scoring in `eval_metrics.py`
4. **Cache Results**: Results are auto-cached in `data/eval/results.json`
5. **Force Re-run**: Use `--force` to ignore cache
6. **Batch Processing**: Use `--batch` for all companies at once
