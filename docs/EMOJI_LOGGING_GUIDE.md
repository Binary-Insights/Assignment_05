# Emoji Logging Guide for Agentic RAG

This document describes the comprehensive emoji-based logging system that has been added throughout the Agentic RAG system to help trace tool calls, Tavily responses, and workflow execution.

## Logging Emojis by Category

### 🔧 System & Initialization
- **🔧** - Orchestrator initialization
- **🔍** - Configuration validation
- **✅** - Configuration/setup successful
- **❌** - Configuration/setup failed

### 📊 Data & File Operations
- **📥** - Reading files
- **📝** - Writing/saving files
- **📋** - Backing up files
- **📄** - Processing companies
- **📂** - Directory operations
- **📦** - Batch processing
- **🔎** - Discovering files/companies
- **📚** - Recursion/calculation info

### 🔍 Workflow Analysis
- **🔍** - Analyzing payloads
- **🔰** - Creating state
- **💬** - Building LangGraph
- **📊** - Graph visualization
- **🔬** - Invoking LangGraph
- **🔍** - Checking completion

### 💡 Processing Steps
- **💡** - Extracting values from search results
- **🧠** - LLM calls for extraction
- **🚀** - Starting workflow
- **⏰** - Executing searches (placeholder)

### 🔎 Search & Tool Calls
- **🔍** - Tavily search starting
- **⏳** - Tavily API call in progress
- **✅** - Tavily API call successful
- **📊** - Processing Tavily response
- **📈** - Found list of results
- **📄** - String result
- **💾** - Saving search results
- **🔄** - Batch search execution
- **⚙️** - Creating concurrent tasks
- **🚀** - Executing searches concurrently
- **📋** - Processing search results
- **🧪** - Test mode operations

### ⏱️ Timing & Status
- **⏳** - Timeout operations
- **⏱️** - Timeout errors
- **⏸️** - Paused/blocked state
- **⏹️** - Completed/stopped state

### 🔄 Iteration & Control Flow
- **🔄** - Batch operations
- **🔀** - Selecting next field
- **📝** - Generating queries
- **🔐** - Decision points
- **▶️** - Workflow continuation
- **🛑** - Workflow end/stop

### 🎯 Results & Outcomes
- **🎉** - Enrichment complete
- **📊** - Metrics/results calculation
- **✅** - Successful completion
- **⚠️** - Warnings
- **❌** - Errors
- **🌟** - Initialization complete

### 🧪 Test Mode
- **🧪** - Test mode enabled/in use
- **📝** - Test output paths

### 🔴 Error Handling
- **❌** - Error occurred
- **⚠️** - Warning issued
- **🛑** - Operation stopped
- **⏱️** - Timeout

## Workflow Execution Trace Example

When you run: `python src/tavily_agent/main.py single abridge --test-mode`

You'll see logs like:

```
🔧 [INIT] Initializing Agentic RAG Orchestrator
🔍 [CONFIG] Validating configuration...
✅ [CONFIG] Configuration valid
💬 [GRAPH] Building LangGraph workflow...
✅ [GRAPH] LangGraph workflow built successfully
🌟 [INIT] Orchestrator ready!

📍 [CLI] Enriching single company: abridge
🧪 [TEST MODE] Outputs will be saved to /tmp/agentic_rag_test

📥 [FILE] Reading payload for abridge...
✅ [FILE] Payload loaded successfully
📋 [BACKUP] Backing up original payload...
✅ [BACKUP] Backup complete
🔰 [STATE] Creating enrichment state...
✅ [STATE] State created with 1 null fields

🚀 [WORKFLOW] Starting enrichment workflow...
📚 [RECURSION] Calculating recursion limit...
🔬 [INVOKE] Invoking LangGraph with config...

🔍 [ANALYZE] Starting payload analysis for abridge
   🏢 company_record found
   🏘️  Checking hq_city: None
   ✅ Found null field: hq_city (needs enrichment)
✅ [ANALYZE COMPLETE] Found 1 null fields to enrich

🔄 [NEXT FIELD] Selecting next null field
✅ [NEXT FIELD SELECTED] hq_city

📝 [QUERY GEN] Generating search queries for field: hq_city
✅ [QUERY GEN] Generated 3 search queries

🔍 [TAVILY SEARCH] Starting search for query: 'abridge hq_city'
⏳ [TAVILY] Executing Tavily API call...
✅ [TAVILY] API call successful
📊 [TAVILY RESPONSE] Processing list response...
📈 [TAVILY] Found list with 5 items
   [1] Title: First Result
💾 [TAVILY] Saving 5 results to disk...
✅ [TAVILY] Results saved successfully
🏁 [TAVILY COMPLETE] Query returned 5 results

💡 [EXTRACT] Extracting value for company_record.hq_city
🧠 [LLM] Calling LLM to extract value from search results...
✅ [LLM] LLM extracted value: 'Not disclosed.'
📝 [UPDATE] hq_city: None → 'Not disclosed.'
✅ [EXTRACT COMPLETE] Removed 1 processed fields. Remaining: 0

🔍 [CHECK COMPLETION] Status check:
🛑 [WORKFLOW END] Stopping - no more fields to process

✅ [INVOKE] LangGraph execution completed
✅ [INVOKE COMPLETE] LangGraph execution completed

📊 [METRICS] Updated 1 fields
   ✅ hq_city: 'Not disclosed.'

📝 [FILE] Saving updated payload...
✅ [FILE] Payload saved successfully

🎉 [ENRICH COMPLETE] abridge: 1 fields updated
```

