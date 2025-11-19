"""
Human-in-the-Loop (HITL) Approval Dashboard
Streamlit page for reviewing and approving agentic RAG extractions
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime
from pathlib import Path

# Get API URL
ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()
if ENVIRONMENT == "docker":
    API_BASE = os.getenv("FASTAPI_URL", "http://fastapi:8000")
else:
    API_BASE = os.getenv("LOCALHOST_URL", "http://localhost:8000")

st.set_page_config(
    page_title="HITL Approval Dashboard",
    page_icon="✅",
    layout="wide"
)

st.title("✅ Human-in-the-Loop Approval Dashboard")
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
#  HITL Settings Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Load current settings from file
settings_file = Path("data/hitl_settings.json")
current_settings = {}
if settings_file.exists():
    try:
        with open(settings_file, 'r') as f:
            current_settings = json.load(f)
            st.success(f"✅ Loaded saved settings from {settings_file}")
    except Exception as e:
        st.warning(f"⚠️ Could not load saved settings: {e}")

st.header("⚙️ HITL Configuration")
st.markdown("Configure which scenarios require human approval during agentic RAG enrichment.")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🔴 High Priority")
    hitl_enabled = st.checkbox(
        "Enable HITL",
        value=current_settings.get("enabled", False),
        help="Master switch for Human-in-the-Loop approval workflow"
    )
    
    high_risk_fields = st.checkbox(
        "High-Risk Fields",
        value=current_settings.get("high_risk_fields", True),
        help="Require approval for financial fields (total_raised_usd, valuation, etc.)",
        disabled=not hitl_enabled
    )
    
    low_confidence = st.checkbox(
        "Low Confidence Extractions",
        value=current_settings.get("low_confidence", True),
        help="Require approval when LLM confidence < 70%",
        disabled=not hitl_enabled
    )

with col2:
    st.subheader("🟡 Medium Priority")
    conflicting_info = st.checkbox(
        "Conflicting Information",
        value=current_settings.get("conflicting_info", False),
        help="Require approval when sources disagree",
        disabled=not hitl_enabled
    )
    
    entity_batch = st.checkbox(
        "Entity Batch Review",
        value=current_settings.get("entity_batch", False),
        help="Require approval for batches of extracted entities (events, products, etc.)",
        disabled=not hitl_enabled
    )

with col3:
    st.subheader("🟢 Low Priority")
    pre_save = st.checkbox(
        "Pre-Save Checkpoint",
        value=current_settings.get("pre_save", False),
        help="Require approval before final payload save",
        disabled=not hitl_enabled
    )

# Save settings to file for workflow to use
settings_to_save = {
    "enabled": hitl_enabled,
    "high_risk_fields": high_risk_fields,
    "low_confidence": low_confidence,
    "conflicting_info": conflicting_info,
    "entity_batch": entity_batch,
    "pre_save": pre_save,
    "confidence_threshold": 0.7
}

# Save to session state
if "hitl_settings" not in st.session_state:
    st.session_state.hitl_settings = {}
st.session_state.hitl_settings = settings_to_save

# Save to persistent file
try:
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_file, 'w') as f:
        json.dump(settings_to_save, f, indent=2)
    if hitl_enabled:
        st.success(f"✅ Settings saved to {settings_file} - will apply to next workflow run!")
except Exception as e:
    st.error(f"❌ Error saving settings: {e}")

# Display current settings
if hitl_enabled:
    enabled_features = []
    if high_risk_fields:
        enabled_features.append("High-Risk Fields")
    if low_confidence:
        enabled_features.append("Low Confidence")
    if conflicting_info:
        enabled_features.append("Conflicting Info")
    if entity_batch:
        enabled_features.append("Entity Batches")
    if pre_save:
        enabled_features.append("Pre-Save")
    
    if enabled_features:
        st.success(f"✅ HITL Enabled for: {', '.join(enabled_features)}")
    else:
        st.warning("⚠️ HITL enabled but no scenarios selected")
else:
    st.info("ℹ️ HITL disabled - all extractions will auto-approve")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Enrich with HITL
# ─────────────────────────────────────────────────────────────────────────────

st.header("🚀 Enrich Company with HITL")

# Initialize session state for enrichment
if "enrichment_task_id" not in st.session_state:
    st.session_state.enrichment_task_id = None
if "enrichment_status" not in st.session_state:
    st.session_state.enrichment_status = None

# Fetch companies list
try:
    companies_response = requests.get(f"{API_BASE}/companies", timeout=5).json()
    companies = companies_response.get("companies", []) if isinstance(companies_response, dict) else companies_response
    company_names = [c["company_name"] for c in companies] if companies else []
except Exception as e:
    st.warning(f"⚠️ Failed to load companies: {e}")
    company_names = ["Abridge"]  # Fallback

# Company selection and enrich button
enrich_col1, enrich_col2 = st.columns([3, 1])

with enrich_col1:
    selected_company = st.selectbox(
        "Select company to enrich:",
        company_names,
        key="hitl_company_select"
    )

with enrich_col2:
    st.write("")  # Spacer to align button
    st.write("")  # Spacer
    enrich_button = st.button(
        "🚀 Enrich with HITL",
        use_container_width=True,
        type="primary",
        disabled=not hitl_enabled
    )

# Handle enrichment
if enrich_button:
    try:
        with st.spinner(f"Starting enrichment for {selected_company}..."):
            response = requests.post(
                f"{API_BASE}/enrich/company/{selected_company}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                st.session_state.enrichment_task_id = result["task_id"]
                st.session_state.enrichment_status = "running"
                st.success(f"✅ Enrichment started! Task ID: {result['task_id'][:8]}...")
                st.info("📊 Monitor progress below. Workflow will pause if approval is needed.")
                st.rerun()
            else:
                st.error(f"❌ Failed to start enrichment: {response.text}")
    except Exception as e:
        st.error(f"❌ Error starting enrichment: {e}")

# Display enrichment status
if st.session_state.enrichment_task_id:
    st.subheader(f"📊 Enrichment Status: {st.session_state.enrichment_task_id[:8]}...")
    
    status_col1, status_col2 = st.columns([4, 1])
    
    with status_col2:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    
    try:
        status_resp = requests.get(
            f"{API_BASE}/enrich/status/{st.session_state.enrichment_task_id}",
            timeout=5
        )
        
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            status = status_data["status"]
            
            if status == "running":
                st.info(f"▶️ **Status:** Running - {status_data.get('message', 'Processing...')}")
            elif status == "waiting_approval":
                st.warning(f"⏸️ **Status:** Waiting for Approval")
                st.markdown(f"""
                **Field:** `{status_data.get('field_name', 'Unknown')}`  
                **Approval ID:** `{status_data.get('approval_id', 'N/A')[:8]}...`
                
                👇 **Review and approve below in the Pending Approvals section**
                """)
            elif status == "completed":
                st.success(f"✅ **Status:** Completed!")
                if status_data.get("result"):
                    with st.expander("View Result"):
                        st.json(status_data["result"])
                if st.button("Clear Task", key="clear_completed"):
                    st.session_state.enrichment_task_id = None
                    st.session_state.enrichment_status = None
                    st.rerun()
            elif status == "failed":
                st.error(f"❌ **Status:** Failed")
                st.error(status_data.get("error", "Unknown error"))
                if st.button("Clear Task", key="clear_failed"):
                    st.session_state.enrichment_task_id = None
                    st.session_state.enrichment_status = None
                    st.rerun()
            else:
                st.info(f"ℹ️ **Status:** {status}")
                st.caption(status_data.get("message", ""))
        else:
            st.error(f"Error fetching status: {status_resp.text}")
    
    except Exception as e:
        st.error(f"Error fetching status: {e}")

if not hitl_enabled:
    st.warning("⚠️ HITL is disabled. Enable it above to use enrichment with approval workflow.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Approval Queue Statistics
# ─────────────────────────────────────────────────────────────────────────────

st.header("📊 Approval Queue Statistics")

try:
    stats_response = requests.get(f"{API_BASE}/hitl/stats", timeout=5)
    if stats_response.status_code == 200:
        stats = stats_response.json()
        
        metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
        
        with metric_col1:
            st.metric("Total Requests", stats["total"])
        with metric_col2:
            st.metric("⏳ Pending", stats["pending"], delta=None)
        with metric_col3:
            st.metric("✅ Approved", stats["approved"])
        with metric_col4:
            st.metric("✏️ Modified", stats["modified"])
        with metric_col5:
            st.metric("❌ Rejected", stats["rejected"])
        
        # Show breakdown by type
        if stats["by_type"]:
            st.subheader("Breakdown by Type")
            type_cols = st.columns(len(stats["by_type"]))
            for idx, (approval_type, count) in enumerate(stats["by_type"].items()):
                with type_cols[idx]:
                    st.metric(approval_type.replace("_", " ").title(), count)
    else:
        st.warning(f"Could not fetch stats: {stats_response.status_code}")

except Exception as e:
    st.error(f"Error fetching stats: {e}")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Pending Approvals
# ─────────────────────────────────────────────────────────────────────────────

st.header("⏳ Pending Approvals")

# Refresh button
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# Fetch pending approvals
try:
    response = requests.get(f"{API_BASE}/hitl/approvals/pending", timeout=5)
    
    if response.status_code == 200:
        approvals = response.json()
        
        if not approvals:
            st.info("✨ No pending approvals - all clear!")
        else:
            st.write(f"Found **{len(approvals)}** pending approval(s)")
            
            for approval in approvals:
                with st.expander(
                    f"🔍 {approval['company_name']} - {approval['field_name']} "
                    f"(Confidence: {approval['confidence']*100:.1f}%)",
                    expanded=True
                ):
                    # Header
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        st.write(f"**Company:** {approval['company_name']}")
                        st.write(f"**Field:** `{approval['field_name']}`")
                    with col2:
                        st.write(f"**Type:** {approval['approval_type'].replace('_', ' ').title()}")
                        st.write(f"**Confidence:** {approval['confidence']*100:.1f}%")
                    with col3:
                        created = datetime.fromisoformat(approval['created_at'].replace('Z', '+00:00'))
                        st.write(f"**Created:**")
                        st.write(created.strftime("%Y-%m-%d %H:%M"))
                    
                    st.divider()
                    
                    # Extracted value
                    st.subheader("📝 Extracted Value")
                    st.code(str(approval['extracted_value']), language="text")
                    
                    # Reasoning
                    st.subheader("💭 LLM Reasoning")
                    st.write(approval['reasoning'])
                    
                    # Sources
                    if approval['sources']:
                        st.subheader("🔗 Sources")
                        for idx, source in enumerate(approval['sources'], 1):
                            st.markdown(f"{idx}. [{source}]({source})")
                    
                    # Metadata (can't use nested expander)
                    if approval['metadata']:
                        st.subheader("📊 Metadata")
                        st.json(approval['metadata'])
                    
                    st.divider()
                    
                    # Action buttons
                    action_col1, action_col2, action_col3 = st.columns([2, 2, 2])
                    
                    with action_col1:
                        st.subheader("✅ Approve")
                        approve_as_is = st.button(
                            "Approve as-is",
                            key=f"approve_{approval['approval_id']}",
                            use_container_width=True,
                            type="primary"
                        )
                    
                    with action_col2:
                        st.subheader("✏️ Modify & Approve")
                        modified_value = st.text_input(
                            "Modified value:",
                            value=str(approval['extracted_value']),
                            key=f"modify_{approval['approval_id']}"
                        )
                        approve_modified = st.button(
                            "Approve with changes",
                            key=f"approve_mod_{approval['approval_id']}",
                            use_container_width=True
                        )
                    
                    with action_col3:
                        st.subheader("❌ Reject")
                        reject_reason = st.text_input(
                            "Rejection reason:",
                            key=f"reject_reason_{approval['approval_id']}"
                        )
                        reject = st.button(
                            "Reject",
                            key=f"reject_{approval['approval_id']}",
                            use_container_width=True,
                            type="secondary"
                        )
                    
                    # Handle actions
                    if approve_as_is:
                        try:
                            approve_response = requests.post(
                                f"{API_BASE}/hitl/approvals/{approval['approval_id']}/approve",
                                json={"reviewer_decision": "Approved as-is via UI"},
                                timeout=5
                            )
                            if approve_response.status_code == 200:
                                st.success(f"✅ Approved: {approval['field_name']}")
                                st.rerun()
                            else:
                                st.error(f"Error: {approve_response.text}")
                        except Exception as e:
                            st.error(f"Error approving: {e}")
                    
                    if approve_modified:
                        try:
                            approve_response = requests.post(
                                f"{API_BASE}/hitl/approvals/{approval['approval_id']}/approve",
                                json={
                                    "approved_value": modified_value,
                                    "reviewer_decision": "Modified and approved via UI"
                                },
                                timeout=5
                            )
                            if approve_response.status_code == 200:
                                st.success(f"✅ Approved with changes: {approval['field_name']}")
                                st.rerun()
                            else:
                                st.error(f"Error: {approve_response.text}")
                        except Exception as e:
                            st.error(f"Error approving: {e}")
                    
                    if reject:
                        try:
                            reject_response = requests.post(
                                f"{API_BASE}/hitl/approvals/{approval['approval_id']}/reject",
                                json={"reviewer_decision": reject_reason or "Rejected via UI"},
                                timeout=5
                            )
                            if reject_response.status_code == 200:
                                st.success(f"❌ Rejected: {approval['field_name']}")
                                st.rerun()
                            else:
                                st.error(f"Error: {reject_response.text}")
                        except Exception as e:
                            st.error(f"Error rejecting: {e}")
    
    else:
        st.error(f"Failed to fetch approvals: {response.status_code}")
        st.code(response.text)

except Exception as e:
    st.error(f"Error connecting to API: {e}")
    st.write(f"API Base: {API_BASE}")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Help & Documentation
# ─────────────────────────────────────────────────────────────────────────────

with st.expander("📖 How HITL Works"):
    st.markdown("""
    ### Human-in-the-Loop Workflow
    
    1. **Workflow Runs**: Agentic RAG workflow extracts data from Tavily searches
    2. **Risk Assessment**: System checks if extraction meets HITL criteria
    3. **Pause & Queue**: If approval needed, workflow pauses and creates approval request
    4. **Human Review**: You review the extraction in this dashboard
    5. **Decision**: Approve (as-is or modified) or reject
    6. **Resume**: Workflow automatically resumes with your decision
    
    ### HITL Scenarios
    
    **High-Risk Fields** ⚠️
    - Financial data (funding, valuation, revenue)
    - Prevents costly errors in critical business metrics
    
    **Low Confidence** 🎯
    - LLM confidence < 70%
    - Catches potential hallucinations or ambiguous data
    
    **Conflicting Information** ⚔️
    - Multiple sources disagree
    - Human judgment needed to resolve conflicts
    
    **Entity Batch Review** 📦
    - Review multiple entities at once (events, products, etc.)
    - Quality control for structured data
    
    **Pre-Save Checkpoint** 💾
    - Final review before committing changes
    - Safety net for complete payload updates
    """)

with st.expander("🔧 API Endpoints"):
    st.code(f"""
# Get pending approvals
GET {API_BASE}/hitl/approvals/pending

# Approve a request
POST {API_BASE}/hitl/approvals/{{approval_id}}/approve
Body: {{"approved_value": "...", "reviewer_decision": "..."}}

# Reject a request
POST {API_BASE}/hitl/approvals/{{approval_id}}/reject
Body: {{"reviewer_decision": "..."}}

# Get statistics
GET {API_BASE}/hitl/stats
    """, language="bash")
