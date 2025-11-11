# Evaluation Framework - Architecture & Data Flow

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Evaluation Framework Architecture                │
└──────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │  Ground Truth   │
                         │  Data (JSON)    │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
        ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
        │ Structured      │ │ RAG             │ │ Reference       │
        │ Dashboard       │ │ Dashboard       │ │ Materials       │
        │ Markdown        │ │ Markdown        │ │ (URLs, Facts)   │
        └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                 │                    │                   │
                 │                    │                   │
                 └────────────────────┼───────────────────┘
                                      │
                          ┌───────────▼───────────┐
                          │  Evaluation Runner    │
                          │  (eval_runner.py)     │
                          │  - Extract facts      │
                          │  - Calculate metrics  │
                          │  - Score output       │
                          └───────────┬───────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────┐
                    │   Evaluation Metrics Module      │
                    │   (eval_metrics.py)              │
                    │                                  │
                    │  • EvaluationMetrics class       │
                    │  • calculate_mrr()               │
                    │  • ComparisonResult class        │
                    │  • Total score calculation       │
                    └────────────┬─────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
        ┌───────────────────────┐  ┌───────────────────────┐
        │ Results Cache         │  │ Comparison Report     │
        │ (results.json)        │  │ (report.md)           │
        │ - Structured scores   │  │ - Table comparison    │
        │ - RAG scores          │  │ - Summary statistics  │
        │ - Winners per metric  │  │ - MRR analysis        │
        └────────┬──────────────┘  └──────────────────────┘
                 │
        ┌────────┼────────┐
        │        │        │
        ▼        ▼        ▼
    ┌─────────────────────────────────────────────┐
    │       Multiple Access Points                │
    ├─────────────────────────────────────────────┤
    │ 1. CLI (eval_runner.py)                     │
    │ 2. API (/evals/{company_slug})             │
    │ 3. Streamlit Dashboard                      │
    └─────────────────────────────────────────────┘
```

## 📊 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Data Processing Pipeline                 │
└──────────────────────────────────────────────────────────────┘

INPUT
  │
  ├─ Ground Truth (data/eval/ground_truth.json)
  │  └─ Official sources
  │  └─ Key facts
  │  └─ Hallucination examples
  │
  ├─ Generated Dashboard (Markdown)
  │  └─ Structured Pipeline
  │  └─ RAG Pipeline
  │
  └─ Reference Material (URLs, fact sources)


PROCESSING (EvaluationRunner)
  │
  ├─ Load & validate ground truth
  ├─ Extract facts from dashboard markdown
  ├─ Assign relevance scores to facts
  ├─ Calculate MRR (fact ranking quality)
  ├─ Score other metrics against ground truth:
  │  ├─ Factual accuracy (0-3)
  │  ├─ Schema compliance (0-2)
  │  ├─ Provenance quality (0-2)
  │  ├─ Hallucination detection (0-2)
  │  ├─ Readability (0-1)
  │  └─ MRR (0-1)
  ├─ Calculate total score (0-14)
  └─ Compare structured vs RAG


OUTPUT
  │
  ├─ Cache Results (data/eval/results.json)
  │  └─ Structured pipeline metrics
  │  └─ RAG pipeline metrics
  │  └─ Winner per metric
  │
  ├─ Generate Report (data/eval/report.md)
  │  └─ Comparison table
  │  └─ Summary statistics
  │  └─ MRR analysis
  │
  └─ Return to User
     ├─ CLI display
     ├─ API response
     └─ Streamlit visualization
```

## 🔄 Evaluation Process Flow

```
START
  │
  ▼
┌─────────────────────────────────────────┐
│ 1. PREPARE GROUND TRUTH                 │
│                                         │
│ User edits data/eval/ground_truth.json  │
│ - Add company info                      │
│ - Add official sources                  │
│ - Add key facts                         │
│ - Add hallucination examples            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 2. GENERATE DASHBOARDS                  │
│                                         │
│ For each company, generate:             │
│ - Structured pipeline output            │
│ - RAG pipeline output                   │
│                                         │
│ Methods:                                │
│ - API: POST /dashboard/structured       │
│ - API: POST /dashboard/rag              │
│ - Streamlit: Click buttons              │
│ - Save outputs for reference            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 3. RUN EVALUATION                       │
│                                         │
│ python src/evals/eval_runner.py --..    │
│                                         │
│ Process:                                │
│ - Load ground truth for company         │
│ - Load dashboard markdown               │
│ - Extract facts from markdown           │
│ - Compare against ground truth          │
│ - Calculate metrics                     │
│ - Cache results                         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 4. RESULTS STORED & CACHED              │
│                                         │
│ Results saved to:                       │
│ data/eval/results.json                  │
│                                         │
│ Structure:                              │
│ {                                       │
│   "company-slug": {                     │
│     "structured": { metrics },          │
│     "rag": { metrics }                  │
│   }                                     │
│ }                                       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 5. VIEW & ANALYZE RESULTS               │
│                                         │
│ Access results via:                     │
│ - CLI: eval_runner.py --view            │
│ - API: GET /evals/{company_slug}       │
│ - Streamlit: Dashboard UI               │
│                                         │
│ Features:                               │
│ - Comparison tables                     │
│ - Charts & visualizations               │
│ - MRR analysis                          │
│ - Batch summary                         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ 6. GENERATE REPORT (Optional)           │
│                                         │
│ python src/evals/eval_runner.py \       │
│   --batch --report                      │
│                                         │
│ Output: data/eval/report.md             │
│ - Markdown table                        │
│ - Summary statistics                    │
│ - MRR analysis                          │
└────────────────┬────────────────────────┘
                 │
                 ▼
               END
```

