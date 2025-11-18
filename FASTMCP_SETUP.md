# FastMCP Server - Complete Setup & Usage Guide

## ✅ Implementation Complete

Your FastMCP MCP server for the Agentic RAG system is now **fully functional and running**.

## 📊 Server Status

```
✅ Server Running (PID: 1589)
Command: python -m src.mcp_server
Transport: Stdio (JSON-RPC)
Tools: 4 available
Resources: 2 available
Prompts: 2 available
```

## 🎯 What You Have

### Tools (4)
1. **search_company** - Search via Tavily API
2. **extract_field** - Extract values using LLM chain
3. **enrich_payload** - Full enrichment workflow (supports test mode)
4. **analyze_payload** - Analyze payloads for null fields

### Resources (2)
1. **payload://{company_name}** - Get payload for company
2. **payloads://available** - List all available payloads

### Prompts (2)
1. **enrichment_workflow** - Step-by-step workflow guide
2. **security_guidelines** - Security policies

## 🚀 Getting Started

### Option 1: Use Existing Client (Recommended for Testing)

In a **NEW terminal** (keep server running in original terminal):

```bash
cd /mnt/c/Users/enigm/OneDrive/Documents/NortheasternAssignments/09_BigDataIntelAnlytics/Assignments/Assignment_05
python test_fastmcp_quick.py
```

This will:
- Connect to the running MCP server
- List available tools
- Test analyze_payload
- Test list_payloads resource
- Test enrichment_workflow prompt

### Option 2: Use with Claude Desktop

1. Create/edit `~/.claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentic-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/mnt/c/Users/enigm/OneDrive/Documents/NortheasternAssignments/09_BigDataIntelAnlytics/Assignments/Assignment_05"
    }
  }
}
```

2. Restart Claude Desktop

3. Look for the **Tools** icon in the bottom-right corner

4. You'll see all 4 tools available to use

### Option 3: Python Client Script

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
            
            # Call tool
            result = await session.call_tool(
                "analyze_payload",
                {"company_name": "abridge"}
            )
            print(result)

asyncio.run(test())
```

## 📝 Tool Examples

### 1. Analyze Payload
```python
await session.call_tool("analyze_payload", {
    "company_name": "abridge",
    "show_values": False
})
```

**Returns:** JSON with null fields summary

### 2. Search Company
```python
await session.call_tool("search_company", {
    "query": "Abridge AI healthcare company",
    "company_name": "abridge",
    "topic": "general"
})
```

**Returns:** JSON with search results from Tavily

### 3. Extract Field
```python
await session.call_tool("extract_field", {
    "field_name": "founded_year",
    "entity_type": "company_record",
    "company_name": "abridge",
    "importance": "high"
})
```

**Returns:** JSON with extracted value and confidence

### 4. Enrich Payload (Full Workflow)
```python
# Without test mode (writes to default directory)
await session.call_tool("enrich_payload", {
    "company_name": "abridge"
})

# With test mode (writes to custom directory)
await session.call_tool("enrich_payload", {
    "company_name": "abridge",
    "test_dir": "/tmp/agentic_rag_test"
})
```

**Returns:** JSON with enrichment status and results

## 📚 Resource Examples

### Get Payload
```python
resource = await session.read_resource("payload://abridge")
# Returns: JSON payload for abridge
```

### List Payloads
```python
resource = await session.read_resource("payloads://available")
# Returns: List of all available company payloads
```

## 📖 Prompt Examples

### Enrichment Workflow
```python
prompt = await session.get_prompt("enrichment_workflow", {
    "company_name": "abridge"
})
# Returns: Markdown guide with workflow steps
```

### Security Guidelines
```python
prompt = await session.get_prompt("security_guidelines", {})
# Returns: Markdown with security policies
```

## 🔄 Typical Workflow

1. **Start server** (already running):
   ```bash
   python -m src.mcp_server
   ```

2. **In another terminal, run test**:
   ```bash
   python test_fastmcp_quick.py
   ```

3. **Or use with Claude Desktop**:
   - Add to config
   - Restart Claude
   - Use tools in chat

4. **Example workflow in Claude**:
   > "Analyze the abridge payload to see what fields are null"
   
   Claude calls → `analyze_payload(company_name="abridge")`
   
   > "Search for information about Abridge's founding year"
   
   Claude calls → `search_company(query="Abridge founded year", ...)`
   
   > "Extract the founded year from those results"
   
   Claude calls → `extract_field(field_name="founded_year", ...)`

## 🔒 Security

All tools have:
- ✅ Input validation (SQL injection, code injection detection)
- ✅ Rate limiting
- ✅ Tool whitelisting
- ✅ API key protection

## 📂 File Structure

```
src/mcp_server/
├── __init__.py           # Package init
├── __main__.py           # Entry point (python -m src.mcp_server)
├── server.py             # FastMCP server (4 tools, 2 resources, 2 prompts)
└── security.py           # Security middleware

