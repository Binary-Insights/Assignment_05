# Payload Agent

LangGraph-based autonomous agent for payload processing with RAG-enhanced field enrichment.

## Structure

```
src/payload_agent/
├── __init__.py              # Package exports
├── payload_agent.py         # Main ReAct agent with LangGraph
├── payload_workflow.py      # LangGraph workflow nodes & state machine
└── tools/                   # Payload processing tools
    ├── __init__.py
    ├── retrieval.py         # @tool: Load payloads from disk
    ├── validation.py        # @tool: Validate & update payloads
    └── rag_adapter.py       # Pinecone RAG search adapter
```

## Components

### PayloadAgent (`payload_agent.py`)
Main agent class with 3 execution modes:

**Autonomous Mode** (default):
```python
agent = PayloadAgent()
result = agent.retrieve_and_validate("abridge", use_agent=True)
```
- LLM decides which tools to call
- Uses LangGraph ReAct pattern
- Natural language query interface

**Manual ReAct Mode**:
```python
result = agent.retrieve_and_validate("abridge", use_react=True)
```
- Predefined tool sequence
- Manual thought/action/observation logging

**Direct Mode**:
```python
result = agent.retrieve_and_validate("abridge", use_agent=False, use_react=False)
```
- Direct tool invocation
- No agent reasoning

### Workflow (`payload_workflow.py`)
LangGraph state machine with nodes:

- `retrieve` → Load payload from disk
- `validate` → Check structure & identify nulls
- `update` → Fill nulls using Pinecone + LLM

**Conditional Logic**:
- If validation succeeds → proceed to update
- If validation fails → end workflow

**Graph Visualization**:
Automatically saved to `data/graph/payload_workflow_graph.png`

### Tools

All tools use `@tool` decorator for agent discovery:

**1. Retrieval** (`get_latest_structured_payload`)
- Loads JSON payload from `data/payloads/{company_id}.json`
- 3-tier validation: strict → normalized → model_construct
- In-memory caching

**2. Validation** (`validate_payload`)
- Checks payload structure
- Identifies null/missing fields
- Returns validation report

**3. Update** (`update_payload`)
- Fills null fields using Pinecone vectors
- LLM extraction from search results
- Saves to `{company_id}_v2.json`

**4. RAG Adapter** (`create_pinecone_adapter`)
- Pinecone search interface
- Company-specific filtering
- Returns callable for vector search

## Usage

### Quick Start

```python
from payload_agent import PayloadAgent

# Initialize agent
agent = PayloadAgent()

# Validate payload (autonomous)
result = agent.retrieve_and_validate("abridge")
print(f"Status: {result['status']}")
print(f"Null fields: {len(result.get('null_fields', []))}")

# Update payload with RAG enrichment
result = agent.retrieve_and_update("abridge")
print(f"Filled: {result.get('filled_count', 0)} fields")
print(f"Saved to: {result.get('output_file')}")
```

### Command Line

**Agent Test**:
```bash
python src/payload_agent/payload_agent.py abridge
```

**Workflow Test**:
```bash
python src/payload_agent/payload_workflow.py abridge
```

### Custom Queries

```python
# Natural language interface
response = agent.execute_with_agent(
    "Check if the abridge payload has any missing fields and fill them"
)
```

## Configuration

**Environment Variables** (`.env`):
```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=bigdata-assignment-05
PINECONE_NAMESPACE=default
PINECONE_EMBEDDING_MODEL=text-embedding-3-large

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=pe-dashboard-ai-50
```

## Output Files

**Updated Payloads**:
- Location: `data/payloads/{company_id}_v2.json`
- Contains filled fields with extraction metadata

**Workflow Graph**:
- Location: `data/graph/payload_workflow_graph.png`
- Auto-generated visualization of LangGraph workflow

## Import Paths

Since this is a dedicated package, use absolute imports:

```python
# Correct
from payload_agent import PayloadAgent
from payload_agent.tools import validate_payload, update_payload

# Not recommended (relative imports outside package)
from tools.payload import validate_payload  # Old path
```

## Dependencies

- `langchain-openai`: LLM integration
- `langgraph`: ReAct agent & workflow graphs
- `langchain-core`: Tool decorator & base classes
- `pinecone-client`: Vector database
- `pydantic`: Data validation

## Architecture

**Tool Pattern**:
- All tools use `@tool` decorator
- `.invoke({"param": value})` calling convention
- Return dictionaries for agent compatibility

**Agent Flow**:
```
User Query → LangGraph Agent → Tool Selection → Tool Execution → Response
                    ↑                                    ↓
                    └──────────── Observation ──────────┘
```

**Workflow Flow**:
```
START → retrieve → validate → [conditional] → update → END
                                   ↓
                                  END (validation failed)
```

## Troubleshooting

**Import Errors**:
- Ensure `src/` is in `PYTHONPATH`
- Use absolute imports: `from payload_agent import ...`

**Pinecone Not Finding Results**:
- Check `PINECONE_NAMESPACE` in `.env`
- Verify data was ingested: `python src/rag/ingest_to_pinecone.py --company-slug <company>`
- Check filter metadata: `company_slug` must match exactly

**LangGraph Tool Errors**:
- Use `.invoke()` not direct calls
- Tools return dicts, not objects
- Check parameter names match tool schema

## Testing

Run the built-in test suite:

```bash
# Test agent (3 modes)
python src/payload_agent/payload_agent.py abridge

# Test workflow (LangGraph state machine)
python src/payload_agent/payload_workflow.py abridge
```

Expected output:
- ✅ Payload retrieved
- ✅ Validation complete (X null fields identified)
- ✅ Update complete (Y fields filled)
- ✅ Saved to: `data/payloads/{company}_v2.json`
- ✅ Graph saved to: `data/graph/payload_workflow_graph.png`
