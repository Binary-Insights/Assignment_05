# Module Architecture: structured_pipeline.py

## File Location
```
src/structured/structured_pipeline.py
```

## Module Purpose
Generates investor-facing markdown dashboards from structured JSON payload files using OpenAI LLM.

## Imports & Dependencies

```python
import json                    # For loading payload JSON
import logging                 # For logging
import os                      # For environment variables
from typing import List, Dict, Any, Optional
from pathlib import Path       # For file path handling

from dotenv import load_dotenv # For .env loading (explicit path)
```

## Public Functions (Entry Points)

### 1. `generate_dashboard_from_payload()`

**Signature**:
```python
def generate_dashboard_from_payload(
    company_name: str,
    company_slug: str,
    llm_client: Any = None,
    llm_model: str = "gpt-4o"
) -> str:
```

**Purpose**: Main entry point for the module

**Parameters**:
- `company_name` (str): Display name of company (e.g., "World Labs")
- `company_slug` (str): URL-friendly slug (e.g., "world-labs")
- `llm_client` (OpenAI, optional): Pre-initialized OpenAI client. If None, creates one automatically
- `llm_model` (str): LLM model to use (default: "gpt-4o")

**Returns**:
- Markdown dashboard string

**Raises**:
- `FileNotFoundError`: If payload file not found at `data/payloads/{slug}.json`
- `json.JSONDecodeError`: If payload JSON is invalid
- Generic exceptions during LLM calls

**Example Usage**:
```python
from structured_pipeline import generate_dashboard_from_payload

dashboard = generate_dashboard_from_payload(
    company_name="World Labs",
    company_slug="world-labs"
)
print(dashboard)
```

**Called By**:
- `src/backend/rag_search_api.py` in `generate_structured_dashboard()` endpoint

---

## Internal Functions (Helper Functions)

### 1. `get_dashboard_system_prompt()`

**Signature**:
```python
def get_dashboard_system_prompt() -> str:
```

**Purpose**: Load the dashboard system prompt from markdown file

**Returns**:
- System prompt string from `src/prompts/dashboard_system.md`
- Empty string if file not found

**Shared With**:
- `rag_pipeline.py` (same implementation)

**Example System Prompt**:
```
You generate an investor-facing diligence dashboard for a private AI startup.

Use ONLY data in the provided payload. If something is unknown or not disclosed, 
literally say "Not disclosed."

If a claim is marketing, attribute it: "The company states ..."

Never include personal emails or phone numbers.

Always include the final section "## Disclosure Gaps".

Required section order:
## Company Overview
## Business Model and GTM
## Funding & Investor Profile
## Growth Momentum
## Visibility & Market Sentiment
## Risks and Challenges
## Outlook
## Disclosure Gaps
```

---

### 2. `format_payload_for_llm()`

**Signature**:
```python
def format_payload_for_llm(payload: Dict[str, Any]) -> str:
```

**Purpose**: Convert structured JSON payload into readable text context for LLM

**Parameters**:
- `payload` (Dict): The structured company payload from JSON

**Returns**:
- Formatted text string with sections

**Processing Logic**:

| Section | Limit | Processing |
|---------|-------|------------|
| Company Record | None | All fields included |
| Events | First 10 | Description shown, date included |
| Products | First 5 | Name + description |
| Leadership | First 10 | Name, title, bio preview (150 chars) |
| Visibility | First 5 | Source + mention preview (200 chars) |
| Snapshots | First 10 | Metric, value, date |
| Notes | All | Full text included |

**Example Output**:
```
## Company Record
**Founded:** 2024
**HQ:** San Francisco, CA
**Industry:** AI/Spatial Intelligence

## Events (15 total)
- **Press Release** (Jan 2025): World Labs announces $230M Series B
- **Press Release** (Dec 2024): World Labs launches spatial intelligence platform
... and 13 more events

## Products (3 total)
- **Spatial Intelligence Platform**: Core product for 3D scene understanding
- **Enterprise API**: RESTful API for spatial data processing
- **Developer SDK**: Python/JavaScript SDK for integration

## Leadership (8 total)
- **CEO Name** - Chief Executive Officer
  Background in AI and computer vision...
- **CTO Name** - Chief Technology Officer
  Previously led research at...
... and 6 more leaders

## Visibility & Market Presence (20 mentions)
- **TechCrunch**: World Labs raises $230M in funding round...
- **VentureBeat**: Spatial intelligence startup leads...
... and 18 more mentions

## Key Snapshots
- **Funding**: $230M (as of Jan 2025)
- **Employees**: 150 (as of Jan 2025)
- **Customers**: 50+ enterprises (as of Jan 2025)
... and 7 more snapshots

## Additional Notes
World Labs is a leading player in spatial intelligence with strong investor backing.
```

---

### 3. `generate_dashboard_markdown()`

**Signature**:
```python
def generate_dashboard_markdown(
    company_name: str,
    payload: Dict[str, Any],
    llm_client: Any = None,
    llm_model: str = "gpt-4o"
) -> str:
```

**Purpose**: Call OpenAI LLM to generate markdown dashboard

**Flow**:
1. Initialize LLM client if not provided
2. Load system prompt from dashboard_system.md
3. Format payload into context text
4. Build user prompt requesting 8 sections
5. Call `chat.completions.create()` with system + user messages
6. Extract and return markdown response

**LLM Parameters**:
```python
response = llm_client.chat.completions.create(
    model="gpt-4o",           # Default, can be overridden
    max_tokens=4096,          # Max response length
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
)
```

