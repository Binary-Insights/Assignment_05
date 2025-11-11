import streamlit as st
import requests
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API URL with Docker/local awareness
# When in Docker container, use service name; otherwise use localhost
ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()

if ENVIRONMENT == "docker":
    # Running in Docker - use Docker service name
    API_BASE = os.getenv("FASTAPI_URL", "http://fastapi:8000")
else:
    # Running locally - use localhost
    API_BASE = os.getenv("LOCALHOST_URL", "http://localhost:8000")

# ─────────────────────────────────────────────────────────────────────────────
#  Utility Functions for Saving LLM Responses
# ─────────────────────────────────────────────────────────────────────────────

def ensure_directories():
    """Ensure all required directories exist."""
    base_dir = Path("data/llm_response")
    (base_dir / "markdown").mkdir(parents=True, exist_ok=True)
    (base_dir / "json").mkdir(parents=True, exist_ok=True)
    return base_dir


def load_master_json(master_path: Path) -> dict:
    """Load the master JSON file."""
    if master_path.exists():
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading master JSON: {e}")
            return {}
    return {}


def save_master_json(master_path: Path, data: dict):
    """Save the master JSON file."""
    try:
        with open(master_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Error saving master JSON: {e}")


def load_company_json(company_json_path: Path) -> dict:
    """Load company-specific JSON file."""
    if company_json_path.exists():
        try:
            with open(company_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Error loading company JSON: {e}")
            return {"company_slug": company_json_path.stem, "structured": None, "rag": None}
    return {"company_slug": company_json_path.stem, "structured": None, "rag": None}


def save_dashboard_response(company_slug: str, pipeline_type: str, response_data: dict):
    """
    Save dashboard response to both markdown and JSON files.
    
    Args:
        company_slug: Company slug identifier
        pipeline_type: 'structured' or 'rag'
        response_data: Response data from API
    """
    try:
        base_dir = ensure_directories()
        
        # Save markdown
        markdown_dir = base_dir / "markdown" / company_slug
        markdown_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = markdown_dir / f"{pipeline_type}.md"
        
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(response_data.get("markdown", ""))
        
        # Prepare JSON data
        json_data = {
            "company_name": response_data.get("company_name", ""),
            "company_slug": company_slug,
            "pipeline_type": pipeline_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "markdown_file": str(markdown_path.relative_to("data/llm_response")),
            "content": response_data.get("markdown", ""),  # Store full markdown content
        }
        
        # Include context results for RAG pipeline
        if pipeline_type == "rag" and "context_results" in response_data:
            json_data["context_results"] = response_data.get("context_results", [])
        
        # Save individual company JSON
        json_dir = base_dir / "json" / company_slug
        json_dir.mkdir(parents=True, exist_ok=True)
        company_json_path = json_dir / "responses.json"
        
        company_json = load_company_json(company_json_path)
        company_json[pipeline_type] = json_data
        company_json["company_slug"] = company_slug
        
        with open(company_json_path, 'w', encoding='utf-8') as f:
            json.dump(company_json, f, indent=2, ensure_ascii=False)
        
        # Update master JSON
        master_path = base_dir / "master.json"
        master_json = load_master_json(master_path)
        
        if company_slug not in master_json:
            master_json[company_slug] = {
                "company_name": response_data.get("company_name", ""),
                "company_slug": company_slug,
                "structured": None,
                "rag": None,
            }
        
        master_json[company_slug][pipeline_type] = json_data
        save_master_json(master_path, master_json)
        
        st.success(f"✅ Saved {pipeline_type} dashboard for {company_slug}")
        
        # Display save details
        with st.expander("📁 Save Details"):
            st.write(f"**Markdown:** `{markdown_path}`")
            st.write(f"**Company JSON:** `{company_json_path}`")
            st.write(f"**Master JSON:** `{master_path}`")
        
    except Exception as e:
        st.error(f"❌ Error saving dashboard: {e}")


def view_saved_responses(company_slug: str):
    """Display saved responses for a company."""
    try:
        base_dir = Path("data/llm_response")
        company_json_path = base_dir / "json" / company_slug / "responses.json"
        
        if company_json_path.exists():
            with open(company_json_path, 'r', encoding='utf-8') as f:
                company_data = json.load(f)
            
            st.write("**Saved Responses:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if company_data.get("structured"):
                    st.write("✅ **Structured** - Saved")
                    st.caption(company_data["structured"].get("timestamp", ""))
                else:
                    st.write("⚪ **Structured** - Not yet generated")
            
            with col2:
                if company_data.get("rag"):
                    st.write("✅ **RAG** - Saved")
                    st.caption(company_data["rag"].get("timestamp", ""))
                else:
                    st.write("⚪ **RAG** - Not yet generated")
        else:
            st.info("No saved responses yet for this company")
    
    except Exception as e:
        st.warning(f"Could not display saved responses: {e}")

st.set_page_config(
    page_title="PE Dashboard (AI 50)",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 Project ORBIT – PE Dashboard for Forbes AI 50")
st.markdown("---")

# Introduction
st.markdown("""
Welcome to the **Project ORBIT Dashboard** for comprehensive analysis of Forbes AI 50 companies.

This multi-page application provides:
- **Generator** (this page): Generate dashboards using Structured and RAG pipelines
- **Evaluation Dashboard**: Compare pipeline performance across metrics

Use the sidebar to navigate between pages.
""")

st.divider()

# Debug: Display API configuration
with st.expander("🔧 Debug - API Configuration"):
    st.write(f"**ENVIRONMENT:** `{ENVIRONMENT}`")
    st.write(f"**API_BASE:** `{API_BASE}`")
    st.write(f"**FASTAPI_URL (from .env):** `{os.getenv('FASTAPI_URL', 'Not set')}`")

# Initialize session state for persisting outputs
if "structured_data" not in st.session_state:
    st.session_state.structured_data = None
if "rag_data" not in st.session_state:
    st.session_state.rag_data = None

st.header("📋 Dashboard Generator")
st.markdown("Select a company and generate dashboards using either pipeline.")

try:
    response = requests.get(f"{API_BASE}/companies", timeout=5).json()
    # Extract companies from the response object
    companies = response.get("companies", []) if isinstance(response, dict) else response
except Exception as e:
    st.warning(f"⚠️ Failed to load companies: {e}")
    companies = []

names = [c["company_name"] for c in companies] if companies else ["ExampleAI"]
choice = st.selectbox("Select company", names)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Structured pipeline")
    if st.button("Generate (Structured)"):
        # Use company name directly
        try:
            # Call the new /dashboard/structured endpoint (POST)
            # Auto-extraction is enabled by default
            with st.spinner("🔄 Generating dashboard... (this may take a few minutes if extraction is needed)"):
                resp = requests.post(
                    f"{API_BASE}/dashboard/structured",
                    params={"company_name": choice},
                    timeout=1200  # 20 minute timeout for ingest + extraction + generation
                )
            
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.structured_data = data  # Store in session state
                
                # Save the response
                company_slug = data.get("company_slug", choice.lower().replace(" ", "-"))
                save_dashboard_response(company_slug, "structured", data)
                
                st.success(f"✅ Dashboard generated for {choice}")
            
            elif resp.status_code == 404:
                error_detail = resp.json().get("detail", "Payload not found")
                st.warning(f"⚠️ {error_detail}")
                
                # Parse the error to provide helpful guidance
                if "discovery pipeline" in error_detail.lower():
                    st.info(
                        "**Next Steps:**\n"
                        "1. Run: `python src/discover/process_discovered_pages.py`\n"
                        "2. Then click 'Generate (Structured)' again"
                    )
                elif "run manually" in error_detail.lower():
                    st.info(
                        "**Extraction might be too complex.** Try running manually:\n"
                        f"```bash\n"
                        f"python src/rag/ingest_to_pinecone.py --company-slug {choice.lower().replace(' ', '_').replace('-', '_')}\n"
                        f"python src/rag/structured_extraction_search.py --company-slug {choice.lower().replace(' ', '_').replace('-', '_')}\n"
                        f"```\n"
                        "Then click 'Generate (Structured)' again"
                    )
            
            elif resp.status_code == 202:
                st.info(
                    "⏳ **Extraction in progress...**\n\n"
                    "The extraction pipeline is running in the background. "
                    "This can take 5-15 minutes. "
                    "Check the server logs for progress."
                )
            
            else:
                st.error(f"❌ Error: {resp.status_code}")
                try:
                    st.json(resp.json())
                except:
                    st.error(resp.text)
        
        except requests.exceptions.Timeout:
            st.error(
                "⏱️ **Request timeout** - The pipeline took longer than 20 minutes.\n\n"
                "This can happen if:\n"
                "- OpenAI API is slow\n"
                "- Pinecone is overloaded\n"
                "- Network issues\n\n"
                "Check the server logs for progress or try again."
            )
        except Exception as e:
            st.error(f"❌ Error generating dashboard: {e}")
    
    # Display saved responses status
    company_slug = choice.lower().replace(" ", "-")
    view_saved_responses(company_slug)
    
    st.divider()
    
    # Display stored structured data if available
    if st.session_state.structured_data:
        data = st.session_state.structured_data
        
        # Create tabs for dashboard and payload
        struct_tab1, struct_tab2 = st.tabs(["Dashboard", "Structured Payload"])
        
        with struct_tab1:
            # Display the markdown dashboard
            if "markdown" in data and data["markdown"]:
                st.markdown(data["markdown"])
            else:
                st.warning("No dashboard content generated")
        
        with struct_tab2:
            # Load and display the structured JSON payload
            company_slug = data.get("company_slug", "")
            if company_slug:
                try:
                    import json
                    from pathlib import Path
                    
                    # Construct path to payload file
                    payload_path = Path("data/payloads") / f"{company_slug}.json"
                    
                    if payload_path.exists():
                        with open(payload_path, 'r') as f:
                            payload_json = json.load(f)
                        
                        # Display as markdown code block with JSON formatting
                        st.write("**Structured Payload (JSON):**")
                        st.json(payload_json)
                        
                        # Also provide a copy-friendly code block
                        st.write("**Raw JSON:**")
                        st.code(json.dumps(payload_json, indent=2), language="json")
                    else:
                        st.warning(f"❌ Payload file not found at: `{payload_path}`")
                
                except Exception as e:
                    st.error(f"❌ Failed to load payload: {e}")
            else:
                st.info("No company slug available to load payload")

with col2:
    st.subheader("RAG pipeline")
    if st.button("Generate (RAG)"):
        # Use company name directly
        try:
            # Call the new /dashboard/rag endpoint
            resp = requests.post(
                f"{API_BASE}/dashboard/rag",
                params={"company_name": choice},
                timeout=30  # Longer timeout for LLM generation
            )
            
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.rag_data = data  # Store in session state
                
                # Save the response
                company_slug = data.get("company_slug", choice.lower().replace(" ", "-"))
                save_dashboard_response(company_slug, "rag", data)
                
                st.success(f"✅ Dashboard generated for {choice}")
            
            elif resp.status_code == 404:
                st.warning(f"⚠️ RAG collection not available for **{choice}**")
                st.info("The collection for this company hasn't been indexed yet. Please run the RAG indexing first.")
            
            else:
                st.error(f"❌ Error: {resp.status_code}")
                try:
                    st.json(resp.json())
                except:
                    st.error(resp.text)
        
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timeout - LLM generation may be slow or API not responding")
        except Exception as e:
            st.error(f"❌ Error generating dashboard: {e}")
    
    # Display stored RAG data if available
    if st.session_state.rag_data:
        data = st.session_state.rag_data
        
        # Create tabs for dashboard and context
        rag_tab1, rag_tab2 = st.tabs(["Dashboard", "Retrieved Context (Top-K)"])
        
        with rag_tab1:
            # Display the markdown dashboard
            if "markdown" in data and data["markdown"]:
                st.markdown(data["markdown"])
            else:
                st.warning("No dashboard content generated")
        
        with rag_tab2:
            # Display the retrieved context
            context_results = data.get("context_results", [])
            
            if context_results:
                st.write(f"**Retrieved {len(context_results)} context chunks:**")
                
                for idx, result in enumerate(context_results, 1):
                    similarity_score = result.get('similarity_score', 0)
                    result_id = result.get('id', 'N/A')
                    
                    with st.expander(f"Context {idx} (ID: {result_id}, Score: {similarity_score:.4f})", expanded=idx == 1):
                        # Create columns for better layout
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**ID:**")
                            st.code(str(result_id), language="text")
                            
                            st.write("**Similarity Score:**")
                            st.metric("Score", f"{similarity_score:.4f}")
                        
                        with col2:
                            st.write("**Metadata:**")
                            if result.get("metadata"):
                                # Display metadata fields in a formatted way
                                metadata = result.get("metadata", {})
                                for key, value in metadata.items():
                                    st.write(f"- **{key}:** `{value}`")
                            else:
                                st.info("No metadata available")
                        
                        # Display text content below metadata
                        st.write("**Text Content:**")
                        st.info(result.get("text", ""))
            else:
                st.info("No context results available")
