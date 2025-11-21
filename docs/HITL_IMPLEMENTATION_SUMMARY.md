# Human-in-the-Loop (HITL) Implementation Summary

## Overview

A comprehensive Human-in-the-Loop approval system has been implemented for the Tavily Agent agentic RAG workflow, allowing selective human approval for high-risk or low-confidence extractions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           LangGraph Agentic RAG Workflow                    │
│                                                             │
│  analyze → get_next_field → generate_queries →             │
│  execute_searches → extract_update → assess_risk           │
│                                      ↓                      │
│                            ┌─────────┴─────────┐           │
│                            │                   │           │
│                    Requires Approval?    No Approval       │
│                            │               Needed          │
│                           Yes                 │            │
│                            ↓                  ↓            │
│                    wait_approval → check_completion        │
│                            ↓                               │
│                     (PAUSE & SAVE)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           Approval Queue (JSON file)                        │
│  data/approval_queue.json                                  │
│  - approval_id                                             │
│  - company_name, field_name                                │
│  - extracted_value, confidence                             │
│  - sources, reasoning                                      │
│  - status: pending/approved/rejected/modified              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           FastAPI Endpoints                                 │
│  GET  /hitl/approvals/pending                              │
│  POST /hitl/approvals/{id}/approve                         │
│  POST /hitl/approvals/{id}/reject                          │
│  GET  /hitl/stats                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           Streamlit Dashboard                               │
│  pages/2_HITL_Approvals.py                                 │
│  - Configure HITL settings                                 │
│  - View pending approvals                                  │
│  - Approve/Modify/Reject                                   │
│  - Monitor statistics                                      │
└─────────────────────────────────────────────────────────────┘
```

## New Files Created

### 1. `src/tavily_agent/approval_queue.py` (361 lines)
**Purpose**: Manages approval queue persistence and approval lifecycle

**Key Classes**:
- `ApprovalStatus`: Enum for approval states (pending, approved, rejected, modified)
- `ApprovalType`: Enum for approval types (high_risk_field, low_confidence, conflicting_info, entity_batch, pre_save)
- `ApprovalRequest`: Represents a single approval request
- `ApprovalQueueManager`: Queue CRUD operations

**Key Methods**:
- `create_approval()`: Create new approval request
- `get_pending_approvals()`: Get all pending approvals (with filters)
- `approve()`: Approve request with optional value modification
- `reject()`: Reject request with reason
- `get_stats()`: Get queue statistics

### 2. `src/frontend/pages/2_HITL_Approvals.py` (397 lines)
**Purpose**: Streamlit UI for human approval workflow

**Features**:
- **Configuration Panel**: Toggle HITL scenarios (high-risk fields, low confidence, etc.)
- **Queue Statistics**: Real-time metrics (pending, approved, rejected, modified)
- **Approval Cards**: Rich UI for each pending approval showing:
  - Extracted value & confidence
  - LLM reasoning
  - Source URLs
  - Metadata
- **Action Buttons**:
  - Approve as-is
  - Modify & approve
  - Reject with reason
- **API Documentation**: Built-in help for developers

## Modified Files

### 1. `src/tavily_agent/config.py`
**Added**:
```python
# HITL Configuration
HITL_ENABLED: bool
HITL_HIGH_RISK_FIELDS: bool
HITL_LOW_CONFIDENCE: bool
HITL_CONFLICTING_INFO: bool
HITL_ENTITY_BATCH: bool
HITL_PRE_SAVE: bool
HITL_CONFIDENCE_THRESHOLD: float = 0.7

HIGH_RISK_FIELDS: List[str] = [
    "total_raised_usd",
    "last_disclosed_valuation_usd",
    "last_round_name",
    "last_round_date",
    "last_round_amount_usd",
    "employee_count"
]
```

### 2. `src/tavily_agent/graph.py`
**Added State Fields**:
```python
class PayloadEnrichmentState(BaseModel):
    # ... existing fields ...
    pending_approval_id: Optional[str] = None
    hitl_enabled: bool = False
    hitl_settings: Dict[str, bool] = Field(default_factory=dict)
