# Evaluation Framework - Complete Index

## 📋 Overview

Complete evaluation framework for comparing LLM-generated dashboards from Structured vs RAG pipelines, including metrics calculation, caching, API endpoints, Streamlit dashboard, and comprehensive documentation.

**Total Implementation**:
- ✅ 1,378 lines of Python code
- ✅ 2,000+ lines of documentation
- ✅ 6 evaluation metrics + Mean Reciprocal Ranking
- ✅ API endpoints + Streamlit dashboard
- ✅ Ground truth management + caching

---

## 📚 Documentation Index

### Getting Started
1. **START HERE: `EVALUATION_QUICK_REFERENCE.md`**
   - 5-minute quick start
   - Command reference
   - Troubleshooting lookup table
   - Learn-by-example approach

2. **`EVALUATION_SUMMARY.md`**
   - Complete feature overview
   - Success criteria met
   - File structure
   - Next steps

3. **`docs/EVALUATION_GUIDE.md`**
   - Basic framework introduction
   - Metric definitions
   - Ground truth structure
   - Step-by-step workflow

### Comprehensive Guides
4. **`docs/EVALUATION_FRAMEWORK_README.md`** (700+ lines)
   - Complete implementation guide
   - Detailed metric explanations
   - Quick start instructions
   - Understanding results
   - MRR calculation details
   - Troubleshooting guide
   - Example evaluations

5. **`docs/MRR_EXPLANATION.md`** (500+ lines)
   - Why MRR is perfect for this evaluation
   - Mathematical definition
   - Real-world examples
   - Comparison with alternatives
   - Implementation details
   - Advanced usage patterns

### Implementation Details
6. **`EVALUATION_IMPLEMENTATION.md`**
   - Component overview
   - API endpoints documentation
   - CLI commands
   - File structure
   - Customization guide
   - Troubleshooting

---

## 🔧 Code Components

### Core Modules
```
src/evals/
├── __init__.py (12 lines)
│   └─ Module exports and imports
│
├── eval_metrics.py (389 lines)
│   ├─ EvaluationMetrics dataclass
│   ├─ ComparisonResult dataclass
│   ├─ calculate_mrr() function
│   ├─ calculate_aggregate_mrr() function
│   └─ Example usage & tests
│
└── eval_runner.py (487 lines)
    ├─ EvaluationRunner class
    ├─ evaluate_company_pipeline()
    ├─ batch_evaluate()
    ├─ generate_report()
    ├─ CLI argument parsing
    └─ Cache management
```

### API Integration
```
src/backend/rag_search_api.py
├─ EvaluationMetricsResponse (model)
├─ ComparisonResponse (model)
├─ MetricScore (model)
├─ GET /evals/{company_slug} (endpoint)
└─ GET /evals (endpoint)
```

### Frontend
```
src/frontend/eval_dashboard.py (434 lines)
├─ Company selector
├─ Comparison table
├─ Radar chart (normalized metrics)
├─ Bar chart (total scores)
├─ MRR analysis panel
├─ Detailed score breakdown
├─ Batch comparison
└─ 5-minute caching
```

### Data
```
data/eval/
├─ ground_truth.json (272 lines)
│  └─ 3 sample companies with reference materials
├─ results.json (auto-generated)
│  └─ Cached evaluation results
└─ report.md (auto-generated)
   └─ Comparison report
```

---

## 🚀 Quick Start

### Option 1: Command Line (Fastest)
```bash
# Single evaluation
python src/evals/eval_runner.py --company world-labs

# View result
python src/evals/eval_runner.py --view world-labs
```

### Option 2: API (For Integration)
```bash
curl http://localhost:8000/evals/world-labs
```

### Option 3: Streamlit Dashboard (Visual)
```bash
streamlit run src/frontend/eval_dashboard.py
```

---

## 📊 Metrics Explained

| Metric | Range | Purpose | What It Measures |
|--------|-------|---------|-----------------|
| Factual Accuracy | 0-3 | Correctness | Are facts accurate? |
| Schema Compliance | 0-2 | Structure | Does it follow schema? |
| Provenance Quality | 0-2 | Citations | Are sources cited? |
| Hallucination Detection | 0-2 | False Info | Any false claims? |
| Readability | 0-1 | Clarity | Is it well-formatted? |
| **Mean Reciprocal Ranking** | 0-1 | **Ordering** | **How well ranked?** |
| **Total Score** | **0-14** | **Overall** | **Combined quality** |

### Why Mean Reciprocal Ranking (MRR)?
✅ Measures information **organization** quality  
✅ Shows if important facts **appear first**  
✅ Captures **user experience**  
✅ Differentiates **subtle quality differences**  
✅ Standard in **information retrieval**  
✅ **Already implemented** and ready to use  

**Example**: Structured (MRR: 0.95) vs RAG (MRR: 0.75) = Structured ranks information better

---

## 📖 Reading Guide by Need

