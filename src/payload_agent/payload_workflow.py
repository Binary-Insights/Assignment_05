"""
LangGraph-Based Payload Workflow with LangSmith Tracing.

This module implements the actual LangGraph state machine for payload processing:
- Node: retrieve_payload_node
- Node: validate_payload_node  
- Node: update_payload_node (with vector fills from Pinecone)
- Conditional edges based on validation status
- Full LangSmith tracing

State schema:
{
    "company_id": str,
    "payload": Payload | None,
    "validation_result": dict,
    "update_result": dict,
    "status": str,
    "error": str | None,
}
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langsmith import traceable

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from payload_agent.tools import (
    get_latest_structured_payload,
    validate_payload,
    update_payload,
)
from payload_agent.tools.rag_adapter import create_pinecone_adapter

load_dotenv()
logger = logging.getLogger(__name__)


# =============================================================================
# State Schema
# =============================================================================

class PayloadWorkflowState(TypedDict):
    """State for the payload processing workflow."""
    company_id: str
    payload: Any  # Pydantic Payload object
    validation_result: Dict[str, Any]
    update_result: Dict[str, Any]
    status: str
    error: str | None
    rag_search_tool: Any  # Callable for vector search
    llm: Any  # LLM for extraction


# =============================================================================
# Graph Nodes (with LangSmith tracing)
# =============================================================================

@traceable(name="retrieve_payload_node", run_type="chain")
def retrieve_payload_node(state: PayloadWorkflowState) -> PayloadWorkflowState:
    """
    Node: Retrieve payload from disk.
    
    Input: company_id
    Output: payload (or error)
    """
    company_id = state["company_id"]
    logger.info(f"action=retrieve stage=start company_id={company_id}")
    
    try:
        payload = get_latest_structured_payload.invoke({"company_id": company_id})
        logger.info(f"action=retrieve stage=complete company_id={company_id} status=success")
        
        return {
            **state,
            "payload": payload,
            "status": "retrieved",
            "error": None,
        }
    except Exception as e:
        logger.error(f"action=retrieve stage=error company_id={company_id} error={e}")
        return {
            **state,
            "payload": None,
            "status": "error",
            "error": str(e),
        }


@traceable(name="validate_payload_node", run_type="chain")
def validate_payload_node(state: PayloadWorkflowState) -> PayloadWorkflowState:
    """
    Node: Validate payload structure.
    
    Input: payload
    Output: validation_result
    """
    payload = state["payload"]
    company_id = state["company_id"]
    
    if not payload:
        logger.warning(f"action=validate stage=skip company_id={company_id} reason=no_payload")
        return {
            **state,
            "validation_result": {"status": "skipped", "issues": ["No payload to validate"]},
            "status": "error",
        }
    
    logger.info(f"action=validate stage=start company_id={company_id}")
    
    try:
        validation_result = validate_payload.invoke({"company_id": company_id})
        logger.info(f"action=validate stage=complete company_id={company_id} validation_status={validation_result['status']}")
        
        return {
            **state,
            "validation_result": validation_result,
            "status": "validated",
        }
    except Exception as e:
        logger.error(f"action=validate stage=error company_id={company_id} error={e}")
        return {
            **state,
            "validation_result": {"status": "error", "issues": [str(e)]},
            "status": "error",
            "error": str(e),
        }


@traceable(name="update_payload_node", run_type="chain")
def update_payload_node(state: PayloadWorkflowState) -> PayloadWorkflowState:
    """
    Node: Update payload with vector fills from Pinecone.
    
    Input: payload, rag_search_tool, llm
    Output: update_result (filled fields, provenance, confidence)
    """
    payload = state["payload"]
    company_id = state["company_id"]
    rag_search_tool = state.get("rag_search_tool")
    llm = state.get("llm")
    
    if not payload:
        logger.warning(f"action=update stage=skip company_id={company_id} reason=no_payload")
        return {
            **state,
            "update_result": {"status": "skipped"},
            "status": "error",
        }
    
    logger.info(f"action=update stage=start company_id={company_id}")
    
    try:
        update_result = update_payload.invoke({
            "company_id": company_id,
            "rag_search_tool": rag_search_tool,
            "llm": llm,
        })
        
        # Handle the actual return structure from update_payload
        filled_count = update_result.get('filled_count', 0)
        output_file = update_result.get('output_file', 'N/A')
        
        logger.info(
            f"action=update stage=complete company_id={company_id} "
            f"status={update_result.get('status')} "
            f"filled_count={filled_count} "
            f"output_file={output_file}"
        )
        
        return {
            **state,
            "update_result": update_result,
            "status": "completed",
        }
    except Exception as e:
        logger.error(f"action=update stage=error company_id={company_id} error={e}")
        return {
            **state,
            "update_result": {"status": "error", "error": str(e)},
            "status": "error",
            "error": str(e),
        }


# =============================================================================
# Conditional Edge Logic
# =============================================================================

def should_update(state: PayloadWorkflowState) -> str:
    """
    Decide whether to proceed to update node or end.
    
    Returns:
        "update" if validation succeeded, "end" otherwise
    """
    validation_status = state.get("validation_result", {}).get("status", "unknown")
    
    if validation_status == "valid":
        return "update"
    else:
        logger.warning(f"Skipping update due to validation status: {validation_status}")
        return "end"


# =============================================================================
# Graph Builder
# =============================================================================

def create_payload_workflow_graph(
    rag_search_tool: Any = None,
    llm: Any = None,
) -> StateGraph:
    """
    Create the LangGraph workflow for payload processing.
    
    Graph structure:
        START -> retrieve -> validate -> [conditional] -> update -> END
                                               |
                                               +-> END (if validation failed)
    
    Args:
        rag_search_tool: Callable for Pinecone vector search
        llm: LLM for extraction assistance
        
    Returns:
        Compiled StateGraph
    """
    # Create graph
    workflow = StateGraph(PayloadWorkflowState)
    
    # Add nodes
    workflow.add_node("retrieve", retrieve_payload_node)
    workflow.add_node("validate", validate_payload_node)
    workflow.add_node("update", update_payload_node)
    
    # Add edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "validate")
    
    # Conditional edge: only update if validation succeeded
    workflow.add_conditional_edges(
        "validate",
        should_update,
        {
            "update": "update",
            "end": END,
        }
    )
    
    workflow.add_edge("update", END)
    
    # Compile
    app = workflow.compile()
    
    logger.info("LangGraph payload workflow compiled successfully")
    return app


# =============================================================================
# Graph Visualization
# =============================================================================

def save_workflow_graph_visualization(graph, output_path: str = "data/graph/payload_workflow_graph.png"):
    """
    Save LangGraph workflow structure as an image.
    
    Args:
        graph: Compiled LangGraph workflow
        output_path: Path to save the visualization (default: data/graph/payload_workflow_graph.png)
    
    Returns:
        str: Path to saved visualization file, or None if failed
    """
    try:
        from pathlib import Path
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Try to generate PNG using Mermaid
        try:
            png_data = graph.get_graph().draw_mermaid_png()
            
            with open(output_file, "wb") as f:
                f.write(png_data)
            
            logger.info(f"✅ Workflow graph visualization saved to: {output_file}")
            return str(output_file)
            
        except Exception as png_error:
            logger.warning(f"⚠️  Could not generate PNG visualization: {png_error}")
            
            # Fallback: save as ASCII diagram
            try:
                ascii_diagram = graph.get_graph().draw_ascii()
                output_file = output_file.with_suffix(".txt")
                
                with open(output_file, "w") as f:
                    f.write(ascii_diagram)
                
                logger.info(f"✅ Workflow ASCII diagram saved to: {output_file}")
                return str(output_file)
                
            except Exception as ascii_error:
                logger.warning(f"⚠️  Could not save ASCII diagram: {ascii_error}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Error saving workflow graph visualization: {e}")
        return None


# =============================================================================
# Convenience Runner
# =============================================================================

@traceable(name="run_payload_workflow", run_type="chain")
def run_payload_workflow(
    company_id: str,
    rag_search_tool: Any = None,
    llm: Any = None,
) -> Dict[str, Any]:
    """
    Execute the full payload workflow for a company.
    
    Args:
        company_id: Company identifier
        rag_search_tool: Optional Pinecone search callable
        llm: Optional LLM for extraction
        
    Returns:
        Final state dict with all results
    """
    logger.info(f"Starting payload workflow for company_id={company_id}")
    
    # Create initial state
    initial_state: PayloadWorkflowState = {
        "company_id": company_id,
        "payload": None,
        "validation_result": {},
        "update_result": {},
        "status": "started",
        "error": None,
        "rag_search_tool": rag_search_tool,
        "llm": llm,
    }
    
    # Create and run graph
    graph = create_payload_workflow_graph(rag_search_tool, llm)
    final_state = graph.invoke(initial_state)
    
    logger.info(f"Payload workflow completed for company_id={company_id} status={final_state['status']}")
    
    return final_state


# =============================================================================
# CLI Entry Point (for direct execution)
# =============================================================================

def main():
    """Main entry point for running workflow from command line."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python payload_workflow.py <company_id>")
        print("Example: python payload_workflow.py abridge")
        sys.exit(1)
    
    company_id = sys.argv[1]
    
    print("\n" + "="*80)
    print(f"PAYLOAD WORKFLOW - {company_id.upper()}")
    print("="*80)
    print(f"\n📊 LangSmith Tracing: {'ENABLED' if os.getenv('LANGCHAIN_TRACING_V2') else 'DISABLED'}")
    if os.getenv('LANGCHAIN_PROJECT'):
        print(f"   Project: {os.getenv('LANGCHAIN_PROJECT')}")
    
    try:
        # Try to create RAG adapter for vector fills
        rag_search_tool = None
        try:
            print("\n🔌 Attempting Pinecone connection...")
            rag_search_tool = create_pinecone_adapter()
            print("   ✅ Pinecone adapter ready")
        except Exception as e:
            print(f"   ⚠️  Pinecone unavailable: {str(e)[:60]}")
        
        # Initialize LLM for field extraction
        llm = None
        try:
            from langchain_openai import ChatOpenAI
            print("\n🤖 Initializing OpenAI LLM...")
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                max_tokens=500,
                api_key=os.getenv("OPENAI_API_KEY")
            )
            print("   ✅ LLM initialized (gpt-4o-mini)")
        except Exception as e:
            print(f"   ⚠️  LLM initialization failed: {str(e)[:60]}")
        
        # Create and save workflow graph visualization
        print("\n📊 Generating workflow graph visualization...")
        try:
            graph = create_payload_workflow_graph(rag_search_tool, llm)
            graph_path = save_workflow_graph_visualization(graph)
            if graph_path:
                print(f"   ✅ Graph saved to: {graph_path}")
            else:
                print(f"   ⚠️  Could not save graph visualization")
        except Exception as e:
            print(f"   ⚠️  Graph visualization failed: {str(e)[:60]}")
        
        # Run workflow
        print(f"\n🚀 Running workflow...")
        final_state = run_payload_workflow(
            company_id=company_id,
            rag_search_tool=rag_search_tool,
            llm=llm
        )
        
        # Display results
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        
        print(f"\n✓ Status: {final_state['status']}")
        
        # Validation
        if final_state.get('validation_result'):
            val = final_state['validation_result']
            print(f"\n🔍 Validation: {val.get('status')}")
            if val.get('issues'):
                for issue in val['issues'][:3]:
                    print(f"   ⚠️  {issue}")
        
        # Update results
        if final_state.get('update_result'):
            update = final_state['update_result']
            print(f"\n🔄 Update:")
            print(f"   Status: {update.get('status')}")
            
            # Handle actual return structure from update_payload
            filled_count = update.get('filled_count', 0)
            output_file = update.get('output_file')
            
            if filled_count > 0:
                print(f"   Filled: {filled_count} fields")
            if output_file:
                print(f"   Output: {output_file}")
            if update.get('message'):
                print(f"   Message: {update.get('message')}")
        
        # Payload info
        if final_state.get('payload'):
            payload = final_state['payload']
            print(f"\n📊 Payload Data:")
            print(f"   Events: {len(payload.events)}")
            print(f"   Products: {len(payload.products)}")
            print(f"   Leadership: {len(payload.leadership)}")
            print(f"   Snapshots: {len(payload.snapshots)}")
        
        # Error details
        if final_state.get('error'):
            print(f"\n❌ Error: {final_state['error']}")
        
        print("\n" + "="*80)
        print("✅ WORKFLOW COMPLETE")
        print("="*80)
        
        # LangSmith info
        if os.getenv('LANGCHAIN_TRACING_V2'):
            print(f"\n📈 View trace at: https://smith.langchain.com/")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
