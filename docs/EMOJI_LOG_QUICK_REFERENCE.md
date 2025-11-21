# 🎨 Emoji Logging Quick Reference

## Core Emojis You'll See

### Tavily Search Execution
```
🔍 [TAVILY SEARCH] Starting search for query
  ⏳ [TAVILY] Executing API call...
    📊 [TAVILY RESPONSE] Processing response
      📈 [TAVILY] Found list with N items
        [1] Title: Result Title
        [2] Title: Another Result
    💾 [TAVILY] Saving N results to disk...
  ✅ [TAVILY] API call successful
  ✅ [TAVILY] Results saved successfully
🏁 [TAVILY COMPLETE] Query returned N results
```

### Batch Search
```
🔄 [BATCH SEARCH] Starting batch with N queries
  ⚙️  [BATCH] Creating N concurrent tasks
  🚀 [BATCH] Executing N searches concurrently...
    (Individual searches execute in parallel)
  ✅ [BATCH] All N searches completed
📋 [BATCH] Processing N search results...
  [1] ✅ 'query1': 5 results
  [2] ✅ 'query2': 3 results
📊 [BATCH COMPLETE] Success: 2, Failed: 0
```

### Workflow State
```
🚀 [WORKFLOW] Starting enrichment workflow...
🔍 [ANALYZE] Starting payload analysis
  ✅ [ANALYZE COMPLETE] Found 1 null fields

🔄 [NEXT FIELD] Selecting next null field
  ✅ [NEXT FIELD SELECTED] hq_city

📝 [QUERY GEN] Generating search queries
  ✅ [QUERY GEN] Generated 3 search queries

🔍 [EXECUTE SEARCH] Executing N search queries...
  ✅ [EXECUTE SEARCH] Search results ready

💡 [EXTRACT] Extracting value...
  🧠 [LLM] Calling LLM to extract value...
  ✅ [LLM] LLM extracted value: 'value'
  📝 [UPDATE] field: old_value → new_value
  ✅ [EXTRACT COMPLETE] Removed 1 fields

🔍 [CHECK COMPLETION] Status check...
  ▶️  [WORKFLOW CONTINUE] N fields remaining
  (or)
  🛑 [WORKFLOW END] Stopping - completed
```

### File Operations
```
📥 [FILE] Reading payload...
  ✅ [FILE] Payload loaded successfully

📋 [BACKUP] Backing up original payload...
  ✅ [BACKUP] Backup complete

📝 [FILE] Saving updated payload...
  ✅ [FILE] Payload saved successfully
```

### Processing Summary
```
📊 [METRICS] Updated N fields
  ✅ field1: value1
  ✅ field2: value2

📦 [BATCH] Processing batch of N companies
  🔄 [BATCH] Processing batch 1/3 (N companies)...

✅ [BATCH COMPLETE] Success: N, Failed: N
```

## Emoji Meanings

| Emoji | Meaning | Category |
|-------|---------|----------|
| 🔍 | Search/Find | Investigation |
| ⏳ | In Progress/Loading | Timing |
| ✅ | Success/Done | Positive |
| ❌ | Error/Failed | Negative |
| 📊 | Data/Chart | Information |
| 💾 | Save/Store | File Ops |
| 🧠 | AI/LLM | Processing |
| 🚀 | Launch/Start | Action |
| 🔄 | Batch/Loop | Control Flow |
| 📝 | Write/Update | File Ops |
| 📥 | Read/Input | File Ops |
| 📋 | Backup/List | File Ops |
| 💡 | Insight/Extract | Analysis |
| ⚙️ | Setup/Config | System |
| 🛑 | Stop/End | Control Flow |
| ▶️ | Continue | Control Flow |
| ⚠️ | Warning | Alert |
| 🌟 | Complete/Ready | Success |
| 🎉 | Celebration/Done | Success |

## Log Levels

### INFO Logs (Most Important)
```
✅ Success indicators
🔍 Starting new operations
🚀 Major workflow steps
❌ Errors (critical)
```

### DEBUG Logs (Details)
```
📊 Detailed metrics
📈 Data breakdowns
Individual search results
Field values
```

## Reading the Logs

