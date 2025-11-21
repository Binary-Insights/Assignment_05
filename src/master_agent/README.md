# Master Orchestrator Agent

The Master Orchestrator combines both the **Tavily Agent** and **Payload Agent** to provide comprehensive payload enrichment for company data.

## 🎯 Overview

The Master Orchestrator runs a two-phase enrichment workflow:

### Phase 1: Tavily Agent (Company Record Enrichment)
- Uses Tavily API for external web search
- Enriches `company_record` fields:
  - `brand_name`, `hq_city`, `hq_state`, `hq_country`
  - `founded_year`, `categories`, `total_raised_usd`
  - `last_disclosed_valuation_usd`, `last_round_name`, `last_round_date`
- Provides provenance tracking with source URLs

### Phase 2: Payload Agent (Entity Extraction)
- Uses Pinecone vector search over crawled company data
- Extracts structured entities:
  - **Events**: funding, partnerships, product releases, etc.
  - **Products**: product names, descriptions, pricing models
  - **Leadership**: executives, founders, roles
  - **Snapshots**: headcount, job openings, hiring focus
  - **Visibility**: news mentions, GitHub stars, ratings

## 🚀 Quick Start

### Basic Usage

Enrich a company with both agents:
```bash
python src/master_agent/master_orchestrator.py abridge
```

### Selective Execution

Run only Tavily agent (company_record fields):
```bash
python src/master_agent/master_orchestrator.py abridge --tavily-only
```

Run only Payload agent (entity extraction):
```bash
python src/master_agent/master_orchestrator.py abridge --payload-only
```

Verbose logging:
```bash
python src/master_agent/master_orchestrator.py abridge --verbose
```

## 📊 Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MASTER ORCHESTRATOR                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Load Initial Payload        │
              └───────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         │                                         │
         ▼                                         ▼
┌─────────────────────┐                 ┌─────────────────────┐
│   PHASE 1           │                 │   PHASE 2           │
│   Tavily Agent      │                 │   Payload Agent     │
├─────────────────────┤                 ├─────────────────────┤
│ • Tavily API        │                 │ • Pinecone Search   │
│ • Web Search        │                 │ • LLM Extraction    │
│ • company_record    │                 │ • Entity Extraction │
│ • Field Validation  │                 │ • Structured Output │
└─────────────────────┘                 └─────────────────────┘
         │                                         │
         └────────────────────┬────────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │   Merge Results               │
              │   Save Final Payload          │
              │   {company_id}.json           │
              └───────────────────────────────┘
```

## 🔧 Technical Details

### Code Reuse

The Master Orchestrator **reuses existing code** from both agents:

**From Tavily Agent:**
```python
from tavily_agent.main import enrich_single_company
from tavily_agent.file_io_manager import FileIOManager
```

**From Payload Agent:**
```python
from payload_agent.payload_workflow import run_payload_workflow
from payload_agent.tools.rag_adapter import create_pinecone_adapter
```

### Workflow Steps

1. **Initialization**
   - Setup logging and LangSmith tracing
   - Initialize file I/O manager
   - Create execution summary tracker

2. **Phase 1: Tavily Agent**
   - Calls `enrich_single_company(company_id)`
   - Enriches company_record fields via Tavily API
   - Saves intermediate payload with auto-versioning

3. **Phase 2: Payload Agent**
   - Initializes Pinecone adapter and LLM
   - Calls `run_payload_workflow(company_id, rag_search_tool, llm)`
   - Extracts entities from vector search results
   - Saves updated payload with auto-versioning

4. **Results Merge**
   - Loads final payload (contains both agents' updates)
   - Counts enriched fields and entities
   - Generates comprehensive summary

## 📁 Output

The master orchestrator produces:

### 1. Enriched Payload
- **Location**: `data/payloads/{company_id}.json`
- **Versioning**: Old versions saved as `{company_id}_v1.json`, `v2.json`, etc.

### 2. Logs
- **Location**: `data/logs/master_orchestrator_YYYYMMDD_HHMMSS.log`
- **Content**: Detailed execution trace with timestamps

### 3. Execution Summary
Printed to console:
```
📈 MASTER ORCHESTRATOR - EXECUTION SUMMARY
===============================================

🏢 Company: abridge

📡 Tavily Agent:
   Status: success
   Fields enriched: 8

🔍 Payload Agent:
   Status: success
   Fields filled: 12

📊 Overall Results:
   Total fields filled: 20
   Total entities added: 45

⏱️  Execution Time: 127.45 seconds

✅ MASTER ORCHESTRATOR COMPLETE
```

## 🔄 Versioning System

The master orchestrator uses **automatic versioning** for payload files:

### First Save
```
→ abridge.json (current version)
```

### Second Save
```
→ abridge_v1.json (backup of previous version)
→ abridge.json (new current version)
```

### Third Save
```
→ abridge_v2.json (backup of previous version)
→ abridge.json (new current version)