### "I want to get started ASAP"
→ Read: `EVALUATION_QUICK_REFERENCE.md` (5 min)  
→ Run: `python src/evals/eval_runner.py --company world-labs`  
→ Done!

### "I need to understand the framework"
→ Read: `docs/EVALUATION_GUIDE.md` (15 min)  
→ Read: `EVALUATION_IMPLEMENTATION.md` (15 min)  
→ Review: Code in `src/evals/eval_metrics.py` (10 min)

### "I need comprehensive documentation"
→ Read: `docs/EVALUATION_FRAMEWORK_README.md` (30 min)  
→ Read: `docs/MRR_EXPLANATION.md` (20 min)  
→ Review: All code modules (30 min)

### "I'm curious about MRR specifically"
→ Read: `docs/MRR_EXPLANATION.md` (20 min)  
→ Try: Examples in `src/evals/eval_metrics.py` (10 min)  
→ Experiment: Run evaluations with different rankings (15 min)

### "I need to integrate this into my system"
→ Read: `EVALUATION_IMPLEMENTATION.md` (API section)  
→ Review: `src/backend/rag_search_api.py` (endpoints)  
→ Implement: Custom scoring logic if needed

### "I need to extend or customize"
→ Read: `EVALUATION_IMPLEMENTATION.md` (Customization section)  
→ Review: `src/evals/eval_runner.py` (customize scoring)  
→ Add: New companies to `data/eval/ground_truth.json`

---

## 🎯 Command Reference

### Evaluation Commands
```bash
# Evaluate single company (structured)
python src/evals/eval_runner.py --company world-labs --pipeline structured

# Evaluate both pipelines
python src/evals/eval_runner.py --company world-labs --pipeline structured
python src/evals/eval_runner.py --company world-labs --pipeline rag

# Batch evaluate all companies
python src/evals/eval_runner.py --batch

# Generate comparison report
python src/evals/eval_runner.py --batch --report

# View cached results
python src/evals/eval_runner.py --view world-labs

# Force re-evaluation (skip cache)
python src/evals/eval_runner.py --company world-labs --force

# Show help
python src/evals/eval_runner.py --help
```

### API Endpoints
```bash
# Get evaluation for specific company
curl http://localhost:8000/evals/world-labs

# Get evaluation as JSON
curl http://localhost:8000/evals/world-labs | jq .

# List all evaluated companies
curl http://localhost:8000/evals

# With pretty printing
curl http://localhost:8000/evals | jq .companies
```

### Streamlit Dashboard
```bash
# Launch dashboard
streamlit run src/frontend/eval_dashboard.py

# Custom port (if 8501 is in use)
streamlit run src/frontend/eval_dashboard.py --server.port 8502

# Headless mode
streamlit run src/frontend/eval_dashboard.py --headless
```

---

## 📁 File Tree

```
.
├── EVALUATION_QUICK_REFERENCE.md          ← START HERE!
├── EVALUATION_SUMMARY.md                  ← Overview
├── EVALUATION_IMPLEMENTATION.md           ← Details
│
├── docs/
│   ├── EVALUATION_GUIDE.md                ← Basic guide
│   ├── EVALUATION_FRAMEWORK_README.md     ← Comprehensive
│   └── MRR_EXPLANATION.md                 ← MRR deep dive
│
├── src/
│   ├── evals/
│   │   ├── __init__.py
│   │   ├── eval_metrics.py                ← Metrics calculation
│   │   └── eval_runner.py                 ← Evaluation execution
│   │
│   ├── backend/
│   │   └── rag_search_api.py              ← API endpoints (added)
│   │
│   └── frontend/
│       └── eval_dashboard.py              ← Streamlit dashboard
│
└── data/
    └── eval/
        ├── ground_truth.json              ← Reference data
        ├── results.json                   ← Cached results
        └── report.md                      ← Generated reports
```

---

## 🎓 Learning Objectives

After reading this documentation, you will understand:

1. ✅ **Why MRR is perfect for evaluation**
   - How it measures information ranking quality
   - How it differs from accuracy metrics
   - Why it matters for user experience

2. ✅ **How to use the framework**
   - Prepare ground truth data
   - Run evaluations
   - Interpret results
   - View via CLI, API, or Streamlit

3. ✅ **How it works internally**
   - Metrics calculation logic
   - MRR computation
   - Caching strategy
   - API responses

4. ✅ **How to extend it**
   - Add new companies
   - Customize scoring logic
   - Add new metrics
   - Integrate with your system

---

## 💡 Key Concepts

### Ground Truth
Reference data for each company including:
- Official sources and URLs
- Key facts with confidence levels
- Known hallucination examples
- Evaluation notes

### Metrics
Six evaluation metrics plus MRR:
- Factual accuracy (correctness)
- Schema compliance (structure)
- Provenance quality (citations)
- Hallucination detection (false claims)
- Readability (clarity)
- MRR (information ranking)

### Total Score
Combined score out of 14:
- 13-14: Excellent
- 11-13: Very Good
- 9-11: Good
- 7-9: Fair
- < 7: Poor