### Example: Complete Execution
```
[16:45:32] 🔍 [TAVILY SEARCH] Starting search for query: 'abridge hq_city'
[16:45:32] ⏳ [TAVILY] Executing Tavily API call (timeout: 30s)...
[16:45:34] ✅ [TAVILY] API call successful
[16:45:34] 📊 [TAVILY RESPONSE] Processing list response...
[16:45:34] 📈 [TAVILY] Found list with 5 items
[16:45:34]    [1] Title: Abridge Careers
[16:45:34]    [2] Title: Abridge Company Info
[16:45:34] 💾 [TAVILY] Saving 5 results to disk...
[16:45:34] ✅ [TAVILY] Results saved successfully
[16:45:34] 🏁 [TAVILY COMPLETE] Query 'abridge hq_city' returned 5 results
```

### Example: Error During Search
```
[16:45:35] 🔍 [TAVILY SEARCH] Starting search for query: 'abridge hq_city'
[16:45:35] ⏳ [TAVILY] Executing Tavily API call (timeout: 30s)...
[16:45:65] ⏱️  [TAVILY ERROR] Search timed out after 30s for query: 'abridge hq_city'
```

### Example: Batch Processing
```
[16:45:00] 📦 [BATCH] Processing batch of 3 companies: abridge, acme, xyz
[16:45:00] 🔄 [BATCH] Processing batch 1/1 (3 companies)...
[16:45:05]    ✅ abridge: completed (1/1 fields)
[16:45:08]    ✅ acme: completed (2/2 fields)
[16:45:12]    ❌ xyz: failed - Could not read payload file
[16:45:12] ✅ [BATCH COMPLETE] Success: 2, Failed: 1
```

## Troubleshooting with Logs

### Problem: No Tavily Results
Look for:
```
🔍 [TAVILY SEARCH] ...
❌ [TAVILY ERROR] ...
```
Check the error message and timeout setting.

### Problem: Workflow Stuck
Look for:
```
🔍 [CHECK COMPLETION] Status check...
🛑 [WORKFLOW END] ...  ← Is this appearing?
```
If not, workflow may be in infinite loop - check recursion limit.

### Problem: Fields Not Updating
Look for:
```
📝 [UPDATE] field: old_value → new_value
```
If not appearing, check if extraction succeeded:
```
💡 [EXTRACT] ...
🧠 [LLM] LLM extracted value: ...
```

### Problem: Backup Files Not Created
Look for:
```
📋 [BACKUP] Backing up original payload...
✅ [BACKUP] Backup complete
```
If ✅ not appearing, check file system permissions.

## Real-Time Monitoring

### Watch logs as they happen:
```bash
# On Mac/Linux
tail -f config/logs/agentic_rag_*.log

# On Windows PowerShell
Get-Content config/logs/agentic_rag_*.log -Wait
```

### Filter by operation:
```bash
# Only Tavily searches
grep "TAVILY" config/logs/agentic_rag_*.log | grep -v DEBUG

# Only errors
grep "❌\|ERROR" config/logs/agentic_rag_*.log

# Only batch operations
grep "BATCH" config/logs/agentic_rag_*.log
```

### Combine with LangSmith:
1. Run: `python src/tavily_agent/main.py single abridge --test-mode`
2. Watch: `tail -f config/logs/agentic_rag_*.log`
3. Monitor: Open LangSmith UI in browser for chain traces
4. Correlate: Match emoji logs with LangSmith timeline

## Performance Indicators

### Fast Execution (< 5 seconds)
```
✅ [TAVILY] API call successful  ← Quick response
📈 [TAVILY] Found list with 5 items  ← Got results immediately
✅ [EXTRACT COMPLETE] Removed 1 fields  ← Fast processing
```

### Slow Execution (> 30 seconds)
```
⏳ [TAVILY] Executing Tavily API call (timeout: 30s)...  ← Check timeout
📚 [RECURSION] Calculating recursion limit: ... 100+  ← Many fields
```

### Timeout Errors
```
⏱️  [TAVILY ERROR] Search timed out after 30s  ← Network/API issue
🛑 [WORKFLOW END] Reached max iterations  ← Too many fields
```
