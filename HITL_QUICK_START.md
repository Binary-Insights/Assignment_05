# HITL Quick Start Guide

## What You Just Got

A complete **Human-in-the-Loop (HITL) approval system** for your agentic RAG workflow!

## Features

### ✅ Streamlit Frontend Controls
- **Configure HITL scenarios** (high-risk fields, low confidence, etc.)
- **Review pending approvals** with rich UI
- **Approve/Modify/Reject** extractions
- **Monitor statistics** in real-time

### ✅ Conditional Risk Routing
- Workflow automatically detects high-risk scenarios
- Routes to approval queue when needed
- Continues automatically for safe extractions

### ✅ FastAPI Backend
- RESTful API for approval management
- Queue persistence in JSON
- Statistics and monitoring

## Quick Test

### 1. Start Services
```bash
# Containers already restarted ✅
# Access Streamlit at: http://localhost:8501
```

### 2. Enable HITL
1. Navigate to **HITL Approvals** page (new page in sidebar)
2. Check **"Enable HITL"**
3. Check **"High-Risk Fields"** and **"Low Confidence"**
4. See confirmation: "✅ HITL Enabled for: High-Risk Fields, Low Confidence"

### 3. Run Workflow
Trigger `agentic_rag_dag` in Airflow for a company with null financial data

### 4. Review Approval
1. Workflow pauses when it extracts `total_raised_usd` (high-risk field)
2. Go to **HITL Approvals** page
3. See pending approval card with:
   - Extracted value
   - Confidence score
   - LLM reasoning
   - Source URLs
4. Choose action:
   - **Approve as-is**
   - **Modify value** → Approve
   - **Reject**

### 5. Resume Workflow
Currently manual - re-trigger workflow after approval

## HITL Scenarios You Can Enable

| Scenario | Description | Status |
|----------|-------------|--------|
| **High-Risk Fields** | Financial data (funding, valuation) | ✅ **Implemented** |
| **Low Confidence** | Confidence < 70% | ✅ **Implemented** |
| **Conflicting Info** | Sources disagree | 🚧 Planned |
| **Entity Batch** | Review multiple entities | 🚧 Planned |
| **Pre-Save** | Final checkpoint | 🚧 Planned |

## API Endpoints

All accessible at `http://localhost:8000`

```bash
# Get pending approvals
GET /hitl/approvals/pending

# Approve request
POST /hitl/approvals/{id}/approve
Body: {"approved_value": "...", "reviewer_decision": "..."}

# Reject request
POST /hitl/approvals/{id}/reject
Body: {"reviewer_decision": "..."}

# Get statistics
GET /hitl/stats
```

## Files Created

```
src/tavily_agent/approval_queue.py         ← Queue manager
src/frontend/pages/2_HITL_Approvals.py     ← Streamlit UI
HITL_IMPLEMENTATION_SUMMARY.md             ← Full documentation
```

## Files Modified

```
src/tavily_agent/config.py    ← HITL configuration
src/tavily_agent/graph.py     ← HITL nodes & routing
src/backend/rag_search_api.py ← API endpoints
```

## Next Steps

1. **Test the system** - Run workflow with HITL enabled
2. **Review the full documentation** - See HITL_IMPLEMENTATION_SUMMARY.md
3. **Customize settings** - Adjust confidence threshold, add more high-risk fields
4. **Implement checkpointing** - For automatic workflow resume (future enhancement)

## Need Help?

Check the **📖 How HITL Works** section in the Streamlit dashboard for detailed workflow explanation!
