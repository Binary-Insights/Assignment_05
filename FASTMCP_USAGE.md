# FastMCP Server for Agentic RAG

## Overview

This FastMCP server exposes the Agentic RAG enrichment workflow as MCP tools, resources, and prompts. It enables secure, controlled access to company payload enrichment through the Model Context Protocol.

## Starting the Server

```bash
# In WSL terminal from project root:
cd /mnt/c/Users/enigm/OneDrive/Documents/NortheasternAssignments/09_BigDataIntelAnlytics/Assignments/Assignment_05

# Start the server
python -m src.mcp_server
```

Expected output:
```
🚀 Launching Agentic RAG FastMCP Server...
✅ [FASTMCP] Registered Tools:
  - search_company: Search company information
  - extract_field: Extract field values using LLM
  - enrich_payload: Run complete enrichment workflow
  - analyze_payload: Analyze payloads for null fields

✅ [FASTMCP] Registered Resources:
  - get_payload: Get company payload
  - list_payloads: List available payloads

✅ [FASTMCP] Registered Prompts:
  - enrichment_workflow: Enrichment workflow guidance
  - security_guidelines: Security guidelines

🔌 [FASTMCP] Server ready and listening on stdio transport
```

## Available Tools

### 1. search_company
Search for company information using Tavily API.

**Parameters:**
- `query` (string, required): Search query
- `company_name` (string, required): Company identifier (e.g., 'abridge')
- `topic` (string, optional): Search topic category (default: 'general')

**Returns:** JSON with search results

**Example:**
```json
{
  "tool": "search_company",
  "query": "Abridge AI healthcare",
  "company_name": "abridge",
  "results": [
    {
      "title": "...",
      "content": "...",
      "url": "..."
    }
  ],
  "count": 5,
  "success": true
}
```

### 2. extract_field
Extract a field value from search results using LLM chain.

**Parameters:**
- `field_name` (string, required): Field name to extract (e.g., 'founded_year')
- `entity_type` (string, required): Entity type (e.g., 'company_record')
- `company_name` (string, required): Company identifier
- `importance` (string, optional): Importance level - 'critical', 'high', 'medium', 'low' (default: 'medium')
- `search_results` (string, optional): JSON string of search results

**Returns:** JSON with extracted value and confidence

### 3. enrich_payload
Run the complete enrichment workflow for a company payload.

**Parameters:**
- `company_name` (string, required): Company identifier (e.g., 'abridge')
- `test_dir` (string, optional): Test directory for outputs (e.g., '/tmp/agentic_rag_test')
- `max_iterations` (integer, optional): Maximum enrichment iterations (default: 20)

**Returns:** JSON with enrichment status and results

**Example with test directory:**
```python
{
  "company_name": "abridge",
  "test_dir": "/tmp/agentic_rag_test",
  "max_iterations": 20
}
```

### 4. analyze_payload
Analyze a payload to identify null fields needing enrichment.

**Parameters:**
- `company_name` (string, required): Company identifier
- `show_values` (boolean, optional): Show current values (default: false)

**Returns:** JSON with analysis result

**Example response:**
```json
{
  "company_name": "abridge",
  "total_null_fields": 5,
  "null_fields_by_type": {
    "company_record": [
      {"field_name": "founded_year", "importance": "high"},
      {"field_name": "total_raised_usd", "importance": "high"}
    ],
    "events": [
      {"field_name": "event_id", "importance": "critical"}
    ]
  },
  "success": true
}
```

## Available Resources

### 1. get_payload
Get the current payload for a company.

**URI format:** `payload://{company_name}`

**Example:** `payload://abridge`

**Returns:** JSON payload content

### 2. list_payloads
List all available company payloads.

**URI:** `payloads://available`

**Returns:**
```json
{
  "total_companies": 45,
  "companies": ["abridge", "world_labs", "company3", ...]
}
```

## Available Prompts

### 1. enrichment_workflow
Provides step-by-step guidance for running the enrichment workflow.

**Parameters:**
- `company_name` (string): Company identifier

