"""
Streamlit Evaluation Dashboard

Displays comparison metrics between Structured and RAG pipeline outputs.
"""

import streamlit as st
import requests
import os
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
import time

# Load environment variables
load_dotenv()

# Get API URL with Docker/local awareness
ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()

if ENVIRONMENT == "docker":
    API_BASE = os.getenv("FASTAPI_URL", "http://fastapi:8000")
else:
    # Running locally - use localhost
    API_BASE = os.getenv("LOCALHOST_URL", "http://localhost:8000")

# Page configuration
st.set_page_config(
    page_title="Evaluation Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 LLM Pipeline Evaluation Dashboard")

st.markdown("""
Compare Structured vs RAG pipeline outputs across multiple evaluation metrics:
- **Factual Accuracy** (0-3): How accurate the information is
- **Schema Compliance** (0-2): Following required structure
- **Provenance Quality** (0-2): Citation and source quality
- **Hallucination Detection** (0-2): Freedom from false information
- **Readability** (0-1): Clarity and formatting
- **Mean Reciprocal Ranking** (0-1): Fact ranking quality
""")

st.divider()

# Fetch available evaluations
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_evaluations():
    """Fetch list of available evaluations."""
    try:
        response = requests.get(f"{API_BASE}/evals", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        st.error(f"Failed to fetch evaluations: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_company_evaluation(company_slug: str) -> Optional[Dict[str, Any]]:
    """Fetch evaluation for a specific company."""
    try:
        response = requests.get(f"{API_BASE}/evals/{company_slug}", timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            st.error(f"Error fetching evaluation: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Failed to fetch evaluation: {e}")
        return None


# Sidebar controls
st.sidebar.header("Evaluation Options")

# Fetch evaluations list
evals_list = fetch_evaluations()

if evals_list and "companies" in evals_list:
    companies = evals_list["companies"]
    
    # Create company selector
    company_options = [f"{c['name']} ({c['slug']})" for c in companies]
    selected_company_option = st.sidebar.selectbox("Select Company", company_options)
    
    # Extract slug from selection
    selected_company_slug = selected_company_option.split("(")[-1].rstrip(")")
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh", key="refresh"):
        st.cache_data.clear()
        st.rerun()
    
    # Show total companies
    st.sidebar.metric("Total Companies Evaluated", len(companies))
    
    # Evaluation button
    st.sidebar.divider()
    st.sidebar.subheader("💡 LLM Evaluation")
    
    if st.sidebar.button("🚀 Run LLM Evaluation", key="run_eval"):
        st.session_state.run_evaluation = True
        st.session_state.eval_company_slug = selected_company_slug
    
    # Show evaluation status
    if hasattr(st.session_state, 'run_evaluation') and st.session_state.run_evaluation:
        with st.sidebar:
            st.info("⏳ Running LLM evaluation... This may take a minute.")
    
    # Batch evaluation button
    if st.sidebar.button("📊 Batch Evaluate All Companies", key="batch_eval"):
        st.session_state.run_batch_evaluation = True
    
    # Fetch evaluation for selected company
    st.markdown("---")
    
    # Check if evaluation was requested
    if hasattr(st.session_state, 'run_evaluation') and st.session_state.run_evaluation:
        # Run evaluation via API
        try:
            with st.spinner(f"🔄 Running LLM evaluation for {selected_company_option.split('(')[0].strip()}..."):
                response = requests.post(
                    f"{API_BASE}/api/evals/evaluate",
                    json={
                        "company_slug": selected_company_slug,
                        "company_name": selected_company_option.split("(")[0].strip()
                    },
                    timeout=120  # 2-minute timeout for LLM evaluation
                )
            
            if response.status_code == 200:
                evaluation_result = response.json()
                st.session_state.evaluation_result = evaluation_result
                st.session_state.run_evaluation = False
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Evaluation failed: {response.status_code} - {response.text}")
                st.session_state.run_evaluation = False
        except requests.exceptions.Timeout:
            st.error("⏱️ Evaluation timed out. The LLM evaluation is taking longer than expected.")
            st.session_state.run_evaluation = False
        except Exception as e:
            st.error(f"❌ Error running evaluation: {str(e)}")
            st.session_state.run_evaluation = False
    
    # Check if batch evaluation was requested
    if hasattr(st.session_state, 'run_batch_evaluation') and st.session_state.run_batch_evaluation:
        try:
            with st.spinner("🔄 Running batch evaluation for all companies..."):
                response = requests.post(
                    f"{API_BASE}/api/evals/evaluate/batch",
                    json={},
                    timeout=300  # 5-minute timeout for batch evaluation
                )
            
            if response.status_code == 200:
                batch_result = response.json()
                st.session_state.batch_evaluation_result = batch_result
                st.session_state.run_batch_evaluation = False
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Batch evaluation failed: {response.status_code}")
                st.session_state.run_batch_evaluation = False
        except requests.exceptions.Timeout:
            st.error("⏱️ Batch evaluation timed out.")
            st.session_state.run_batch_evaluation = False
        except Exception as e:
            st.error(f"❌ Error running batch evaluation: {str(e)}")
            st.session_state.run_batch_evaluation = False
    
    evaluation = fetch_company_evaluation(selected_company_slug)
    
    if evaluation and evaluation.get("status") == "success":
        # Extract data
        company_name = evaluation.get("company_name", "")
        structured = evaluation.get("structured", {})
        rag = evaluation.get("rag", {})
        winners = evaluation.get("winners", {})
        
        st.header(f"📈 Evaluation: {company_name}")
        
        # Show evaluation metadata
        eval_timestamp = evaluation.get("timestamp", "")
        if eval_timestamp:
            st.caption(f"Evaluated at: {eval_timestamp}")
        
        # Show evaluation badges
        col_badge1, col_badge2 = st.columns(2)
        
        with col_badge1:
            total_score_winner = winners.get("total_score")
            struct_score = structured.get('total_score', 0)
            rag_score = rag.get('total_score', 0)
            
            if total_score_winner == "structured":
                st.success(f"✅ Structured Pipeline Wins ({struct_score:.1f} vs {rag_score:.1f})")
            elif total_score_winner == "rag":
                st.success(f"✅ RAG Pipeline Wins ({rag_score:.1f} vs {struct_score:.1f})")
            else:
                st.info(f"🤝 Tie: Both pipelines scored {struct_score:.1f}")
        
        with col_badge2:
            mrr_diff = abs((structured.get('mrr_score', 0) or 0) - (rag.get('mrr_score', 0) or 0))
            st.metric("MRR Difference", f"{mrr_diff:.3f}")
        
        st.markdown("---")
        
        # Create comparison table
        st.subheader("Metric Comparison Table")
        
        # Prepare data for table
        metrics_data = {
            "Metric": [
                "Factual Accuracy",
                "Schema Compliance",
                "Provenance Quality",
                "Hallucination Detection",
                "Readability",
                "Mean Reciprocal Ranking",
                "Total Score"
            ],
            "Structured": [
                f"{structured.get('factual_accuracy', '-')}/3",
                f"{structured.get('schema_compliance', '-')}/2",
                f"{structured.get('provenance_quality', '-')}/2",
                f"{structured.get('hallucination_detection', '-')}/2",
                f"{structured.get('readability', '-')}/1",
                f"{structured.get('mrr_score', '-'):.3f}" if structured.get('mrr_score') else "-",
                f"{structured.get('total_score', '-'):.1f}/14" if structured.get('total_score') else "-"
            ],
            "RAG": [
                f"{rag.get('factual_accuracy', '-')}/3",
                f"{rag.get('schema_compliance', '-')}/2",
                f"{rag.get('provenance_quality', '-')}/2",
                f"{rag.get('hallucination_detection', '-')}/2",
                f"{rag.get('readability', '-')}/1",
                f"{rag.get('mrr_score', '-'):.3f}" if rag.get('mrr_score') else "-",
                f"{rag.get('total_score', '-'):.1f}/14" if rag.get('total_score') else "-"
            ],
            "Winner": [
                winners.get("factual_accuracy", "-").title(),
                winners.get("schema_compliance", "-").title(),
                winners.get("provenance_quality", "-").title(),
                winners.get("hallucination_detection", "-").title(),
                winners.get("readability", "-").title(),
                winners.get("mrr_score", "-").title(),
                "-"
            ]
        }
        
        df = pd.DataFrame(metrics_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Visualization: Score Comparison
        st.subheader("Visual Comparison")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Radar chart data
            metrics = [
                "Factual\nAccuracy",
                "Schema\nCompliance",
                "Provenance",
                "Hallucination",
                "Readability",
                "MRR"
            ]
            
            # Normalize scores to 0-1 range for radar chart
            struct_values = [
                (structured.get('factual_accuracy', 0) or 0) / 3,
                (structured.get('schema_compliance', 0) or 0) / 2,
                (structured.get('provenance_quality', 0) or 0) / 2,
                (structured.get('hallucination_detection', 0) or 0) / 2,
                (structured.get('readability', 0) or 0) / 1,
                structured.get('mrr_score', 0) or 0
            ]
            
            rag_values = [
                (rag.get('factual_accuracy', 0) or 0) / 3,
                (rag.get('schema_compliance', 0) or 0) / 2,
                (rag.get('provenance_quality', 0) or 0) / 2,
                (rag.get('hallucination_detection', 0) or 0) / 2,
                (rag.get('readability', 0) or 0) / 1,
                rag.get('mrr_score', 0) or 0
            ]
            
            # Create radar chart
            fig_radar = go.Figure()
            
            fig_radar.add_trace(go.Scatterpolar(
                r=struct_values,
                theta=metrics,
                fill='toself',
                name='Structured',
                line=dict(color='#1f77b4')
            ))
            
            fig_radar.add_trace(go.Scatterpolar(
                r=rag_values,
                theta=metrics,
                fill='toself',
                name='RAG',
                line=dict(color='#ff7f0e')
            ))
            
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                showlegend=True,
                height=400
            )
            
            st.plotly_chart(fig_radar, use_container_width=True)
        
        with col2:
            # Bar chart for total scores
            fig_bar = go.Figure()
            
            fig_bar.add_trace(go.Bar(
                x=["Structured", "RAG"],
                y=[
                    structured.get('total_score', 0) or 0,
                    rag.get('total_score', 0) or 0
                ],
                text=[
                    f"{structured.get('total_score', 0) or 0:.1f}/14",
                    f"{rag.get('total_score', 0) or 0:.1f}/14"
                ],
                textposition="auto",
                marker=dict(color=['#1f77b4', '#ff7f0e']),
                showlegend=False
            ))
            
            fig_bar.update_layout(
                title="Total Score Comparison",
                yaxis_title="Score",
                xaxis_title="Pipeline",
                height=400,
                yaxis=dict(range=[0, 14])
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # MRR Analysis
        st.subheader("Mean Reciprocal Ranking (MRR) Analysis")
        
        st.markdown("""
        **MRR** measures how well important facts are ranked in the output:
        - **1.0**: Most relevant fact appears first
        - **0.5**: Most relevant fact appears second
        - **0.0**: No relevant facts found
        
        Higher MRR indicates better information organization.
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            struct_mrr = structured.get('mrr_score', 0) or 0
            st.metric("Structured MRR", f"{struct_mrr:.3f}", 
                     delta=f"{(struct_mrr - (rag.get('mrr_score', 0) or 0)):.3f}")
        
        with col2:
            rag_mrr = rag.get('mrr_score', 0) or 0
            st.metric("RAG MRR", f"{rag_mrr:.3f}")
        
        with col3:
            st.metric("MRR Difference", f"{abs(struct_mrr - rag_mrr):.3f}")
        
        # Score breakdown
        st.subheader("Detailed Score Breakdown")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Structured Pipeline**")
            st.write(f"- Factual Accuracy: {structured.get('factual_accuracy', '-')}/3")
            st.write(f"- Schema Compliance: {structured.get('schema_compliance', '-')}/2")
            st.write(f"- Provenance Quality: {structured.get('provenance_quality', '-')}/2")
            st.write(f"- Hallucination Detection: {structured.get('hallucination_detection', '-')}/2")
            st.write(f"- Readability: {structured.get('readability', '-')}/1")
            struct_score = structured.get('total_score')
            struct_total = f"{struct_score:.1f}/14" if struct_score is not None else "-/14"
            st.write(f"- **Total: {struct_total}**")
            
            if structured.get('notes'):
                st.info(f"Notes: {structured.get('notes')}")
        
        with col2:
            st.write("**RAG Pipeline**")
            st.write(f"- Factual Accuracy: {rag.get('factual_accuracy', '-')}/3")
            st.write(f"- Schema Compliance: {rag.get('schema_compliance', '-')}/2")
            st.write(f"- Provenance Quality: {rag.get('provenance_quality', '-')}/2")
            st.write(f"- Hallucination Detection: {rag.get('hallucination_detection', '-')}/2")
            st.write(f"- Readability: {rag.get('readability', '-')}/1")
            rag_score = rag.get('total_score')
            rag_total = f"{rag_score:.1f}/14" if rag_score is not None else "-/14"
            st.write(f"- **Total: {rag_total}**")
            
            if rag.get('notes'):
                st.info(f"Notes: {rag.get('notes')}")
        
    else:
        st.warning(f"⚠️ No evaluation results for {selected_company_slug}")
        st.info(f"Run the evaluation:\n```\npython src/evals/eval_runner.py --company {selected_company_slug}\n```")
    
    # Batch comparison across all companies
    st.divider()
    st.subheader("📊 Batch Evaluation Summary")
    
    if len(companies) > 1:
        # Fetch all evaluations
        all_evals = []
        
        for company in companies:
            slug = company['slug']
            eval_data = fetch_company_evaluation(slug)
            if eval_data:
                all_evals.append({
                    'company': company['name'],
                    'slug': slug,
                    'structured_score': eval_data.get('structured', {}).get('total_score', 0),
                    'rag_score': eval_data.get('rag', {}).get('total_score', 0),
                    'struct_mrr': eval_data.get('structured', {}).get('mrr_score', 0),
                    'rag_mrr': eval_data.get('rag', {}).get('mrr_score', 0),
                })
        
        if all_evals:
            # Create batch comparison table
            batch_df = pd.DataFrame(all_evals)
            
            st.dataframe(
                batch_df[[
                    'company',
                    'structured_score',
                    'rag_score',
                    'struct_mrr',
                    'rag_mrr'
                ]],
                column_config={
                    'company': st.column_config.TextColumn('Company'),
                    'structured_score': st.column_config.NumberColumn('Struct Score (/14)', format='%.1f'),
                    'rag_score': st.column_config.NumberColumn('RAG Score (/14)', format='%.1f'),
                    'struct_mrr': st.column_config.NumberColumn('Struct MRR', format='%.3f'),
                    'rag_mrr': st.column_config.NumberColumn('RAG MRR', format='%.3f'),
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Average MRR
            st.markdown("**Average MRR Across Companies**")
            col1, col2 = st.columns(2)
            
            with col1:
                avg_struct_mrr = batch_df['struct_mrr'].mean()
                st.metric("Structured Avg MRR", f"{avg_struct_mrr:.3f}")
            
            with col2:
                avg_rag_mrr = batch_df['rag_mrr'].mean()
                st.metric("RAG Avg MRR", f"{avg_rag_mrr:.3f}")
        
    else:
        st.info("Run evaluations for multiple companies to see batch comparison")

else:
    st.warning("⚠️ No evaluations found")
    st.info("""
    To get started with evaluation:
    
    1. Generate dashboards:
       ```bash
       # Structured pipeline
       curl http://localhost:8000/dashboard/structured?company_name=World%20Labs
       
       # RAG pipeline
       curl http://localhost:8000/dashboard/rag?company_name=World%20Labs
       ```
    
    2. Run evaluation:
       ```bash
       python src/evals/eval_runner.py --batch
       ```
    
    3. Refresh this page to view results
    """)
