# Architecture Diagram: Structured Pipeline

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PROJECT ORBIT - PE DASHBOARD                     │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────┐
│   STREAMLIT UI       │         │    FASTAPI BACKEND   │
│  (Web Interface)     │         │  (REST API Server)   │
└──────────────────────┘         └──────────────────────┘
         │                                │
         │  POST /dashboard/structured   │
         │<──────────────────────────────>│
         │  company_name=World Labs      │
         │                               │
         │  Response: markdown dashboard │
         │                               │
         └────────────────┬──────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
    ┌─────▼──────────┐         ┌──────────▼────────┐
    │  QDRANT DB     │         │ FILE SYSTEM       │
    │  (Not used by  │         │ data/payloads/    │
    │   structured)  │         │ {slug}.json       │
    └────────────────┘         └───────────────────┘
                                        │
                            ┌───────────┴──────────────┐
                            │                          │
                    ┌───────▼────────┐      ┌─────────▼──────┐
                    │ STRUCTURED     │      │ RAG PIPELINE   │
                    │ PIPELINE       │      │ (Alternative)  │
                    │ (NEW)          │      │                │
                    └────────────────┘      └────────────────┘
```

---

## Structured Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      STREAMLIT APP                                  │
│                  streamlit_app.py                                   │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ User selects "World Labs"                                    │ │
│  │ Clicks "Generate (Structured)" button                         │ │
│  └───────────────────────────┬─────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ requests.post(                                               │ │
│  │   "/dashboard/structured",                                  │ │
│  │   params={"company_name": "World Labs"},                    │ │
│  │   timeout=30                                                 │ │
│  │ )                                                            │ │
│  └───────────────────────────┬─────────────────────────────────┘ │
└──────────────────────────────┼─────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                                 │
│                 rag_search_api.py                                   │
│                                                                     │
│  POST /dashboard/structured                                        │
│    company_name: str (query parameter)                             │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 1. Convert company_name to slug                              │ │
│  │    "World Labs" → "world-labs"                               │ │
│  └───────────────────────────┬─────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 2. Import structured_pipeline module                         │ │
│  │    from structured.structured_pipeline import \             │ │
│  │      generate_dashboard_from_payload                        │ │
│  └───────────────────────────┬─────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 3. Call generate_dashboard_from_payload(                     │ │
│  │      company_name="World Labs",                              │ │
│  │      company_slug="world-labs",                              │ │
│  │      llm_client=None,  # Auto-initialize                     │ │
│  │      llm_model="gpt-4o"                                      │ │
│  │    )                                                          │ │
│  └───────────────────────────┬─────────────────────────────────┘ │
│                              │                                    │
│                              ▼ ENTERS STRUCTURED_PIPELINE         │
└──────────────────────────────┼─────────────────────────────────────┘
                               │
┌──────────────────────────────┼─────────────────────────────────────┐
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │        STRUCTURED_PIPELINE.PY                              │  │
│  │    (src/structured/structured_pipeline.py)             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│   ┌──────────────────────────┴──────────────────────────────┐     │
│   │                                                         │     │
│   ▼ Function Chain:                                        │     │
│                                                             │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ generate_dashboard_from_payload(...)                │   │     │
│ │ Entry point                                          │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 1. Load data/payloads/world-labs.json              │   │     │
│ │    {                                                │   │     │
│ │      "company_record": {...},                       │   │     │
│ │      "events": [...],                               │   │     │
│ │      "products": [...],                             │   │     │
│ │      "leadership": [...],                           │   │     │
│ │      "visibility": [...],                           │   │     │
│ │      "snapshots": [...],                            │   │     │
│ │      "notes": "..."                                 │   │     │
│ │    }                                                │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 2. Call format_payload_for_llm(payload)             │   │     │
│ │    Returns: ~600-800 line text string               │   │     │
│ │                                                      │   │     │
│ │    Output format:                                   │   │     │
│ │    ---                                              │   │     │
│ │    ## Company Record                                │   │     │
│ │    **Founded:** 2024                                │   │     │
│ │    **HQ:** San Francisco, CA                        │   │     │
│ │                                                      │   │     │
│ │    ## Events (15 total)                             │   │     │
│ │    - **Press Release** (Jan 2025): ...              │   │     │
│ │    ... (limited to first 10)                        │   │     │
│ │                                                      │   │     │
│ │    ## Products (3 total)                            │   │     │
│ │    - **Platform**: Description...                   │   │     │
│ │    ... (limited to first 5)                         │   │     │
│ │                                                      │   │     │
│ │    [... more sections ...]                          │   │     │
│ │    ---                                              │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 3. Call generate_dashboard_markdown(                │   │     │
│ │      company_name="World Labs",                     │   │     │
│ │      payload=<loaded_json>,                         │   │     │
│ │      llm_client=None,                               │   │     │
│ │      llm_model="gpt-4o"                             │   │     │
│ │    )                                                │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 3a. Initialize OpenAI client                        │   │     │
│ │     client = OpenAI(api_key=os.environ[...])        │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 3b. Load system prompt                              │   │     │
│ │     get_dashboard_system_prompt()                   │   │     │
│ │     (from src/prompts/dashboard_system.md)      │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 3c. Build LLM prompt                                │   │     │
│ │     system: [system prompt from MD file]            │   │     │
│ │     user: "Generate dashboard for World Labs        │   │     │
│ │           using ONLY this context: [formatted]"     │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 3d. Call OpenAI API                                 │   │     │
│ │     response = client.chat.completions.create(      │   │     │
│ │       model="gpt-4o",                               │   │     │
│ │       max_tokens=4096,                              │   │     │
│ │       messages=[                                     │   │     │
│ │         {"role": "system", "content": system_...}, │   │     │
│ │         {"role": "user", "content": user_message}   │   │     │
│ │       ]                                              │   │     │
│ │     )                                                │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼ (5-10 seconds delay)                 │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 3e. Extract markdown from response                  │   │     │
│ │     markdown = response.choices[0].message.content  │   │     │
│ │                                                      │   │     │
│ │ Returns: "# World Labs - Investor Diligence..."     │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 4. Return markdown from generate_dashboard_markdown │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼                                       │     │
│ ┌─────────────────────────────────────────────────────┐   │     │
│ │ 5. Return from generate_dashboard_from_payload      │   │     │
│ │    Returns: markdown_string (2000-4000 chars)       │   │     │
│ └──────────────────┬──────────────────────────────────┘   │     │
│                    │                                       │     │
│                    ▼ EXITS STRUCTURED_PIPELINE             │     │
└────────────────────┼────────────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────────────┐
│                    ▼                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Create DashboardStructuredResponse:                 │   │
│  │ {                                                   │   │
│  │   "company_name": "World Labs",                     │   │
│  │   "company_slug": "world-labs",                     │   │
│  │   "markdown": "# World Labs - Investor...",         │   │
│  │   "status": "success",                              │   │
│  │   "message": "Generated successfully..."            │   │
│  │ }                                                   │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                      │
│                     ▼                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Serialize to JSON                                   │   │
│  │ Return 200 OK response                              │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                      │
│                     ▼                                      │
│  HTTP Response (200 OK)                                 │
│  Content-Type: application/json                        │
│                     │                                      │
└─────────────────────┼──────────────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │   STREAMLIT RECEIVES       │
         │   JSON RESPONSE            │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │ Parse response.json()      │
         │ Extract markdown field     │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │ st.markdown(markdown)      │
         │ Display formatted content  │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │   USER SEES:               │
         │                            │
         │ # World Labs - Investor    │
         │   Diligence Dashboard      │
         │                            │
         │ ## Company Overview        │
         │ World Labs is a leading AI │
         │ company founded in 2024... │
         │                            │
         │ ## Business Model and GTM  │
         │ The company provides...    │
         │                            │
         │ [... more sections ...]    │
         │                            │
         │ ## Disclosure Gaps         │
         │ * Revenue: Not disclosed   │
         │ * Employees: Not disclosed │
         │                            │
         └────────────────────────────┘
```

