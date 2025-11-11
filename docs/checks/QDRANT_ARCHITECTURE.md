# Architecture Diagram: Qdrant-Enhanced RAG Pipeline

## System Architecture (Bird's Eye View)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         RAG EXTRACTION SYSTEM                         │
└──────────────────────────────────────────────────────────────────────┘

┌─ LAYER 1: INPUT ─────────────────────────────────────────────────────┐
│                                                                       │
│  Web Pages (downloaded by process_discovered_pages.py)              │
│  ├─ data/raw/world_labs/about/text.txt                            │
│  ├─ data/raw/world_labs/product/text.txt                          │
│  ├─ data/raw/world_labs/careers/text.txt                          │
│  ├─ data/raw/world_labs/blog/text.txt                             │
│  ├─ data/raw/world_labs/linkedin/text.txt                         │
│  └─ (Total: ~50KB raw text per company)                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LAYER 2: PROCESSING ────────────────────────────────────────────────┐
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Text Processing Pipeline                                   │    │
│  │                                                             │    │
│  │  1. Load Raw Text                                          │    │
│  │     raw_text = read(data/raw/world_labs/*/text.txt)       │    │
│  │                                                             │    │
│  │  2. Split into Chunks                                      │    │
│  │     chunks = RecursiveCharacterTextSplitter(               │    │
│  │       chunk_size=500,                                      │    │
│  │       chunk_overlap=100                                    │    │
│  │     ).split_text(raw_text)                                 │    │
│  │     → Result: ~40-50 chunks per company                   │    │
│  │                                                             │    │
│  │  3. Generate Embeddings                                    │    │
│  │     for chunk in chunks:                                   │    │
│  │       embedding = OpenAIEmbeddings.embed_query(chunk)      │    │
│  │       → 1536-dimensional vector                            │    │
│  │                                                             │    │
│  │  4. Create Qdrant Points                                   │    │
│  │     point = PointStruct(                                   │    │
│  │       id=chunk_id,                                         │    │
│  │       vector=embedding,                                    │    │
│  │       payload={text, page_type, company_slug}             │    │
│  │     )                                                       │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LAYER 3: VECTOR DATABASE ───────────────────────────────────────────┐
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ QDRANT VECTOR DATABASE                                        │  │
│  │                                                               │  │
│  │ Collection: company_world_labs                               │  │
│  │ ├─ Vector Space: 1536-dimensional (text-embedding-3-small)  │  │
│  │ ├─ Distance Metric: COSINE SIMILARITY                       │  │
│  │ │                                                             │  │
│  │ └─ Points (43 total):                                        │  │
│  │    ID  │ Vector (1536-dim) │ Payload                         │  │
│  │    ────┼──────────────────┼──────────────────────────────── │  │
│  │    1   │ [0.23, 0.45...] │ text: "founded in 2023..."      │  │
│  │    2   │ [0.12, 0.67...] │ text: "Series A $12M...", page  │  │
│  │    3   │ [0.89, 0.34...] │ text: "CEO is John Doe..." │     │  │
│  │    ... │ ...             │ ...                         │     │  │
│  │    43  │ [0.56, 0.78...] │ text: "5000 GitHub stars..."     │  │
│  │                                                               │  │
│  │ Index: COSINE (for semantic similarity)                      │  │
│  │ Storage: On-disk with in-memory cache                        │  │
│  │                                                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LAYER 4: SEMANTIC SEARCH ───────────────────────────────────────────┐
│                                                                       │
│  For each extraction type (Company, Events, Snapshots, etc.):      │
│                                                                       │
│  ┌─ Extract Events (example) ─────────────────────────────────┐    │
│  │                                                             │    │
│  │  Search Queries (6 queries):                              │    │
│  │  ├─ Q1: "funding rounds Series A B C seed investment"    │    │
│  │  ├─ Q2: "M&A acquisition merger merger company"          │    │
│  │  ├─ Q3: "product launch release announcement"            │    │
│  │  ├─ Q4: "partnership partnership collaboration"          │    │
│  │  ├─ Q5: "hiring jobs positions team expansion"           │    │
│  │  └─ Q6: "milestones achievements awards"                 │    │
│  │                                                             │    │
│  │  For each query:                                           │    │
│  │  ├─ Generate query embedding (1536-dim)                   │    │
│  │  │  embedding = OpenAI.embed_query("funding rounds...")   │    │
│  │  │                                                         │    │
│  │  ├─ Search Qdrant (COSINE similarity)                     │    │
│  │  │  results = qdrant.search(                              │    │
│  │  │    collection="company_world_labs",                    │    │
│  │  │    query_vector=embedding,                            │    │
│  │  │    limit=2  # Top 2 similar chunks per query           │    │
│  │  │  )                                                     │    │
│  │  │                                                         │    │
│  │  └─ Retrieve Top-K (k=2):                                │    │
│  │     Result 1: ID=2, Score=0.89                            │    │
│  │       text: "Series A funding round of $12M from Sequoia" │    │
│  │       page_type: "blog"                                   │    │
│  │       ← HIGHEST RELEVANCE                                 │    │
│  │                                                             │    │
│  │     Result 2: ID=8, Score=0.87                            │    │
│  │       text: "Raised Series A in Nov 2023"                 │    │
│  │       page_type: "about"                                  │    │
│  │                                                             │    │
│  │  Aggregate all queries:                                    │    │
│  │  Total retrieved: ~12 documents (6 queries × 2 results)   │    │
│  │  (May have duplicates, removed by dedup)                  │    │
│  │  Final context: ~2000 chars of high-relevance text        │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LAYER 5: LLM EXTRACTION ────────────────────────────────────────────┐
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ GPT-4 Turbo (with Instructor + Pydantic)                  │    │
│  │                                                             │    │
│  │ INPUT PROMPT:                                              │    │
│  │ "Extract events for company_world_labs from:              │    │
│  │                                                             │    │
│  │  [blog] Series A funding round of $12M from Sequoia...    │    │
│  │  [about] Raised Series A in Nov 2023...                   │    │
│  │  [careers] Hiring 50 engineers and 20 sales reps...       │    │
│  │  ...                                                        │    │
│  │                                                             │    │
│  │  Return Event objects with:                                │    │
│  │  - event_type: Literal[funding|mna|partnership|...]       │    │
│  │  - occurred_on: date (YYYY-MM-DD)                         │    │
│  │  - amount_usd: Optional[float]                            │    │
│  │  - title, description, actors, tags                        │    │
│  │  Use only explicit information. No inference."             │    │
│  │                                                             │    │
│  │ RESPONSE MODEL:                                            │    │
│  │ class EventList(BaseModel):                                │    │
│  │     events: List[Event]                                    │    │
│  │                                                             │    │
│  │ OUTPUT:                                                     │    │
│  │ {                                                           │    │
│  │   "events": [                                              │    │
│  │     {                                                       │    │
│  │       "event_id": "world-labs-funding-series-a",          │    │
│  │       "occurred_on": "2023-11-20",                        │    │
│  │       "event_type": "funding",                            │    │
│  │       "amount_usd": 12000000,                             │    │
│  │       ...                                                  │    │
│  │     },                                                      │    │
│  │     {...}  ← More events extracted                         │    │
│  │   ]                                                        │    │
│  │ }                                                           │    │
│  │                                                             │    │
│  │ AUTOMATIC VALIDATION:                                      │    │
│  │ ✓ Field types checked                                     │    │
│  │ ✓ Date format validated                                   │    │
│  │ ✓ Enum values validated (event_type)                      │    │
│  │ ✓ Required fields present                                 │    │
│  │ ✓ Returns Python Event objects (not strings)              │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Repeat for each extraction type:                                   │
│  ├─ extract_company_info() → Company                                │
│  ├─ extract_events() → List[Event]                                 │
│  ├─ extract_snapshots() → List[Snapshot]                           │
│  ├─ extract_products() → List[Product]                             │
│  ├─ extract_leadership() → List[Leadership]                        │
│  └─ extract_visibility() → Visibility                              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LAYER 6: PAYLOAD ASSEMBLY ──────────────────────────────────────────┐
│                                                                       │
│  Combine all extractions into single Payload:                       │
│                                                                       │
│  payload = Payload(                                                │
│    company_record=Company(...),                                    │
│    events=[Event(...), Event(...), ...],                          │
│    snapshots=[Snapshot(...), ...],                                │
│    products=[Product(...), ...],                                  │
│    leadership=[Leadership(...), ...],                             │
│    visibility=[Visibility(...)],                                  │
│    notes="Extracted with semantic search via Qdrant on ..."       │
│  )                                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ LAYER 7: OUTPUT & PERSISTENCE ──────────────────────────────────────┐
│                                                                       │
│  Save to: data/structured/world-labs.json                           │
│                                                                       │
│  {                                                                   │
│    "company_record": {                                              │
│      "company_id": "world-labs",                                    │
│      "legal_name": "World Labs Inc.",                               │
│      "founded_year": 2023,                                          │
│      "total_raised_usd": 25000000,                                  │
│      ...                                                            │
│    },                                                               │
│    "events": [                                                      │
│      {                                                              │
│        "event_id": "world-labs-funding-series-a",                 │
│        "occurred_on": "2023-11-20",                               │
│        "event_type": "funding",                                   │
│        "amount_usd": 12000000,                                    │
│        ...                                                          │
│      },                                                             │
│      ...                                                            │
│    ],                                                               │
│    "snapshots": [...],                                             │
│    "products": [...],                                              │
│    "leadership": [...],                                            │
│    "visibility": [...],                                            │
│    "notes": "Extracted with semantic search via Qdrant on ..."     │
│  }                                                                   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Request-Response Flow (Single Extraction)

```
User Input: python structured_extraction.py --company-slug world_labs
                    │
                    ↓
        ┌─────────────────────────┐
        │ Load Company Pages      │
        │ (from data/raw/)        │
        └──────────┬──────────────┘
                   │
                   ↓
        ┌─────────────────────────┐
        │ Initialize Qdrant       │
        │ Initialize Embeddings   │
        └──────────┬──────────────┘
                   │
                   ↓
        ┌──────────────────────────────┐
        │ Index to Qdrant              │
        │ (Split, Embed, Upsert)       │
        │ company_world_labs created   │
        └──────────┬───────────────────┘
                   │
        ┌──────────┴──────────────────────┐
        │                                  │
        ↓                                  ↓
Extract Company Info              Extract Events
├─ Search Qdrant (4 queries)      ├─ Search Qdrant (6 queries)
├─ Get ~12 results                ├─ Get ~12 results
├─ Build prompt                   ├─ Build prompt
├─ Call GPT-4 (with Instructor)   ├─ Call GPT-4 (with Instructor)
└─ Validate → Company             └─ Validate → List[Event]
        │                                  │
        │          ┌──────────────┬────────┘
        │          │              │
        ↓          ↓              ↓
    Extract        Extract       Extract
    Snapshots      Products      Leadership
        │          │              │
        └──────────┼──────────────┤
                   │              │
                   ↓              ↓
              Extract Visibility
                   │
                   ↓
        ┌──────────────────────────┐
        │ Combine into Payload     │
        │ (Company + 5 Lists)      │
        └──────────┬───────────────┘
                   │
                   ↓
        ┌──────────────────────────┐
        │ Save JSON                │
        │ data/structured/         │
        │ world-labs.json          │
        └──────────┬───────────────┘
                   │
                   ↓
        ✓ Complete (30-50 seconds)
```

## Data Volume & Cost Analysis

```
┌────────────────────────────────────────────────────────────┐
│ INPUT VOLUME                                               │
├────────────────────────────────────────────────────────────┤
│ Raw text per company: ~50KB                                │
│ Tokens in raw text: ~12,500 (50KB × 0.25)                │
│ Pages per company: 5 (about, product, careers, blog, linkedin)
│ Characters per page: ~10KB average                        │
└────────────────────────────────────────────────────────────┘
                        │
                        ↓ [Chunk & Embed]
┌────────────────────────────────────────────────────────────┐
│ QDRANT VECTORS                                             │
├────────────────────────────────────────────────────────────┤
│ Chunks per company: ~40-50                                 │
│ Embedding dimension: 1536                                  │
│ Storage per chunk: ~6KB (1536 floats + metadata)          │
│ Total Qdrant storage: ~250KB per company                   │
│ Tokens used: ~2,000 (for embeddings)                      │
│ Cost: ~$0.03 per company (at $0.015/1M tokens)           │
└────────────────────────────────────────────────────────────┘
                        │
                        ↓ [Search & Extract]
┌────────────────────────────────────────────────────────────┐
│ LLM OPERATIONS (GPT-4 Turbo)                              │
├────────────────────────────────────────────────────────────┤
│ Prompt tokens (per extraction):                            │
│   - Guidelines: ~500 tokens                                │
│   - Search results (~2000 chars): ~500 tokens             │
│   - Schema: ~200 tokens                                    │
│   = ~1200 tokens per extraction                            │
│                                                             │
│ Completion tokens (per extraction):                        │
│   - Structured output: ~300 tokens average                 │
│                                                             │
│ Total per company (6 extractions):                         │
│   - Prompt: 1200 × 6 = 7200 tokens                        │
│   - Completion: 300 × 6 = 1800 tokens                     │
│   - TOTAL: ~9000 tokens                                   │
│                                                             │
│ Cost: ~$0.09 per company                                   │
│   ($0.01/1K input + $0.03/1K output)                      │
└────────────────────────────────────────────────────────────┘
                        │
                        ↓ [Save Output]
┌────────────────────────────────────────────────────────────┐
│ OUTPUT STORAGE                                             │
├────────────────────────────────────────────────────────────┤
│ JSON file per company: ~200-500KB                         │
│ Estimated final database (100 companies):                 │
│   - Qdrant collections: ~25MB                              │
│   - JSON outputs: ~40MB                                    │
│   - Logs: ~10MB                                            │
│   = ~75MB total                                            │
└────────────────────────────────────────────────────────────┘

COST SUMMARY (per company):
├─ Embeddings: $0.03
├─ LLM Extraction: $0.09
└─ TOTAL: ~$0.12 per company

BATCH COST (100 companies):
├─ Total: ~$12
└─ All operational (no GPU/compute costs, pay-per-use)
```

## Performance Characteristics

```
Timeline (Single Company):
┌─ Load Raw Text: <1s
├─ Initialize Qdrant: 1-2s
├─ Text Splitting: 1s
├─ Generate Embeddings: 8-12s (depends on chunk count)
├─ Index to Qdrant: 2-3s
├─ Extract Company Info: 3-5s (LLM call)
├─ Extract Events: 3-5s (LLM call)
├─ Extract Snapshots: 3-5s (LLM call)
├─ Extract Products: 3-5s (LLM call)
├─ Extract Leadership: 3-5s (LLM call)
├─ Extract Visibility: 3-5s (LLM call)
└─ Save Output: <1s
  ────────────────────
  TOTAL: 30-50 seconds per company
  (with 6 sequential LLM calls)

Parallelization Opportunity:
├─ 6 extraction types could run in parallel
├─ Potential speedup: ~6x
├─ Parallel time: 5-10 seconds per company
└─ (limited by OpenAI API rate limits in practice)

Memory Usage:
├─ Python process: ~500MB-1GB
├─ Qdrant (in-memory index): ~50MB per collection
├─ OpenAI/Langchain buffers: ~200MB
└─ Total: ~1.5-2GB per process

Scalability:
├─ Single machine: ~100-200 companies/hour
├─ Distributed (10 machines): ~1000-2000 companies/hour
└─ Cost-effective up to ~10k companies
```

---

**Architecture Version**: 2.0 (with Qdrant)  
**Last Updated**: 2025-11-05  
**Status**: Production Ready
