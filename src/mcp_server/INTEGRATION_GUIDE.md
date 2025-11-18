# MCP Server Integration Guide

Complete guide for integrating the MCP server with your environment and existing agent code.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Code Reuse](#code-reuse)
4. [Testing](#testing)
5. [Deployment](#deployment)
6. [Client Integration](#client-integration)

## Quick Start

### 1. Verify File Structure

```
src/
├── mcp_server/
│   ├── __init__.py           # Package init
│   ├── __main__.py           # Launch script
│   ├── security.py           # Security middleware
│   ├── server.py             # Main MCP server
│   └── README.md             # Documentation
├── tavily_agent/
│   ├── main.py              # Entry point (enrich_single_company)
│   ├── graph.py             # LangGraph workflow
│   ├── llm_extraction.py    # 3-step LLM extraction chain
│   ├── tools.py             # ToolManager (search_tavily)
│   ├── file_io_manager.py   # File I/O operations
│   └── config.py            # Configuration
```

### 2. Start Server

```bash
cd /path/to/Assignment_05
python -m src.mcp_server
```

Expected output:
```
🚀 [MCP] Starting Agentic RAG MCP Server
📋 [MCP] Registering tools...
✅ [MCP] All tools registered
🔌 [MCP] Starting stdio transport...
✅ [MCP] Server running and ready for requests
📡 [MCP] Waiting for client connections...
```

### 3. Connect Client

Claude Desktop:
```json
{
  "mcpServers": {
    "agentic-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"]
    }
  }
}
```

## Architecture

### Data Flow

```
MCP Client Request
        ↓
    stdio transport (MCP Protocol)
        ↓
    server.py (Tool Handler)
        ↓
    security_middleware.can_execute_tool()
    ├── Tool Whitelist ✓
    ├── Role-based Access ✓
    ├── Rate Limiting ✓
    └── Input Validation ✓
        ↓
    Reused Agent Code
    ├── ToolManager.search_tavily()
    ├── LLMExtractionChain.run_extraction_chain()
    ├── enrich_single_company()
    └── analyze_payload()
        ↓
    Response Format (JSON)
        ↓
    MCP Client Receives Response
```

### Tool Mapping

```
MCP Tool                  Reused Code
─────────────────────────────────────────────────────────────
search_company        →   tavily_agent.tools.ToolManager
                           └── search_tavily()

extract_field         →   tavily_agent.llm_extraction.LLMExtractionChain
                           └── run_extraction_chain()

enrich_payload        →   tavily_agent.main
                           └── enrich_single_company()

analyze_null_fields   →   tavily_agent.graph
                           └── analyze_payload()
```

## Code Reuse

### 1. Search Company Tool

**MCP Server Code** (server.py):
```python
@server.call_tool()
async def search_company(arguments: Dict[str, Any]) -> List[ToolResult]:
    """Search for company information via Tavily."""
    # 1. Validate input
    input_data = SearchCompanyInput(**arguments)
    
    # 2. Security check
    can_execute, reason = security_middleware.can_execute_tool(
        "search_company", arguments, "user"
    )
    
    # 3. Call existing code
    tool_manager = await get_tool_manager()
    result = await tool_manager.search_tavily(
        query=input_data.query,
        company_name=input_data.company_name,
        topic=input_data.topic
    )
    
    # 4. Return result
    return [ToolResult(content=[TextContent(type="text", text=json.dumps(result))])]
```

**Original Agent Code** (tools.py):
```python
class ToolManager:
    async def search_tavily(self, query: str, company_name: str, topic: str):
        """Original search implementation - unchanged"""
        # ... existing code ...
```

**Reuse Percentage**: 100% ✅

### 2. Extract Field Tool

**MCP Server Code** (server.py):
```python
@server.call_tool()
async def extract_field(arguments: Dict[str, Any]) -> List[ToolResult]:
    """Extract value for a field using LLM chain."""
    # 1. Validate input
    input_data = ExtractFieldInput(**arguments)
    
    # 2. Security check
    can_execute, reason = security_middleware.can_execute_tool(
        "extract_field", arguments, "user"
    )
    
    # 3. Call existing code
    chain = LLMExtractionChain(
        llm_model=LLM_MODEL,
        temperature=LLM_TEMPERATURE
    )
    extraction_result = await chain.run_extraction_chain(
        field_name=input_data.field_name,
        entity_type="company_record",
        company_name=input_data.company_name,
        importance=input_data.importance,
        search_results=input_data.search_results
    )
    
    # 4. Return result
    return [ToolResult(content=[TextContent(type="text", text=json.dumps({...}))])]
```

**Original Agent Code** (llm_extraction.py):
```python
class LLMExtractionChain:
    async def run_extraction_chain(self, field_name: str, ...):
        """Original extraction implementation - unchanged"""
        # ... existing code ...
```

**Reuse Percentage**: 100% ✅

### 3. Enrichment Payload Tool

**MCP Server Code** (server.py):
```python
@server.call_tool()
async def enrich_payload(arguments: Dict[str, Any]) -> List[ToolResult]:
    """Run full enrichment workflow for a company."""
    # 1. Validate input
    input_data = EnrichPayloadInput(**arguments)
    
    # 2. Security check (admin-only)
    can_execute, reason = security_middleware.can_execute_tool(
        "enrich_payload", arguments, "system"
    )
    
    # 3. Call existing code
    result = await enrich_single_company(input_data.company_name)
    
    # 4. Return result
    return [ToolResult(content=[TextContent(type="text", text=json.dumps(result))])]
```

**Original Agent Code** (main.py):
```python
async def enrich_single_company(company_name: str):
    """Original enrichment implementation - unchanged"""
    # ... existing code ...
```

**Reuse Percentage**: 100% ✅

### 4. Analyze Null Fields Tool

**MCP Server Code** (server.py):
```python
@server.call_tool()
async def analyze_null_fields(arguments: Dict[str, Any]) -> List[ToolResult]:
    """Analyze payload to find null fields."""
    # 1. Validate input
    input_data = AnalyzeNullFieldsInput(**arguments)
    
    # 2. Security check
    can_execute, reason = security_middleware.can_execute_tool(
        "analyze_null_fields", arguments, "user"
    )
    
    # 3. Prepare state
    payload = await FileIOManager.read_payload(input_data.company_name)
    state = PayloadEnrichmentState(
        company_name=input_data.company_name,
        current_payload=payload
    )
    
    # 4. Call existing code
    analyzed_state = analyze_payload(state)
    
    # 5. Return result
    return [ToolResult(content=[TextContent(type="text", text=json.dumps({...}))])]
```

**Original Agent Code** (graph.py):
```python
def analyze_payload(state: PayloadEnrichmentState):
    """Original analysis implementation - unchanged"""
    # ... existing code ...
```

**Reuse Percentage**: 95% (only wrapping, core logic unchanged) ✅

### Summary

| Tool | Reused Code | Percentage | Changes |
|------|------------|-----------|---------|
| search_company | 100% | 100% | Input wrapper, output formatter |
| extract_field | 100% | 100% | Input wrapper, output formatter |
| enrich_payload | 100% | 100% | Input wrapper, output formatter |
| analyze_null_fields | 95% | 95% | State preparation + output formatter |
| **Total** | **~95%** | **~95%** | Thin wrapper layer |

## Testing

### 1. Unit Tests

**Test Security Middleware**:
```python
# tests/test_security.py
def test_tool_whitelist():
    assert security_middleware.can_execute_tool("search_company", {}, "user")[0]
    assert not security_middleware.can_execute_tool("invalid_tool", {}, "user")[0]

def test_rate_limiting():
    # Simulate 61 requests (limit is 60)
    for i in range(60):
        security_middleware.can_execute_tool("search_company", {}, "user")
    can_exec, reason = security_middleware.can_execute_tool("search_company", {}, "user")
    assert not can_exec
    assert "rate limit" in reason.lower()

def test_input_validation():
    bad_query = {"query": "DROP TABLE companies"}
    can_exec, reason = security_middleware.can_execute_tool("search_company", bad_query, "user")
    assert not can_exec
    assert "validation" in reason.lower()
```

**Test Tool Handlers**:
```python
# tests/test_tools.py
@pytest.mark.asyncio
async def test_search_company_tool():
    result = await search_company({
        "company_name": "OpenAI",
        "query": "OpenAI company information",
        "topic": "general"
    })
    assert result[0].is_error is False
    # Verify response format

@pytest.mark.asyncio
async def test_extract_field_tool():
    result = await extract_field({
        "field_name": "founded_year",
        "company_name": "OpenAI",
        "search_results": [{"title": "...", "content": "..."}],
        "importance": "high"
    })
    assert result[0].is_error is False
```

### 2. Integration Tests

**Test Full Workflow**:
```python
# tests/integration_test.py
@pytest.mark.asyncio
async def test_full_enrichment_workflow():
    # 1. Analyze null fields
    analysis = await analyze_null_fields({"company_name": "test-company"})
    null_fields = json.loads(analysis[0].content[0].text)
    
    # 2. Search for each field
    for field in null_fields["null_fields"][:3]:
        search_result = await search_company({
            "company_name": "test-company",
            "query": f"test-company {field}",
            "topic": "general"
        })
        assert search_result[0].is_error is False
    
    # 3. Extract fields
    search_results = json.loads(search_result[0].content[0].text)
    extract_result = await extract_field({
        "field_name": "founded_year",
        "company_name": "test-company",
        "search_results": search_results.get("results", []),
        "importance": "high"
    })
    assert extract_result[0].is_error is False
```

### 3. Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run unit tests
pytest tests/test_security.py -v
pytest tests/test_tools.py -v

# Run integration tests
pytest tests/integration_test.py -v

# Run with coverage
pytest tests/ --cov=src.mcp_server --cov-report=html
```

## Deployment

### Local Development

```bash
# Terminal 1: Start MCP server
python -m src.mcp_server

# Terminal 2: Use with Claude Desktop or custom client
```

### Docker Deployment

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code
COPY src/ src/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Run MCP server
CMD ["python", "-m", "src.mcp_server"]
```

**docker-compose.yml** (add to existing):
```yaml
services:
  mcp-server:
    build:
      context: .
      dockerfile: docker/Dockerfile
    environment:
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    ports:
      - "5000:5000"
    restart: unless-stopped
```

### Production Checklist

- [ ] Environment variables configured (TAVILY_API_KEY, OPENAI_API_KEY)
- [ ] Rate limits tuned for expected load
- [ ] Security rules customized for use case
- [ ] Logging aggregation configured (ELK, Splunk, etc.)
- [ ] Monitoring alerts setup (error rate, latency, rate limit hits)
- [ ] Backup and disaster recovery plan
- [ ] Load balancing configured for multi-instance deployment
- [ ] HTTPS/TLS configured for external clients

## Client Integration

### Claude Desktop

1. Edit `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentic-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "env": {
        "TAVILY_API_KEY": "your-key",
        "OPENAI_API_KEY": "your-key"
      }
    }
  }
}
```

2. Restart Claude Desktop

3. Tools available in Claude:
   - search_company
   - extract_field
   - enrich_payload
   - analyze_null_fields

### Custom MCP Client

```python
import json
import subprocess
import sys
from contextlib import asynccontextmanager

class MCPClient:
    def __init__(self, command, args):
        self.command = command
        self.args = args
        self.process = None
    
    @asynccontextmanager
    async def connect(self):
        """Connect to MCP server via stdio."""
        self.process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            yield self
        finally:
            self.process.terminate()
    
    async def call_tool(self, tool_name, arguments):
        """Call tool on MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        # Send request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Read response
        response = self.process.stdout.readline()
        return json.loads(response)

# Usage
async def main():
    client = MCPClient("python", ["-m", "src.mcp_server"])
    async with client.connect():
        result = await client.call_tool("search_company", {
            "company_name": "OpenAI",
            "query": "OpenAI company information",
            "topic": "general"
        })
        print(json.dumps(result, indent=2))
```

### HTTP Bridge (FastAPI)

```python
# Optional: Wrap MCP server in HTTP API
from fastapi import FastAPI, HTTPException
import subprocess
import json

app = FastAPI()

@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, arguments: dict):
    """Call MCP tool via HTTP."""
    process = subprocess.Popen(
        ["python", "-m", "src.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True
    )
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    output, _ = process.communicate(json.dumps(request) + "\n")
    return json.loads(output)
```

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to MCP server"
**Solution**: 
- Verify server is running: `python -m src.mcp_server`
- Check firewall/port access
- Verify environment variables: `echo $TAVILY_API_KEY`

### Tool Execution Failures

**Problem**: "Tool not found" or "Security check failed"
**Solution**:
- Verify tool name matches allowed list (check `security.py`)
- Check input validation rules
- Review rate limit settings
- Check API key credentials

### Performance Issues

**Problem**: "Tool execution is slow"
**Solution**:
- Monitor Tavily API response times
- Check OpenAI API latency
- Review LangSmith traces for bottlenecks
- Consider caching common queries

## Next Steps

1. **Test Integration**: Run full workflow with test data
2. **Performance Tuning**: Monitor and optimize for production
3. **Client Integration**: Connect Claude Desktop or other clients
4. **Monitoring Setup**: Configure logging and alerts
5. **Deployment**: Deploy to production environment

## Support

For issues or questions:
1. Check logs: `tail -f logs/mcp_server.log`
2. Review MCP specification: https://modelcontextprotocol.io/
3. Check security rules: `src/mcp_server/security.py`
4. Review tool code: `src/mcp_server/server.py`
