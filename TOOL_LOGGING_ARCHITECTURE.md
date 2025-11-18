# 📊 Complete Tool Logging Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INPUT                           │
│     python src/tavily_agent/main.py single abridge          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   MAIN ORCHESTRATOR                          │
│              src/tavily_agent/main.py                       │
│                                                             │
│  🔧 [INIT] Initializing...                                 │
│  📥 [FILE] Reading payload for abridge                     │
│  🔰 [STATE] Creating enrichment state                      │
│  🚀 [WORKFLOW] Starting enrichment workflow                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              LANGGRAPH WORKFLOW NODES                       │
│            src/tavily_agent/graph.py                       │
│                                                             │
│  ┌─────────────────────────────────────────┐              │
│  │  1. analyze_payload()                   │              │
│  │  ✅ FIXED: Now checks 4 fields         │              │
│  │  🔍 [ANALYZE] Starting analysis...     │              │
│  │     🏷️  hq_city: None → NEEDS ENRICHMENT │              │
│  │     🏷️  hq_country: None → NEEDS ENRICHMENT │              │
│  │  ✅ [ANALYZE COMPLETE] Found 2 fields  │              │
│  └────────────────┬────────────────────────┘              │
│                   │                                        │
│  ┌────────────────▼────────────────────┐                  │
│  │  2. get_next_null_field()           │                  │
│  │  🔄 [NEXT FIELD] Selecting...       │                  │
│  │  ✅ [NEXT FIELD SELECTED] hq_city   │                  │
│  └────────────────┬────────────────────┘                  │
│                   │                                        │
│  ┌────────────────▼────────────────────┐                  │
│  │  3. generate_search_queries()       │                  │
│  │  📝 [QUERY GEN] Generating...       │                  │
│  │  ✅ [QUERY GEN] Generated 3 queries │                  │
│  └────────────────┬────────────────────┘                  │
│                   │                                        │
│  ┌────────────────▼────────────────────┐                  │
│  │  4. execute_searches()              │                  │
│  │  ✅ FIXED: Better logging           │                  │
│  │  🔎 [EXECUTE SEARCH] Ready...       │                  │
│  │  📊 Tool execution in async context │                  │
│  └────────────────┬────────────────────┘                  │
│                   │                                        │
│                   ▼ (Tool calls happen here)              │
│  ┌────────────────────────────────────┐                   │
│  │  5. extract_and_update_payload()   │                   │
│  │  💡 [EXTRACT] Extracting...        │                   │
│  │  🧠 [LLM] Calling LLM...           │                   │
│  │  📝 [UPDATE] hq_city: None → ...   │                   │
│  │  ✅ [EXTRACT COMPLETE] Done        │                   │
│  └────────────────┬────────────────────┘                   │
│                   │                                        │
│  ┌────────────────▼────────────────────┐                   │
│  │  6. check_completion()              │                   │
│  │  🔍 [CHECK COMPLETION] Status check │                   │
│  │  ▶️  [WORKFLOW CONTINUE] or 🛑 END │                   │
│  └─────────────────────────────────────┘                   │
│                                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    TOOL MANAGER                             │
│             src/tavily_agent/tools.py                      │
│   THIS IS WHERE TAVILY LOGS APPEAR! 🎯                     │
│                                                             │
│  search_tavily()                                           │
│  ├─ 🔍 [TAVILY SEARCH] Starting search...               │
│  ├─ ⏳ [TAVILY] Executing Tavily API call...            │
│  ├─ 📊 [TAVILY RESPONSE] Processing response...         │
│  ├─ 📈 [TAVILY] Found list with 5 items                │
│  │  ├─ [1] Title: Result 1                            │
│  │  ├─ [2] Title: Result 2                            │
│  │  └─ [3] Title: Result 3                            │
│  ├─ 💾 [TAVILY] Saving 5 results to disk...            │
│  ├─ ✅ [TAVILY] Results saved successfully             │
│  └─ 🎯 [TAVILY COMPLETE] Query returned 5 results      │
│                                                             │
│  execute_batch_searches()                                  │
│  ├─ 🔄 [BATCH SEARCH] Starting batch...                │
│  ├─ 🚀 [BATCH] Executing 3 searches concurrently...    │
│  ├─ 📋 [BATCH] Processing 3 search results...          │
│  │  ├─ [1] ✅ 'query1': 5 results                     │
│  │  ├─ [2] ✅ 'query2': 4 results                     │
│  │  └─ [3] ✅ 'query3': 3 results                     │
│  └─ 📊 [BATCH COMPLETE] Success: 3, Failed: 0          │
│                                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   LOG OUTPUTS                               │
│                                                             │
│  🔵 CONSOLE (Real-time streaming)                          │
│     └─ Shows all logs as they happen                       │
│        🔍 [TAVILY SEARCH] Starting search...               │
│                                                             │
│  🟢 LANGSMITH (Trace events)                               │
│     └─ Shows tool_use events                               │
│        ├─ tool_use: tavily_search                          │
│        └─ tool_result: 5 items returned                    │
│                                                             │
│  🟡 LOG FILES (config/logs/agentic_rag_*.log)              │
│     └─ Persistent record of all logs                       │
│        All console logs saved to file                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow with Logging

