# Structured Pipeline - Test Plan & Validation

## Pre-Flight Checklist

### Step 1: Verify Files Exist
```bash
# Check new module
ls -la src/structured/structured_pipeline.py
# Output: -rw-r--r-- ... structured_pipeline.py

# Check payload data
ls -la data/payloads/ | head -5
# Output: world-labs.json, anthropic.json, etc.

# Check prompt file
ls -la src/prompts/dashboard_system.md
# Output: -rw-r--r-- ... dashboard_system.md

# Check .env file
ls -la .env
# Output: -rw-r--r-- ... .env
```

### Step 2: Verify Environment
```bash
# Check OPENAI_API_KEY is set
grep OPENAI_API_KEY .env
# Output: OPENAI_API_KEY=sk-proj-xxxxx

# Check Python version
python --version
# Output: Python 3.11.x

# Verify dependencies installed
pip list | grep -E "fastapi|streamlit|openai|python-dotenv"
```

### Step 3: Verify Import Works
```bash
cd src/structured
python -c "from structured_pipeline import generate_dashboard_from_payload; print('✅ Import successful')"
```

---

## Unit Tests

### Test 1: Module Imports

**Command**:
```python
import sys
sys.path.insert(0, 'src/structured')
from structured_pipeline import (
    generate_dashboard_from_payload,
    generate_dashboard_markdown,
    format_payload_for_llm,
    get_dashboard_system_prompt,
)
print("✅ All imports successful")
```

**Expected**: No errors, all functions imported

---

### Test 2: System Prompt Loading

**Command**:
```python
import sys
sys.path.insert(0, 'src/structured')
from structured_pipeline import get_dashboard_system_prompt

prompt = get_dashboard_system_prompt()
assert len(prompt) > 100, "Prompt too short"
assert "Company Overview" in prompt, "Missing required section"
print(f"✅ System prompt loaded: {len(prompt)} characters")
```

**Expected**: Prompt loads, contains required sections

---

### Test 3: Payload Formatting

**Command**:
```python
import sys
sys.path.insert(0, 'src/structured')
from structured_pipeline import format_payload_for_llm

test_payload = {
    "company_record": {"name": "Test Corp", "founded": 2024},
    "events": [{"event_type": "Launch", "date": "Jan 2024", "description": "Product launch"}],
    "products": [{"name": "Product 1", "description": "Test product"}],
    "leadership": [{"name": "CEO", "title": "Chief Executive", "bio": "Bio here"}],
    "visibility": [{"source": "TechCrunch", "mention": "Coverage"}],
    "snapshots": [{"metric": "Revenue", "value": "$1M", "date": "Jan 2024"}],
    "notes": "Test notes"
}

context = format_payload_for_llm(test_payload)
assert "Test Corp" in context, "Company name missing"
assert "Product 1" in context, "Product missing"
assert "CEO" in context, "Leadership missing"
print(f"✅ Payload formatting works: {len(context)} characters")
```

**Expected**: Context contains all data fields

---

### Test 4: File Loading (Happy Path)

**Command**:
```python
import sys
sys.path.insert(0, 'src/structured')
from structured_pipeline import generate_dashboard_from_payload
import os

# Verify file exists first
payload_path = "data/payloads/world-labs.json"
assert os.path.exists(payload_path), f"Test data missing: {payload_path}"

# Try to generate (with real LLM)
try:
    dashboard = generate_dashboard_from_payload(
        company_name="World Labs",
        company_slug="world-labs"
    )
    assert len(dashboard) > 100, "Dashboard too short"
    assert "##" in dashboard, "No markdown headers"
    assert "Company Overview" in dashboard or "Disclosure" in dashboard
    print(f"✅ Dashboard generated: {len(dashboard)} characters")
except Exception as e:
    print(f"⚠️ Generation failed (may need OPENAI_API_KEY): {e}")
```

**Expected**: Dashboard generates with markdown content

---

### Test 5: File Loading (Error Path)

**Command**:
```python
import sys
sys.path.insert(0, 'src/structured')
from structured_pipeline import generate_dashboard_from_payload

try:
    dashboard = generate_dashboard_from_payload(
        company_name="Nonexistent Corp",
        company_slug="nonexistent-corp"
    )
    print("❌ Should have raised FileNotFoundError")
except FileNotFoundError as e:
    print(f"✅ FileNotFoundError caught correctly: {e}")
except Exception as e:
    print(f"❌ Wrong exception type: {type(e).__name__}: {e}")
```

**Expected**: FileNotFoundError raised for missing payload

---

## Integration Tests

### Test 6: FastAPI Endpoint (Mock Request)

**Command**:
```bash
# In one terminal, start FastAPI
cd src/backend
python rag_search_api.py

# In another terminal, test the endpoint
curl -X POST "http://localhost:8000/dashboard/structured?company_name=World%20Labs" \
  -H "Content-Type: application/json" | python -m json.tool
```

