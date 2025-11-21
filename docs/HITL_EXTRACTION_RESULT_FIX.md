# HITL Extraction Result Bug Fix

## Issue Summary

**Problem**: High-risk fields (`total_raised_usd`, `last_disclosed_valuation_usd`) were being auto-approved and updated in the payload without triggering HITL approval requests, despite HITL being enabled.

**Root Cause**: The `assess_risk_and_route()` function was unable to access the extraction result because of a mismatch between where it was stored and where it was retrieved.

## Technical Details

### The Bug

In `src/tavily_agent/graph.py`:

**Line 771 (STORING):**
```python
state.extracted_values[f"{field_name}_extraction_result"] = extraction_result.dict()
```
- Stored with field-specific key: `"total_raised_usd_extraction_result"`

**Line 856 (RETRIEVING):**
```python
extracted_result = state.extracted_values.get("extraction_result")
```
- Looking for generic key: `"extraction_result"`

**Result**: `extracted_result` was always `None`, causing this log message:
```
ℹ️  [HITL] No extraction result for {field_name} - skipping risk assessment
```

### The Fix

**Change 1**: Add `extraction_result` field to `PayloadEnrichmentState` (line 78)
```python
class PayloadEnrichmentState(BaseModel):
    # Tool results
    search_results: Optional[Dict[str, Any]] = None
    extracted_values: Dict[str, Any] = Field(default_factory=dict)
    extraction_result: Optional[Dict[str, Any]] = None  # Current field's extraction result for HITL
```

**Change 2**: Set `state.extraction_result` after LLM extraction (line 772)
```python
# Store extraction result in state for HITL assessment
state.extraction_result = extraction_result.dict()
state.extracted_values[f"{field_name}_extraction_result"] = extraction_result.dict()
```

**Change 3**: Clear `extraction_result` after field processing (line 831)
```python
# Clear extraction_result to avoid reuse for next field
state.extraction_result = None
```

## Expected Behavior After Fix

### Before (Broken)
```
📝 [UPDATE] company_record.total_raised_usd: None → '757500000 USD'
   ✅ Tracked: extracted_values[total_raised_usd] = '757500000 USD'
✅ [EXTRACT COMPLETE] Removed 0 processed fields. Remaining: 8
ℹ️  [HITL] No extraction result for total_raised_usd - skipping risk assessment  ❌
🔀 [ROUTE] No approval needed - continuing to check_completion  ❌
```

### After (Fixed)
```
📝 [UPDATE] company_record.total_raised_usd: None → '757500000 USD'
   ✅ Tracked: extracted_values[total_raised_usd] = '757500000 USD'
✅ [EXTRACT COMPLETE] Removed 0 processed fields. Remaining: 8
⚠️  [HITL RISK] High-risk field detected: total_raised_usd  ✅
⏸️  [HITL] Created approval request: {approval_id}  ✅
   Field: total_raised_usd, Type: high_risk_field
   Value: 757500000 USD, Confidence: 0.95
⏸️  [HITL] Waiting for approval - INTERRUPTING WORKFLOW  ✅
💾 [HITL] State saved to checkpoint - workflow can be resumed  ✅
```

## Testing Instructions

1. **Clear existing payload** (optional):
   ```bash
   rm data/payloads/abridge.json
   ```

2. **Reset approval queue** (optional):
   ```bash
   rm data/approval_queue.json
   ```

3. **Trigger enrichment** via Streamlit:
   - Open http://localhost:8501
   - Select "Abridge" company
   - Click "🚀 Enrich with HITL" button

4. **Verify HITL activation**:
   - Check FastAPI logs for `⚠️  [HITL RISK] High-risk field detected`
   - Status should show "⏸️ Waiting for Approval"
   - Navigate to HITL Approvals page
   - Verify approval request appears for `total_raised_usd`

5. **Test approval workflow**:
   - Review extracted value and sources
   - Click "Approve" or "Reject"
   - Verify workflow automatically resumes
   - Check payload file for updated value

## Files Modified

- `src/tavily_agent/graph.py`:
  - Added `extraction_result` field to `PayloadEnrichmentState` class
  - Updated `extract_and_update_payload()` to set `state.extraction_result`
  - Added cleanup to clear `state.extraction_result` after processing

## Deployment

Containers restarted to apply fix:
```bash
docker compose restart streamlit fastapi
```

## Verification Logs

Expected log sequence for high-risk field:
1. `💡 [EXTRACT] Extracting value for company_record.total_raised_usd`
2. `✅ [LLM CHAIN] Extraction complete: ... Confidence: 95.00%`
3. `💾 [UPDATE] Updating payload with extracted value`
4. `⚠️  [HITL RISK] High-risk field detected: total_raised_usd`
5. `⏸️  [HITL] Created approval request: {uuid}`
6. `⏸️  [HITL] Waiting for approval - INTERRUPTING WORKFLOW`
7. (Workflow pauses until approval granted)

## Related Configuration

HITL settings in `data/hitl_settings.json`:
```json
{
  "enabled": true,
  "high_risk_fields": true,
  "low_confidence": true,
  "confidence_threshold": 0.7
}
```

High-risk fields defined in `config/config.py`:
```python
HIGH_RISK_FIELDS = [
    "total_raised_usd",
    "last_disclosed_valuation_usd",
    "last_round_date",
    "last_round_name"
]
```

## Impact

This fix restores proper HITL functionality for:
- ✅ High-risk field detection
- ✅ Low-confidence value detection
- ✅ Workflow interruption (pause)
- ✅ Approval queue creation
- ✅ Automatic workflow resume after approval
- ✅ State persistence via checkpointing
