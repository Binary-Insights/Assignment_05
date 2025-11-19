# HITL FastAPI Architecture Implementation

## Summary

Implemented a true Human-in-the-Loop (HITL) system with FastAPI backend, LangGraph checkpointing, and workflow pause/resume capabilities.

## Key Changes

### 1. **LangGraph Checkpointing** (`src/tavily_agent/graph.py`)

**Added Imports:**
```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
```

**Updated `build_enrichment_graph()`:**
- Added `with_checkpointing: bool = False` parameter
- When enabled, compiles graph with `MemorySaver()` checkpointer
- Allows workflow to persist state and resume from interrupts

**Updated `wait_for_approval()`:**
- When approval status is PENDING, calls `interrupt()` to pause workflow
- Saves interrupt metadata (approval_id, field_name, company_name)
- Workflow can be resumed externally after approval processed

### 2. **FastAPI Enrichment Endpoints** (`src/backend/rag_search_api.py`)

**New Endpoints:**

#### `POST /enrich/company/{company_name}`
- Triggers enrichment with HITL support
- Runs in background task
- Returns `task_id` immediately for status polling

#### `GET /enrich/status/{task_id}`
- Check enrichment task status
- Status values: `started`, `running`, `waiting_approval`, `completed`, `failed`
- Returns approval details when paused

#### `POST /enrich/resume/{task_id}`
- Resume workflow after approval processed
- Automatically called after approve/reject actions

**Implementation Details:**

```python
# Global task tracking
enrichment_tasks: Dict[str, Dict[str, Any]] = {}

async def run_enrichment_with_checkpointing(company_name: str, task_id: str):
    """
    Run enrichment workflow with checkpointing enabled.
    Workflow pauses on interrupt(), resumes on approval.
    """
    # Build graph with checkpointing
    graph = build_enrichment_graph(with_checkpointing=True)
    
    # Execute with thread_id for checkpoint persistence
    config = {
        "configurable": {"thread_id": task_id},
        "recursion_limit": 100
    }
    
    final_state = await graph.ainvoke(state.dict(), config=config)
    
    # Handle interrupt (HITL pause)
    if final_state.pending_approval_id:
        enrichment_tasks[task_id]["status"] = "waiting_approval"
        enrichment_tasks[task_id]["approval_id"] = final_state.pending_approval_id
```

### 3. **Updated Main Orchestrator** (`src/tavily_agent/main.py`)

**Modified `initialize()` method:**
```python
async def initialize(self, with_checkpointing: bool = False):
    """Initialize with optional checkpointing for HITL."""
    self.graph = build_enrichment_graph(with_checkpointing=with_checkpointing)
```

### 4. **Next Steps for Complete Integration**

#### Update Approval Endpoints (TODO)

**Modify `/hitl/approvals/{approval_id}/approve`:**
```python
@app.post("/hitl/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, action: ApprovalActionRequest):
    # Existing approval logic
    queue = get_approval_queue()
    success = queue.approve(approval_id, action.approved_value, action.reviewer_decision)
    
    # NEW: Find and resume paused workflow
    for task_id, task in enrichment_tasks.items():
        if task.get("approval_id") == approval_id and task["status"] == "waiting_approval":
            # Resume workflow from checkpoint
            await resume_workflow_from_checkpoint(task_id, approval_id)
            break
    
    return {"status": "success", "message": "Approved and workflow resumed"}
```

**Modify `/hitl/approvals/{approval_id}/reject`:**
```python
@app.post("/hitl/approvals/{approval_id}/reject")
async def reject_request(approval_id: str, action: ApprovalActionRequest):
    # Existing rejection logic
    queue = get_approval_queue()
    success = queue.reject(approval_id, action.reviewer_decision)
    
    # NEW: Find and resume paused workflow (will skip rejected field)
    for task_id, task in enrichment_tasks.items():
        if task.get("approval_id") == approval_id and task["status"] == "waiting_approval":
            await resume_workflow_from_checkpoint(task_id, approval_id)
            break
    
    return {"status": "success", "message": "Rejected and workflow resumed"}
```