## 🎯 Metrics Calculation Flow

```
Dashboard Markdown
       │
       ▼
┌──────────────────────────────────────┐
│ Extract Facts                        │
│ - Parse markdown lines               │
│ - Extract key information            │
│ - Assign initial relevance scores    │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Compare with Ground Truth            │
│ - Verify factual accuracy            │
│ - Check for hallucinations           │
│ - Validate citations                 │
│ - Assess information completeness    │
└──────────────────┬───────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │ Score  │ │ Score  │ │ Score  │
    │ (0-3)  │ │ (0-2)  │ │ (0-1)  │
    ├────────┤ ├────────┤ ├────────┤
    │ Fact.  │ │Schema  │ │ Read.  │
    │ Accu.  │ │Compl.  │ │        │
    │ + Hall.│ │ + Prov.│ │+ others│
    └────┬───┘ └───┬────┘ └───┬────┘
         │         │         │
         └─────────┼─────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Calculate MRR                        │
│                                      │
│ Facts: [                             │
│   {"relevance": 0.95, "rank": 1},   │
│   {"relevance": 0.50, "rank": 2},   │
│ ]                                    │
│                                      │
│ MRR = 1/1 = 1.00 (first is most rel)│
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│ Calculate Total Score                │
│                                      │
│ Total = Fact (3)                     │
│       + Schema (2)                   │
│       + Prov (2)                     │
│       + Hall (2)                     │
│       + Read (1)                     │
│       + MRR*2 (0-2)                  │
│       = 0-14                         │
└──────────────────┬───────────────────┘
                   │
                   ▼
            EvaluationMetrics
            {
              factual_accuracy: 3,
              schema_compliance: 2,
              provenance_quality: 2,
              hallucination_detection: 2,
              readability: 1,
              mrr_score: 0.95,
              total_score: 13.9
            }
```

## 🔗 Component Interactions

```
┌─────────────────────────────────────────────────────────────┐
│                  System Components                          │
└─────────────────────────────────────────────────────────────┘

┌────────────────────────┐
│  eval_metrics.py       │  (Core Logic)
│                        │
│ • EvaluationMetrics    │
│ • ComparisonResult     │
│ • calculate_mrr()      │
│ • validate()           │
│ • get_total_score()    │
└─────────┬──────────────┘
          │ (imports & uses)
          │
          ▼
┌────────────────────────┐
│  eval_runner.py        │  (Orchestration)
│                        │
│ • EvaluationRunner     │
│ • evaluate_company()   │
│ • batch_evaluate()     │
│ • generate_report()    │
│ • CLI interface        │
└─────────┬──────────────┘
          │ (uses & caches)
          │
          ▼
┌────────────────────────┐
│  FastAPI Backend       │  (API Layer)
│  (rag_search_api.py)   │
│                        │
│ • EvaluationMetrics    │
│   Response (model)     │
│ • /evals/{slug}        │
│   (endpoint)           │
│ • /evals               │
│   (endpoint)           │
└─────────┬──────────────┘
          │ (returns JSON)
          │
          ▼
┌────────────────────────┐
│  Streamlit Frontend    │  (UI Layer)
│  (eval_dashboard.py)   │
│                        │
│ • Company selector     │
│ • Comparison table     │
│ • Radar chart          │
│ • Bar chart            │
│ • MRR analysis         │
│ • Batch summary        │
└────────────────────────┘
```

## 📈 Score Calculation Example