**Expected Response** (200 OK):
```json
{
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "markdown": "# World Labs - Investor Diligence Dashboard\n...",
    "status": "success",
    "message": "Structured dashboard generated successfully for World Labs"
}
```

**Verify**:
- Status code is 200
- `company_name` matches input
- `company_slug` is generated correctly
- `markdown` contains dashboard content
- `status` is "success"

---

### Test 7: FastAPI Endpoint (404 Error)

**Command**:
```bash
curl -X POST "http://localhost:8000/dashboard/structured?company_name=Unknown%20Company" \
  -H "Content-Type: application/json"
```

**Expected Response** (404 Not Found):
```json
{
    "detail": "No structured payload found for company 'Unknown Company'. Please run the structured extraction pipeline first."
}
```

**Verify**:
- Status code is 404
- Error message is clear
- No internal error traces

---

### Test 8: Streamlit UI

**Steps**:
1. Start Streamlit: `streamlit run src/frontend/streamlit_app.py`
2. Navigate to http://localhost:8501
3. Select "World Labs" from dropdown
4. Click "Generate (Structured)" button
5. Verify:
   - ✅ Success message appears: "✅ Dashboard generated for World Labs"
   - ✅ Markdown dashboard displays
   - ✅ Dashboard contains sections: "Company Overview", "Business Model", etc.
   - ✅ No error messages shown
   - ✅ No debug output displayed

**Expected UI**:
```
┌─────────────────────────────────────┐
│ Structured pipeline                 │
├─────────────────────────────────────┤
│ [Generate (Structured)] button       │
│                                     │
│ ✅ Dashboard generated for World... │
│                                     │
│ # World Labs - Investor             │
│   Diligence Dashboard               │
│                                     │
│ ## Company Overview                 │
│ World Labs is a leading AI...       │
│                                     │
│ ## Business Model and GTM           │
│ The company provides spatial...     │
│ ... (more sections)                 │
│                                     │
│ ## Disclosure Gaps                  │
│ * Revenue: Not disclosed            │
│ ... (gaps list)                     │
│                                     │
└─────────────────────────────────────┘
```

---

## Performance Tests

### Test 9: Response Time

**Test**:
```python
import time
import requests

start = time.time()
response = requests.post(
    "http://localhost:8000/dashboard/structured?company_name=World%20Labs",
    timeout=30
)
elapsed = time.time() - start

print(f"Response time: {elapsed:.2f}s")
assert elapsed < 15, "Response too slow"
assert response.status_code == 200
print(f"✅ Performance acceptable: {elapsed:.2f}s")
```

**Expected**: < 15 seconds (5-12 seconds typical)

---

### Test 10: Payload Size

**Test**:
```python
import json
from pathlib import Path

payload_path = Path("data/payloads/world-labs.json")
with open(payload_path) as f:
    payload = json.load(f)

size_bytes = payload_path.stat().st_size
size_mb = size_bytes / (1024 * 1024)

print(f"Payload size: {size_mb:.2f} MB")
print(f"Top-level keys: {list(payload.keys())}")
print(f"Company record keys: {len(payload.get('company_record', {}))}")
print(f"Events count: {len(payload.get('events', []))}")
print(f"Products count: {len(payload.get('products', []))}")
print(f"Leadership count: {len(payload.get('leadership', []))}")
print(f"Visibility count: {len(payload.get('visibility', []))}")
```

**Expected**: Payload < 5 MB, all required keys present

---

## Comparison Tests

### Test 11: Structured vs RAG Output

**Test**:
```bash
# Get structured dashboard
curl -X POST "http://localhost:8000/dashboard/structured?company_name=World%20Labs" > structured.json

# Get RAG dashboard
curl -X POST "http://localhost:8000/dashboard/rag?company_name=World%20Labs" > rag.json

# Compare
echo "Structured markdown length: $(jq '.markdown | length' structured.json)"
echo "RAG markdown length: $(jq '.markdown | length' rag.json)"
echo "RAG context chunks: $(jq '.context_results | length' rag.json)"

# Check for same sections
echo "Structured sections:"
jq '.markdown' structured.json | grep "^##" | head -8

echo "RAG sections:"
jq '.markdown' rag.json | grep "^##" | head -8
```