#### Add Resume Helper Function:
```python
async def resume_workflow_from_checkpoint(task_id: str, approval_id: str):
    """Resume workflow from checkpoint after approval processed."""
    task = enrichment_tasks[task_id]
    company_name = task["company_name"]
    
    logger.info(f"▶️  [RESUME] Resuming workflow for {company_name} after approval {approval_id}")
    
    # Get graph with checkpointing
    from tavily_agent.graph import build_enrichment_graph
    graph = build_enrichment_graph(with_checkpointing=True)
    
    # Resume from checkpoint
    config = {
        "configurable": {"thread_id": task_id},
        "recursion_limit": 100
    }
    
    # Invoke with None input - will resume from saved checkpoint
    final_state = await graph.ainvoke(None, config=config)
    
    # Update task status
    if final_state.pending_approval_id:
        # Hit another approval
        task["status"] = "waiting_approval"
        task["approval_id"] = final_state.pending_approval_id
    else:
        # Completed
        task["status"] = "completed"
        task["message"] = "Enrichment completed"
```

### 5. **Streamlit UI Updates** (TODO)

#### Add Enrichment Button (`src/frontend/streamlit_app.py`)

```python
import requests
import time

# Replace current DAG trigger with:
if st.button("🚀 Enrich with HITL"):
    company_slug = choice.lower().replace(" ", "-")
    
    # Trigger enrichment via FastAPI
    response = requests.post(f"{API_BASE}/enrich/company/{company_slug}")
    data = response.json()
    task_id = data["task_id"]
    
    st.success(f"✅ Enrichment started! Task ID: {task_id}")
    
    # Poll for status
    progress = st.progress(0)
    status_text = st.empty()
    
    while True:
        status_response = requests.get(f"{API_BASE}/enrich/status/{task_id}")
        status_data = status_response.json()
        
        status_text.write(f"Status: {status_data['status']}")
        
        if status_data["status"] == "waiting_approval":
            st.warning(f"⏸️ Waiting for approval of field: {status_data['field_name']}")
            st.info("👉 Go to HITL Approvals page to review")
            break
        
        elif status_data["status"] == "completed":
            st.success("✅ Enrichment completed!")
            break
        
        elif status_data["status"] == "failed":
            st.error(f"❌ Error: {status_data['error']}")
            break
        
        time.sleep(2)
```

#### Update HITL Approvals Page (`src/frontend/pages/2_HITL_Approvals.py`)

```python
# After approve/reject button click:
if st.button("✅ Approve", key=f"approve_{approval_id}"):
    response = requests.post(
        f"{API_BASE}/hitl/approvals/{approval_id}/approve",
        json={"approved_value": modified_value, "reviewer_decision": "Approved"}
    )
    
    if response.status_code == 200:
        st.success("✅ Approved! Workflow resuming...")
        st.balloons()
        time.sleep(1)
        st.rerun()  # Refresh to show updated status
```

## Workflow Flow

### Complete End-to-End Process:

1. **User triggers enrichment:**
   - Clicks "🚀 Enrich with HITL" in Streamlit
   - FastAPI creates task, returns `task_id`
   - Workflow starts with checkpointing enabled

2. **Workflow detects high-risk field:**
   - `assess_risk_and_route()` detects `last_disclosed_valuation_usd`
   - Creates approval request
   - `wait_for_approval()` finds PENDING status
   - Calls `interrupt()` - workflow **pauses**
   - State saved to checkpoint

3. **User sees pause in UI:**
   - Status polling shows `waiting_approval`
   - UI displays: "⏸️ Waiting for approval of field: last_disclosed_valuation_usd"
   - Directs user to HITL Approvals page

