# RAG Search API Backend

FastAPI backend service for querying the Qdrant vector database using RAG (Retrieval-Augmented Generation).

## Overview

The `/rag/search` endpoint enables semantic similarity search against your Qdrant vector database. It:

1. **Embeds queries** using OpenAI or HuggingFace embeddings
2. **Searches Qdrant** for semantically similar chunks
3. **Returns ranked results** with metadata

## Quick Start

### 1. Start the API

```bash
# Basic start (uses environment defaults)
python src/backend/rag_search_api.py

# With environment variables
QDRANT_URL=http://localhost:6333 \
EMBEDDING_PROVIDER=hf \
VERBOSE=1 \
python src/backend/rag_search_api.py
```

### 2. Access the API

- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Root Endpoint**: http://localhost:8000/

### 3. Test with cURL

```bash
# Basic search for "funding"
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "funding", "top_k": 5}'

# Search for "leadership" with threshold
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "leadership", "top_k": 5, "threshold": 0.5}'

# Health check
curl http://localhost:8000/health
```

### 4. Run Tests

```bash
python src/backend/test_rag_search.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `QDRANT_API_KEY` | `""` | Qdrant API key (if required) |
| `EMBEDDING_PROVIDER` | `auto-detect` | `"openai"` or `"hf"` (HuggingFace) |
| `EMBEDDING_MODEL` | (default per provider) | Model name (e.g., `text-embedding-3-small`) |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `VERBOSE` | `0` | Set to `1` for debug logging |
| `OPENAI_API_KEY` | (from .env) | OpenAI API key for embeddings |

## Endpoints

### `/health` (GET)

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "qdrant_url": "http://localhost:6333",
  "qdrant_connected": true
}
```

### `/rag/search` (POST)

Search the vector database for similar chunks.

**Request:**
```json
{
  "query": "funding and investment",
  "collection_name": "world_labs_chunks",
  "top_k": 5,
  "threshold": 0.0
}
```

**Response:**
```json
{
  "query": "funding and investment",
  "collection_name": "world_labs_chunks",
  "results": [
    {
      "id": 12345,
      "similarity_score": 0.8234,
      "text": "We've already made promising strides...",
      "metadata": {
        "chunk_id": "chunk_000005",
        "page_type": "about",
        "source_file": "data/raw/world_labs/about/text.txt",
        "company_slug": "world_labs",
        "keywords": ["funding", "investors", "venture capital"],
        "chunk_strategy": "Recursive"
      }
    }
  ],
  "total_results": 1,
  "provider": "openai",
  "model": "text-embedding-3-small"
}
```

## API Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query (min 1 character) |
| `collection_name` | string | No | `rag_chunks` | Qdrant collection name |
| `top_k` | integer | No | `5` | Number of results (1-100) |
| `threshold` | float | No | `null` | Similarity threshold (0-1). `null` = no threshold |

## Example Queries

### Checkpoint Queries (Required)

These should return relevant chunks:

```bash
# Funding-related query
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "funding", "top_k": 5}'

# Leadership-related query
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "leadership", "top_k": 5}'
```

### Other Examples

```bash
# Question format
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "what is spatial intelligence?", "top_k": 3}'

# Topic-based search
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "3D world generation", "top_k": 5}'

# Job opportunities
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "careers and job opportunities", "top_k": 5}'
```

## Embedding Providers

### OpenAI (Default if OPENAI_API_KEY set)

Uses OpenAI's embedding API.

**Model:** `text-embedding-3-small` (1536 dimensions)

**Pros:**
- High quality embeddings
- Optimized for semantic search
- Works out of the box with OPENAI_API_KEY

**Cons:**
- Requires API key
- Rate-limited
- Costs money per request

**Setup:**
```bash
export OPENAI_API_KEY="sk-..."
python src/backend/rag_search_api.py
```

### HuggingFace (Default fallback)

Uses local sentence-transformers model.

**Model:** `all-MiniLM-L6-v2` (384 dimensions)

**Pros:**
- Free, local inference
- No API calls or rate limits
- Privacy-friendly (no data sent to OpenAI)

**Cons:**
- Slightly lower quality than OpenAI
- Requires model download on first run (~100MB)
- Runs CPU-only (slower without GPU)

**Setup:**
```bash
EMBEDDING_PROVIDER=hf python src/backend/rag_search_api.py
```

## Testing

### Run Full Test Suite

```bash
python src/backend/test_rag_search.py
```

Tests include:
- Health check endpoint
- Checkpoint queries (funding, leadership)
- Multi-word queries
- Error handling

### Manual Testing with Python

```python
import requests

# Search for funding
response = requests.post(
    "http://localhost:8000/rag/search",
    json={"query": "funding", "top_k": 5}
)

result = response.json()
for chunk in result["results"]:
    print(f"Score: {chunk['similarity_score']:.4f}")
    print(f"Text: {chunk['text'][:200]}...")
    print(f"Metadata: {chunk['metadata']}")
    print("---")
```

## Architecture

```
Query (text)
    ↓
[Embedding Provider: OpenAI or HuggingFace]
    ↓
Query Vector (1536 or 384 dims)
    ↓
[Qdrant Vector Database]
    ↓
Similarity Search
    ↓
Top-K Results with Metadata
    ↓
Response (JSON)
```

## Performance

### Latency (Approximate)

| Provider | First Run | Subsequent |
|----------|-----------|-----------|
| OpenAI | ~300-500ms | ~300-500ms |
| HuggingFace | ~100-200ms | ~100-200ms |

### Throughput

- OpenAI: ~10 req/sec (rate-limited)
- HuggingFace: ~50-100 req/sec (depends on CPU)

## Troubleshooting

### "Connection refused" error

**Problem:** Cannot connect to API or Qdrant

**Solution:**
```bash
# Check if API is running
curl http://localhost:8000/health

# Check if Qdrant is running
curl http://localhost:6333/health

# Start Qdrant if needed
docker run -p 6333:6333 qdrant/qdrant:v1.12.0
```

### "No embedding provider available"

**Problem:** API startup fails with embedding provider error

**Solution:**
```bash
# Install sentence-transformers
pip install sentence-transformers

# Or set OpenAI API key
export OPENAI_API_KEY="sk-..."
```

### "Collection not found"

**Problem:** Search returns error about missing collection

**Solution:**
```bash
# Ingest chunks first
python src/rag/ingest_to_qdrant.py \
  --input-dir data/rag_experiments \
  --collection world_labs_chunks
```

### Slow queries

**Problem:** Searches take >5 seconds

**Solution:**
- Use OpenAI embeddings (faster, API-cached)
- Use GPU if available (HuggingFace with CUDA)
- Reduce `top_k` parameter
- Increase batch size in ingestion

## Integration with RAG Pipeline

The search API integrates with your complete RAG pipeline:

```
1. Web Scraping (discover/)
   ↓
2. Text Extraction (src/scraper.py)
   ↓
3. Text Chunking (experimental_framework.py)
   ↓
4. Embedding & Indexing (ingest_to_qdrant.py)
   ↓
5. Vector Search (rag_search_api.py) ← You are here
   ↓
6. LLM Augmentation (future: structured_pipeline.py)
```

## Next Steps

- [ ] Integrate search results with LLM for answer generation
- [ ] Add filtering by metadata (company, page_type, keywords)
- [ ] Implement hybrid search (vector + keyword)
- [ ] Add result re-ranking with LLM
- [ ] Implement caching layer
- [ ] Add query logging and analytics
