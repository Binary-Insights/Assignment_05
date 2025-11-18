# 🎬 What to Expect: Complete Execution Flow with Tool Logs

## Complete Example: Running with Tavily Tools

### Command
```bash
python src/tavily_agent/main.py single abridge --test-mode
```

### Expected Output (WITH TOOL LOGS)

#### Phase 1: Initialization
```
======================================================================
🔧 [INIT] Initializing Agentic RAG Orchestrator
======================================================================
🔍 [CONFIG] Validating configuration...
✅ [CONFIG] Configuration valid
💬 [GRAPH] Building LangGraph workflow...
✅ [GRAPH] LangGraph workflow built successfully
📊 [GRAPH] Graph visualization saved
🌟 [INIT] Orchestrator ready!
```

#### Phase 2: File Operations
```
======================================================================
📄 [ENRICH] Processing abridge
======================================================================
📥 [FILE] Reading payload for abridge...
✅ [FILE] Payload loaded successfully
📋 [BACKUP] Backing up original payload...
✅ [BACKUP] Backup complete
```

#### Phase 3: Payload Analysis (CHANGED - Now checks multiple fields)
```
🔰 [STATE] Creating enrichment state...
✅ [STATE] State created with 2 null fields

🚀 [WORKFLOW] Starting enrichment workflow...

🔍 [ANALYZE] Starting payload analysis for abridge
   Company ID: abridge_xyz
   📦 company_record found with 47 fields
   🔎 Checking 4 fields for null values...
   🏷️  hq_city: None
      ✅ NEEDS ENRICHMENT
   🏷️  hq_country: None
      ✅ NEEDS ENRICHMENT
   🏷️  description: 'AI company'
      ⏭️  Already has value (skip)
   🏷️  founded_year: 2020
      ⏭️  Already has value (skip)
✅ [ANALYZE COMPLETE] Found 2 null fields to enrich
```

#### Phase 4: First Field Processing
```
🔄 [NEXT FIELD] Selecting next null field
   Iteration: 0/10
   Remaining fields: 2
✅ [NEXT FIELD SELECTED] hq_city (iteration 1/10, 1 remaining)

📝 [QUERY GEN] Generating search queries for field: hq_city
   Company: abridge, Field type: company_record
✅ [QUERY GEN] Generated 3 search queries:
   [1] abridge hq_city
   [2] abridge company hq_city
   [3] hq_city abridge
```

#### Phase 5: Tool Execution (THIS IS WHERE YOU SEE TAVILY LOGS)
```
🔎 [EXECUTE SEARCH] Executing 3 search queries...
   [1] abridge hq_city
   [2] abridge company hq_city
   [3] hq_city abridge
⏳ [EXECUTE SEARCH] Tool execution happens in async context
   📊 Tavily API calls will appear as:
      - tool_use events in LangSmith
      - 🔍 [TAVILY SEARCH] logs when called
      - Real API responses will be captured
   ℹ️  This is sync wrapper - actual async execution happens elsewhere
✅ [EXECUTE SEARCH] Ready to invoke tool_use (see LangSmith for actual calls)

--- ACTUAL TOOL LOGS (FROM ASYNC EXECUTION) ---
🔍 [TAVILY SEARCH] Starting search for query: 'abridge hq_city'
   Company: abridge, Topic: general
⏳ [TAVILY] Executing Tavily API call (timeout: 30s)...
✅ [TAVILY] API call successful
📊 [TAVILY RESPONSE] Processing list response...
📈 [TAVILY] Found list with 5 items
   [1] Title: Abridge - Medical AI Company
       Content preview: Abridge is an AI platform for healthcare...
   [2] Title: Abridge Company Headquarters
       Content preview: Abridge's headquarters are located in...
   [3] Title: Abridge News and Updates
       Content preview: Latest news from Abridge, the AI company...
   [4] Title: Abridge Career Opportunities
       Content preview: Join Abridge, located in San Francisco...
   [5] Title: Abridge Market Analysis
       Content preview: Abridge is a leading AI healthcare company...
💾 [TAVILY] Saving 5 results to disk...
✅ [TAVILY] Results saved successfully
🎯 [TAVILY COMPLETE] Query 'abridge hq_city' returned 5 results

🔍 [TAVILY SEARCH] Starting search for query: 'abridge company hq_city'
⏳ [TAVILY] Executing Tavily API call (timeout: 30s)...
✅ [TAVILY] API call successful
📊 [TAVILY RESPONSE] Processing list response...
📈 [TAVILY] Found list with 4 items
   [1] Title: Abridge Headquarters Information
   ... (similar to above)
🎯 [TAVILY COMPLETE] Query returned 4 results

🔍 [TAVILY SEARCH] Starting search for query: 'hq_city abridge'
⏳ [TAVILY] Executing Tavily API call (timeout: 30s)...
✅ [TAVILY] API call successful
... (similar results)
🎯 [TAVILY COMPLETE] Query returned 3 results

🔄 [BATCH SEARCH] Starting batch search with 3 queries
   [1/3] abridge hq_city
   [2/3] abridge company hq_city
   [3/3] hq_city abridge
✅ [BATCH] All 3 searches completed
📋 [BATCH] Processing 3 search results...
   [1] ✅ 'abridge hq_city': 5 results
   [2] ✅ 'abridge company hq_city': 4 results
   [3] ✅ 'hq_city abridge': 3 results
📊 [BATCH COMPLETE] Success: 3, Failed: 0, Total documents: 12
--- END TAVILY LOGS ---
```