---

## Component Interaction Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPONENTS & INTERACTIONS                        │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐
│   streamlit_app.py       │  ← User Interface
│  (Streamlit)             │
│                          │
│ - Company dropdown       │
│ - "Generate" buttons     │
│ - Markdown display       │
└────────┬─────────────────┘
         │ HTTP POST
         │ company_name=X
         │
         ▼
┌──────────────────────────────────────────────────────┐
│           rag_search_api.py                          │ ← API Server
│  (FastAPI)                                           │
│                                                      │
│  Routes:                                             │
│  GET  /                → root info                   │
│  GET  /health         → health check                 │
│  GET  /companies      → list all companies           │
│  POST /rag/search     → vector search                │
│  POST /dashboard/rag  → RAG generation               │
│  POST /dashboard/structured → STRUCTURED generation  │ ← NEW
│                                                      │
│  When /dashboard/structured called:                  │
│  1. Import structured_pipeline                       │
│  2. Call generate_dashboard_from_payload()           │
│  3. Return DashboardStructuredResponse               │
└──────┬──────────────────────────────────────────────┘
       │ imports
       │
       ▼
┌──────────────────────────────────────────────────────┐
│      structured_pipeline.py                          │ ← NEW
│  (Structured Dashboard Generator)                    │
│                                                      │
│  Functions:                                          │
│  • generate_dashboard_from_payload()  ← Entry point  │
│  • generate_dashboard_markdown()                     │
│  • format_payload_for_llm()                          │
│  • get_dashboard_system_prompt()                     │
│  • _generate_default_dashboard()                     │
└──────┬──────────────────────────────────────────────┘
       │ reads
       │
       ▼