### MRR (Mean Reciprocal Ranking)
1/rank_of_first_relevant_fact:
- 1.0: Perfect ranking (important info first)
- 0.5: Good ranking (second position)
- 0.0: Poor ranking (no relevant info)

### Caching
Results stored in `data/eval/results.json`:
- Prevents re-evaluation
- Fast API responses
- `--force` flag bypasses cache

---

## 🔗 Cross-References

### By Topic

**Understanding Metrics**:
- Definitions: `docs/EVALUATION_GUIDE.md`
- Detailed guide: `docs/EVALUATION_FRAMEWORK_README.md`
- Examples: `EVALUATION_IMPLEMENTATION.md`

**MRR Specifically**:
- Why use it: `docs/MRR_EXPLANATION.md`
- Implementation: `src/evals/eval_metrics.py` (calculate_mrr function)
- Examples: `docs/MRR_EXPLANATION.md` (Real Scenario section)

**Running Evaluations**:
- Quick: `EVALUATION_QUICK_REFERENCE.md`
- Detailed: `docs/EVALUATION_GUIDE.md`
- CLI: `src/evals/eval_runner.py` (--help)

**API Integration**:
- Endpoints: `EVALUATION_IMPLEMENTATION.md`
- Models: `src/backend/rag_search_api.py`
- Examples: `docs/EVALUATION_GUIDE.md` (API section)

**Streamlit Dashboard**:
- Features: `EVALUATION_SUMMARY.md`
- Code: `src/frontend/eval_dashboard.py`
- Usage: `EVALUATION_QUICK_REFERENCE.md`

**Troubleshooting**:
- Lookup table: `EVALUATION_QUICK_REFERENCE.md`
- Full guide: `docs/EVALUATION_FRAMEWORK_README.md`
- Examples: Each component documentation

---

## ✨ Features at a Glance

| Feature | Where | How to Use |
|---------|-------|-----------|
| Calculate metrics | `src/evals/eval_metrics.py` | `python -c "from eval_metrics import..."` |
| Run evaluations | `src/evals/eval_runner.py` | `python src/evals/eval_runner.py --batch` |
| API endpoints | `src/backend/rag_search_api.py` | `curl http://localhost:8000/evals/...` |
| Streamlit dashboard | `src/frontend/eval_dashboard.py` | `streamlit run src/frontend/eval_dashboard.py` |
| Ground truth mgmt | `data/eval/ground_truth.json` | Edit JSON file |
| Result caching | `data/eval/results.json` | Auto-managed by runner |
| Report generation | `data/eval/report.md` | `python src/evals/eval_runner.py --batch --report` |
| MRR calculation | `src/evals/eval_metrics.py` | `calculate_mrr(facts, threshold=0.7)` |

---

## 🎯 Success Criteria

All requirements met and implemented:

✅ **Ground Truth Dataset**
- Structured JSON format in `data/eval/ground_truth.json`
- 3 sample companies with reference materials
- Official sources and key facts

✅ **Evaluation Metrics**
- Factual accuracy (0-3)
- Schema compliance (0-2)
- Provenance quality (0-2)
- Hallucination detection (0-2)
- Readability (0-1)
- Mean Reciprocal Ranking (0-1)

✅ **Python Scripts in `src/evals/`**
- `eval_metrics.py` - Metrics calculation
- `eval_runner.py` - Evaluation execution
- CLI interface with batch support

✅ **API Endpoints**
- `/evals/{company_slug}` - Get metrics
- `/evals` - List companies
- Results cached in `data/eval/`

✅ **Streamlit Evaluation Dashboard**
- Comparison tables and charts
- MRR analysis
- Batch summary

✅ **MRR Implementation**
- Why it's good (comprehensive explanation)
- How it works (mathematical and practical)
- Already integrated and ready to use

---

## 🚀 Next Steps

1. **Read**: Start with `EVALUATION_QUICK_REFERENCE.md` (5 min)
2. **Try**: Run `python src/evals/eval_runner.py --company world-labs` (2 min)
3. **View**: Check results via API or Streamlit (5 min)
4. **Expand**: Add more companies to `data/eval/ground_truth.json`
5. **Customize**: Implement your own scoring logic in `eval_runner.py`

---

## 📞 Support

- **Quick Start**: `EVALUATION_QUICK_REFERENCE.md`
- **How-To Guide**: `docs/EVALUATION_GUIDE.md`
- **Complete Guide**: `docs/EVALUATION_FRAMEWORK_README.md`
- **MRR Details**: `docs/MRR_EXPLANATION.md`
- **Code Examples**: `src/evals/eval_metrics.py` (__main__ section)
- **Troubleshooting**: `docs/EVALUATION_FRAMEWORK_README.md` (Troubleshooting section)

---

**Framework Complete and Ready to Use! 🎉**

Total Lines of Code: **1,378**  
Total Lines of Documentation: **2,000+**  
Time to Get Started: **5 minutes**  