#### Phase 6: Value Extraction
```
💡 [EXTRACT] Extracting value for company_record.hq_city (index: 0)
   Search results available: 12 documents
🧠 [LLM] Calling LLM to extract value from search results...
✅ [LLM] LLM extracted value: 'San Francisco, California'
📝 [UPDATE] hq_city: None → 'San Francisco, California'
   Tracked: extracted_values[hq_city] = 'San Francisco, California'
✅ [EXTRACT COMPLETE] Removed 1 processed fields. Remaining: 1
```

#### Phase 7: Continue Loop
```
🔄 [NEXT FIELD] Selecting next null field
   Iteration: 1/10
   Remaining fields: 1
✅ [NEXT FIELD SELECTED] hq_country (iteration 2/10, 0 remaining)

📝 [QUERY GEN] Generating search queries for field: hq_country
✅ [QUERY GEN] Generated 3 search queries:
   [1] abridge hq_country
   [2] abridge company hq_country
   [3] hq_country abridge

🔎 [EXECUTE SEARCH] Executing 3 search queries...

--- TAVILY LOGS FOR SECOND FIELD ---
🔍 [TAVILY SEARCH] Starting search for query: 'abridge hq_country'
⏳ [TAVILY] Executing Tavily API call...
✅ [TAVILY] API call successful
📊 [TAVILY RESPONSE] Processing list response...
📈 [TAVILY] Found list with 5 items
   [1] Title: Abridge is a USA-based AI company...
🎯 [TAVILY COMPLETE] Query returned 5 results
... (3 more searches)
```

#### Phase 8: Workflow Completion
```
🔍 [CHECK COMPLETION] Status check:
   Status: initialized
   Iteration: 2/10
   Remaining fields: 0
🛑 [WORKFLOW END] Stopping - no more fields to process
```

#### Phase 9: Metrics & Summary
```
📊 [METRICS] Updated 2 fields
   ✅ hq_city: 'San Francisco, California'
   ✅ hq_country: 'United States'

📝 [FILE] Saving updated payload...
✅ [FILE] Payload saved successfully

🎉 [ENRICH COMPLETE] abridge: 2 fields updated
======================================================================
```

#### Phase 10: JSON Result
```json
{
  "company_name": "abridge",
  "status": "completed",
  "timestamp": "2025-11-15T03:15:22.123456+00:00",
  "null_fields_found": 2,
  "null_fields_filled": 2,
  "errors": [],
  "extracted_fields": {
    "hq_city": "San Francisco, California",
    "hq_country": "United States"
  },
  "iteration": 2
}
```