## Log Output Destinations

All logs are saved to:
- **Console**: Real-time streaming output
- **File**: `config/logs/agentic_rag_YYYYMMDD_HHMMSS.log`

## Tracing Tool Calls

With these emoji logs, you can now:

1. **Track Tavily API calls**: Look for 🔍 [TAVILY SEARCH] → ⏳ [TAVILY] API → ✅ [TAVILY] Success
2. **Monitor batch searches**: 🔄 [BATCH] → 🚀 [BATCH] Executing → ✅ [BATCH COMPLETE]
3. **Debug extraction**: 💡 [EXTRACT] → 🧠 [LLM] → 📝 [UPDATE]
4. **Follow workflow**: 🚀 [WORKFLOW] → 🔍 [ANALYZE] → 📝 [QUERY GEN] → 🔍 [TAVILY] → 💡 [EXTRACT]

## Using with LangSmith

These detailed logs will complement LangSmith traces:
- **LangSmith shows**: Chain structure, token usage, latency
- **Console logs show**: Actual tool calls, search results, field updates
- **Together**: Complete visibility into the enrichment process

To view logs while monitoring LangSmith:
```bash
# Terminal 1: Run the enrichment
python src/tavily_agent/main.py single abridge --test-mode

# Terminal 2: Watch the logs
tail -f config/logs/agentic_rag_*.log
```

## Performance Monitoring

Use the recursion limit logs to understand workflow complexity:
```
📚 [RECURSION] Calculating recursion limit:
   - Null fields: 3
   - Steps per field: 6
   - Buffer: 10
   - Calculated: (3 * 6) + 10 = 28
   - Final recursion limit: 33
```

This helps debug issues with:
- **Too many fields**: High recursion limit needed
- **Stuck workflows**: Monitor [NEXT FIELD] and [CHECK COMPLETION] logs
- **Failed searches**: Look for ❌ errors near Tavily logs

## Custom Log Filtering

To filter logs by category:
```bash
# Only Tavily logs
grep "\[TAVILY" config/logs/agentic_rag_*.log

# Only errors
grep "❌" config/logs/agentic_rag_*.log

# Only workflow decisions
grep "\[DECISION\]\|\[RESULT\]" config/logs/agentic_rag_*.log

# Only file operations
grep "\[FILE\]\|\[BACKUP\]" config/logs/agentic_rag_*.log
```

## LangSmith Integration

The logs now provide context for what you see in LangSmith:
- When you see a tool_call in LangSmith, find the corresponding 🔍 [TAVILY] logs
- When you see a token count, correlate it with 📊 [TAVILY RESPONSE] processing
- When extraction fails, check 💡 [EXTRACT] and 🧠 [LLM] logs

## Summary

This comprehensive emoji logging system provides:
- ✅ Real-time visibility into tool execution
- ✅ Clear tracing of Tavily API calls and responses
- ✅ Easy identification of success/failure points
- ✅ Workflow decision tracking
- ✅ Performance and recursion monitoring
- ✅ Seamless integration with LangSmith traces
