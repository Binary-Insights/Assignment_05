# HITL Configuration Fix - Persistent Settings

## Problem Identified

**Root Cause**: HITL settings from Streamlit were not reaching the Airflow DAG workflow.

**Why It Happened**:
- Streamlit saved settings to `st.session_state` (session-only, not persistent)
- Airflow DAG runs `python main.py` in a subprocess (new process, no access to Streamlit session)
- Workflow initialized with default `hitl_enabled=False`, ignoring Streamlit checkbox

**Evidence from Logs**:
```
✅ last_disclosed_valuation_usd: '5300000000 USD'  # High-risk field updated WITHOUT approval
```

## Solution Implemented

### **Persistent Configuration File**

HITL settings now stored in **`data/hitl_settings.json`** - accessible by both Streamlit and workflow.

**File Location**: `data/hitl_settings.json`

**Example Content**:
```json
{
  "enabled": true,
  "high_risk_fields": true,
  "low_confidence": true,
  "conflicting_info": false,
  "entity_batch": false,
  "pre_save": false,
  "confidence_threshold": 0.7
}
```

### **Files Modified**

1. **`src/tavily_agent/config.py`**:
   - Added `load_hitl_settings()` function
   - Reads from `data/hitl_settings.json`
   - Falls back to environment variables if file missing
   - Auto-called during config initialization

2. **`src/frontend/pages/2_HITL_Approvals.py`**:
   - **Loads** settings from file on page load
   - **Saves** settings to file when checkboxes change
   - Shows success message: "✅ Settings saved - will apply to next workflow run!"

3. **`src/tavily_agent/graph.py`**:
   - `analyze_payload()` loads settings via `load_hitl_settings()`
   - Sets `state.hitl_enabled` and `state.hitl_settings` from file
   - `assess_risk_and_route()` uses `state.hitl_settings` instead of config constants
   - Logs configuration on workflow start

## How to Use

### **Step 1: Configure HITL in Streamlit**