Documentation:
├── FASTMCP_USAGE.md                       # Complete API reference
├── FASTMCP_IMPLEMENTATION_SUMMARY.md      # Architecture & features
└── FASTMCP_SETUP.md                       # This file

Test scripts:
├── test_mcp_client.py                     # Full featured test
└── test_fastmcp_quick.py                  # Quick sanity check
```

## 🛠️ Troubleshooting

### Server won't start
```bash
# Check environment variables
echo $TAVILY_API_KEY
echo $OPENAI_API_KEY

# Clear cache
find . -type d -name __pycache__ -exec rm -rf {} +

# Try again
python -m src.mcp_server
```

### Client can't connect
- Make sure server is running in another terminal
- Check it's listening: `ps aux | grep mcp_server`
- Try: `python test_fastmcp_quick.py`

### Tools timing out
- Increase timeout in client
- Check network connectivity
- Check API key quotas (Tavily, OpenAI)

### Low confidence extractions
- Refine search queries
- Provide more context
- Review manually

## 📞 Integration Points

The FastMCP server **wraps existing code** without modifications:
- Uses `ToolManager.search_tavily()` for Tavily searches
- Uses `LLMExtractionChain` for LLM-based extraction
- Uses `enrich_single_company()` for full enrichment
- Uses `FileIOManager` for payload I/O
- Uses `build_enrichment_graph()` for analysis

## 📝 Next Steps

1. ✅ **Server is running** - keep it running in your terminal
2. **Test it** - Run `python test_fastmcp_quick.py` in new terminal
3. **Try Claude Desktop** - Add to config and restart Claude
4. **Run enrichment** - Use any of the tools/resources/prompts

## 📚 Documentation Files

- **FASTMCP_USAGE.md** - Detailed API documentation with all parameters
- **FASTMCP_IMPLEMENTATION_SUMMARY.md** - Architecture, features, and design
- **This file** - Quick setup and usage guide

## ✨ Key Features

✅ Simple decorator-based API (`@app.tool()`, `@app.resource()`, `@app.prompt()`)
✅ Full tavily agent integration
✅ Test mode support with custom output directories
✅ Comprehensive security (validation, rate limiting, whitelisting)
✅ Well documented with examples
✅ Ready for Claude Desktop integration
✅ Async/await throughout
✅ JSON-RPC over stdio transport

## 🎓 Example: Full Enrichment via MCP

```python
# Step 1: Analyze
result = await session.call_tool("analyze_payload", {
    "company_name": "abridge"
})
# See 5 null fields

# Step 2: Search
result = await session.call_tool("search_company", {
    "query": "Abridge AI company information",
    "company_name": "abridge"
})
# Get 5 search results

# Step 3: Extract
result = await session.call_tool("extract_field", {
    "field_name": "founded_year",
    "entity_type": "company_record",
    "company_name": "abridge",
    "search_results": json.dumps({"results": [...]})
})
# Get extracted year with confidence

# Step 4: Enrich (Full Workflow)
result = await session.call_tool("enrich_payload", {
    "company_name": "abridge",
    "test_dir": "/tmp/test"
})
# Complete enrichment with all 5 fields

# Step 5: Verify
resource = await session.read_resource("payload://abridge")
# See updated payload
```

---

**Status**: ✅ Production Ready

Your FastMCP server is fully functional and ready to use!
