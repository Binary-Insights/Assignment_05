# LLM Response Storage Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STREAMLIT FRONTEND                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────┐      ┌──────────────────────────┐             │
│  │ Generate (Structured)    │      │   Generate (RAG)         │             │
│  │     Button Click         │      │    Button Click          │             │
│  └──────────────┬───────────┘      └────────────┬─────────────┘             │
│                 │                               │                           │
│                 └───────────────┬───────────────┘                           │
│                                 ▼                                           │
│                      ┌──────────────────────┐                               │
│                      │   FastAPI Backend    │                               │
│                      │ /dashboard/structured│                               │
│                      │ /dashboard/rag       │                               │
│                      └──────────────┬───────┘                               │
│                                     │                                       │
│                      ┌──────────────▼───────────────┐                       │
│                      │ API Response                 │                       │
│                      │ - company_name              │                       │
│                      │ - company_slug              │                       │
│                      │ - markdown                  │                       │
│                      │ - context_results (RAG only)│                       │
│                      └──────────────┬───────────────┘                       │
│                                     │                                       │
│                      ┌──────────────▼──────────────────────────┐             │
│                      │ save_dashboard_response()               │             │
│                      │ (Core Saving Function)                  │             │
│                      └──────────────┬───────────────────────────┘             │
│                                     │                                       │
│          ┌──────────────────────────┼──────────────────────────┐             │
│          │                          │                          │             │
│          ▼                          ▼                          ▼             │
│  ┌─────────────────┐       ┌──────────────────┐       ┌────────────────┐   │
│  │ Save Markdown   │       │ Update Company   │       │ Update Master  │   │
│  │ File            │       │ JSON             │       │ JSON           │   │
│  └────────┬────────┘       └────────┬─────────┘       └────────┬───────┘   │
│           │                         │                          │           │
│           ▼                         ▼                          ▼           │
│  markdown/{company_slug}/  json/{company_slug}/    master.json             │
│  ├─structured.md            responses.json           ├─All companies      │
│  └─rag.md                   {                        │ Latest timestamps  │
│                              "structured": {...},    │ File locations     │
│                              "rag": {...}            └─Metadata tracking  │
│                             }                                             │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │ Display Success Message with Save Details                          │   │
│  │ - File paths (markdown, company JSON, master JSON)                 │   │
│  │ - Timestamps                                                        │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

            ▼──── View Saved Responses Status ──────────────────┐
                                                                 │
                  ┌─────────────────────────────────────────────┘
                  │
                  ▼
            ┌─────────────────────┐
            │ Saved Responses Box │
            │ ✅ Structured      │ (timestamp)
            │ ✅ RAG             │ (timestamp)
            └─────────────────────┘
```

## Directory Tree

```
data/llm_response/
│
├── master.json (ALL companies aggregated)
│   └── {company_slug: {structured: {...}, rag: {...}}}
│
├── markdown/
│   ├── world-labs/
│   │   ├── structured.md (1500 lines of markdown)
│   │   └── rag.md (1200 lines of markdown)
│   │
│   ├── anthropic/
│   │   ├── structured.md
│   │   └── rag.md
│   │
│   └── abridge/
│       ├── structured.md
│       └── rag.md
│
└── json/
    ├── world-labs/
    │   └── responses.json ({structured: {...}, rag: {...}})
    │
    ├── anthropic/
    │   └── responses.json ({structured: {...}, rag: {...}})
    │
    └── abridge/
        └── responses.json ({structured: {...}, rag: {...}})
```

## Data Structure Details

### Master JSON Structure
```
master.json
├── world-labs
│   ├── company_name: "World Labs"
│   ├── company_slug: "world-labs"
│   ├── structured
│   │   ├── company_name: "World Labs"
│   │   ├── company_slug: "world-labs"
│   │   ├── pipeline_type: "structured"
│   │   ├── timestamp: "2025-11-09T05:03:48.457071Z"
│   │   └── markdown_file: "markdown/world-labs/structured.md"
│   │
│   └── rag
│       ├── company_name: "World Labs"
│       ├── company_slug: "world-labs"
│       ├── pipeline_type: "rag"
│       ├── timestamp: "2025-11-09T05:04:12.123456Z"
│       └── markdown_file: "markdown/world-labs/rag.md"
│
├── anthropic
│   ├── ...
│
└── abridge
    └── ...
```

### Company-Specific JSON Structure
```
responses.json (for world-labs)
├── company_slug: "world-labs"
├── structured
│   ├── company_name: "World Labs"
│   ├── company_slug: "world-labs"
│   ├── pipeline_type: "structured"
│   ├── timestamp: "2025-11-09T05:03:48.457071Z"
│   └── markdown_file: "markdown/world-labs/structured.md"
│
└── rag
    ├── company_name: "World Labs"
    ├── company_slug: "world-labs"
    ├── pipeline_type: "rag"
    ├── timestamp: "2025-11-09T05:04:12.123456Z"
    ├── markdown_file: "markdown/world-labs/rag.md"
    └── context_results (ONLY IN RAG)
        └── [
              {id, similarity_score, text, metadata},
              ...
            ]
