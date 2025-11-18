# Quick Start Guide - Agentic RAG System

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file in project root:

```env
# Required API Keys
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
PINECONE_API_KEY=your_pinecone_key

# Optional (defaults provided)
LLM_MODEL=gpt-4o
MAX_ITERATIONS=5
BATCH_SIZE=3
```

### 3. Verify Setup
```bash
python -m src.agents.examples 6
```

Expected output:
```
✓ All required API keys configured
✓ System is ready for use
```

## Running Your First Enrichment

### Option A: Single Company (Recommended for testing)

```bash
python -m src.agents.main single abridge
```

Output:
```json
{
  "company_name": "abridge",
  "status": "completed",
  "null_fields_found": 5,
  "null_fields_filled": 3,
  "iteration": 3
}
```

### Option B: Multiple Companies

```bash
python -m src.agents.main multiple abridge anthropic
```

### Option C: All Companies

```bash
python -m src.agents.main all
```

## Check Results

### View Updated Payload
```bash
cat data/payloads/abridge.json | python -m json.tool | head -50
```

### View Original Payload (Backup)
```bash
cat data/payloads/abridge_v1.json | python -m json.tool
```

### View Raw Search Results
```bash
ls -la data/raw/abridge/tavily/
cat data/raw/abridge/tavily/tavily_20240115_120000.json
```

### Check Execution Logs
```bash
tail -100 data/logs/agentic_rag_*.log
```

### View Summary Report
```bash
cat data/logs/execution_summary_*.json | python -m json.tool
```

## Python API Usage

### Simple Script

```python
import asyncio
from src.agents import enrich_single_company

async def main():
    result = await enrich_single_company("abridge")
    print(f"Status: {result['status']}")
    print(f"Fields filled: {result['null_fields_filled']}")

asyncio.run(main())
```

Save as `enrich.py`, then run:
```bash
python enrich.py
```

### Batch Processing Script

```python
import asyncio
from src.agents import enrich_multiple_companies

async def main():
    companies = ["abridge", "anthropic", "openai"]
    summary = await enrich_multiple_companies(companies)
    
    print(f"\nSuccessful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    
    for result in summary['results']:
        if result['status'] == 'completed':
            print(f"✓ {result['company_name']}: {result['null_fields_filled']} fields")

asyncio.run(main())
```

## Monitoring Progress

### Real-time Logs
```bash
# Terminal 1: Start enrichment
python -m src.agents.main all

# Terminal 2: Monitor logs
tail -f data/logs/agentic_rag_*.log
```

### Check Vector DB
```python
import asyncio
from src.agents import VectorDBManager

async def check_vectors():
    db = VectorDBManager()
    results = await db.search("funding", "abridge", top_k=3)
    print(f"Found {len(results)} vectors")
    for r in results:
        print(f"  - {r['metadata']['source']}")

asyncio.run(check_vectors())
```

## Common Issues & Solutions

### Issue: "OPENAI_API_KEY not found"
**Solution:**
```bash
# Check .env file exists
cat .env | grep OPENAI_API_KEY

# If empty, add it
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Issue: "Index not found"
**Solution:**
```bash
# Check Pinecone index exists
python -c "from pinecone import Pinecone; p = Pinecone(); print(p.list_indexes())"

# If missing, create it through Pinecone console
```

### Issue: "Timeout error from Tavily"
**Solution:**
```env
# Increase timeout in .env
TOOL_TIMEOUT=60  # seconds
```

### Issue: "Duplicate vectors in Pinecone"
**Solution:**
```env
# Ensure deduplication is enabled
DEDUP_CHECK_ENABLED=true
```

## Performance Tuning

### For Speed (Quick Testing)
```env
MAX_ITERATIONS=2
BATCH_SIZE=5
LLM_TEMPERATURE=0.5  # Faster, less creative
```

### For Quality (Thorough Enrichment)
```env
MAX_ITERATIONS=10
BATCH_SIZE=1
LLM_TEMPERATURE=0.3  # Slower, more precise
```

### For Large Batch Processing
```env
MAX_ITERATIONS=5
BATCH_SIZE=10  # Process 10 companies in parallel
TOOL_TIMEOUT=45
```

## Understanding Output Files

### Payload Structure (Updated)
```
data/payloads/
├── abridge.json              # Current version (updated)
├── abridge_v1.json           # Version 1 (original backup)
└── abridge_v2.json           # Version 2 (previous state)
```

### Raw Search Results
```
data/raw/
├── abridge/
│   ├── tavily/
│   │   ├── tavily_20240115_120000.json  # First search session
│   │   └── tavily_20240115_120530.json  # Second search session
│   └── <other_tools>/
```

### Logs and Summaries
```
data/logs/
├── agentic_rag_20240115_120000.log     # Full execution log
└── execution_summary_20240115_120000.json  # Results summary
```

## Next Steps

1. **Read Full Documentation**: See [README.md](README.md)
2. **Explore Examples**: `python src/agents/examples.py`
3. **Check API Reference**: Section in README.md
4. **Monitor Performance**: Review execution summaries
5. **Customize Prompts**: Edit graph.py for domain-specific extraction
6. **Integrate with Pipeline**: Import modules in your workflow

## Getting Help

### View Detailed Logs
```bash
python -c "
import json
with open('data/logs/execution_summary_*.json') as f:
    summary = json.load(f)
    for r in summary['results']:
        print(f'{r[\"company_name\"]}: {r[\"status\"]}')
        for e in r.get('errors', []):
            print(f'  ERROR: {e}')
"
```

### Debug Single Company
```python
import asyncio
import logging
from src.agents import enrich_single_company

logging.basicConfig(level=logging.DEBUG)

async def debug():
    result = await enrich_single_company("abridge")
    print(result)

asyncio.run(debug())
```

### Check Payload Changes
```bash
python -c "
import json
from src.agents import PayloadAnalyzer

with open('data/payloads/abridge_v1.json') as f:
    original = json.load(f)
    
with open('data/payloads/abridge.json') as f:
    updated = json.load(f)

analyzer = PayloadAnalyzer()
changes = analyzer.compare_payloads(original, updated)
print(json.dumps(changes, indent=2))
"
```

## Support Resources

- **Documentation**: `src/agents/README.md`
- **Examples**: `src/agents/examples.py`
- **API Docs**: See README API Reference section
- **Issues**: Check logs in `data/logs/`
- **Configuration**: See `.env` options in README

## Ready to Start?

```bash
# 1. Set up .env with API keys
# 2. Run single test
python -m src.agents.main single abridge
# 3. Check results
cat data/payloads/abridge.json | python -m json.tool
# 4. View summary
cat data/logs/execution_summary_*.json | python -m json.tool
```

Good luck! 🚀