4. **User reviews and approves:**
   - Goes to HITL Approvals page
   - Reviews extracted value, sources, reasoning
   - Clicks "✅ Approve"
   - FastAPI updates approval status to APPROVED
   - **Automatically resumes workflow from checkpoint**

5. **Workflow resumes:**
   - `wait_for_approval()` re-checks approval status
   - Finds APPROVED status
   - Updates payload with approved value
   - Continues to next field

6. **Completion:**
   - Workflow processes remaining fields
   - Saves final payload
   - Task status updates to `completed`
   - Streamlit shows success message

## Architecture Benefits

### ✅ **True HITL** - Workflow actually pauses
- Not just flagging - workflow execution stops
- No updates without approval
- Full state preservation

### ✅ **No Manual Re-triggering**
- Approval automatically resumes workflow
- Seamless user experience
- No need to restart from beginning

### ✅ **Stateful Execution**
- Checkpoints preserve all context
- Can handle multiple approvals in sequence
- Recoverable from failures

### ✅ **Scalable**
- Multiple concurrent enrichments
- Each with independent checkpoints
- Task tracking for monitoring

### ✅ **Better than Airflow for HITL**
- Airflow designed for batch scheduling
- FastAPI better for interactive workflows
- Real-time status updates
- Background task management

## Migration Strategy

### Phase 1: Keep Both Systems
- **Airflow DAG**: Batch overnight processing (HITL disabled)
- **FastAPI**: Interactive enrichment (HITL enabled)
- Users choose based on use case

### Phase 2: Deprecate Airflow (Optional)
- Once FastAPI proven stable
- Add scheduling to FastAPI (APScheduler)
- Remove Airflow dependency

## Testing Checklist

- [ ] Trigger enrichment via `/enrich/company/abridge`
- [ ] Verify task created and status=`running`
- [ ] Confirm workflow pauses on high-risk field
- [ ] Check approval appears in `/hitl/approvals/pending`
- [ ] Approve request via UI
- [ ] Verify workflow resumes automatically
- [ ] Confirm field updated with approved value
- [ ] Test rejection flow (field should be skipped)
- [ ] Test multiple approvals in single workflow
- [ ] Verify final payload saved correctly

## Configuration

### Enable HITL in Settings
```json
// data/hitl_settings.json
{
  "enabled": true,
  "high_risk_fields": true,
  "low_confidence": true,
  "confidence_threshold": 0.7
}
```

### Environment Variables
```bash
# FastAPI
API_HOST=0.0.0.0
API_PORT=8000

# HITL
HITL_ENABLED=true
HITL_HIGH_RISK_FIELDS=true
```

## Known Limitations

1. **MemorySaver is in-memory** - checkpoints lost on server restart
   - **Solution**: Use `PostgresSaver` for persistence
   - Requires PostgreSQL connection

2. **No notification system** - user must poll status
   - **Solution**: Add WebSocket for real-time updates
   - Or implement email/Slack notifications

3. **Task cleanup** - enrichment_tasks dict grows unbounded
   - **Solution**: Add TTL and periodic cleanup
   - Or use Redis for task storage

## Next Steps

1. Complete FastAPI approval endpoint updates
2. Implement Streamlit UI changes
3. Test end-to-end HITL flow
4. Add PostgresSaver for production persistence
5. Implement WebSocket for real-time updates
6. Add comprehensive error handling
7. Create user documentation

## Files Modified

- ✅ `src/tavily_agent/graph.py` - Checkpointing + interrupt
- ✅ `src/tavily_agent/main.py` - Optional checkpointing parameter
- ✅ `src/backend/rag_search_api.py` - New enrichment endpoints
- ⏳ `src/backend/rag_search_api.py` - Update approval endpoints (pending)
- ⏳ `src/frontend/streamlit_app.py` - Add enrichment button (pending)
- ⏳ `src/frontend/pages/2_HITL_Approvals.py` - Auto-resume on approval (pending)