┌──────────────────────────────────────────────────────┐
│     data/payloads/*.json                             │ ← Data Files
│                                                      │
│  Structure:                                          │
│  {                                                   │
│    "company_record": {...},                          │
│    "events": [...],                                  │
│    "products": [...],                                │
│    "leadership": [...],                              │
│    "visibility": [...],                              │
│    "snapshots": [...],                               │
│    "notes": "..."                                    │
│  }                                                   │
└──────┬──────────────────────────────────────────────┘
       │ reads
       │
       ▼
┌──────────────────────────────────────────────────────┐
│     src/prompts/dashboard_system.md              │ ← Prompt
│                                                      │
│  LLM System Prompt (shared with RAG)                 │
│  Instructions for generating 8 sections              │
└──────┬──────────────────────────────────────────────┘
       │ uses
       │
       ▼
┌──────────────────────────────────────────────────────┐
│     OpenAI API (gpt-4o)                              │ ← LLM
│                                                      │
│  Generates markdown dashboard from:                  │
│  • System prompt (from dashboard_system.md)          │
│  • Formatted payload context                         │
│                                                      │
│  Returns: Markdown with 8 sections                   │
└──────┬──────────────────────────────────────────────┘
       │ response
       │
       ▼
┌──────────────────────────────────────────────────────┐
│     data/logs/rag_search_api.log                     │ ← Logging
│                                                      │
│  Logs all operations:                                │
│  • Request received                                  │
│  • Payload loaded                                    │
│  • LLM called                                        │
│  • Response generated                                │
│  • Errors caught                                     │
└──────────────────────────────────────────────────────┘

(Also .env for configuration)
```

---

## Error Handling Flow

```
POST /dashboard/structured?company_name=Unknown
        │
        ▼
generate_dashboard_from_payload()
        │
        ├─ Try to load data/payloads/unknown.json
        │  │
        │  └─ FileNotFoundError
        │     │
        │     ▼
        │  Raise FileNotFoundError("No payload found...")
        │     │
        │     ▼
        │ Catch in FastAPI endpoint
        │     │
        │     ▼
        │ Return 404 HTTPException
        │     │
        │     ▼
        │ Return to client: {"detail": "No structured payload found..."}
        │
        └─ (If file exists)
           Try to load JSON
           │
           ├─ JSONDecodeError
           │  │
           │  ▼
           │  Return 500 HTTPException
           │  └─ {"detail": "Invalid JSON format..."}
           │
           └─ (If JSON valid)
              format_payload_for_llm()
              │
              └─ generate_dashboard_markdown()
                 │
                 ├─ Try OpenAI API call
                 │  │
                 │  ├─ Success: Return markdown
                 │  │
                 │  └─ Exception
                 │     │
                 │     ▼
                 │  Log error
                 │  Call _generate_default_dashboard()
                 │  Return fallback template
                 │
                 └─ Return markdown
                    │
                    ▼
                 Return markdown in DashboardStructuredResponse
                    │
                    ▼
                 Return to client: {"markdown": "# ...", "status": "success"}
```

---

## Comparison: Old vs New

```
┌─────────────────────────────────────────────────────────┐
│                    OLD (Deprecated)                     │
└─────────────────────────────────────────────────────────┘

GET /dashboard/structured?company_slug=world-labs
        │
        ▼
File system: data/structured/world-labs.json
        │
        ▼
Load JSON (no processing)
        │
        ▼
Return StructuredDataResponse with raw JSON:
{
    "company_id": "world-labs",
    "data": {
        "company_record": {...},
        "events": [...],
        ...
    },
    "status": "success"
}
        │
        ▼
Streamlit: Display 6 tabs with JSON data
- Company Info tab
- Events tab
- Products tab
- Leadership tab
- Visibility tab
- Raw JSON tab


┌─────────────────────────────────────────────────────────┐
│                    NEW (Current)                        │
└─────────────────────────────────────────────────────────┘

POST /dashboard/structured?company_name=World%20Labs
        │
        ▼
Convert to slug: world-labs
        │
        ▼
File system: data/payloads/world-labs.json
        │
        ▼
Load JSON
        │
        ▼
Format to text context (600-800 lines)
        │
        ▼
Load system prompt (dashboard_system.md)
        │
        ▼
Call OpenAI LLM (gpt-4o)
        │
        ▼
Get markdown response
        │
        ▼
Return DashboardStructuredResponse with markdown:
{
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "markdown": "# World Labs - Investor Diligence Dashboard\n...",
    "status": "success",
    "message": "Generated successfully..."
}
        │
        ▼
Streamlit: Display single markdown panel
- # World Labs - Investor Diligence Dashboard
- ## Company Overview
- ## Business Model and GTM
- ## Funding & Investor Profile
- ## Growth Momentum
- ## Visibility & Market Sentiment
- ## Risks and Challenges
- ## Outlook
- ## Disclosure Gaps
```

---

For detailed implementation info, see documentation files.