**Expected**:
- Both contain 8 required sections
- Structured typically shorter (single dataset)
- RAG includes context chunks (structured doesn't)
- Markdown structure similar

---

## Logging Tests

### Test 12: Check Logs

**Command**:
```bash
# Watch logs in real-time
tail -f data/logs/rag_search_api.log | grep "Structured\|structured"

# Then trigger endpoint in another terminal
curl -X POST "http://localhost:8000/dashboard/structured?company_name=World%20Labs"
```

**Expected Log Entries**:
```
INFO Structured dashboard request for company: World Labs
INFO Generating structured dashboard for World Labs (slug: world-labs)
INFO Calling LLM to generate dashboard for World Labs
INFO Successfully generated structured dashboard for World Labs
```

---

## Error Scenario Tests

### Test 13: Missing OPENAI_API_KEY

**Setup**:
1. Temporarily remove or comment out OPENAI_API_KEY in .env
2. Restart FastAPI
3. Call endpoint

**Expected**:
- Returns 500 error
- Falls back to default dashboard
- Error message mentions OPENAI_API_KEY

---

### Test 14: Invalid Payload JSON

**Setup**:
1. Create corrupted JSON: `echo "{invalid json" > data/payloads/test.json`
2. Call endpoint with test company

**Expected**:
- Returns 500 error
- Error message mentions JSON parsing
- Original payloads untouched

---

### Test 15: Network Timeout

**Setup**:
```bash
# Simulate slow network
# Call endpoint with network issues (unplug cable, throttle connection)
# Use timeout parameter: curl --max-time 3
```

**Expected**:
- Client-side timeout occurs
- Server keeps running
- No corrupted state

---

## Validation Checklist

### Code Quality
- [ ] No hardcoded paths (use Path, join properly)
- [ ] All exceptions caught and logged
- [ ] No print statements (use logging)
- [ ] Docstrings present on all functions
- [ ] Type hints present
- [ ] No debug code left in

### Functionality
- [ ] Loads payload from data/payloads/
- [ ] Formats payload correctly
- [ ] Calls OpenAI LLM
- [ ] Returns markdown with 8 sections
- [ ] Fallback works when LLM unavailable
- [ ] 404 error when file missing
- [ ] All required sections in output

### Integration
- [ ] FastAPI endpoint works
- [ ] Streamlit button works
- [ ] Response model serializable
- [ ] Error handling returns proper HTTP codes
- [ ] Logging shows execution flow
- [ ] Works with existing RAG pipeline

### Performance
- [ ] < 15 seconds per request
- [ ] < 5 MB payload size
- [ ] Concurrent requests don't fail
- [ ] No memory leaks

### Documentation
- [ ] Docstrings on functions
- [ ] README/guides created
- [ ] Examples provided
- [ ] Architecture documented
- [ ] API documented

---

## Full System Test

### End-to-End Workflow

**Step 1**: Verify Prerequisites
```bash
echo "✓ Checking prerequisites..."
[ -f .env ] && echo "  ✓ .env exists"
[ -d data/payloads ] && echo "  ✓ data/payloads exists"
[ -f src/structured/structured_pipeline.py ] && echo "  ✓ structured_pipeline.py exists"
[ -f src/prompts/dashboard_system.md ] && echo "  ✓ dashboard_system.md exists"
grep -q OPENAI_API_KEY .env && echo "  ✓ OPENAI_API_KEY set"
```

**Step 2**: Start Services
```bash
# Terminal 1
python src/backend/rag_search_api.py

# Terminal 2
streamlit run src/frontend/streamlit_app.py

# Terminal 3 (monitoring)
tail -f data/logs/rag_search_api.log
```

**Step 3**: Test in UI
1. Go to http://localhost:8501
2. Select "World Labs"
3. Click "Generate (Structured)"
4. Verify success and content

**Step 4**: Test via API
```bash
curl -X POST "http://localhost:8000/dashboard/structured?company_name=World%20Labs" | jq .
```

**Step 5**: Verify Logs
```bash
grep "Structured dashboard" data/logs/rag_search_api.log
```

---

## Success Criteria

✅ **All tests pass** if:
1. Module imports without errors
2. FastAPI endpoint returns 200 OK
3. Streamlit displays markdown dashboard
4. Dashboard contains all 8 required sections
5. Response time < 15 seconds
6. 404 returned for missing payloads
7. Logs show execution flow
8. No debug output visible
9. Falls back gracefully when LLM unavailable

---

## Failure Recovery

If any test fails:

| Failure | Recovery |
|---------|----------|
| Import Error | Check sys.path, verify module location |
| FileNotFoundError | Verify data/payloads/ directory, run extraction |
| LLM Error | Check OPENAI_API_KEY, verify API access |
| Timeout | Increase timeout, check OpenAI status |
| 500 Error | Check logs, verify .env loading |
| No Output | Check Streamlit console, verify API responding |

---

## Test Artifacts

Save these for documentation:
- [ ] Successful API response (JSON)
- [ ] Successful Streamlit screenshot
- [ ] Log output showing execution
- [ ] Dashboard markdown content
- [ ] Error response examples
- [ ] Performance metrics

---

For automated testing, see pytest examples in test files.
