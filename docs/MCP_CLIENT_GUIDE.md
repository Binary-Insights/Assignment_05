# MCP Enrichment Client - User Guide

## Overview

`mcp_enrichment_client.py` is a command-line client that demonstrates how to use the FastMCP server to enrich company payloads using the Tavily agent. It supports multiple operations with test directory storage.

## Quick Start

### 1. Make sure the server is running
```bash
python -m src.mcp_server
```

### 2. Run the client in a new terminal

```bash
# Basic: Analyze a company payload
python mcp_enrichment_client.py abridge

# Full enrichment with test directory
python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/agentic_rag_test

# Search for information
python mcp_enrichment_client.py abridge --search "founding year"

# Complete workflow (analyze → search → extract → enrich)
python mcp_enrichment_client.py abridge --workflow
```

## Usage Examples

### Example 1: Analyze Payload (Default)
```bash
python mcp_enrichment_client.py abridge
```

**Output:**
```
📊 [ANALYZE] Analyzing payload for abridge...
✅ [ANALYZE] Found 11 null fields
   • company_record: 11 fields
      - brand_name
      - hq_city
      - hq_state
      - ... and 8 more
```

**What it does:**
- Loads the payload for the company
- Analyzes to find null/missing fields
- Shows summary by entity type
- Saves result to `results/mcp_client_results.json`

### Example 2: Full Enrichment
```bash
python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/agentic_rag_test
```

**Output:**
```
⚡ [ENRICH] Starting full enrichment for abridge...
   Max iterations: 20
   Test directory: /tmp/agentic_rag_test
✅ [ENRICH] Enrichment completed
   Status: completed
   Null fields found: 11
   Null fields filled: 10
```

**What it does:**
- Runs the complete enrichment workflow
- Searches for information for each null field
- Extracts values using LLM
- Updates the payload
- Stores results in the test directory
- Saves operation log

### Example 3: Search Only
```bash
python mcp_enrichment_client.py abridge --search "Abridge AI healthcare company"
```

**Output:**
```
🔍 [SEARCH] Searching for: Abridge AI healthcare company...
✅ [SEARCH] Found 5 results
   Result 1: Abridge: AI-powered clinical documentation platform...
   Result 2: Abridge Raises $30M Series B Funding...
   ... and 3 more results
```

**What it does:**
- Searches for company information via Tavily
- Returns top results
- Saves search results to operation log

### Example 4: Extract Field
```bash
python mcp_enrichment_client.py abridge --extract founded_year company_record
```

**Output:**
```
🔗 [EXTRACT] Extracting founded_year from company_record...
✅ [EXTRACT] Extracted: 2019
   Confidence: 95.00%
```

**What it does:**
- Extracts a specific field value
- Uses LLM chain for extraction
- Shows confidence score
- Logs the operation

### Example 5: Complete Workflow
```bash
python mcp_enrichment_client.py abridge --workflow --test-dir /tmp/test
```

**Output:**
```
🔄 [WORKFLOW] Running complete enrichment workflow...

📊 [ANALYZE] Analyzing payload for abridge...
✅ [ANALYZE] Found 11 null fields

🔍 [SEARCH] Searching for: abridge founding information...
✅ [SEARCH] Found 5 results

🔗 [EXTRACT] Extracting founded_year...
✅ [EXTRACT] Extracted: 2019

⚡ [ENRICH] Starting full enrichment...
✅ [ENRICH] Enrichment completed

📄 [PAYLOAD] Retrieving payload for abridge...
✅ [PAYLOAD] Retrieved payload

💾 [SAVE] Saving results to /tmp/test/mcp_client_results.json
✅ [SAVE] Results saved successfully
```

**What it does:**
1. Analyzes payload for null fields
2. Searches for company information
3. Extracts a sample field
4. Runs full enrichment workflow
5. Retrieves updated payload
6. Saves all operations and results

## Command-Line Options

```
usage: mcp_enrichment_client.py [-h] [--test-dir TEST_DIR] [--enrich] 
                                 [--search SEARCH] [--extract FIELD ENTITY]
                                 [--workflow] [--max-iterations MAX_ITERATIONS]
                                 company

positional arguments:
  company                       Company identifier (e.g., 'abridge')

optional arguments:
  -h, --help                    Show help message
  --test-dir TEST_DIR           Test directory for output storage
  --enrich                      Run full enrichment workflow
  --search SEARCH               Search query
  --extract FIELD ENTITY        Extract field from entity (e.g., --extract founded_year company_record)
  --workflow                    Run complete workflow
  --max-iterations MAX_ITERATIONS
                                Max iterations for enrichment (default: 20)
```

## Test Directory Structure

When using `--test-dir`, the client creates:

```
/tmp/agentic_rag_test/
├── mcp_client_results.json       # Operation log and results
```

The `mcp_client_results.json` contains:

```json
{
  "timestamp": "2025-11-16T19:25:27.123456",
  "test_dir": "/tmp/agentic_rag_test",
  "operations": [
    {
      "operation": "analyze_payload",
      "company": "abridge",
      "status": "success",
      "null_fields": 11,
      "fields_by_type": {
        "company_record": [
          {"field_name": "brand_name", "importance": "medium"},
          ...
        ]
      }
    },
    {
      "operation": "search_company",
      "company": "abridge",
      "query": "...",
      "status": "success",
      "result_count": 5
    },
    {
      "operation": "enrich_payload",
      "company": "abridge",
      "status": "completed",
      "null_fields_found": 11,
      "null_fields_filled": 10,
      "success": true
    }
  ]
}
```

## Common Workflows

### Workflow 1: Analyze Before Enriching
```bash
# First, see what needs to be enriched
python mcp_enrichment_client.py abridge

# Then, run enrichment
python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/test
```

### Workflow 2: Search-Driven Enrichment
```bash
# Search for specific information
python mcp_enrichment_client.py abridge --search "Abridge AI company information"

# Search for funding information
python mcp_enrichment_client.py abridge --search "Abridge Series B funding"

# Then run full enrichment with all results
python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/test
```

### Workflow 3: Field-by-Field Extraction
```bash
# Extract specific fields one at a time
python mcp_enrichment_client.py abridge --extract founded_year company_record
python mcp_enrichment_client.py abridge --extract hq_city company_record
python mcp_enrichment_client.py abridge --extract total_raised_usd company_record

# Then verify with full enrichment
python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/test
```

### Workflow 4: Complete Automated Workflow
```bash
# One command does everything
python mcp_enrichment_client.py abridge --workflow --test-dir /tmp/complete_test
```

## Output Files

### Results File
- Location: `{test_dir}/mcp_client_results.json`
- Contains: All operations, results, and metadata
- Updated: After each enrichment operation

### Logs
- Console output: Detailed logging during execution
- Format: Timestamp, logger name, level, message
- Color-coded: ✅ success, ❌ error, 📊 operation

## Error Handling

The client gracefully handles errors:

```bash
# Server not running
❌ Error: Connection refused
   (Make sure the server is running: python -m src.mcp_server)

# Invalid company
❌ Error: Payload not found
   (Make sure the company exists)

# API errors
❌ [SEARCH] Error: API rate limit exceeded
   (Wait and try again)
```

## Tips & Tricks

### Tip 1: Use Test Directories for Safety
```bash
# Always use --test-dir for testing
python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/test
# Outputs go to /tmp/test, not production
```

### Tip 2: Monitor with Multiple Terminals
```bash
# Terminal 1: Run server
python -m src.mcp_server

# Terminal 2: Run client
python mcp_enrichment_client.py abridge --workflow --test-dir /tmp/test

# Terminal 3: Monitor logs
tail -f logs/mcp_server.log
```

### Tip 3: Combine Operations
```bash
# Search multiple terms
python mcp_enrichment_client.py abridge --search "founded"
python mcp_enrichment_client.py abridge --search "headquarters"
python mcp_enrichment_client.py abridge --search "funding"

# Then enrich with all results in mind
python mcp_enrichment_client.py abridge --workflow --test-dir /tmp/test
```

## Troubleshooting

### Issue: "Connection refused"
**Cause**: MCP server is not running
**Solution**: Start the server in another terminal
```bash
python -m src.mcp_server
```

### Issue: "Payload not found"
**Cause**: Company doesn't exist in payloads
**Solution**: Check available companies
```bash
python mcp_enrichment_client.py abridge --list  # List payloads
```

### Issue: "API rate limit exceeded"
**Cause**: Too many API calls to Tavily or OpenAI
**Solution**: Wait a while and retry, or use smaller batches

### Issue: "Low confidence extraction"
**Cause**: LLM couldn't confidently extract the value
**Solution**: Refine search queries or manually review

## Next Steps

1. Try basic analysis: `python mcp_enrichment_client.py abridge`
2. Run search: `python mcp_enrichment_client.py abridge --search "company info"`
3. Run enrichment: `python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/test`
4. Check results: `cat /tmp/test/mcp_client_results.json`
5. Run complete workflow: `python mcp_enrichment_client.py abridge --workflow --test-dir /tmp/test`

## For More Information

- **Server Documentation**: See `FASTMCP_USAGE.md`
- **Architecture Details**: See `FASTMCP_ARCHITECTURE.md`
- **API Reference**: See `FASTMCP_README.md`