## Key Differences from Previous Run

### Before (No tool logs)
```
✅ [STATE] State created with 0 null fields
📚 [RECURSION] Calculating recursion limit: (0 * 6) + 10 = 10
✅ [INVOKE] LangGraph execution completed
```
**Problem:** No fields found → No Tavily calls

### After (With tool logs)
```
✅ [STATE] State created with 2 null fields
🔍 [ANALYZE] Starting payload analysis...
   🏷️  hq_city: None → ✅ NEEDS ENRICHMENT
   🏷️  hq_country: None → ✅ NEEDS ENRICHMENT
📚 [RECURSION] Calculating recursion limit: (2 * 6) + 10 = 22
🔍 [TAVILY SEARCH] Starting search...  ← TAVILY APPEARS HERE!
⏳ [TAVILY] Executing Tavily API call...
📊 [TAVILY RESPONSE] Processing...
📈 [TAVILY] Found list with 5 items...
🎯 [TAVILY COMPLETE]...
```

## In LangSmith Dashboard

You'll see a trace like:

```
abridge_enrichment (run)
├─ [invoke] PayloadEnrichmentState
│  ├─ [node] analyze_payload
│  │  └─ 🔍 [ANALYZE] Starting payload analysis...
│  ├─ [node] get_next_null_field
│  │  └─ 🔄 [NEXT FIELD] Selecting next...
│  ├─ [node] generate_search_queries
│  │  └─ 📝 [QUERY GEN] Generating queries...
│  ├─ [node] execute_searches
│  │  └─ 🔎 [EXECUTE SEARCH] Ready to invoke...
│  ├─ [tool_use] tavily_search (ACTUAL TOOL CALLS HERE)
│  │  └─ 🔍 [TAVILY SEARCH] Starting search...
│  │  └─ ⏳ [TAVILY] Executing API call...
│  │  └─ 📊 [TAVILY RESPONSE] Processing...
│  ├─ [node] extract_and_update_payload
│  │  └─ 💡 [EXTRACT] Extracting value...
│  │  └─ 🧠 [LLM] Calling LLM...
│  │  └─ 📝 [UPDATE] Updating field...
│  └─ (loop back if more fields)
└─ Result: 2 fields updated
```

## Verification Checklist

- [ ] Payload has null fields (hq_city: null, hq_country: null)
- [ ] 🔍 [ANALYZE] shows "Found N null fields"
- [ ] 📝 [QUERY GEN] shows search queries generated
- [ ] 🔍 [TAVILY SEARCH] logs appear
- [ ] 📈 [TAVILY] shows "Found X items"
- [ ] 💡 [EXTRACT] shows extracted values
- [ ] 📝 [UPDATE] shows field being updated
- [ ] 🎉 [ENRICH COMPLETE] shows "N fields updated"
- [ ] LangSmith shows tool_use events with Tavily calls

## Debugging

If you still don't see TAVILY logs:

1. **Check if fields are actually null:**
   ```bash
   grep "NEEDS ENRICHMENT" your_output.log
   ```
   Should see at least one field marked for enrichment

2. **Check if Tavily API key is set:**
   ```bash
   echo $TAVILY_API_KEY
   ```
   Should print your API key

3. **Check LangSmith has tracing enabled:**
   Look at LangSmith dashboard - should see the run

4. **Check log file directly:**
   ```bash
   tail -f config/logs/agentic_rag_*.log | grep TAVILY
   ```
   Should see TAVILY logs in real-time

## Summary

The key changes ensure:
- ✅ Multiple fields are checked for enrichment
- ✅ When fields are null, search queries are generated
- ✅ Tool execution is clearly logged
- ✅ Tavily API responses are captured
- ✅ All logs have emoji prefixes for easy filtering

Now when you run the script, you should see the full chain of:
**Analyze → Query Gen → Tavily Search → Extract → Update**

With detailed logging at each step, including actual Tavily responses!
