# Quick Reference: Structured Pipeline

## Files Overview

| File | Purpose | Type |
|------|---------|------|
| `src/structured/structured_pipeline.py` | Dashboard generation from JSON | NEW |
| `src/backend/rag_search_api.py` | FastAPI endpoints | MODIFIED |
| `src/frontend/streamlit_app.py` | Streamlit UI | MODIFIED |
| `src/prompts/dashboard_system.md` | LLM system prompt | SHARED |
| `data/payloads/{slug}.json` | Structured payload files | DATA |

---

## Quick Start

### 1. Verify Data
```bash
ls data/payloads/
# Should show: world-labs.json, anthropic.json, etc.
```

### 2. Start Backend
```bash
cd src/backend
python rag_search_api.py
```

### 3. Start Frontend
```bash
streamlit run src/frontend/streamlit_app.py
```

### 4. Test Endpoint
```bash
curl -X POST "http://localhost:8000/dashboard/structured?company_name=World%20Labs"
```

---

## API Reference

### POST /dashboard/structured

**Query Parameter**:
```
?company_name=World%20Labs
```

**Response** (200 OK):
```json
{
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "markdown": "# World Labs - Investor Diligence Dashboard\n...",
    "status": "success",
    "message": "Structured dashboard generated successfully for World Labs"
}
```

**Errors**:
- `404`: Payload file not found
- `500`: LLM generation failed (check OPENAI_API_KEY)

---

## Key Functions

### Entry Point
```python
generate_dashboard_from_payload(
    company_name: str,
    company_slug: str,
    llm_client = None,
    llm_model: str = "gpt-4o"
) -> str
```

**Workflow**:
1. Load `data/payloads/{company_slug}.json`
2. Format payload as text context
3. Call OpenAI LLM with prompt
4. Return markdown dashboard

### Helper Functions
```python
get_dashboard_system_prompt()          # Load prompt from MD file
format_payload_for_llm(payload)        # Convert JSON to context text
generate_dashboard_markdown(...)       # Call LLM to generate dashboard
_generate_default_dashboard(...)       # Fallback template
```

---

## Environment Setup

### .env File
```
OPENAI_API_KEY=sk-proj-xxxxx
QDRANT_URL=http://localhost:6333
OPENAI_API_BASE=https://api.openai.com/v1
```

### Loading .env
```python
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)
```

---

## Payload Structure Example

```json
{
    "company_record": {
        "company_name": "World Labs",
        "website": "https://worldlabs.ai",
        "founded": 2024,
        "hq": "San Francisco, CA"
    },
    "events": [
        {
            "event_type": "Press Release",
            "date": "Jan 2025",
            "description": "Series B funding announcement"
        }
    ],
    "products": [
        {
            "name": "Spatial Intelligence Platform",
            "description": "3D scene understanding"
        }
    ],
    "leadership": [
        {
            "name": "CEO Name",
            "title": "Chief Executive Officer",
            "bio": "Previously at OpenAI..."
        }
    ],
    "visibility": [
        {
            "source": "TechCrunch",
            "mention": "World Labs raises $230M..."
        }
    ],
    "snapshots": [
        {
            "metric": "Funding",
            "value": "$230M",
            "date": "Jan 2025"
        }
    ],
    "notes": "Additional context..."
}
```

---

## Expected Dashboard Sections

The LLM generates 8 required sections:

1. **Company Overview** - Basic company info
2. **Business Model and GTM** - Revenue model, market entry
3. **Funding & Investor Profile** - Funding rounds, investors
4. **Growth Momentum** - Recent metrics, expansion
5. **Visibility & Market Sentiment** - Press coverage, perception
6. **Risks and Challenges** - Competitive threats, operational risks
7. **Outlook** - Future prospects
8. **Disclosure Gaps** - Missing information

---

## Troubleshooting

### Issue: 404 Not Found
**Cause**: Payload file doesn't exist at `data/payloads/world-labs.json`
**Solution**: Run extraction pipeline to generate payload files

### Issue: 500 Error - "OPENAI_API_KEY not set"
**Cause**: Environment variable not loaded
**Solution**: 
```bash
# Check .env exists
ls -la .env

# Verify key is set
grep OPENAI_API_KEY .env

# Restart API server
python src/backend/rag_search_api.py
```

### Issue: Timeout waiting for response
**Cause**: LLM generation taking too long
**Solution**: 
- Increase timeout to 60 seconds
- Check OpenAI API status
- Check internet connection

### Issue: Empty dashboard with "Not disclosed"
**Cause**: Payload file exists but is empty or missing data
**Solution**:
- Verify payload file has data: `jq '.' data/payloads/world-labs.json`
- Re-run extraction pipeline

---

## Comparison: Structured vs RAG

