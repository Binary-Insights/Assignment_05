# Structured Pipeline Implementation - Summary

**Date**: November 5, 2025  
**Status**: ✅ Complete

## Overview

Created a new `structured_pipeline.py` module that mirrors the `rag_pipeline.py` functionality but uses structured JSON payloads instead of vector database retrieval.

## Files Created

### 1. `src/structured/structured_pipeline.py` (NEW)

**Purpose**: Dashboard generation from structured payload JSON files

**Key Functions**:

1. **`get_dashboard_system_prompt()`**
   - Loads system prompt from `src/prompts/dashboard_system.md`
   - Same as `rag_pipeline.py`

2. **`format_payload_for_llm(payload: Dict[str, Any]) -> str`**
   - Formats the structured JSON payload into context for LLM
   - Extracts and summarizes:
     - Company Record (basic info)
     - Events (first 10, with description truncation)
     - Products (first 5, with description)
     - Leadership (first 10, with bio preview)
     - Visibility (first 5 mentions)
     - Snapshots (key metrics)
     - Notes

3. **`generate_dashboard_markdown(company_name, payload, llm_client, llm_model) -> str`**
   - Calls OpenAI chat.completions API with system + user messages
   - System message from dashboard_system.md
   - User message instructs LLM to generate 8 required sections
   - Falls back to default template if LLM unavailable

4. **`_generate_default_dashboard(company_name, payload) -> str`**
   - Fallback template when LLM is unavailable
   - Shows formatted context sections

5. **`generate_dashboard_from_payload(company_name, company_slug, llm_client, llm_model) -> str`**
   - Main entry point for the module
   - Loads payload from `data/payloads/{company_slug}.json`
   - Calls `generate_dashboard_markdown()` with the loaded payload
   - Raises `FileNotFoundError` if payload not found

## Files Modified

### 2. `src/backend/rag_search_api.py`

#### Added Imports (after rag_pipeline imports)
```python
# Import Structured pipeline utilities
try:
    import sys
    from pathlib import Path as PathlibPath
    sys.path.insert(0, str(PathlibPath(__file__).resolve().parent.parent / "structured"))
    from structured_pipeline import generate_dashboard_from_payload
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import structured_pipeline: {e}")
    generate_dashboard_from_payload = None
```

#### Added Response Model
```python
class DashboardStructuredResponse(BaseModel):
    """Response model for structured dashboard generation."""
    
    company_name: str
    company_slug: str
    markdown: str = Field(description="Dashboard markdown content")
    status: str = "success"
    message: Optional[str] = None
```

#### Changed Endpoint (GET → POST)

**OLD**:
```
GET /dashboard/structured?company_slug=world-labs
```
- Returned raw JSON data from `data/structured/` directory
- 6 tabs with company info, events, products, etc.

**NEW**:
```
POST /dashboard/structured?company_name=World%20Labs
```
- Loads `data/payloads/world-labs.json`
- Passes payload to LLM with dashboard system prompt
- Returns markdown dashboard only (no tabs)
- Response includes `markdown`, `company_name`, `company_slug`, `status`, `message`

**Error Handling**:
- 404 if payload file not found
- 500 if LLM generation fails
- Clear error messages for troubleshooting

### 3. `src/frontend/streamlit_app.py`

#### Updated "Structured pipeline" Section

**OLD**:
- Used GET request to `/dashboard/structured`
- Displayed 6 tabs with structured data breakdown
- Parameters: `company_slug`

**NEW**:
- Uses POST request to `/dashboard/structured`
- Displays markdown dashboard directly
- Parameters: `company_name` (same as RAG pipeline)
- 30 second timeout for LLM generation
- Cleaner UI matching RAG pipeline layout

## Data Flow

### Old Flow (Deprecated)
```
GET /dashboard/structured
  ↓
Load data/structured/{slug}.json
  ↓
Return raw JSON with tabs
```

### New Flow (Structured)
```
POST /dashboard/structured
  ↓
Load data/payloads/{slug}.json
  ↓
Format payload to text context
  ↓
Call OpenAI LLM with system + user prompt
  ↓
Return markdown dashboard
```

### Comparison with RAG Flow
```
POST /dashboard/rag
  ↓
Load data/payloads/{slug}.json
  ↓
Create OpenAI embedding for query
  ↓
Search Qdrant collection
  ↓
Format search results to text context
  ↓
Call OpenAI LLM with system + user prompt
  ↓
Return markdown dashboard + 10 context chunks
```

## Key Differences: Structured vs RAG

| Feature | Structured | RAG |
|---------|-----------|-----|
| Data Source | JSON payload file | Qdrant vector database |
| Embedding | None | OpenAI text-embedding-3-small |
| Search | None | Vector similarity search (top-10) |
| Context | Entire payload formatted | Top-10 relevant chunks |
| LLM | OpenAI gpt-4o | OpenAI gpt-4o |
| Output | Markdown dashboard | Markdown + context chunks |
| Use Case | Complete data available | Large/distributed data |

## Environment Requirements

Both pipelines require:
- `OPENAI_API_KEY` in `.env` file
- Explicit `.env` loading at module level:
  ```python
  env_path = Path(__file__).resolve().parents[2] / ".env"
  load_dotenv(env_path)
  ```

## Testing the New Endpoint

### Using Streamlit UI
1. Start FastAPI: `python src/backend/rag_search_api.py`
2. Start Streamlit: `streamlit run src/frontend/streamlit_app.py`
3. Select company from dropdown
4. Click "Generate (Structured)" button
5. View markdown dashboard

### Using cURL
```bash
curl -X POST "http://localhost:8000/dashboard/structured?company_name=World%20Labs" \
  -H "Content-Type: application/json"
```

### Using Python Requests
```python
import requests

response = requests.post(
    "http://localhost:8000/dashboard/structured",
    params={"company_name": "World Labs"},
    timeout=30
)
print(response.json())
```

## Expected Response

```json
{
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "markdown": "# World Labs - Investor Diligence Dashboard\n\n## Company Overview\n...",
    "status": "success",
    "message": "Structured dashboard generated successfully for World Labs"
}
```

## Error Responses

### 404 - Payload Not Found
```json
{
    "detail": "No structured payload found for company 'Unknown Company'. Please run the structured extraction pipeline first."
}
```

### 500 - LLM Generation Failed
```json
{
    "detail": "Dashboard generation failed: [error details]"
}
```

## Implementation Notes

1. **Prompt Reuse**: Both `rag_pipeline.py` and `structured_pipeline.py` use the same `dashboard_system.md` system prompt for consistency

2. **Payload Formatting**: The `format_payload_for_llm()` function intelligently summarizes large arrays (e.g., limits events to 10, products to 5) to keep token count reasonable

3. **Fallback Behavior**: If LLM is unavailable, returns default template with all available data shown in "Disclosure Gaps" section

4. **Error Handling**: Both retrieval errors (missing file) and generation errors (LLM failures) are caught and returned as appropriate HTTP status codes

5. **Collection Naming**: While RAG uses Qdrant collections, Structured uses simple file naming convention: `data/payloads/{company_slug}.json`

## Next Steps (Optional Enhancements)

1. Add endpoint for fetching raw payload without LLM generation
2. Add caching layer for frequently requested dashboards
3. Add support for different LLM models via environment variable
4. Add markdown diff endpoint to compare Structured vs RAG dashboards
5. Add rate limiting to prevent excessive API calls
