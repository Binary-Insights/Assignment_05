# MCP Server - Next Steps & Integration Guide

## Current Status ✅
Your Agentic RAG MCP server is running successfully with:
- ✅ 4 tools registered and operational
- ✅ Security middleware active
- ✅ Logging to `/logs/mcp_server.log`
- ✅ Stdio transport listening for clients

---

## What You Can Do Now

### 1. **Test the Server Locally**
Run the test client to verify all tools work:

```bash
# Terminal 1: Start the MCP server
python -m src.mcp_server

# Terminal 2: Run the test client
python test_mcp_client.py
```

The test client demonstrates:
- Connecting via stdio
- Initializing the session
- Listing available tools
- Calling individual tools with arguments
- Parsing responses

### 2. **Integrate with Claude Desktop** (macOS/Windows)
Create a config file at:
- **macOS**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

Then restart Claude Desktop. The tools will appear in the Claude interface.

### 3. **Available Tools**

| Tool | Purpose | Parameters |
|------|---------|------------|
| `search_company` | Web search via Tavily | `company_name`, `query`, `topic` |
| `extract_field` | LLM field extraction | `field_name`, `company_name`, `search_results`, `importance` |
| `enrich_payload` | Full enrichment workflow | `company_name`, `max_iterations` |
| `analyze_null_fields` | Find missing data fields | `company_name` |

### 4. **Monitor Server Activity**
Watch logs in real-time:

```bash
tail -f logs/mcp_server.log
```

Each tool call is logged with:
- Timestamp
- Tool name
- Arguments received
- Security check results
- Success/failure status

### 5. **Development & Iteration**

**Add New Tools:**
1. Define handler function in `src/mcp_server/server.py`
2. Decorate with `@server.call_tool()`
3. Return list of `TextContent` objects
4. Restart server

**Modify Security Rules:**
Edit `src/mcp_server/security.py` to adjust:
- Whitelist/blacklist rules
- Role-based access control
- Rate limiting
- Input validation

**Extend with Resources/Prompts:**
The MCP protocol also supports:
- **Resources**: Read-only access to data (e.g., company profiles)
- **Prompts**: Reusable prompt templates for Claude

---

## Testing Without Claude Desktop

### Quick Single Tool Test
```bash
python test_mcp_client.py
```

### Manual Tool Testing
Create a script in your project:
```python
import asyncio
from mcp.client.stdio import stdio_client
from mcp.client.session import Session

async def test():
    async with stdio_client("python", "-m", "src.mcp_server") as (read, write):
        async with Session(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_company",
                {"company_name": "OpenAI", "query": "founded"}
            )
            print(result)

asyncio.run(test())
```

---

## Architecture Overview

```
src/mcp_server/
├── __init__.py              # Module exports
├── __main__.py              # Server launcher with logging
├── server.py                # MCP server with 4 tools
└── security.py              # Security middleware

tavily_agent/
├── main.py                  # enrich_single_company()
├── tools.py                 # search_tavily()
├── llm_extraction.py        # LLMExtractionChain
├── graph.py                 # analyze_payload()
└── ...
```

---

## Common Issues & Troubleshooting

### Issue: "Server crashed: unhandled errors in a TaskGroup"
- **Cause**: Client disconnected unexpectedly
- **Fix**: This is normal when running timeout tests; not an error

### Issue: Tools return "Security check failed"
- **Cause**: Security middleware is blocking the request
- **Fix**: Check `security.py` rules; may need to adjust role or whitelist

### Issue: "Payload not found for {company_name}"
- **Cause**: Data file doesn't exist for that company
- **Fix**: Ensure company payloads are created in `config/data/payloads/`

### Issue: LLM extraction fails
- **Cause**: OpenAI API rate limit or connectivity issue
- **Fix**: Check API key, check logs for detailed error

---

## Next Steps

1. **Try the test client**: `python test_mcp_client.py`
2. **Integrate with Claude**: Update Claude Desktop config
3. **Add more tools**: Extend `server.py` with new capabilities
4. **Monitor production**: Set up log rotation and alerting
5. **Deploy**: Host server for remote access (with proper security)

---

## References

- [MCP Protocol Docs](https://modelcontextprotocol.io)
- [Your Agent Code](./tavily_agent/)
- [Server Logs](./logs/mcp_server.log)