**Output:** Markdown guide with recommended workflow steps and example commands

### 2. security_guidelines
Security policies and best practices for using the server.

**Output:** Markdown guide covering:
- Tool access control
- Input validation
- Rate limiting
- Best practices
- Troubleshooting

## Usage Examples

### Using with Claude Desktop

Add to `~/.claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentic-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/Assignment_05"
    }
  }
}
```

### Using with Python Client

```python
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import asyncio

async def test():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.mcp_server"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Call tool
            result = await session.call_tool("analyze_payload", {
                "company_name": "abridge"
            })
            print(result)
            
            # Read resource
            resource = await session.read_resource("payloads://available")
            print(resource)
            
            # Get prompt
            prompt = await session.get_prompt("enrichment_workflow", {
                "company_name": "abridge"
            })
            print(prompt)

asyncio.run(test())
```

## Security Features

1. **Tool Filtering**: Only whitelisted tools are accessible
   - search_company
   - extract_field
   - enrich_payload
   - analyze_payload

2. **Input Validation**: All inputs validated for:
   - SQL injection patterns
   - Code injection attempts
   - Command injection
   - Suspicious network calls

3. **Rate Limiting**: Per-tool rate limits
   - search_company: 60 requests/min
   - extract_field: 30 requests/min
   - enrich_payload: 5 requests/min
   - analyze_payload: 30 requests/min

4. **API Key Protection**: All API keys loaded from environment variables only

## Workflow Example

### Step 1: Analyze Payload
```
Call: analyze_payload(company_name="abridge")
Returns: List of 5 null fields to fill
```

### Step 2: Search for Information
```
Call: search_company(
  query="Abridge AI healthcare company",
  company_name="abridge"
)
Returns: Search results from Tavily
```

### Step 3: Extract Field Values
```
Call: extract_field(
  field_name="founded_year",
  entity_type="company_record",
  company_name="abridge",
  search_results=<result from step 2>
)
Returns: Extracted value with confidence score
```

### Step 4: Run Full Enrichment
```
Call: enrich_payload(
  company_name="abridge",
  test_dir="/tmp/test",
  max_iterations=20
)
Returns: Complete enrichment status and updated payload
```

### Step 5: Verify Results
```
Call: get_payload(company_name="abridge")
Returns: Updated payload with filled fields
```

## Troubleshooting

### Server won't start
- Ensure TAVILY_API_KEY is set: `echo $TAVILY_API_KEY`
- Ensure OPENAI_API_KEY is set: `echo $OPENAI_API_KEY`
- Clear Python cache: `find . -type d -name __pycache__ -exec rm -rf {} +`

### Tool calls timing out
- Increase timeout duration
- Use smaller batches
- Check network connectivity to Tavily and OpenAI

### Low confidence extractions
- Refine search queries
- Provide more context
- Manual review of results

### Rate limit exceeded
- Wait before retrying
- Check rate limit settings
- Batch requests appropriately

## Configuration

All configuration is handled via environment variables in `.env`:

```bash
TAVILY_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
LANGSMITH_API_KEY=your_key_here
LANGSMITH_ENABLED=true
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
MAX_ITERATIONS=20
BATCH_SIZE=3
LOG_LEVEL=INFO
```

## File Structure

```
src/mcp_server/
├── __init__.py          # Package initialization
├── __main__.py          # Entry point for `python -m src.mcp_server`
├── server.py            # FastMCP server implementation
└── security.py          # Security middleware (optional)

src/tavily_agent/
├── main.py              # Enrichment orchestrator
├── graph.py             # LangGraph workflow
├── tools.py             # Tavily search tools
├── llm_extraction.py    # LLM extraction chain
├── config.py            # Configuration management
├── file_io_manager.py   # File I/O utilities
└── ...
```

## Next Steps

1. ✅ Start the server: `python -m src.mcp_server`
2. ✅ Test with client script: `python test_mcp_client.py`
3. ✅ Configure Claude Desktop integration
4. ✅ Run enrichment workflow via MCP interface