```
PIPELINE: Structured (World Labs)
────────────────────────────────────────

Dashboard Content:
┌─ Company Founded: 2023
├─ Funding: $230M Series Unknown
├─ Investors: NEA, a16z
├─ Location: San Francisco
├─ Products: Large World Models
└─ Headcount: 38 employees


SCORING PROCESS
────────────────────────────────────────

1. FACTUAL ACCURACY (0-3)
   ├─ "Founded 2023": ✓ Correct (ground truth)
   ├─ "$230M funding": ✓ Correct (ground truth)
   ├─ "NEA, a16z": ✓ Correct (ground truth)
   ├─ "San Francisco": ✓ Correct (ground truth)
   └─ All facts verified → Score: 3/3

2. SCHEMA COMPLIANCE (0-2)
   ├─ All required sections: ✓
   ├─ Proper formatting: ✓
   └─ → Score: 2/2

3. PROVENANCE QUALITY (0-2)
   ├─ Citations for funding: ✓
   ├─ Sources cited: ✓
   └─ → Score: 2/2

4. HALLUCINATION DETECTION (0-2)
   ├─ No false claims: ✓
   └─ → Score: 2/2

5. READABILITY (0-1)
   ├─ Clear structure: ✓
   └─ → Score: 1/1

6. MEAN RECIPROCAL RANKING (0-1)
   ├─ Most relevant fact (funding): Position 1
   ├─ MRR = 1/1 = 1.00
   └─ → Score: 0.95 (slight adjustment)


TOTAL SCORE CALCULATION
────────────────────────────────────────

Factual Accuracy:       3
Schema Compliance:      2
Provenance Quality:     2
Hallucination Detect:   2
Readability:            1
MRR (scaled 0-2):     1.9 (0.95 * 2)
────────────────────────
TOTAL:             13.9 / 14


INTERPRETATION
────────────────────────────────────────

Score: 13.9 / 14
Percentage: 99%
Rating: ⭐⭐⭐⭐⭐ EXCELLENT
Status: Production Ready
```

## 🎯 MRR Ranking Example

```
Dashboard Output Order:
────────────────────────

1. "World Labs raised $230M in Series Unknown"
   └─ Relevance: 0.95 ← MOST RELEVANT (funding info)
      Rank: 1

2. "Founded in 2023, headquarters in San Francisco"
   └─ Relevance: 0.85 (important but secondary)
      Rank: 2

3. "Large World Models (LWMs) technology"
   └─ Relevance: 0.70 (supporting info)
      Rank: 3


MRR CALCULATION
────────────────────────

First relevant fact (≥ 0.7 threshold):
├─ Fact 1: relevance 0.95 ≥ 0.7 ✓
└─ This is the first relevant fact

MRR = 1 / rank_of_first_relevant
    = 1 / 1
    = 1.00 (perfect ranking)

But adjusted for actual relevance score:
MRR = min(0.95, 1.0) = 0.95


ALTERNATIVE SCENARIO (Sub-optimal)
────────────────────────────────────────

If dashboard had organized differently:

1. "Historical background of AI emergence"
   └─ Relevance: 0.30 (not relevant)

2. "Industry comparison overview"
   └─ Relevance: 0.40 (not relevant)

3. "World Labs: $230M funding"
   └─ Relevance: 0.95 ← MOST RELEVANT (but third!)
      Rank: 3

First relevant fact:
├─ Fact 1: relevance 0.30 < 0.7 ✗
├─ Fact 2: relevance 0.40 < 0.7 ✗
└─ Fact 3: relevance 0.95 ≥ 0.7 ✓

MRR = 1 / 3 = 0.33 (poor ranking)

COMPARISON
──────────
Good ranking (MRR 0.95): Important info first
Poor ranking (MRR 0.33): Important info buried
→ Structured pipeline (0.95) >> RAG pipeline (0.33)
```

## 💾 Storage & Caching

```
REQUEST FLOW WITH CACHING
────────────────────────────────────────

User Request
     │
     ▼
Check Cache (data/eval/results.json)
     │
     ├─ YES: Return cached result
     │
     └─ NO: 
        │
        ▼
     Load Ground Truth
     │
     ▼
     Extract & Score Facts
     │
     ▼
     Calculate Metrics
     │
     ▼
     Cache Result
     │
     ▼
     Return Result to User


CACHE STRUCTURE
────────────────────────────────────────

data/eval/results.json
{
  "world-labs": {
    "structured": {
      "company_name": "World Labs",
      "pipeline_type": "structured",
      "timestamp": "2025-11-06T10:30:00Z",
      "factual_accuracy": 3,
      "schema_compliance": 2,
      "provenance_quality": 2,
      "hallucination_detection": 2,
      "readability": 1,
      "mrr_score": 0.95,
      "total_score": 13.9,
      "notes": "Excellent output"
    },
    "rag": {
      "company_name": "World Labs",
      "pipeline_type": "rag",
      "timestamp": "2025-11-06T10:35:00Z",
      "factual_accuracy": 2,
      "schema_compliance": 2,
      "provenance_quality": 1,
      "hallucination_detection": 1,
      "readability": 1,
      "mrr_score": 0.75,
      "total_score": 10.5,
      "notes": "Good but some hallucinations"
    }
  }
}
```

---

**Complete architecture and data flow of the evaluation framework!**
