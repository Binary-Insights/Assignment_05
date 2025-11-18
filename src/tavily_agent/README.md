# Agentic RAG System Documentation

## Overview

The Agentic RAG (Retrieval-Augmented Generation) system is an intelligent tool for enriching company payload JSON files with missing data. It uses:

- **LangGraph**: For orchestrating the agentic workflow with state management
- **LangChain**: For LLM integration and tool definitions
- **Tavily Search**: For retrieving current information about companies
- **Pinecone**: For vector storage with deduplication and metadata tracking
- **OpenAI GPT Models**: For intelligent data extraction and reasoning

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Payload Files (data/payloads/*.json)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Main Orchestrator (src/agents/main.py)                      │
│ - Reads payloads                                            │
│ - Backs up originals as v1                                 │
│ - Manages batch processing                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ LangGraph Enrichment Graph (src/agents/graph.py)            │
│ ┌─────────────────┬──────────────┬───────────────┐         │
│ │ Analyze Payload │ Get Null     │ Generate      │         │
│ │                 │ Fields       │ Queries       │         │
│ └────────┬────────┴──────┬───────┴───────┬───────┘         │
│          │               │               ▼                 │
│          ▼               ▼        ┌──────────────────┐     │
│  ┌──────────────────────────────────┐ Execute        │     │
│  │  Workflow Nodes                  │ Searches       │     │
│  │ - Analyze payload                │                │     │
│  │ - Get next null field            └────────┬───────┘     │
│  │ - Generate search queries               │              │
│  │ - Execute searches                      ▼              │
│  │ - Extract and update payload    ┌──────────────────┐   │
│  └──────────────────────────────────┤ Tavily Search   │   │
│                                     │ (Tool)          │   │
│                                     └────────┬────────┘   │
└─────────────────────────────────────────────────────────────┘
                                              │
                    ┌─────────────────────────┼──────────────────────┐
                    │                         │                      │
                    ▼                         ▼                      ▼
            ┌──────────────────┐      ┌──────────────────┐  ┌──────────────────┐
            │ File I/O Manager │      │ Vector DB Manager│  │ Payload Updated  │
            │ (file_io_manager)│      │ (Pinecone)       │  │ (data/payloads/) │
            │                  │      │ - Deduplication │  │                  │
            │ - Save raw data  │      │ - Metadata mgmt │  │ - Original: v1   │
            │ - Create backups │      │ - Vector search │  │ - Updated: curr  │
            │ - Version control│      └──────────────────┘  └──────────────────┘
            └──────────────────┘
                    │
                    ▼
            ┌──────────────────┐
            │ data/raw/        │
            │ {company}/{tool} │
            │ /{timestamp}.json│
            └──────────────────┘
```

## Directory Structure

```
src/agents/
├── __init__.py                 # Package exports
├── config.py                   # Configuration management
├── file_io_manager.py         # File operations (read/write payloads)
├── vector_db_manager.py       # Pinecone integration
├── tools.py                   # Tool definitions (Tavily, etc.)
├── graph.py                   # LangGraph state and nodes
├── main.py                    # Main orchestrator and entry point
├── utils.py                   # Utility functions
└── examples.py                # Example usage

data/
├── payloads/                  # Payload files
│   ├── {company}.json         # Updated payload
│   ├── {company}_v1.json      # Original backup
│   ├── {company}_v2.json      # Previous version
│   └── ...
├── raw/                       # Raw tool responses
│   ├── {company}/
│   │   ├── tavily/
│   │   │   ├── tavily_20240101_120000.json
│   │   │   └── tavily_20240101_130000.json
│   │   └── ...
│   └── ...
├── vectors/                   # Vector store metadata
├── logs/                      # Execution logs
```

## Configuration

Configure via `.env` file in project root:

```env
# API Keys
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
PINECONE_API_KEY=your-key
PINECONE_ENVIRONMENT=us-east-1-aws

# LLM Settings
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# Pinecone Configuration
PINECONE_INDEX_NAME=agentic-rag-payloads
PINECONE_NAMESPACE=default
PINECONE_DIMENSION=1536
EMBEDDING_MODEL=text-embedding-3-small

# Processing
MAX_ITERATIONS=5
TOOL_TIMEOUT=30
BATCH_SIZE=3
DEDUP_CHECK_ENABLED=true

# Logging
LOG_LEVEL=INFO
```

## Usage

### Command Line Interface

```bash
# Enrich a single company
python -m src.agents.main single abridge

# Enrich multiple companies
python -m src.agents.main multiple abridge anthropic openai

# Enrich all available companies
python -m src.agents.main all
```

### Python API

```python
import asyncio
from src.agents import (
    enrich_single_company,
    enrich_multiple_companies,
    enrich_all_companies
)

async def main():
    # Single company
    result = await enrich_single_company("abridge")
    print(result)
    
    # Multiple companies
    summary = await enrich_multiple_companies(["abridge", "anthropic"])
    print(summary)
    
    # All companies
    summary = await enrich_all_companies()

asyncio.run(main())
```

### Advanced Usage with Orchestrator

```python
import asyncio
from src.agents import AgenticRAGOrchestrator

async def custom_workflow():
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    
    # Process specific companies
    companies = ["abridge", "anthropic"]
    summary = await orchestrator.process_batch(companies)
    
    # Print and save summary
    orchestrator.print_summary()
    orchestrator.save_execution_summary()

asyncio.run(custom_workflow())
```

### Running Examples

```bash
# Run all examples
python src/agents/examples.py

# Run specific example
python src/agents/examples.py 1  # Single company
python src/agents/examples.py 3  # Analyze payload
python src/agents/examples.py 5  # List companies
```

## Workflow Details

### 1. Payload Analysis Phase
- Reads payload from `data/payloads/{company}.json`
- Identifies all null fields across all entities
- Prioritizes fields by importance (critical > high > medium > low)
- Creates backup as `{company}_v1.json`

### 2. Query Generation Phase
- For each null field, generates 3 targeted search queries
- Uses LLM to create context-aware, specific queries
- Stores queries for concurrent execution

### 3. Search and Retrieval Phase
- Executes searches concurrently using Tavily Search API
- Saves raw results to `data/raw/{company}/tavily/{timestamp}.json`
- Converts results to LangChain Documents
- Checks for duplicates before vector storage

### 4. Deduplication and Vector Storage
- Computes MD5 hash of each document
- Checks against existing documents in `data/raw/`
- Only stores new, unique content in Pinecone
- Includes rich metadata (company_id, tool_name, crawled_at, etc.)

### 5. Extraction and Payload Update
- Uses LLM to extract field value from search results
- Calculates confidence score for extracted value
- Only updates payload if confidence > 0.5
- Updates provenance with:
  - Tool source (Tavily)
  - Crawl timestamp
  - Extracted value reasoning
  - Source references

### 6. Iteration and Completion
- Repeats phases 2-5 for remaining null fields
- Stops when:
  - All fields processed
  - Max iterations reached (default: 5)
  - No more null fields
- Saves updated payload as `{company}.json`

## Data Flow Example

### Input Payload
```json
{
  "company_record": {
    "company_id": "abridge",
    "legal_name": "Abridge AI, Inc.",
    "website": null,  // ← Null field
    "founded_year": null,  // ← Null field
    "hq_city": null  // ← Null field
  }
}
```

### Processing Steps

1. **Analyze**: Identifies 3 null fields
2. **Query Generation**: Creates searches like:
   - "Abridge AI headquarters location"
   - "Abridge AI founding date when founded"
   - "Abridge AI website official"
3. **Search**: Executes via Tavily, gets results
4. **Deduplicate**: Checks against existing data
5. **Store**: Adds to Pinecone with metadata
6. **Extract**: LLM processes results
7. **Update**: Updates null values if confident

### Output Payload
```json
{
  "company_record": {
    "company_id": "abridge",
    "legal_name": "Abridge AI, Inc.",
    "website": "https://abridge.com",
    "founded_year": 2018,
    "hq_city": "San Francisco",
    "provenance": [
      {
        "source_url": "tavily_search",
        "crawled_at": "2024-01-15T10:30:00Z",
        "snippet": "Founded in 2018, based in San Francisco",
        "chunk_id": ["abridge_tavily_20240115"]
      }
    ]
  }
}
```

## Deduplication Strategy

The system prevents duplicate data ingestion through:

1. **Hash-based Detection**
   - Computes MD5 hash of document content
   - Stores hashes in `data/raw/{company}/{tool}/`
   - Compares new content against existing hashes

2. **Concurrent Safety**
   - File-based deduplication works across async operations
   - Each tool response saved immediately with hash

3. **Vector DB Efficiency**
   - Only unique content enters Pinecone
   - Saves tokens and storage costs
   - Prevents search result pollution

## Metadata Management

All documents in Pinecone store:

```python
{
    "company_id": "abridge",
    "tool_name": "tavily",
    "source": "https://example.com/article",
    "crawled_at": "2024-01-15T10:30:00Z",
    "field": "founded_year",  # Which field was being researched
    "entity_type": "company_record",
    "title": "Article title",
    "chunk_index": 0
}
```

## Async Concurrency

All I/O operations are async for performance:

- **File Operations**: Async file read/write
- **Vector DB**: Concurrent embeddings and Pinecone calls
- **Search Execution**: Batch queries run concurrently
- **Batch Processing**: Multiple companies processed in parallel (configurable BATCH_SIZE)

Example timing (5 companies):
- Sequential: ~5 × 120s = 600s
- Concurrent (BATCH_SIZE=3): ~200s

## Error Handling

The system implements multi-level error handling:

1. **Configuration Errors**: Caught at startup
2. **File I/O Errors**: Logged, processing continues
3. **API Errors**: Timeout handling, retry on failures
4. **LLM Parsing Errors**: Fallback to basic extraction
5. **Vector DB Errors**: Logged, deduplication skipped

All errors stored in:
- Execution summary JSON
- Log files with timestamps
- State.errors for per-company tracking

## Logging

Logs are stored in `data/logs/`:

```
agentic_rag_20240115_103000.log
execution_summary_20240115_103000.json
```

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

Example log:
```
2024-01-15 10:30:00 - agentic_rag - INFO - Analyzing payload for abridge
2024-01-15 10:30:01 - agentic_rag - INFO - Found 3 null fields to enrich
2024-01-15 10:30:02 - agentic_rag - INFO - Generated 3 search queries
2024-01-15 10:30:05 - agentic_rag - INFO - Retrieved 15 documents
2024-01-15 10:30:06 - agentic_rag - INFO - Stored 12 documents (skipped 3 duplicates)
```

## Performance Considerations

1. **Batch Processing**: Process multiple companies concurrently (BATCH_SIZE=3)
2. **Vector Embeddings**: Cached in Pinecone for reuse
3. **Deduplication**: Prevents redundant API calls
4. **Timeout Handling**: 30-second default per tool call
5. **Memory**: Async streaming for large payloads

## Best Practices

1. **Start Small**: Test with single company first
2. **Monitor Logs**: Review execution_summary.json after batch runs
3. **Backup Before**: Always backup payloads before updating
4. **Verify Confidence**: Check confidence scores in logs
5. **Adjust Iterations**: Tune MAX_ITERATIONS based on needs
6. **API Monitoring**: Track Tavily and Pinecone usage

## Troubleshooting

### "Missing API keys" Error
```
Solution: Add required keys to .env:
- OPENAI_API_KEY
- TAVILY_API_KEY
- PINECONE_API_KEY
```

### "Payload file not found"
```
Solution: Ensure payload file exists at:
data/payloads/{company_name}.json
```

### "Vector DB connection failed"
```
Solution: Verify Pinecone credentials:
- PINECONE_API_KEY correct
- PINECONE_INDEX_NAME exists
- PINECONE_ENVIRONMENT correct
```

### "Search timeout"
```
Solution: Increase TOOL_TIMEOUT in .env
Default: 30 seconds
```

## API Reference

### Main Functions

```python
# Enrich single company
result = await enrich_single_company(company_name: str) -> Dict[str, Any]

# Enrich multiple companies
summary = await enrich_multiple_companies(company_names: List[str]) -> Dict[str, Any]

# Enrich all available companies
summary = await enrich_all_companies() -> Dict[str, Any]
```

### FileIOManager

```python
# Read payload
payload = await FileIOManager.read_payload(company_name: str) -> Optional[Dict]

# Save payload
success = await FileIOManager.save_payload(company_name: str, payload: Dict) -> bool

# Backup payload
success = await FileIOManager.backup_payload(company_name: str) -> bool

# List companies
companies = await FileIOManager.list_company_payloads() -> List[str]
```

### VectorDBManager

```python
# Add documents
added, skipped = await VectorDBManager.add_documents(documents, company_id, tool_name) -> Tuple[int, int]

# Search documents
results = await VectorDBManager.search(query, company_id, top_k=5) -> List[Dict]

# Check duplicate
is_dup = await VectorDBManager.check_duplicate(content, company_id, tool_name) -> bool
```

### Utilities

```python
# Analyze null fields
summary = PayloadAnalyzer.get_null_fields_summary(payload) -> Dict

# Compare payloads
changes = PayloadAnalyzer.compare_payloads(original, updated) -> Dict

# Create provenance entry
prov = ProvenanceManager.create_provenance_entry(source_tool, source_url) -> Dict
```

## Future Enhancements

1. **Multiple Search Providers**: Integrate additional search APIs
2. **Custom LLM Models**: Support other LLM providers
3. **Advanced Filtering**: Query-specific field extraction
4. **Human-in-the-Loop**: Approval workflows for high-value updates
5. **Dashboard UI**: Real-time monitoring of enrichment progress
6. **RAG Optimization**: Fine-tune prompts based on domain
7. **Performance Metrics**: Track enrichment quality over time
8. **Export Formats**: Support CSV, Parquet, SQL exports