Final state:
- abridge.json (current - latest)
- abridge_v1.json (historical)
- abridge_v2.json (historical)
```

## 📦 Dependencies

The master agent requires both Tavily and Payload agent dependencies:

### Tavily Agent Dependencies
- `langchain`, `langchain-openai`
- `tavily-python` (Tavily API)
- `langgraph`, `langsmith`
- `qdrant-client` (vector DB)

### Payload Agent Dependencies
- `pinecone-client` (Pinecone vector search)
- `pydantic` (data validation)
- `langchain-openai` (LLM)

### Environment Variables
```bash
# Tavily Agent
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key

# Payload Agent
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=your_environment
PINECONE_INDEX_NAME=your_index_name

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=master-orchestrator
```

## 🎨 Example Output

```bash
$ python src/master_agent/master_orchestrator.py abridge

================================================================================
🚀 MASTER ORCHESTRATOR - Starting enrichment for abridge
================================================================================
   Tavily Agent: ✅ ENABLED
   Payload Agent: ✅ ENABLED

================================================================================
📡 PHASE 1: TAVILY AGENT - Enriching company_record fields
================================================================================
🔧 Initializing Tavily Agent for abridge...
📊 Tavily Agent Results:
   Status: success
   Fields enriched: 8
✅ Tavily phase complete: success

================================================================================
🔍 PHASE 2: PAYLOAD AGENT - Extracting entities from Pinecone
================================================================================
🔧 Initializing Payload Agent for abridge...
   Connecting to Pinecone...
   ✅ Pinecone connection established
   Initializing LLM (gpt-4o)...
   ✅ LLM initialized
   Running payload workflow...
📊 Payload Agent Results:
   Status: success
   Fields filled: 12
   Output: data/payloads/abridge.json
✅ Payload phase complete: success

================================================================================
🔄 MERGING RESULTS - Combining Tavily and Payload agent outputs
================================================================================
📊 Final Payload Statistics:
   Company record fields filled: 20
   Total entities: 45
      - Events: 15
      - Products: 8
      - Leadership: 12
      - Snapshots: 7
      - Visibility: 3

================================================================================
📈 MASTER ORCHESTRATOR - EXECUTION SUMMARY
================================================================================

🏢 Company: abridge

📡 Tavily Agent:
   Status: success
   Fields enriched: 8

🔍 Payload Agent:
   Status: success
   Fields filled: 12

📊 Overall Results:
   Total fields filled: 20
   Total entities added: 45

⏱️  Execution Time: 127.45 seconds

================================================================================
✅ MASTER ORCHESTRATOR COMPLETE
================================================================================

✅ SUCCESS - abridge enriched successfully
```

## 🧪 Testing

Test the master orchestrator with a sample company:

```bash
# Full enrichment
python src/master_agent/master_orchestrator.py world_labs --verbose

# Tavily only (company_record)
python src/master_agent/master_orchestrator.py world_labs --tavily-only

# Payload only (entities)
python src/master_agent/master_orchestrator.py world_labs --payload-only
```

## 📚 Integration with Existing Agents

The Master Orchestrator is designed to work seamlessly with existing agents:

### Tavily Agent
- **Entry Point**: `src/tavily_agent/main.py`
- **Function**: `enrich_single_company(company_id)`
- **Reused Components**: `AgenticRAGOrchestrator`, `FileIOManager`

### Payload Agent
- **Entry Point**: `src/payload_agent/payload_workflow.py`
- **Function**: `run_payload_workflow(company_id, rag_search_tool, llm)`
- **Reused Components**: LangGraph workflow, Pinecone adapter, validation tools

## 🔍 Debugging

Enable verbose logging to see detailed execution:

```bash
python src/master_agent/master_orchestrator.py abridge --verbose
```

Check logs:
```bash
tail -f data/logs/master_orchestrator_*.log
```

## 🚧 Future Enhancements

Potential improvements:
- [ ] Parallel execution of Tavily and Payload agents
- [ ] Conflict resolution when both agents update same fields
- [ ] Custom field routing (specify which agent handles which fields)
- [ ] Batch processing for multiple companies
- [ ] Human-in-the-loop approval for master orchestrator
- [ ] Export summary reports (JSON, CSV, HTML)

## 📄 License

Same as parent project.

## 🤝 Contributing

The master orchestrator is designed to be extensible. To add new agents:

1. Create agent workflow in `src/<agent_name>/`
2. Import agent's main function in `master_orchestrator.py`
3. Add new phase in `enrich_company()` method
4. Update merge logic to handle new agent's outputs

## 📞 Support

For issues related to:
- **Tavily Agent**: See `src/tavily_agent/README.md`
- **Payload Agent**: See `src/payload_agent/README.md`
- **Master Orchestrator**: Create GitHub issue with `master-orchestrator` label
