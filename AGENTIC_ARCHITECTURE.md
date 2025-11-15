# Agentic RAG Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [Agent Classification](#agent-classification)
3. [System Architecture](#system-architecture)
4. [Workflow Components](#workflow-components)
5. [Data Flow](#data-flow)
6. [Key Features](#key-features)
7. [State Management](#state-management)
8. [Decision Logic](#decision-logic)
9. [Extraction Pipeline](#extraction-pipeline)
10. [Observability & Tracing](#observability--tracing)

---

## Overview

This system implements a **Supervisor/Planner** agent that orchestrates intelligent payload enrichment using LLM-powered data extraction. It combines:

- **Deterministic workflow control** via LangGraph state machine
- **Multi-step LLM extraction chains** with confidence-based validation
- **Real-time search integration** with Tavily API
- **Full observability** through LangSmith tracing

### Core Purpose
Automatically enrich company data payloads by:
1. Identifying null/empty fields in structured data
2. Searching for relevant information via Tavily
3. Intelligently extracting values using a 3-step LLM chain
4. Validating and updating payloads with provenance tracking

---

## Agent Classification

### Type: **Supervisor/Planner Agent**

```
┌──────────────────────────────────────────────────────────┐
│  SUPERVISOR/PLANNER AGENT (LangGraph)                   │
│  ├─ Analyzes payloads upfront                           │
│  ├─ Plans enrichment sequence                           │
│  ├─ Manages execution state                             │
│  ├─ Controls loop/iteration logic                       │
│  └─ Decides continue/stop conditions                    │
└──────────────────────────────────────────────────────────┘
```

### Why Supervisor/Planner?

| Characteristic | Status | Evidence |
|---|---|---|
| **Upfront Planning** | ✅ | `analyze_payload()` identifies all enrichable fields at start |
| **Sequential Execution** | ✅ | One field processed per iteration via `get_next_null_field()` |
| **Central Control** | ✅ | `check_completion()` gate controls all loop decisions |
| **State Management** | ✅ | `PayloadEnrichmentState` tracks all workflow metadata |
| **Iteration Limits** | ✅ | `MAX_ITERATIONS=20` prevents runaway loops |
| **Error Accumulation** | ✅ | Collects errors, aborts if >5 critical failures |
| **Dynamic Routing** | ✅ | Routes to continue/end based on state conditions |

### NOT an Evaluator Agent

An **Evaluator** agent would:
- Generate multiple extraction solutions
- Compare and score each approach
- Select the best performing one

This system makes a **single extraction attempt** per field with confidence-based filtering (threshold: 0.5).

---

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│  ENTRY POINT: @traceable enrich_single_company()           │
│  (LangSmith trace root - single unified trace)             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  SUPERVISOR: LangGraph Workflow State Machine              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. analyze_payload()          (PLANNING PHASE)      │   │
│  │    - Identifies null fields                         │   │
│  │    - Builds enrichment queue                        │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. get_next_null_field()      (SELECTION PHASE)    │   │
│  │    - Picks field from queue                         │   │
│  │    - Checks iteration limits                        │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. generate_search_queries()  (QUERY GENERATION)    │   │
│  │    - Creates 3 targeted queries                     │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 4. execute_searches()         (SEARCH EXECUTION)    │   │
│  │    - Calls Tavily API 3 times                       │   │
│  │    - Saves responses to disk                        │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 5. extract_and_update_payload() (EXTRACTION/UPDATE)│   │
│  │    - Runs LLM extraction chain (3 steps)            │   │
│  │    - Updates payload with results                   │   │
│  │    - Adds source URL tracking                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 6. check_completion()         (DECISION GATE)       │   │
│  │    - Evaluates 4 stop conditions                    │   │
│  │    - Routes to continue or END                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  LLM EXTRACTION CHAIN (3-Step Sub-Agent)                   │
│  ├─ Step 1: generate_extraction_question()                 │
│  │           → Generates targeted question                 │
│  ├─ Step 2: extract_value_from_context()                   │
│  │           → Extracts from top 5 search results         │
│  └─ Step 3: validate_and_refine()                          │
│              → Validates and refines confidence             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  TOOLS & SERVICES                                           │
│  ├─ Tavily Search API      (external search)               │
│  ├─ OpenAI ChatGPT         (LLM extraction)                │
│  ├─ Pinecone              (vector storage - optional)      │
│  └─ LangSmith             (observability)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Workflow Components

### 1. **Planning Phase: `analyze_payload()`**

**Purpose:** Identify all enrichable null fields upfront

**Logic:**
```python
null_fields = []

# Check nested company_record fields (primary target)
if "company_record" in payload:
    for field_name, value in company.items():
        if field_name in SKIP_LIST:  # metadata fields
            continue
        
        if value is None or value == "" or (is_list and len == 0):
            null_fields.append({
                "entity_type": "company_record",
                "field_name": field_name,
                "importance": "high"
            })

# Also check top-level payload fields (secondary)
for key, value in payload.items():
    if not is_special_key(key) and is_empty(value):
        null_fields.append({
            "entity_type": "payload",
            "field_name": key,
            "importance": "medium"
        })

state.null_fields = null_fields
```

**Output:** Queue of enrichable fields (e.g., ~12 fields for typical company payload)

---

### 2. **Selection Phase: `get_next_null_field()`**

**Purpose:** Sequentially select the next field to enrich

**Stop Conditions (Precedence Order):**
1. ✅ Iteration reached `MAX_ITERATIONS` (20)
2. ✅ No more fields in queue
3. ✅ `status == "completed"` (explicit mark)
4. ✅ Error count > 5

**Action:**
```python
if state.iteration >= state.max_iterations:
    return END  # Stop workflow

if not state.null_fields:
    return END  # Stop workflow

# Get next field from queue
state.current_null_field = state.null_fields.pop(0)
state.status = "searching"
return "continue"  # Loop back to query generation
```

---

### 3. **Query Generation: `generate_search_queries()`**

**Purpose:** Create targeted search queries for field enrichment

**Strategy:** Generate 3 variations for breadth
```python
field_name = "categories"
company_name = "Abridge"

queries = [
    "Abridge categories",                    # Basic
    "Abridge company categories",            # Company context
    "categories Abridge"                     # Reversed
]
```

**Output:** `state.search_queries = ["query1", "query2", "query3"]`

---

### 4. **Search Execution: `execute_searches()`**

**Purpose:** Call Tavily API for each query

**Implementation:**
```python
for query in state.search_queries:
    result = _execute_tavily_search(tool_manager, query, company_name)
    
    if result.get("success"):
        all_documents.extend(result["results"])
        save_to_disk(result)  # Save JSON response
    else:
        state.errors.append(f"Query failed: {query}")

state.search_results = {
    "results": all_documents,           # Flattened list
    "combined_content": combined_text,
    "total_results": len(all_documents),
    "queries_executed": len(queries)
}
```

**Output Format for Each Result:**
```json
{
  "title": "Abridge - AI-powered...",
  "content": "Abridge is a healthcare company...",
  "url": "https://example.com/abridge",
  "relevance_score": 0.95
}
```

---

### 5. **Extraction & Update: `extract_and_update_payload()`**

**Purpose:** Use LLM chain to extract values and update payload

**Core Logic:**
```python
# Run 3-step LLM extraction chain
extraction_result = await chain.run_extraction_chain(
    field_name=field_name,
    search_results=search_results,  # Top 5 results
    company_name=company_name
)

extracted_value = extraction_result.final_value
confidence = extraction_result.confidence

# Update payload only if confident
if extracted_value is not None and confidence >= 0.5:
    company[field_name] = extracted_value
    
    # Add extraction metadata with source URLs
    company["_extraction_metadata"][field_name] = {
        "source": "agentic_rag",
        "tool": "tavily_llm_extraction",
        "source_urls": extraction_result.sources,  # ← KEY: URLs tracked here
        "extracted_at": iso_timestamp,
        "confidence": confidence,
        "reasoning": reasoning_text
    }
else:
    # Skip update if not confident enough
    state.iteration += 1
```

---

### 6. **Decision Gate: `check_completion()`**

**Purpose:** Determine workflow continuation

**Decision Logic:**
```python
if state.status == "completed":
    return END  # Explicit completion

if not state.null_fields:
    state.status = "completed"
    return END  # No more fields

if state.iteration >= state.max_iterations:
    state.status = "completed"
    return END  # Iteration limit

if len(state.errors) > 5:
    state.status = "completed"
    return END  # Too many errors

# Continue processing
return "continue"  # Loop back to get_next_field()
```

---

## Data Flow

### Payload Enrichment Sequence

```
INPUT: Company Payload
├─ company_record
│  ├─ brand_name: "Abridge"        ✅ Has value
│  ├─ founded_year: null           ❌ Needs enrichment
│  ├─ categories: []               ❌ Empty list
│  ├─ headquarters_city: null      ❌ Needs enrichment
│  └─ ...12 more null fields
├─ events: []
├─ products: []
└─ leadership: []

                    ↓ [PLANNING]

ENRICHMENT QUEUE (Sorted by Priority)
[
  {field: "founded_year",      importance: "high"},
  {field: "categories",        importance: "high"},
  {field: "headquarters_city", importance: "high"},
  ... (9 more)
]

                    ↓ [ITERATION 1]

Query: "Abridge founded_year"
  ↓
Tavily Results: [{url: "...", content: "...founded in 2018..."}]
  ↓
LLM Extraction: "2018" (confidence: 1.0)
  ↓
Update Payload:
  company_record.founded_year = "2018"
  company_record._extraction_metadata.founded_year = {
    "source_urls": ["https://..."],
    "confidence": 1.0,
    "reasoning": "..."
  }

                    ↓ [ITERATION 2-N...]

(Process remaining fields...)

                    ↓ [OUTPUT]

ENRICHED PAYLOAD
├─ company_record
│  ├─ brand_name: "Abridge"
│  ├─ founded_year: "2018"               ← Updated with URL tracking
│  ├─ categories: ["Healthcare", "AI"]   ← Updated with URL tracking
│  ├─ headquarters_city: "Pittsburgh"    ← Updated with URL tracking
│  ├─ _extraction_metadata
│  │  ├─ founded_year
│  │  │  ├─ source_urls: ["https://..."]
│  │  │  ├─ confidence: 1.0
│  │  │  └─ reasoning: "..."
│  │  └─ ... (more fields)
│  └─ ...
└─ ...
```

---

## Key Features

### 1. **Deterministic LLM Extraction**

**Temperature: 0.1** (vs default 0.7)
- Produces consistent, reproducible results
- Minimizes hallucination for data extraction

**3-Step Chain Pattern:**
```
Step 1: Question Generation
  Q: "What is the founding year of Abridge?"
  ↓
Step 2: Context Extraction  
  A: "Abridge was founded in 2018"
  ↓
Step 3: Validation & Refinement
  Confirmed: "2018" (confidence: 1.0)
```

### 2. **Source URL Tracking**

Every extracted value includes source URLs:
```json
{
  "source_urls": [
    "https://en.wikipedia.org/wiki/Abridge",
    "https://www.crunchbase.com/organization/abridge"
  ],
  "confidence": 0.95
}
```

**Benefit:** Complete traceability for audit/compliance

### 3. **Confidence-Based Filtering**

Only updates payload if `confidence >= 0.5`:
- **1.0** - Extracted directly from clear source
- **0.8-0.9** - Inferred from multiple sources
- **0.5-0.7** - Partially confident extraction
- **<0.5** - Rejected (skipped update)

### 4. **Iteration Control**

- **MAX_ITERATIONS: 20** - Prevents infinite loops
- Tracks iteration count for each field processed
- Aborts if max reached (with status log)

### 5. **Error Accumulation**

- Collects all errors in `state.errors` list
- Aborts if error count > 5
- Detailed logging of all failures

### 6. **Full Observability**

**Single LangSmith Trace:**
```
enrich_single_company()  [ROOT TRACE]
├─ analyze_payload()
├─ get_next_null_field()
├─ generate_search_queries()
├─ execute_searches()
│  └─ tavily_search [CHILD SPAN] ← Visible sub-spans
├─ extract_and_update_payload()
│  ├─ generate_extraction_question()
│  ├─ extract_value_from_context()
│  └─ validate_and_refine()
└─ check_completion()
```

---

## State Management

### `PayloadEnrichmentState` Pydantic Model

```python
class PayloadEnrichmentState(BaseModel):
    # Payload data
    company_name: str
    company_id: str
    current_payload: Dict[str, Any]          # Modified payload
    original_payload: Dict[str, Any]         # Immutable snapshot
    
    # Processing metadata
    iteration: int = 0                       # Current iteration count
    max_iterations: int = 20                 # Hard limit
    
    # Null fields queue
    null_fields: List[Dict] = []             # Remaining fields to process
    current_null_field: Optional[Dict] = None # Currently processing
    
    # LLM messages (for multi-turn if needed)
    messages: List[BaseMessage] = []
    
    # Tool results
    search_results: Optional[Dict] = None    # Tavily results
    extracted_values: Dict[str, Any] = {}    # Accumulated extractions
    
    # Vector DB context (optional)
    vector_context: str = ""
    
    # Workflow control
    status: str = "initialized"  # initialized|analyzing|searching|updating|completed
    errors: List[str] = []       # Error accumulator
```

**State Transitions:**
```
initialized → analyzing → searching → updating → (check_completion)
                                                    ├─ continue → get_next_field
                                                    └─ END → completed
```

---

## Decision Logic

### Stop Condition Matrix

| Condition | Priority | Action | Log Level |
|---|---|---|---|
| `status == "completed"` | 1 | END | INFO |
| `null_fields.empty()` | 2 | END | INFO |
| `iteration >= max_iterations` | 3 | END | WARNING |
| `errors > 5` | 4 | END | ERROR |

### Continue Condition

If **none** of the stop conditions are met:
```python
return "continue"  # → loops back to get_next_field()
```

---

## Extraction Pipeline

### The 3-Step LLM Chain

#### Step 1: Question Generation
**LLM Prompt:**
```
You are an expert data extraction specialist.
Generate a precise, targeted question to extract a specific field value.

Generate an extraction question for:
- Field Name: founded_year
- Company: Abridge
- Importance: high

Respond with JSON:
{
  "question": "When was Abridge founded?",
  "expected_format": "year",
  "context": "Founding year is critical for company history"
}
```

**Output:** `ExtractionQuestion` object with targeted question

#### Step 2: Value Extraction
**LLM Prompt:**
```
Extract specific information from search results.
Be conservative - only extract values you're confident about.

Question: When was Abridge founded?
Expected Format: year

Search Results:
[1] Title: Abridge Company Overview
    URL: https://...
    Content: "Abridge, founded in 2018, is a healthcare AI company..."

[2] Title: Abridge Funding History
    URL: https://...
    Content: "The company was founded in 2018 by..."

Extract the founded_year value.
Respond with JSON:
{
  "field_name": "founded_year",
  "extracted_value": "2018",
  "confidence": 1.0,
  "reasoning": "Multiple sources clearly state 2018",
  "sources": ["https://...", "https://..."]
}
```

**Output:** `ExtractedValue` with value, confidence, reasoning, sources

#### Step 3: Validation & Refinement
**LLM Prompt:**
```
Validate and refine extracted information.
Ensure consistency and correctness.

Company: Abridge
Field: founded_year
Extracted Value: 2018
Current Confidence: 1.0

Respond with JSON:
{
  "is_valid": true,
  "refined_value": "2018",
  "final_confidence": 1.0,
  "validation_notes": "Confirmed across multiple reliable sources"
}
```

**Output:** Validated `ExtractedValue` with refined confidence

### All Steps Use Pipe Operator

```python
# Pattern used in all 3 steps
chain = prompt | self.llm | JsonOutputParser()
response = await chain.ainvoke({
    "field_name": field_name,
    # ... other params
})
```

**Benefits:**
- ✅ Proper async/await support
- ✅ Type-safe LangChain integration
- ✅ Automatic serialization
- ✅ Clean data flow

---

## Observability & Tracing

### LangSmith Integration

**Setup:**
```python
@traceable  # Entry point decorator
async def enrich_single_company(company_name: str) -> Dict[str, Any]:
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    result = await orchestrator.process_single_company(company_name)
    return result

@traceable(name="tavily_search", tags=["search", "tavily"])
def _execute_tavily_search(tool_manager, query: str, company_name: str):
    # Tavily search visible as child span
    ...
```

**Trace Structure:**
```
Trace: enrich_single_company [ROOT]
├─ Span: analyze_payload
├─ Span: get_next_null_field
├─ Span: generate_search_queries
├─ Span: execute_searches
│  ├─ Span: tavily_search (iteration 1)
│  ├─ Span: tavily_search (iteration 2)
│  └─ Span: tavily_search (iteration 3)
├─ Span: extract_and_update_payload
│  ├─ LLM Call: generate_extraction_question
│  ├─ LLM Call: extract_value_from_context
│  └─ LLM Call: validate_and_refine
└─ Span: check_completion
```

### Logging Strategy

**Log Levels:**
- **INFO** ← Primary execution flow (all major steps)
- **DEBUG** ← Detailed state/variable values
- **WARNING** ← Non-critical issues (skipped updates)
- **ERROR** ← Critical failures (extraction errors)

**Log Tags:**
- `[ANALYZE]` - Payload analysis
- `[QUERY GEN]` - Query generation
- `[TAVILY SEARCH]` - API calls
- `[LLM CHAIN]` - Extraction steps
- `[UPDATE]` - Payload updates
- `[CHECK COMPLETION]` - Workflow decisions

---

## Configuration

### Key Parameters

| Parameter | Value | Purpose |
|---|---|---|
| `LLM_MODEL` | `gpt-4o-mini` | Fast, deterministic extraction |
| `LLM_TEMPERATURE` | `0.1` | Minimal randomness |
| `MAX_ITERATIONS` | `20` | Process up to 20 fields |
| `CONFIDENCE_THRESHOLD` | `0.5` | Only update if confident |
| `TOOL_TIMEOUT` | `30s` | Tavily API timeout |
| `TAVILY_MAX_RESULTS` | `5` | Limit context size |

### Environment Variables

```bash
OPENAI_API_KEY=sk-...          # ChatGPT API
TAVILY_API_KEY=tvly-...        # Tavily search
LANGSMITH_API_KEY=...          # Tracing
LANGCHAIN_PROJECT=agentic-rag  # Trace project
LANGCHAIN_TRACING_V2=true      # Enable V2
```

---

## Example Output

### Input Payload
```json
{
  "company_record": {
    "legal_name": "Abridge Inc",
    "brand_name": "Abridge",
    "founded_year": null,
    "categories": [],
    "hq_city": null,
    "hq_state": null
  }
}
```

### Enriched Output
```json
{
  "company_record": {
    "legal_name": "Abridge Inc",
    "brand_name": "Abridge",
    "founded_year": "2018",
    "categories": ["Healthcare", "Artificial Intelligence"],
    "hq_city": "Pittsburgh",
    "hq_state": "PA",
    "_extraction_metadata": {
      "founded_year": {
        "source": "agentic_rag",
        "tool": "tavily_llm_extraction",
        "source_urls": [
          "https://en.wikipedia.org/wiki/Abridge",
          "https://crunchbase.com/organization/abridge"
        ],
        "extracted_at": "2025-11-15T10:30:45.123Z",
        "confidence": 1.0,
        "reasoning": "Multiple reliable sources confirm founded in 2018"
      },
      "categories": {
        "source": "agentic_rag",
        "tool": "tavily_llm_extraction",
        "source_urls": [
          "https://www.abridge.com"
        ],
        "extracted_at": "2025-11-15T10:30:52.456Z",
        "confidence": 0.95,
        "reasoning": "Extracted from company website and industry databases"
      }
    }
  }
}
```

---

## Advantages of This Architecture

### 1. **Deterministic & Reproducible**
- Fixed LLM temperature (0.1) ensures consistent results
- Pipe operator chaining guarantees proper async handling
- Detailed logging enables debugging

### 2. **Observable & Auditable**
- Single unified LangSmith trace
- All Tavily searches visible as child spans
- Source URLs tracked for every extracted value
- Complete extraction reasoning stored

### 3. **Robust & Recoverable**
- State machine with clear stopping conditions
- Error accumulation with abort logic
- Iteration limits prevent infinite loops
- Original payload immutable (backup in `original_payload`)

### 4. **Scalable & Extensible**
- Easy to add new enrichment fields
- Support for multiple entity types
- Confidence-based filtering allows field-specific strategies
- Modular 3-step extraction pipeline

### 5. **Production-Ready**
- Comprehensive error handling
- Timeout protection on API calls
- Test mode with isolated outputs
- Backup creation before updates

---

## Future Enhancements

### Potential Improvements

1. **Adaptive Field Prioritization**
   - Route critical fields first based on domain
   - Skip low-confidence extractions automatically

2. **Multi-Strategy Extraction**
   - Different extraction strategies per field type
   - Fallback strategies for failed extractions

3. **Batch Processing**
   - Process multiple companies in parallel
   - Load balancing across concurrent requests

4. **Dynamic Confidence Thresholds**
   - Different thresholds by field importance
   - Learn optimal thresholds from feedback

5. **Feedback Loop Integration**
   - Collect user corrections
   - Retrain extraction model with feedback

6. **Hybrid Search**
   - Combine Tavily + Vector DB search
   - Weighted result ranking

---

## Conclusion

This **Supervisor/Planner agent** provides enterprise-grade data enrichment by combining:

- ✅ Deterministic workflow orchestration (LangGraph)
- ✅ Multi-step intelligent extraction (LLM chain)
- ✅ Real-time external search (Tavily)
- ✅ Full observability (LangSmith)
- ✅ Comprehensive provenance tracking
- ✅ Production-ready error handling

The architecture balances **automation** with **control**, enabling reliable, auditable payload enrichment at scale.
