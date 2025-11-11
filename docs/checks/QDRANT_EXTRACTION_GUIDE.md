# Qdrant-Enhanced Structured Extraction Guide

## Overview

The `structured_extraction.py` script has been upgraded to use **Qdrant vector database for semantic search** before LLM-based extraction. This approach:

1. **Indexes** all company web pages into Qdrant using OpenAI embeddings
2. **Searches** Qdrant semantically to find relevant context for each extraction type
3. **Passes** only relevant documents to the LLM (instead of all raw text)
4. **Extracts** structured Pydantic models using instructor + OpenAI
5. **Saves** results to `data/structured/{company_id}.json`

## Architecture

### Data Flow

```
Raw Text Files (data/raw/{company_slug}/{page_type}/text.txt)
        ↓
[RecursiveCharacterTextSplitter] - Split into 500-char chunks with 100-char overlap
        ↓
[OpenAI Embeddings] - Generate vector embeddings for each chunk
        ↓
[Qdrant Collection] - Store vectors + metadata (text, page_type, company_slug)
        ↓
[Semantic Search] - Query-specific retrieval (e.g., "funding rounds Series A B C")
        ↓
[Top-K Results] - Extract most relevant documents (~10-15 per extraction type)
        ↓
[LLM Prompt Construction] - Build focused prompt with search results
        ↓
[Instructor + GPT-4] - Extract structured data into Pydantic models
        ↓
[JSON Output] - Save to data/structured/{company_id}.json
```

### Key Components

#### 1. **Qdrant Client Initialization** (`get_qdrant_client()`)
- Connects to local or remote Qdrant server
- Default: `http://localhost:6333`
- Optional API key support via `QDRANT_API_KEY` env var
- Gracefully degrades if Qdrant unavailable (falls back to raw text)

#### 2. **Embeddings** (`get_embeddings_model()`)
- Uses OpenAI `text-embedding-3-small` model
- 1536-dimensional vectors
- Requires `OPENAI_API_KEY`

#### 3. **Indexing** (`index_company_pages_to_qdrant()`)
- Creates collection per company: `company_{company_slug}`
- Splits text with `RecursiveCharacterTextSplitter`:
  - Chunk size: 500 characters
  - Overlap: 100 characters (for context preservation)
- Generates embeddings and stores in Qdrant
- Payload per point: `{text, page_type, company_slug}`

#### 4. **Semantic Search** (`search_qdrant_for_context()`)
- Takes free-form query: "funding rounds Series A B C"
- Generates query embedding
- Finds top-K similar vectors (default K=5)
- Returns text + metadata + similarity score

#### 5. **Extraction Functions** (All Updated)
Each function now:
1. Builds targeted search queries (3-5 semantic queries per extraction type)
2. Calls `search_qdrant_for_context()` for each query
3. Combines results into a single `context_text`
4. Passes context to LLM instead of raw text
5. Extracts using instructor-patched OpenAI client

### Search Queries by Extraction Type

#### Company Info
```python
"company {name} legal name brand headquarters location founded"
"{name} website URL domain"
"{name} categories industry vertical"
"{name} funding raised valuation investment round"
```

#### Events
```python
"funding rounds Series A B C seed investment capital raised"
"M&A acquisition merger merger company"
"product launch release announcement"
"partnership partnership collaboration integration"
"hiring jobs positions team expansion layoffs"
"milestones achievements awards recognition"
```

#### Snapshots (Business Metrics)
```python
"headcount employees team size headcount growth hiring"
"pricing tiers pricing model pricing plans subscription"
"products features product offerings services"
"geographic presence countries regions locations"
"job openings hiring positions vacancies"
```

#### Products
```python
"product name product description features"
"pricing model pricing tiers pricing plans cost"
"integrations partners integrations APIs"
"GitHub repository source code open source"
"customers clients reference accounts"
```