```

## Function Call Stack

```
st.button("Generate (Structured)") / st.button("Generate (RAG)")
    ↓
requests.post(f"{API_BASE}/dashboard/{pipeline_type}")
    ↓
if response.status_code == 200:
    ↓
    data = response.json()
    ↓
    company_slug = data.get("company_slug")
    ↓
    save_dashboard_response(company_slug, pipeline_type, data)
        ↓
        ensure_directories()  ← Create markdown/ and json/ if needed
        ↓
        Save Markdown:
        │   markdown_path = base_dir / "markdown" / company_slug / f"{pipeline_type}.md"
        │   write markdown_path.write_text(data["markdown"])
        ├
        Save Company JSON:
        │   json_dir = base_dir / "json" / company_slug
        │   company_json = load_company_json(company_json_path)
        │   company_json[pipeline_type] = json_data
        │   save json_dir / "responses.json"
        ├
        Update Master JSON:
        │   master_json = load_master_json(master_path)
        │   master_json[company_slug][pipeline_type] = json_data
        │   save master_path
        └
        Display Success + Save Details
    ↓
st.success("✅ Saved...")
view_saved_responses(company_slug)
```

## File Write Operations (Per Click)

```
ONE CLICK = THREE FILE OPERATIONS:

1. MARKDOWN FILE
   Path: data/llm_response/markdown/{company_slug}/{pipeline_type}.md
   Operation: CREATE or OVERWRITE
   Content: Full markdown dashboard (1000-2000 lines)
   Size: ~100-300 KB

2. COMPANY JSON
   Path: data/llm_response/json/{company_slug}/responses.json
   Operation: READ → UPDATE → WRITE (merge operation)
   Content: Both {structured} and {rag} entries
   Size: ~10-50 KB (can grow with RAG context_results)

3. MASTER JSON
   Path: data/llm_response/master.json
   Operation: READ → UPDATE → WRITE (merge operation)
   Content: Summary of ALL companies
   Size: ~5-20 KB (summary only, no context_results)
```

## State Management in Streamlit

```
Session State:
  ├── structured_data (dict)  ← stores latest response
  ├── rag_data (dict)         ← stores latest response
  └── (used to re-render UI without re-generating)

Files (Persistent):
  ├── data/llm_response/master.json
  ├── data/llm_response/markdown/{slug}/{type}.md
  └── data/llm_response/json/{slug}/responses.json
  
  └─ SURVIVE: app restart, browser refresh, etc.
```

## Error Handling Flow

```
save_dashboard_response()
    ├── ensure_directories()
    │   ├── Try: mkdir (parents=True, exist_ok=True)
    │   └── If error: st.error("Failed to create directories")
    │
    ├── Save Markdown
    │   ├── Try: write file
    │   └── If error: st.error("Failed to save markdown")
    │
    ├── Update Company JSON
    │   ├── Try: load existing JSON
    │   ├── Try: update with new data
    │   ├── Try: save updated JSON
    │   └── If error: st.error("Failed to save company JSON")
    │
    ├── Update Master JSON
    │   ├── Try: load existing master
    │   ├── Try: update with new data
    │   ├── Try: save updated master
    │   └── If error: st.error("Failed to save master JSON")
    │
    └── Display Success
        ├── st.success("✅ Saved...")
        ├── st.expander("📁 Save Details")
        │   ├── Show markdown path
        │   ├── Show company JSON path
        │   └── Show master JSON path
        └── (All paths relative to data/llm_response/)
```

## Integration Points

### With Evaluation System
```
Evaluation reads from:
├── data/llm_response/markdown/{company_slug}/structured.md
├── data/llm_response/markdown/{company_slug}/rag.md
└── Uses for: Comparing pipeline outputs, generating metrics
```

### With Version Control
```
Git tracks:
├── data/llm_response/master.json (summary only)
└── Can track timestamps to know when responses changed
```

### With Export Tools
```
External tools can read from:
├── data/llm_response/master.json (quick overview)
├── data/llm_response/json/{slug}/responses.json (company details)
└── data/llm_response/markdown/{slug}/{type}.md (full content)
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Save markdown | ~10-50ms | Write speed depends on file size |
| Update company JSON | ~5-10ms | JSON parse + write |
| Update master JSON | ~10-20ms | Scales with number of companies |
| Total save time | ~30-80ms | Async from network latency |
| View saved status | ~5ms | Just reads existing JSON |

## Scalability

```
Current design supports:
├── Up to 100+ companies
├── Multiple regenerations (overwrites old files)
├── RAG context_results with 100+ chunks per company
└── Unlimited markdown content

Storage estimate:
├── Per company (1 structured + 1 RAG): ~400-600 KB
├── 50 companies: ~20-30 MB
├── master.json overhead: ~50 KB
└── Total for all: manageable on any system
```
