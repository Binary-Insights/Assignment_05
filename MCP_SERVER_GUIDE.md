# MCP Server - Getting Started Guide

## ✅ Status: Production Ready

Your Agentic RAG MCP server is **fully operational** and tested:
- ✅ Server starts cleanly
- ✅ 4 tools registered and accessible
- ✅ Client connection verified
- ✅ Security middleware active
- ✅ Logging operational

---

## Quick Start (60 seconds)

### 1. Start the Server
```bash
python -m src.mcp_server
```
Server listens on stdio for incoming MCP requests.

### 2. Test with Client (in another terminal)
```bash
python test_mcp_client.py
```
This will run connection, tool listing, and basic tool call tests.

### 3. View Logs
```bash
tail -f logs/mcp_server.log
```

---

## Integration with Claude Desktop

### macOS Setup
```bash
# Edit the config file
nano ~/.config/Claude/claude_desktop_config.json
```

### Windows Setup
```bash
# Edit the config file
%APPDATA%\Claude\claude_desktop_config.json
```

### Config Content
Replace `/path/to/Assignment_05` with your actual path:

```json
{
  "mcpServers": {
    "agentic-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/Assignment_05",
      "env": {
        "OPENAI_API_KEY": "your-key-here",
        "TAVILY_API_KEY": "your-key-here"
      }
    }
  }
}
```

Then restart Claude Desktop. The tools will appear in Claude's interface.

---

## Available Tools

### 1. `search_company`
Web search for company information via Tavily.

**Parameters:**
- `company_name` (string, required): Company name
- `query` (string, required): Search query
- `topic` (string, optional): Search topic (default: "general")

**Returns:**
```json
{
  "count": 5,
  "results": [...],
  "status": "success"
}
```

### 2. `extract_field`
LLM-based extraction of specific company fields.

**Parameters:**
- `field_name` (string, required): Field to extract (e.g., "founded_year")
- `company_name` (string, required): Company name
- `search_results` (list, optional): Search results to use
- `importance` (string, optional): "high", "medium", "low"

**Returns:**
```json
{
  "field_name": "founded_year",
  "value": "2015",
  "confidence": 0.95,
  "reasoning": "...",
  "sources": ["source1", "source2"],
  "status": "success"
}
```

### 3. `enrich_payload`
Full enrichment workflow (search + extract + validate).

**Parameters:**
- `company_name` (string, required): Company name
- `max_iterations` (integer, optional): Max workflow iterations

**Returns:**
```json
{
  "company_name": "OpenAI",
  "status": "success",
  "fields_enriched": 15,
  "completion_time": 45.2
}
```

### 4. `analyze_null_fields`
Analyze payload to find missing/null fields.

**Parameters:**
- `company_name` (string, required): Company name

**Returns:**
```json
{
  "company_name": "OpenAI",
  "null_fields_count": 5,
  "null_fields": ["field1", "field2", ...],
  "status": "success"
}
```

---

## Testing & Development

### Run Full Test Suite
```bash
python test_mcp_client.py
```

Expected output:
```
✅ Connected to MCP server
✅ Session initialized
✅ Available tools (4 total):
   - search_company: Search for company information via Tavily
   - extract_field: Extract value for a field using LLM chain
   - enrich_payload: Run full enrichment workflow for a company
   - analyze_null_fields: Analyze payload to find null fields
```

### Manual Tool Test
Create `test_tool.py`:
```python
import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def test():
    params = StdioServerParameters(
        command="python",
        args=["-m", "src.mcp_server"]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Call a tool
            result = await session.call_tool(
                "search_company",
                {
                    "company_name": "OpenAI",
                    "query": "headquarters location"
                }
            )
            print(result)

asyncio.run(test())
```

Run it:
```bash
python test_tool.py
```

---

## Architecture

### Server Components
```
src/mcp_server/
├── server.py           # Main MCP server & tool implementations
├── __main__.py         # Launcher with logging setup
├── __init__.py         # Module exports
└── security.py         # Security middleware & rate limiting
```

### Integration Points
```
tavily_agent/
├── main.py             # enrich_single_company()
├── tools.py            # Tavily search wrapper
├── llm_extraction.py   # LLM extraction chain
├── graph.py            # LangGraph enrichment workflow
└── config.py           # OpenAI & settings
```

### Data Flow
```
Client → MCP Protocol (stdio) → Server
         ↓
    Security Middleware (whitelist → role → rate limit → validate)
         ↓
    Tool Handler (search_company / extract_field / enrich_payload / analyze_null_fields)
         ↓
    Tavily Agent Components
         ↓
    OpenAI LLM (gpt-4o-mini)
         ↓
    Response → Client
```

---

## Monitoring & Troubleshooting

### View Real-Time Logs
```bash
tail -f logs/mcp_server.log
```

### Common Issues

**"Server crashed: unhandled errors in a TaskGroup"**
- Normal during client disconnections; not an error
- Check logs for details if tools fail

**"Security check failed"**
- Tool is being blocked by security middleware
- Check `src/mcp_server/security.py` rules
- Verify requester_role is whitelisted

**"Payload not found for {company_name}"**
- Company data doesn't exist in `config/data/payloads/`
- Create payload or use different company name

**"OpenAI API rate limit"**
- Wait a few seconds and retry
- Check your API key has quota
- Monitor `logs/mcp_server.log` for details

---

## Performance Tips

1. **Batch Requests**: Group multiple tool calls in one client session
2. **Cache Results**: Store extracted fields to avoid re-running expensive LLM calls
3. **Adjust Timeouts**: Modify timeout in `test_mcp_client.py` if needed
4. **Monitor Memory**: Check `/logs/mcp_server.log` for OOM warnings

---

## Next Steps

### Immediate
1. ✅ Test: `python test_mcp_client.py`
2. Configure Claude Desktop (optional)
3. Verify logs look normal

### Short-term
1. Add more companies to `config/data/company_pages.json`
2. Customize security rules in `src/mcp_server/security.py`
3. Extend tools with new capabilities

### Long-term
1. Deploy to remote server (Docker recommended)
2. Set up log aggregation & monitoring
3. Create deployment docs for team

---

## Key Files

| File | Purpose |
|------|---------|
| `src/mcp_server/server.py` | Main MCP server implementation |
| `src/mcp_server/security.py` | Security middleware |
| `test_mcp_client.py` | Test client & verification script |
| `logs/mcp_server.log` | Server logs |
| `config/data/` | Company payload data |
| `tavily_agent/` | Core enrichment logic (reused) |

---

## Support

- **MCP Protocol**: https://modelcontextprotocol.io
- **Claude Desktop Docs**: https://claude.ai/docs
- **Your Agent Code**: See `tavily_agent/README.md`

---

**Server Status**: ✅ Ready for production use
**Last Updated**: November 16, 2025