#### Leadership
```python
"founder co-founder CEO CTO CPO founder"
"executive team leadership management"
"CEO founder name role"
"LinkedIn profile background education"
"previous company employment history"
```

#### Visibility
```python
"news mentions press coverage media articles"
"GitHub stars repository rating metrics"
"Glassdoor rating employee reviews"
"awards recognition industry recognition"
"social media followers engagement"
```

## Installation & Setup

### 1. Ensure Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `qdrant-client==1.15.1`
- `langchain`
- `langchain-openai`
- `openai`
- `instructor`
- `pydantic`
- `python-dotenv`

### 2. Start Qdrant Server (Local)
```bash
# Using Docker
docker run -p 6333:6333 qdrant/qdrant:latest

# Or use Docker Compose from docker/docker-compose.yml
docker-compose -f docker/docker-compose.yml up qdrant
```

### 3. Set Environment Variables
```bash
# .env file
OPENAI_API_KEY=sk-...
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional, only if using cloud Qdrant
```

### 4. Prepare Data
Run data collection pipeline first:
```bash
python src/discover/process_discovered_pages.py
```

This creates:
- `data/raw/{company_slug}/{page_type}/text.txt` (extracted text)
- `data/raw/{company_slug}/{page_type}/links_extracted.json`
- `data/raw/{company_slug}/{page_type}/{page_type}.html`

## Usage

### Extract Single Company
```bash
python src/rag/structured_extraction.py --company-slug world_labs
```

Output:
```
2025-11-05 00:25:14 - structured_extraction - INFO - Processing Company: World Labs (world_labs)
2025-11-05 00:25:14 - structured_extraction - INFO - Initializing Qdrant vector database...
2025-11-05 00:25:14 - structured_extraction - INFO - Connected to Qdrant at http://localhost:6333
2025-11-05 00:25:15 - structured_extraction - INFO - Indexed 42 chunks to Qdrant collection company_world_labs
2025-11-05 00:25:15 - structured_extraction - INFO - Starting structured extraction with semantic search...
2025-11-05 00:25:20 - structured_extraction - INFO - Company ID: world-labs
2025-11-05 00:25:45 - structured_extraction - INFO - ✓ Saved structured data to: data/structured/world-labs.json
```

### Extract All Companies
```bash
python src/rag/structured_extraction.py
```

### Verbose Output
```bash
python src/rag/structured_extraction.py --company-slug world_labs --verbose
```

## Output Format

File: `data/structured/{company_id}.json`

```json
{
  "company_record": {
    "company_id": "world-labs",
    "legal_name": "World Labs Inc.",
    "brand_name": "World Labs",
    "website": "https://worldlabs.ai",
    "hq_city": "San Francisco",
    "hq_state": "CA",
    "hq_country": "USA",
    "founded_year": 2023,
    "categories": ["AI", "Computer Vision", "Robotics"],
    "total_raised_usd": 25000000,
    "last_round_name": "Series B",
    "last_round_date": "2024-09-15",
    ...
  },
  "events": [
    {
      "event_id": "world-labs-funding-series-a",
      "company_id": "world-labs",
      "occurred_on": "2023-11-20",
      "event_type": "funding",
      "title": "Series A Funding Round",
      "amount_usd": 12000000,
      "investors": ["Sequoia Capital", "a16z"],
      ...
    }
  ],
  "snapshots": [...],
  "products": [...],
  "leadership": [...],
  "visibility": [...],
  "notes": "Extracted with semantic search via Qdrant on 2025-11-05T00:25:45.123456"
}
```

## Benefits of Qdrant Integration

### 1. **Reduced Token Usage**
- **Before**: 3000-4000 chars of raw text per extraction → ~750-1000 tokens
- **After**: ~10-15 relevant chunks (~2000 chars) → ~500 tokens
- **Savings**: 30-50% fewer tokens per company