```

**New Nodes**:
- `assess_risk_and_route()`: Evaluate if extraction requires approval
- `wait_for_approval()`: Check approval status (pauses if pending)
- `route_after_extraction()`: Conditional routing (approval vs continue)
- `route_after_approval()`: Conditional routing (wait vs continue)

**Updated Graph Flow**:
```
extract_update → assess_risk → [wait_approval OR get_next_field]
wait_approval → [PAUSE(END) OR get_next_field]
```

### 3. `src/backend/rag_search_api.py`
**Added Response Models**:
```python
ApprovalRequestModel
ApprovalActionRequest
ApprovalStatsResponse
HITLSettingsRequest
```

**New Endpoints**:
- `GET /hitl/approvals/pending`: List pending approvals
- `POST /hitl/approvals/{id}/approve`: Approve with optional modification
- `POST /hitl/approvals/{id}/reject`: Reject with reason
- `GET /hitl/stats`: Queue statistics

## How to Use HITL

### Step 1: Configure HITL Settings
Open Streamlit dashboard → **HITL Approvals** page

**Options**:
- ✅ **Enable HITL**: Master switch
- 🔴 **High-Risk Fields**: Financial data (total_raised_usd, valuation, etc.)
- 🔴 **Low Confidence**: Confidence < 70%
- 🟡 **Conflicting Info**: Sources disagree (not yet implemented)
- 🟡 **Entity Batch**: Review entity extractions (not yet implemented)
- 🟢 **Pre-Save**: Final review before save (not yet implemented)

### Step 2: Run Agentic RAG Workflow
```bash
# Trigger via Airflow DAG
# Or run manually:
cd src/tavily_agent
python main.py abridge
```

**With HITL Enabled**:
1. Workflow runs normally
2. When high-risk field or low-confidence extraction detected:
   - Creates approval request in queue
   - Sets `pending_approval_id`
   - Pauses workflow (returns END)

**Workflow Logs**:
```
⚠️  [HITL RISK] High-risk field detected: total_raised_usd
⏸️  [HITL] Created approval request: abc-123-def-456
   Field: total_raised_usd, Type: high_risk_field
   Value: $77M, Confidence: 0.65
🔀 [ROUTE] Approval required - routing to wait_for_approval
⏳ [HITL] Waiting for approval: abc-123-def-456
🔀 [ROUTE] Still waiting for approval - pausing workflow
```

### Step 3: Review in Streamlit Dashboard
Navigate to **HITL Approvals** page:

**Approval Card Shows**:
- Company name & field name
- Approval type & confidence score
- Extracted value
- LLM reasoning
- Source URLs
- Metadata (entity type, importance)

**Actions**:
1. **Approve as-is**: Accept LLM extraction unchanged
2. **Modify & Approve**: Edit value then approve
3. **Reject**: Reject with reason (field won't be updated)

### Step 4: Workflow Resumes Automatically
After approval/rejection:
- Streamlit calls FastAPI endpoint
- Approval status updated in queue
- **Manual Resume** (for now): Re-trigger workflow
  ```bash
  python src/tavily_agent/main.py abridge
  ```
- Workflow checks approval status
- If approved: Updates payload with approved value
- If rejected: Skips field update
- Continues to next field

### Step 5: Monitor Statistics
Dashboard shows:
- Total requests
- Pending count
- Approved/Modified/Rejected counts
- Breakdown by approval type

## HITL Scenarios

### 1. High-Risk Field ⚠️
**Trigger**: Field is in `HIGH_RISK_FIELDS` list

**Example**:
```
Field: total_raised_usd
Value: "$77M"
Confidence: 0.85
Reason: High-risk financial data
```

**Why**: Prevents costly errors in critical business metrics

### 2. Low Confidence 🎯
**Trigger**: `confidence < HITL_CONFIDENCE_THRESHOLD` (0.7)

**Example**:
```
Field: founded_year
Value: "2019"
Confidence: 0.65
Reason: LLM uncertainty - multiple sources disagree
```

**Why**: Catches potential hallucinations or ambiguous data

### 3. Conflicting Information ⚔️ (Planned)
**Trigger**: Multiple sources disagree on value

**Example**:
```
Field: employee_count
Source A: 150
Source B: 200
Confidence: 0.50
```

**Why**: Human judgment needed to resolve conflicts

### 4. Entity Batch Review 📦 (Planned)
**Trigger**: 5+ entities extracted in one iteration

**Example**:
```
Entities: 7 events, 5 products, 8 leadership
Confidence: 0.75 avg
Reason: Bulk quality control
```

**Why**: Quality control for structured data

### 5. Pre-Save Checkpoint 💾 (Planned)
**Trigger**: Before final payload save

**Example**:
```
Changes: 12 fields updated, 25 entities added
Confidence: 0.82 avg
Reason: Final safety check
```

**Why**: Safety net for complete payload updates

## API Usage Examples

### Get Pending Approvals
```bash
curl http://localhost:8000/hitl/approvals/pending
```

**Response**:
```json
[
  {
    "approval_id": "abc-123-def-456",
    "company_name": "abridge",
    "approval_type": "high_risk_field",
    "field_name": "total_raised_usd",
    "extracted_value": "$77M",
    "confidence": 0.65,
    "sources": ["https://..."],
    "reasoning": "Found in Tavily search...",
    "metadata": {"entity_type": "company_record", "importance": "high"},
    "status": "pending",
    "created_at": "2025-11-19T00:30:00Z"
  }
]
```

### Approve Request
```bash
curl -X POST http://localhost:8000/hitl/approvals/abc-123-def-456/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer_decision": "Looks good!"}'
```

### Approve with Modification
```bash
curl -X POST http://localhost:8000/hitl/approvals/abc-123-def-456/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved_value": "$75M",
    "reviewer_decision": "Corrected amount based on latest press release"
  }'