**Fallback**: If LLM fails, calls `_generate_default_dashboard()`

---

### 4. `_generate_default_dashboard()`

**Signature**:
```python
def _generate_default_dashboard(
    company_name: str,
    payload: Dict[str, Any]
) -> str:
```

**Purpose**: Generate fallback dashboard when LLM is unavailable

**When Used**:
- OPENAI_API_KEY not set
- LLM client initialization fails
- LLM API call fails
- System prompt not found

**Output Format**:
```markdown
# {company_name} - Investor Diligence Dashboard

## Company Overview
Not disclosed.

## Business Model and GTM
Not disclosed.

## Funding & Investor Profile
Not disclosed.

## Growth Momentum
Not disclosed.

## Visibility & Market Sentiment
Not disclosed.

## Risks and Challenges
Not disclosed.

## Outlook
Not disclosed.

## Disclosure Gaps
**Available Context:**
{formatted_payload_content}

**Note:** This is a fallback dashboard generated without LLM processing.
For full dashboard generation, ensure OPENAI_API_KEY is set and the LLM is available.
```

---

## Comparison with rag_pipeline.py

### Similarities
| Aspect | Details |
|--------|---------|
| System Prompt | Both use `dashboard_system.md` |
| Fallback | Both have `_generate_default_dashboard()` |
| LLM | Both use OpenAI `chat.completions.create()` |
| Max Tokens | Both use 4096 token limit |
| Model Default | Both default to "gpt-4o" |
| Error Handling | Both catch exceptions and return fallback |

### Differences
| Aspect | structured_pipeline | rag_pipeline |
|--------|-------------------|-------------|
| **Data Source** | JSON file | Qdrant database |
| **Retrieval** | File I/O | Vector search |
| **Context Size** | All payload data | Top-10 similar chunks |
| **Entry Point Name** | `generate_dashboard_from_payload()` | `generate_dashboard_with_retrieval()` |
| **Return Type** | Single string | Tuple: (markdown, results) |
| **Embedding** | None | OpenAI text-embedding-3-small |

---

## Error Handling

### FileNotFoundError
```python
try:
    with open(payload_path, 'r') as f:
        payload = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError(f"No payload found for {company_slug}")
```

### JSONDecodeError
```python
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON in payload file: {e}")
    raise
```

### LLM Errors
```python
try:
    response = llm_client.chat.completions.create(...)
except Exception as e:
    logger.error(f"LLM call failed: {e}")
    return _generate_default_dashboard(...)
```

---

## Environment Variables

**Required**:
- `OPENAI_API_KEY`: OpenAI API key for LLM and embeddings

**Optional**:
- `OPENAI_API_BASE`: Custom OpenAI endpoint

**Loading**:
```python
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(env_path)
```

---

## Logging

Uses Python's standard `logging` module:

```python
logger = logging.getLogger(__name__)

# Info-level logs (normal flow)
logger.info(f"Generating dashboard from structured payload for {company_name}")
logger.info(f"Successfully loaded payload from {payload_path}")
logger.info(f"Successfully generated dashboard for {company_name}")

# Error-level logs (errors)
logger.error(f"Payload file not found: {payload_path}")
logger.error(f"LLM call failed: {e}")

# Warning-level logs (potential issues)
logger.warning(f"Dashboard system prompt not found")
```

**Log Output**:
```
2025-11-05 14:23:45,123 INFO structured_pipeline: Generating dashboard from structured payload for World Labs
2025-11-05 14:23:45,456 INFO structured_pipeline: Successfully loaded payload from data/payloads/world-labs.json
2025-11-05 14:23:45,789 INFO structured_pipeline: Calling LLM to generate dashboard for World Labs
2025-11-05 14:23:52,123 INFO structured_pipeline: Successfully generated dashboard for World Labs
```

---

## Usage Examples

### Example 1: Basic Usage (Streamlit)
```python
from structured_pipeline import generate_dashboard_from_payload

try:
    dashboard = generate_dashboard_from_payload(
        company_name="World Labs",
        company_slug="world-labs"
    )
    st.markdown(dashboard)
except FileNotFoundError:
    st.error("Payload not found for this company")
except Exception as e:
    st.error(f"Error: {e}")
```

### Example 2: With Custom LLM Client (FastAPI)
```python
from openai import OpenAI
from structured_pipeline import generate_dashboard_from_payload

client = OpenAI(api_key="sk-...")
dashboard = generate_dashboard_from_payload(
    company_name="World Labs",
    company_slug="world-labs",
    llm_client=client,
    llm_model="gpt-4-turbo"
)
```

### Example 3: Error Handling
```python
try:
    dashboard = generate_dashboard_from_payload("World Labs", "world-labs")
except FileNotFoundError as e:
    print(f"Payload missing: {e}")
    # Fallback: run extraction pipeline first
except Exception as e:
    print(f"Generation failed: {e}")
    # Retry with different LLM or manual review
```

---

## Testing Checklist

- [ ] Payload file exists at `data/payloads/world-labs.json`
- [ ] `.env` has `OPENAI_API_KEY`
- [ ] `src/prompts/dashboard_system.md` exists
- [ ] OpenAI API key is valid
- [ ] Import works: `from structured_pipeline import generate_dashboard_from_payload`
- [ ] Generated dashboard has all 8 required sections
- [ ] Fallback dashboard appears when OPENAI_API_KEY is missing
- [ ] 404 error when payload file doesn't exist
- [ ] Logging shows successful execution