### 2. **Better Extraction Quality**
- LLM receives focused, relevant context
- Reduces hallucination/inference
- Improves accuracy for specific fields
- Handles noise in raw HTML better

### 3. **Semantic Search**
- "funding rounds" query finds relevant sections regardless of exact wording
- Handles synonyms: "capital raise" = "Series A" = "investment"
- Context-aware retrieval

### 4. **Graceful Degradation**
- If Qdrant unavailable, automatically falls back to raw text
- No blocking failures
- Logs warnings for monitoring

### 5. **Reusable**
- Indexed Qdrant collections can be queried later
- Enables interactive search API
- Foundation for downstream dashboards

## Configuration

### Search Result Limits
Adjust per-extraction-type in each function:

```python
def extract_company_info(...):
    search_queries = [...]  # 4 queries
    for query in search_queries:
        docs = search_qdrant_for_context(query, ..., limit=3)  # 3 results per query
    # Total: ~12 documents
```

### Text Splitting
In `index_company_pages_to_qdrant()`:
```python
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,        # Adjust chunk size
    chunk_overlap=100,     # Adjust overlap
)
```

### Temperature
All LLM calls use `temperature=0.3` for consistency:
```python
client.create(
    model="gpt-4-turbo-preview",
    response_model=Company,
    messages=[...],
    temperature=0.3,  # Change if needed
)
```

## Troubleshooting

### Error: "Connection refused" to Qdrant
```bash
# Start Qdrant server
docker run -p 6333:6333 qdrant/qdrant:latest

# Verify connection
curl http://localhost:6333/health
```

### Error: "OPENAI_API_KEY not set"
```bash
# Set in .env or environment
export OPENAI_API_KEY=sk-...
```

### Slow Embedding Generation
- Embeddings are generated per-chunk during indexing
- First run slower (~1-2 min per company with 40-50 chunks)
- Subsequent runs retrieve from Qdrant (much faster)
- Consider batching embeddings if doing bulk processing

### "No page texts found"
```bash
# Ensure process_discovered_pages.py ran successfully
python src/discover/process_discovered_pages.py --company-slug world_labs
ls -la data/raw/world_labs/*/text.txt
```

### Empty Extraction Results
- Check Qdrant indexing: "Indexed N chunks"
- Verify search results: Add `--verbose` flag
- Check LLM context: Are search queries finding documents?
- Try increasing `limit` parameter in `search_qdrant_for_context()`

## Performance Metrics

### Cost
- Embeddings: ~$0.02 per million tokens (text-embedding-3-small)
- LLM extraction: ~$0.10-0.15 per company (gpt-4-turbo-preview)
- **Total: ~$0.12-0.17 per company**

### Time (per company)
- Text loading: <1s
- Qdrant indexing: 10-30s (depending on chunk count)
- Semantic searches: 2-3s (6 extraction types × 3-5 queries)
- LLM extraction: 15-20s (sequential calls)
- **Total: 30-60s per company**

### Storage
- Qdrant vectors: ~50KB per company (1536-dim vectors, 40-50 chunks)
- Structured JSON output: ~100-500KB per company
- **Total per company: ~500KB-1MB**

## Next Steps

1. **Monitor Quality**
   - Review extracted data in `data/structured/`
   - Compare against raw text in `data/raw/`
   - Adjust search queries if needed

2. **API Integration**
   - Build FastAPI endpoint on structured output
   - Implement search over extracted fields
   - Create dashboards with extracted metrics

3. **Batch Processing**
   - Process all companies: `python structured_extraction.py`
   - Monitor logs for failures
   - Re-run failed companies

4. **Optimization**
   - Fine-tune search queries for better results
   - Experiment with different embedding models
   - Consider batching embeddings for speed

## See Also

- `rag_models.py` - Pydantic model definitions
- `data/logs/structured_extraction.log` - Execution logs
- `data/structured/*.json` - Extracted outputs
- Qdrant docs: https://qdrant.tech/documentation/
