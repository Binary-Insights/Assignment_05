# LLM Response Storage Implementation

## Overview

The Streamlit frontend now automatically saves all generated dashboards to organized directories with master and individual JSON tracking files.

## Directory Structure

```
data/llm_response/
├── markdown/
│   ├── company-slug-1/
│   │   ├── structured.md
│   │   └── rag.md
│   ├── company-slug-2/
│   │   ├── structured.md
│   │   └── rag.md
│   └── ...
├── json/
│   ├── company-slug-1/
│   │   └── responses.json
│   ├── company-slug-2/
│   │   └── responses.json
│   └── ...
└── master.json
```

## File Descriptions

### Markdown Files: `markdown/{company_slug}/{pipeline_type}.md`

Contains the raw markdown dashboard content for a specific company and pipeline.

**Example:** `markdown/world-labs/structured.md`

```markdown
# World Labs Dashboard

## Company Overview
...
```

### Company-Specific JSON: `json/{company_slug}/responses.json`

Tracks both structured and RAG responses for a single company, **including full markdown content**.

**Structure:**
```json
{
  "company_slug": "world-labs",
  "structured": {
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "pipeline_type": "structured",
    "timestamp": "2025-11-09T05:03:48.457071Z",
    "markdown_file": "markdown/world-labs/structured.md",
    "content": "# World Labs Dashboard\n\n## Overview\n...[FULL MARKDOWN CONTENT]..."
  },
  "rag": {
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "pipeline_type": "rag",
    "timestamp": "2025-11-09T05:04:12.123456Z",
    "markdown_file": "markdown/world-labs/rag.md",
    "content": "# World Labs Dashboard (RAG)\n\n## Analysis\n...[FULL MARKDOWN CONTENT]...",
    "context_results": [
      {
        "id": "abridge_blog_5_5794e918",
        "similarity_score": 0.92,
        "text": "...",
        "metadata": {...}
      }
    ]
  }
}
```

### Master JSON: `master.json`

Aggregates metadata for all companies, tracking when each pipeline was last generated.

**Structure:**
```json
{
  "world-labs": {
    "company_name": "World Labs",
    "company_slug": "world-labs",
    "structured": {
      "company_name": "World Labs",
      "company_slug": "world-labs",
      "pipeline_type": "structured",
      "timestamp": "2025-11-09T05:03:48.457071Z",
      "markdown_file": "markdown/world-labs/structured.md"
    },
    "rag": {
      "company_name": "World Labs",
      "company_slug": "world-labs",
      "pipeline_type": "rag",
      "timestamp": "2025-11-09T05:04:12.123456Z",
      "markdown_file": "markdown/world-labs/rag.md"
    }
  },
  "anthropic": {...},
  "abridge": {...}
}
```

## Usage in Streamlit Frontend

### Automatic Saving

When you click either "Generate (Structured)" or "Generate (RAG)" button:

1. **API Call:** Dashboard is generated via the FastAPI endpoint
2. **Save Markdown:** Response markdown is saved to `markdown/{company_slug}/{pipeline_type}.md`
3. **Save Company JSON:** Response metadata and context is saved to `json/{company_slug}/responses.json`
4. **Update Master JSON:** Master file is updated with the new response metadata
5. **Display Status:** A success message and save details are shown

### Viewing Saved Responses

The UI displays a status section showing:
- ✅ **Structured** - Saved (with timestamp)
- ✅ **RAG** - Saved (with timestamp)
- ⚪ **[Pipeline]** - Not yet generated

## Utility Functions

### `ensure_directories()`
Creates all required directories if they don't exist.

```python
base_dir = ensure_directories()
# Returns: Path("data/llm_response")
```

### `save_dashboard_response(company_slug, pipeline_type, response_data)`
Main function that handles all saving operations.

```python
save_dashboard_response(
    company_slug="world-labs",
    pipeline_type="structured",
    response_data=api_response
)
```

### `load_master_json(master_path)`
Loads the master JSON file or returns empty dict if not found.

```python
master_json = load_master_json(Path("data/llm_response/master.json"))
```

### `load_company_json(company_json_path)`
Loads company-specific JSON file with fallback to default structure.

```python
company_json = load_company_json(Path("data/llm_response/json/world-labs/responses.json"))
```

### `view_saved_responses(company_slug)`
Displays saved response status in Streamlit UI.

```python
view_saved_responses("world-labs")
```

## Data Flow

```
User clicks Generate Button
        ↓
API generates dashboard
        ↓
save_dashboard_response() called
        ↓
├─→ Save markdown file
├─→ Update company JSON file
└─→ Update master JSON file
        ↓
Display success message with file paths
```

## Key Features

✅ **Automatic Persistence:** All responses are immediately saved
✅ **Master Aggregation:** Single file tracks all companies' latest responses
✅ **Company Isolation:** Each company has its own response tracking file
✅ **Metadata Tracking:** Timestamps and file paths included for audit trail
✅ **Context Storage:** RAG context_results preserved for reproducibility
✅ **Error Handling:** Graceful fallbacks and user-friendly error messages
✅ **UI Status Display:** Users can see which pipelines have been run

## Accessing Saved Data Programmatically

```python
import json
from pathlib import Path

# Load master JSON
with open("data/llm_response/master.json") as f:
    master = json.load(f)

# Get all company slugs that have responses
companies = master.keys()

# Get structured response for specific company
company_data = master["world-labs"]
structured_response = company_data["structured"]

# Load markdown content
markdown_path = structured_response["markdown_file"]
with open(f"data/llm_response/{markdown_path}") as f:
    markdown_content = f.read()
```

## Integration with Evaluation System

The saved JSON files can be used by the evaluation system to:
- Compare actual LLM outputs between pipelines
- Verify that evaluation metrics differentiate between responses
- Track historical performance changes over time
- Audit the exact content that was evaluated

## Notes

- Timestamps are stored in ISO 8601 format with Z suffix (UTC timezone)
- Company slugs use kebab-case (e.g., "world-labs", "together-ai")
- All JSON files are formatted with 2-space indentation for readability
- UTF-8 encoding is used for all text files to support international characters
- Relative paths in JSON reference the `data/llm_response/` base directory