```

### Reject Request
```bash
curl -X POST http://localhost:8000/hitl/approvals/abc-123-def-456/reject \
  -H "Content-Type: application/json" \
  -d '{"reviewer_decision": "Conflicting sources - need more research"}'
```

### Get Statistics
```bash
curl http://localhost:8000/hitl/stats
```

## Testing the Implementation

### Test 1: High-Risk Field Approval
1. Enable HITL with "High-Risk Fields" checked
2. Run workflow for company with null `total_raised_usd`
3. Workflow should pause with pending approval
4. Check Streamlit dashboard for approval card
5. Approve/reject and verify workflow resumes

### Test 2: Low Confidence Approval
1. Enable HITL with "Low Confidence" checked
2. Run workflow for field with low confidence extraction
3. Verify approval created with confidence < 0.7
4. Modify value and approve
5. Verify payload updated with modified value

### Test 3: Multiple Approvals
1. Enable both "High-Risk Fields" and "Low Confidence"
2. Run workflow for company with multiple null high-risk fields
3. Verify multiple approval requests queued
4. Approve some, reject others
5. Verify payload reflects decisions

## Future Enhancements

### 1. Automatic Workflow Resume
Currently requires manual re-trigger. Future: Use checkpointing

### 2. Conflicting Information Detection
Implement logic to detect source disagreements

### 3. Entity Batch Review
Aggregate entity extractions for batch approval

### 4. Pre-Save Checkpoint
Show full diff before final save

### 5. Approval History & Audit Trail
Track all approvals with timestamps and reviewers

### 6. Email/Slack Notifications
Alert reviewers when approval needed

### 7. Role-Based Access Control
Different approval permissions for different users

### 8. Approval Delegation
Route to different reviewers based on field type

## Environment Variables

Add to `.env`:
```bash
# HITL Configuration
HITL_ENABLED=false
HITL_HIGH_RISK_FIELDS=true
HITL_LOW_CONFIDENCE=true
HITL_CONFLICTING_INFO=false
HITL_ENTITY_BATCH=false
HITL_PRE_SAVE=false
HITL_CONFIDENCE_THRESHOLD=0.7
```

## Troubleshooting

### Workflow Not Pausing
- Check `HITL_ENABLED=true` in config
- Verify field is in `HIGH_RISK_FIELDS` or confidence < 0.7
- Check logs for "Created approval request"

### Approvals Not Appearing in UI
- Verify FastAPI running on correct port
- Check `API_BASE` in Streamlit
- Look for approval_queue.json in data/

### Workflow Not Resuming
- Currently requires manual re-trigger
- Check approval status in queue file
- Verify approval was approved/rejected

## File Locations

```
src/
├── tavily_agent/
│   ├── approval_queue.py          # NEW: Queue manager
│   ├── config.py                  # MODIFIED: HITL config
│   └── graph.py                   # MODIFIED: HITL nodes
├── backend/
│   └── rag_search_api.py          # MODIFIED: HITL endpoints
└── frontend/
    └── pages/
        └── 2_HITL_Approvals.py    # NEW: Streamlit UI

data/
└── approval_queue.json            # CREATED: Queue persistence
```

## Summary

The HITL system provides:
✅ Selective human approval for high-risk scenarios
✅ Rich Streamlit UI for review workflow
✅ RESTful API for programmatic access
✅ Configurable approval triggers
✅ Approval queue persistence
✅ Statistics and monitoring
✅ Value modification support
✅ Audit trail (timestamps, decisions)

**Next Steps**:
1. Test with real workflow
2. Implement automatic resume via checkpointing
3. Add remaining approval scenarios
4. Set up notifications