```
INPUT: abridge payload (hq_city: null, hq_country: null)
   │
   ▼ 📥 [FILE] Reading payload
   │
   ▼ 🔰 [STATE] Creating state with 2 null fields
   │
   ▼ 🚀 [WORKFLOW] Starting workflow
   │
   ├─→ 🔍 [ANALYZE] Checking fields
   │   ├─ hq_city: None → ✅ NEEDS ENRICHMENT
   │   └─ hq_country: None → ✅ NEEDS ENRICHMENT
   │
   ├─→ 🔄 [NEXT FIELD] Get hq_city
   │
   ├─→ 📝 [QUERY GEN] Generate queries
   │   ├─ abridge hq_city
   │   ├─ abridge company hq_city
   │   └─ hq_city abridge
   │
   ├─→ 🔎 [EXECUTE SEARCH] Execute queries
   │   │
   │   └─→ 🔍 [TAVILY SEARCH] Call Tavily API
   │       ├─ ⏳ [TAVILY] Executing...
   │       ├─ ✅ [TAVILY] Success
   │       ├─ 📊 [TAVILY RESPONSE] Processing
   │       ├─ 📈 [TAVILY] Found 5 items
   │       │  ├─ Abridge Headquarters
   │       │  ├─ Abridge HQ Location
   │       │  └─ Abridge Company Info
   │       ├─ 💾 [TAVILY] Saving
   │       └─ 🎯 [TAVILY COMPLETE] Done
   │
   ├─→ 💡 [EXTRACT] Extract values
   │   ├─ 🧠 [LLM] Call LLM
   │   ├─ ✅ [LLM] Got: "San Francisco"
   │   └─ 📝 [UPDATE] hq_city: None → "San Francisco"
   │
   ├─→ 🔄 [NEXT FIELD] Get hq_country
   │
   ├─→ (Repeat QUERY GEN → TAVILY SEARCH → EXTRACT)
   │   └─ ✅ [LLM] Got: "United States"
   │   └─ 📝 [UPDATE] hq_country: None → "United States"
   │
   └─→ 🔍 [CHECK COMPLETION] No more fields
       └─ 🛑 [WORKFLOW END] Stop
   
OUTPUT: abridge_updated payload (hq_city: "San Francisco", hq_country: "United States")
   │
   ▼ 📝 [FILE] Saving payload
   │
   ▼ 📊 [METRICS] 2 fields updated
   │
   ▼ 🎉 [ENRICH COMPLETE] Done!

RESULTS CAPTURED IN:
   ├─ Console (real-time)
   ├─ LangSmith (tool_use events)
   └─ Log files (persistent record)
```

## Emoji Flow for Tool Execution

### Before (Broken - No tool logs)
```
🔍 [ANALYZE]      ← Analyzed, found 0 fields
🔄 [NEXT FIELD]   ← No fields, stopped
🛑 [WORKFLOW END] ← Done
❌ NO TAVILY LOGS
```

### After (Fixed - With tool logs)
```
🔍 [ANALYZE]        ← Found 2 fields
🔄 [NEXT FIELD]     ← Selected hq_city
📝 [QUERY GEN]      ← Generated 3 queries
🔎 [EXECUTE SEARCH] ← Ready for tools

🔍 [TAVILY SEARCH]  ← Tool call begins
⏳ [TAVILY]         ← API executing
✅ [TAVILY]         ← API success
📊 [TAVILY RESPONSE]← Processing response
📈 [TAVILY]         ← Found items
💾 [TAVILY]         ← Saving results
✅ [TAVILY]         ← Save success
🎯 [TAVILY COMPLETE]← Done with this query

💡 [EXTRACT]        ← Extracting value
🧠 [LLM]            ← LLM call
📝 [UPDATE]         ← Field updated

(Loop back for next field...)

🛑 [WORKFLOW END]   ← All fields processed
📊 [METRICS]        ← 2 fields updated
🎉 [ENRICH COMPLETE]← Success!
```

## Where Each Log Type Appears

| Log Type | Source | Destination | Emoji |
|----------|--------|-------------|-------|
| Orchestration | main.py | Console + File | 🔧📄 |
| Workflow nodes | graph.py | Console + File | 🔍🔄📝 |
| **Tool execution** | **tools.py** | **Console + File + LangSmith** | **🔍⏳📊** |
| Extraction | graph.py | Console + File | 💡🧠📝 |
| Completion | main.py | Console + File | 🎉📊 |

## Configuration Points

### Enable All Logging
```python
# src/tavily_agent/main.py
LOG_LEVEL = "INFO"        # Shows all important logs
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Enable LangSmith
```bash
# .env
LANGSMITH_TRACING_V2=true
LANGSMITH_PROJECT="agentic-rag-enrichment"
```

### Run with Test Mode
```bash
python src/tavily_agent/main.py single abridge --test-mode
# Test mode outputs to /tmp/agentic_rag_test
```

## Summary

**Architecture shows:**
1. ✅ Workflow nodes in graph.py
2. ✅ Tool manager in tools.py (WHERE TAVILY LOGS COME FROM)
3. ✅ Orchestrator in main.py
4. ✅ Logs flow to 3 destinations (Console, LangSmith, Files)

**Key insight:**
- Console shows real-time logs
- LangSmith shows tool_use events
- Log files persist everything

**Before fix:**
- analyze_payload() checked 1 field → 0 found → No tools

**After fix:**
- analyze_payload() checks 4 fields → 2 found → Tools execute → Logs appear!