1. Navigate to **HITL Approvals** page (http://localhost:8501)
2. Check **"Enable HITL"** checkbox
3. Select scenarios (e.g., "High-Risk Fields", "Low Confidence")
4. See confirmation: ✅ **"Settings saved to data/hitl_settings.json - will apply to next workflow run!"**

### **Step 2: Verify Settings Persisted**

Check file contents:
```powershell
Get-Content data\hitl_settings.json
```

Expected output:
```json
{
  "enabled": true,
  "high_risk_fields": true,
  "low_confidence": true,
  ...
}
```

### **Step 3: Trigger Workflow from Airflow**

1. Open Airflow at http://localhost:8080
2. Trigger **`agentic_rag_enrichment_dag`**
3. Monitor logs for HITL activation:

**Expected Logs**:
```
✅ [CONFIG] Loaded HITL settings from data/hitl_settings.json
🔧 [HITL CONFIG] Loaded settings: enabled=True
   High-risk fields: True
   Low confidence: True
   Threshold: 0.7

⚠️  [HITL RISK] High-risk field detected: last_disclosed_valuation_usd
⏸️  [HITL] Created approval request: abc-123-def-456
📊 [HITL] Workflow paused - waiting for approval
```

### **Step 4: Approve in Streamlit**

1. Return to **HITL Approvals** page
2. See pending approval card with:
   - Field: `last_disclosed_valuation_usd`
   - Value: `5300000000 USD`
   - Confidence: 98%
   - Sources: 4 URLs
3. Click **"Approve as-is"** or **"Modify & Approve"**
4. Re-trigger DAG to resume workflow

## Expected Workflow Behavior

### **Before Fix**
```
Iteration 1: Extracting last_disclosed_valuation_usd
   Confidence: 98%
   ❌ HITL bypassed (state.hitl_enabled=False)
   ✅ Updated payload directly
```

### **After Fix**
```
Iteration 1: Extracting last_disclosed_valuation_usd
   Confidence: 98%
   🔧 Loaded HITL settings: enabled=True, high_risk_fields=True
   ⚠️  High-risk field detected
   ⏸️  Created approval request: abc-123
   📊 Status: waiting_approval
   ⏹️  Workflow paused (END node reached)
```

## Testing Checklist

- [ ] Enable HITL in Streamlit
- [ ] Verify `data/hitl_settings.json` created
- [ ] Trigger DAG from Airflow
- [ ] Check logs for "✅ [CONFIG] Loaded HITL settings"
- [ ] Check logs for "⚠️ [HITL RISK] High-risk field detected"
- [ ] Check logs for "⏸️ [HITL] Created approval request"
- [ ] Verify approval appears in Streamlit dashboard
- [ ] Approve extraction
- [ ] Re-trigger DAG to verify workflow resume

## Troubleshooting

### **Settings Not Loading**

**Symptom**: Logs show `hitl_enabled=False` despite checkbox enabled

**Solution**:
```powershell
# Verify file exists
Test-Path data\hitl_settings.json

# Check file permissions
Get-Acl data\hitl_settings.json

# Manually verify content
Get-Content data\hitl_settings.json | ConvertFrom-Json
```

### **Approval Not Created**

**Symptom**: High-risk field updated without approval request

**Check**:
1. Settings file `enabled: true`
2. Settings file `high_risk_fields: true`
3. Field is in `HIGH_RISK_FIELDS` list (config.py)
4. Logs show "🔧 [HITL CONFIG] Loaded settings: enabled=True"

### **Workflow Doesn't Pause**

**Reason**: Current implementation requires **manual re-trigger** after approval

**Future Enhancement**: Implement LangGraph checkpointing for automatic resume

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │  HITL Configuration Page                           │     │
│  │  - Enable HITL checkbox                            │     │
│  │  - High-risk fields checkbox                       │     │
│  │  - Low confidence checkbox                         │     │
│  └───────────────────┬────────────────────────────────┘     │
│                      │ WRITE                                 │
│                      ▼                                       │
│              ┌───────────────────┐                           │
│              │ hitl_settings.json│◄───────────────┐          │
│              │  (persistent)     │                │          │
│              └───────┬───────────┘                │          │
│                      │ READ                       │          │
│                      ▼                            │          │
│  ┌────────────────────────────────────────────────┴────┐    │
│  │  HITL Approvals Dashboard                          │    │
│  │  - Loads settings from file                        │    │
│  │  - Displays pending approvals                      │    │
│  │  - Approve/Modify/Reject actions                   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                      │ READ
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Airflow DAG (Subprocess)                    │
│  ┌────────────────────────────────────────────────────┐     │
│  │  agentic_rag_enrichment_dag                        │     │
│  │  python main.py single abridge                     │     │
│  └───────────────────┬────────────────────────────────┘     │
│                      │                                       │
│                      ▼                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │  LangGraph Workflow                                │     │
│  │  ┌──────────────────────────────────────────┐      │     │
│  │  │ analyze_payload()                        │      │     │
│  │  │   1. load_hitl_settings() from JSON      │      │     │
│  │  │   2. state.hitl_enabled = True           │      │     │
│  │  │   3. state.hitl_settings = {...}         │      │     │
│  │  └──────────────────────────────────────────┘      │     │
│  │                                                     │     │
│  │  ┌──────────────────────────────────────────┐      │     │
│  │  │ extract_and_update_payload()             │      │     │
│  │  │   Extract value with LLM                 │      │     │
│  │  └──────────────────────────────────────────┘      │     │
│  │                      │                             │     │
│  │                      ▼                             │     │
│  │  ┌──────────────────────────────────────────┐      │     │
│  │  │ assess_risk_and_route()                  │      │     │
│  │  │   if state.hitl_settings['high_risk']:   │      │     │
│  │  │     if field in HIGH_RISK_FIELDS:        │      │     │
│  │  │       create_approval_request()          │      │     │
│  │  │       return state (workflow pauses)     │      │     │
│  │  └──────────────────────────────────────────┘      │     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Precedence

1. **`data/hitl_settings.json`** (highest priority - if file exists)
2. **Environment variables** (fallback if no file)
3. **Hardcoded defaults** (last resort)

## Next Steps

1. **Test end-to-end flow** with persistent settings
2. **Verify approval queue** stores pending requests
3. **Implement automatic resume** (LangGraph checkpointing)
4. **Add notification system** (email/Slack when approval needed)

## Related Files

- **Config**: `src/tavily_agent/config.py`
- **Frontend**: `src/frontend/pages/2_HITL_Approvals.py`
- **Workflow**: `src/tavily_agent/graph.py`
- **Settings**: `data/hitl_settings.json` (created on first save)
- **Approvals**: `data/approval_queue.json` (created on first approval)

## Summary

**Before**: Streamlit settings isolated in session state → DAG ignored them → No approvals created

**After**: Streamlit saves to JSON → DAG reads JSON → Workflow uses settings → Approvals created ✅

**Key Insight**: Need **persistent storage** (filesystem) for cross-process communication between Streamlit and Airflow subprocess.
