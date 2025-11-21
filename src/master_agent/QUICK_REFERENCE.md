# Master Orchestrator - Quick Reference

## 🚀 Usage

### Basic Commands

```bash
# Full enrichment (both agents)
python src/master_agent/master_orchestrator.py abridge

# Tavily only (company_record fields)
python src/master_agent/master_orchestrator.py abridge --tavily-only

# Payload only (entities: events, products, leadership, etc.)
python src/master_agent/master_orchestrator.py abridge --payload-only

# Verbose logging
python src/master_agent/master_orchestrator.py abridge --verbose
```

## 📊 What Gets Enriched

### Phase 1: Tavily Agent (Web Search)
**Target**: `company_record` fields
- `brand_name`, `hq_city`, `hq_state`, `hq_country`
- `founded_year`, `categories`
- `total_raised_usd`, `last_disclosed_valuation_usd`
- `last_round_name`, `last_round_date`

### Phase 2: Payload Agent (Pinecone Vector Search)
**Target**: Entity arrays
- `events[]` - funding, partnerships, product releases
- `products[]` - product details, pricing
- `leadership[]` - executives, founders
- `snapshots[]` - headcount, job openings
- `visibility[]` - news mentions, ratings

## 🔄 Versioning

```
First run:  → abridge.json
Second run: → abridge_v1.json (backup) + abridge.json (new)
Third run:  → abridge_v2.json (backup) + abridge.json (new)
```

## 📁 Output Locations

- **Payload**: `data/payloads/{company_id}.json`
- **Backups**: `data/payloads/{company_id}_v*.json`
- **Logs**: `data/logs/master_orchestrator_*.log`

## 🔑 Required Environment Variables

```bash
# Tavily Agent
TAVILY_API_KEY=your_key
OPENAI_API_KEY=your_key

# Payload Agent
PINECONE_API_KEY=your_key
PINECONE_ENVIRONMENT=your_env
PINECONE_INDEX_NAME=your_index

# Optional: LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=your_key
LANGCHAIN_PROJECT=master-orchestrator
```

## ⚡ Quick Examples

### Enrich Single Company
```bash
python src/master_agent/master_orchestrator.py world_labs
```

### Debug Mode
```bash
python src/master_agent/master_orchestrator.py world_labs --verbose 2>&1 | tee debug.log
```

### Test Tavily Agent Only
```bash
python src/master_agent/master_orchestrator.py world_labs --tavily-only
```

### Test Payload Agent Only
```bash
python src/master_agent/master_orchestrator.py world_labs --payload-only
```

## 📈 Expected Output

```
🚀 MASTER ORCHESTRATOR - Starting enrichment for abridge
   Tavily Agent: ✅ ENABLED
   Payload Agent: ✅ ENABLED

📡 PHASE 1: TAVILY AGENT
📊 Tavily Agent Results:
   Status: success
   Fields enriched: 8

🔍 PHASE 2: PAYLOAD AGENT
📊 Payload Agent Results:
   Status: success
   Fields filled: 12

🔄 MERGING RESULTS
📊 Final Payload Statistics:
   Company record fields filled: 20
   Total entities: 45
      - Events: 15
      - Products: 8
      - Leadership: 12
      - Snapshots: 7
      - Visibility: 3

⏱️  Execution Time: 127.45 seconds
✅ MASTER ORCHESTRATOR COMPLETE
```

## 🐛 Troubleshooting

### Check Logs
```bash
tail -f data/logs/master_orchestrator_*.log
```

### Verify Payload
```bash
python -m json.tool data/payloads/abridge.json | head -50
```

### Test Individual Agents

Tavily Agent:
```bash
python src/tavily_agent/main.py single abridge
```

Payload Agent:
```bash
python src/payload_agent/payload_workflow.py abridge
```

## 🔗 Related Commands

### Check Pinecone Index
```bash
curl -s http://localhost:6333/collections/world_labs_chunks | python -m json.tool
```

### Verify Environment Variables
```bash
python -c "import os; print('Tavily:', bool(os.getenv('TAVILY_API_KEY'))); print('Pinecone:', bool(os.getenv('PINECONE_API_KEY')))"
```

## 📚 Documentation

- **Full Guide**: `src/master_agent/README.md`
- **Tavily Agent**: `src/tavily_agent/README.md`
- **Payload Agent**: `src/payload_agent/README.md`