### Structured Pipeline
- **Input**: JSON payload file
- **Processing**: Format to text + LLM generation
- **Speed**: ~5-10 seconds
- **Output**: Single markdown dashboard
- **Use Case**: When complete data is available

### RAG Pipeline
- **Input**: Vector database (Qdrant)
- **Processing**: Vector search + context formatting + LLM
- **Speed**: ~5-15 seconds
- **Output**: Markdown dashboard + 10 context chunks
- **Use Case**: When data is distributed/large

---

## Testing in Python

### Simple Test
```python
from src.structured.structured_pipeline import generate_dashboard_from_payload

dashboard = generate_dashboard_from_payload(
    company_name="World Labs",
    company_slug="world-labs"
)

print(dashboard[:500])  # Print first 500 chars
```

### With Error Handling
```python
import sys
sys.path.insert(0, 'src/structured')
from structured_pipeline import generate_dashboard_from_payload

try:
    dashboard = generate_dashboard_from_payload(
        company_name="World Labs",
        company_slug="world-labs"
    )
    print("✅ Dashboard generated successfully")
    print(f"Length: {len(dashboard)} characters")
except FileNotFoundError as e:
    print(f"❌ File not found: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
```

### Test with Mock Payload
```python
import json
from pathlib import Path
from src.structured.structured_pipeline import format_payload_for_llm

# Create minimal payload
payload = {
    "company_record": {"name": "Test Co"},
    "events": [],
    "products": [],
    "leadership": [],
    "visibility": [],
    "snapshots": [],
    "notes": ""
}

context = format_payload_for_llm(payload)
print(context)
```

---

## Debugging

### Enable Verbose Logging
```bash
VERBOSE=1 python src/backend/rag_search_api.py
```

### Check Log File
```bash
tail -f data/logs/rag_search_api.log
```

### Debug Payload Loading
```python
import json
from pathlib import Path

payload_path = Path("data/payloads/world-labs.json")
if payload_path.exists():
    with open(payload_path) as f:
        payload = json.load(f)
    print(f"✅ Payload loaded: {len(payload)} keys")
    print(f"   Keys: {list(payload.keys())}")
else:
    print(f"❌ File not found: {payload_path}")
```

---

## Performance Notes

- **Payload Loading**: < 100ms
- **Context Formatting**: 100-200ms (depends on data volume)
- **LLM Generation**: 5-10 seconds
- **Total Request Time**: 5-12 seconds

**Factors Affecting Speed**:
1. OpenAI API response time
2. Size of payload (more data = longer formatting)
3. Network latency
4. LLM model (gpt-4o vs gpt-4-turbo)

---

## Best Practices

1. **Always check `.env`**: Ensure OPENAI_API_KEY is set before starting API
2. **Use company_name, not slug**: The endpoint uses company name, slug is generated
3. **Increase timeouts**: LLM generation takes 5-10 seconds, not 5 seconds
4. **Check logs**: Always check `data/logs/rag_search_api.log` for errors
5. **Verify payload exists**: Before calling endpoint, verify `data/payloads/{slug}.json` exists
6. **Use try-catch**: Always wrap API calls in error handling for 404/500 responses

---

## File Locations

```
Project Root/
├── .env                           ← OPENAI_API_KEY here
├── src/
│   ├── structured/
│   │   └── structured_pipeline.py ← New module
│   ├── backend/
│   │   └── rag_search_api.py      ← Modified
│   ├── frontend/
│   │   └── streamlit_app.py       ← Modified
│   └── prompts/
│       └── dashboard_system.md    ← Shared prompt
├── data/
│   ├── payloads/                  ← Load from here
│   │   ├── world-labs.json
│   │   └── anthropic.json
│   └── logs/
│       └── rag_search_api.log     ← Check here
```

---

## API Documentation URLs

Once running:
- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health
- **Root**: http://localhost:8000/

---

## Related Modules

- **rag_pipeline.py**: Similar module using vector database
- **rag_search_api.py**: FastAPI backend with endpoints
- **streamlit_app.py**: Streamlit frontend UI
- **dashboard_system.md**: Shared LLM prompt

---

## Version Info

- **Python**: 3.11+
- **FastAPI**: Latest
- **Streamlit**: Latest
- **OpenAI**: Latest (with `gpt-4o` model available)
- **Qdrant**: v1.12+ (not used by structured pipeline)

---

## Next Steps

1. Verify payload files exist in `data/payloads/`
2. Start FastAPI backend
3. Start Streamlit frontend
4. Test "Generate (Structured)" button
5. Check generated markdown dashboard
6. Compare with RAG output (if available)

---

For detailed documentation, see:
- `STRUCTURED_PIPELINE_IMPLEMENTATION.md` - Full implementation details
- `API_ENDPOINT_CHANGES.md` - Endpoint changes (GET → POST)
- `STRUCTURED_PIPELINE_ARCHITECTURE.md` - Module architecture & functions
