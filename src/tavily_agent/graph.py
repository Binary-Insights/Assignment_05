"""
LangGraph state and node definitions for Agentic RAG.
Defines the workflow graph for payload enrichment.
"""

import json
import logging
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Annotated

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from langsmith import traceable

# try:
#     from langsmith import traceable
# except ImportError:
#     # Fallback if langsmith not installed
#     def traceable(func):
#         return func

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import LLM_MODEL, LLM_TEMPERATURE, MAX_ITERATIONS
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.vector_db_manager import VectorDBManager, get_vector_db_manager
from tavily_agent.tools import get_tool_manager
from tavily_agent.llm_extraction import LLMExtractionChain, ChainedExtractionResult

logger = logging.getLogger(__name__)


# ===========================
# State Definitions
# ===========================

class PayloadEnrichmentState(BaseModel):
    """State for payload enrichment workflow."""
    
    # Payload data
    company_name: str
    company_id: str
    current_payload: Dict[str, Any]
    original_payload: Dict[str, Any]
    
    # Processing metadata
    iteration: int = 0
    max_iterations: int = MAX_ITERATIONS
    
    # Null fields to fill (stored as dicts for LangGraph compatibility)
    null_fields: List[Dict[str, Any]] = Field(default_factory=list)
    current_null_field: Optional[Dict[str, Any]] = None
    
    # Messages for LLM
    messages: List[BaseMessage] = Field(default_factory=list)
    
    # Tool results
    search_results: Optional[Dict[str, Any]] = None
    extracted_values: Dict[str, Any] = Field(default_factory=dict)
    
    # Vector DB context
    vector_context: str = ""
    
    # Processing state
    status: str = "initialized"  # initialized, analyzing, searching, updating, completed
    errors: List[str] = Field(default_factory=list)


# ===========================
# Node Functions (Synchronous)
# NOTE: No @traceable decorators on node functions - they are part of the parent trace
# ===========================

def analyze_payload(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Analyze payload to identify null fields that need enrichment.
    Checks first-level keys in the payload AND nested fields in company_record.
    """
    try:
        logger.info(f"\n🔍 [ANALYZE] Starting payload analysis for {state.company_name}")
        logger.info(f"   Company ID: {state.company_id}")
        logger.info(f"   Payload keys: {list(state.current_payload.keys())}")
        
        null_fields = []
        payload = state.current_payload
        
        # Strategy: Check nested company_record fields first (most enrichable)
        # then check top-level payload fields
        
        if "company_record" in payload and isinstance(payload["company_record"], dict):
            company = payload["company_record"]
            logger.info(f"   📦 Found company_record with {len(company)} fields")
            logger.info(f"   🔎 Checking nested company_record fields for null/empty values...")
            logger.debug(f"      All fields in company_record: {list(company.keys())}")
            
            for field_name, value in company.items():
                # Skip metadata fields
                if field_name in ['schema_version', 'as_of', 'provenance', 'company_id', 'legal_name']:
                    logger.debug(f"   🏷️  {field_name}: [SKIPPED - metadata]")
                    continue
                
                is_null = value is None
                is_empty_str = value == ""
                is_empty_list = isinstance(value, list) and len(value) == 0
                
                logger.info(f"   🏷️  {field_name}: {repr(value) if value is not None else 'None'} (null={is_null}, empty_str={is_empty_str}, empty_list={is_empty_list})")
                
                # Check if value is None, empty string, or empty list
                if is_null or is_empty_str or is_empty_list:
                    null_fields.append({
                        "entity_type": "company_record",
                        "field_name": field_name,
                        "entity_index": 0,
                        "current_value": value,
                        "importance": "high"
                    })
                    logger.info(f"      ✅ NEEDS ENRICHMENT")
                else:
                    logger.info(f"      ⏭️  Has value (skip)")
        else:
            logger.warning(f"   ❌ No company_record found or not a dict")
        
        # Also check top-level payload keys for completeness
        logger.info(f"   📦 Checking {len(payload)} top-level payload keys...")
        for key, value in payload.items():
            # Skip nested structures and special keys
            if isinstance(value, (dict, list)) or key.startswith('_') or key in ['company_record', 'llm_responses', 'enrichment_history', 'metadata']:
                logger.debug(f"   🏷️  {key}: [SKIPPED - special/nested]")
                continue
            
            logger.info(f"   🏷️  {key}: {repr(value)}")
            
            if value is None or value == "":
                null_fields.append({
                    "entity_type": "payload",
                    "field_name": key,
                    "entity_index": 0,
                    "current_value": value,
                    "importance": "medium"
                })
                logger.info(f"      ✅ NEEDS ENRICHMENT")
            else:
                logger.info(f"      ⏭️  Has value (skip)")
        
        state.null_fields = null_fields
        state.status = "analyzed"
        
        logger.info(f"✅ [ANALYZE COMPLETE] Found {len(null_fields)} null fields to enrich")
        for idx, field in enumerate(null_fields, 1):
            logger.info(f"   [{idx}] {field['entity_type']}.{field['field_name']}")
        
        # If no null fields found, mark as complete
        if not null_fields:
            state.status = "completed"
            logger.info(f"   🛑 No null fields found - marking workflow as complete")
        
        return state
    except Exception as e:
        logger.error(f"❌ [ANALYZE] Error in analyze_payload: {type(e).__name__}: {e}", exc_info=True)
        state.errors.append(f"analyze_payload error: {str(e)}")
        state.status = "completed"
        return state


def get_next_null_field(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Select the next null field to work on.
    This node also acts as a checkpoint for workflow decisions.
    """
    logger.info(f"\n🔄 [NEXT FIELD] Selecting next null field")
    logger.info(f"   Iteration: {state.iteration}/{state.max_iterations}")
    logger.info(f"   Remaining fields: {len(state.null_fields)}")
    logger.info(f"   Current status: {state.status}")
    
    # EARLY EXIT 1: Reached max iterations
    if state.iteration >= state.max_iterations:
        state.status = "completed"
        logger.warning(f"⛔ [DECISION] Reached max iterations ({state.max_iterations}) - stopping")
        return state
    
    # EARLY EXIT 2: No more fields to process
    if not state.null_fields or len(state.null_fields) == 0:
        state.status = "completed"
        logger.info(f"✅ [DECISION] No more null fields to process - marking as complete")
        return state
    
    # Get next field
    state.current_null_field = state.null_fields.pop(0)
    state.status = "searching"
    
    field_name = state.current_null_field.get('field_name', 'unknown')
    logger.info(
        f"✅ [NEXT FIELD SELECTED] {field_name} "
        f"(iteration {state.iteration + 1}/{state.max_iterations}, {len(state.null_fields)} remaining)"
    )
    
    return state


def generate_search_queries(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Generate search queries to find information about null field.
    Returns placeholder queries for now.
    """
    print(f"\n>>> GENERATE_QUERIES CALLED")
    print(f">>>   current_null_field: {state.current_null_field}")
    
    if not state.current_null_field:
        logger.warning(f"⚠️  [QUERY GEN] No current_null_field to process!")
        return state
    
    field = state.current_null_field
    company_name = state.company_name
    field_name = field.get("field_name", "unknown")
    
    print(f">>>   Generating queries for field: {field_name}")
    logger.info(f"\n📝 [QUERY GEN] Generating search queries for field: {field_name}")
    logger.debug(f"   Company: {company_name}, Field type: {field.get('entity_type')}")
    
    # Generate basic queries
    queries = [
        f"{company_name} {field_name}",
        f"{company_name} company {field_name}",
        f"{field_name} {company_name}"
    ]
    
    print(f">>>   Generated {len(queries)} queries")
    print(f">>>   📋 QUERIES TO EXECUTE:")
    for idx, q in enumerate(queries, 1):
        print(f">>>      [{idx}] {q}")
    
    logger.info(f"✅ [QUERY GEN] Generated {len(queries)} search queries:")
    for idx, q in enumerate(queries, 1):
        logger.info(f"   [{idx}] {q}")
    
    state.extracted_values["search_queries"] = queries
    
    return state


@traceable(name="tavily_search", tags=["search", "tavily"])
def _execute_tavily_search(tool_manager, query: str, company_name: str) -> Dict[str, Any]:
    """
    Helper function to execute Tavily search synchronously.
    Wraps async call and captures result in LangSmith trace as a named span.
    
    This uses @traceable to make Tavily responses visible as child spans in the parent trace.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're in an event loop, use thread executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            def run_search():
                return asyncio.run(
                    tool_manager.search_tavily(
                        query=query,
                        company_name=company_name,
                        topic="company_enrichment"
                    )
                )
            result = executor.submit(run_search).result(timeout=30)
    except RuntimeError:
        # No event loop, run directly
        result = asyncio.run(
            tool_manager.search_tavily(
                query=query,
                company_name=company_name,
                topic="company_enrichment"
            )
        )
    return result


def execute_searches(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Execute searches using tools and collect results.
    Makes actual Tavily API calls to search for information.
    Stores Tavily responses as JSON files.
    """
    queries = state.extracted_values.get("search_queries", [])
    
    print(f"\n>>> EXECUTE_SEARCHES CALLED: {len(queries)} queries")
    logger.info(f"\n🔎 [EXECUTE SEARCH] Executing {len(queries)} search queries...")
    
    if not queries:
        logger.warning(f"⚠️  [EXECUTE SEARCH] No search queries to execute")
        return state
    
    for idx, q in enumerate(queries, 1):
        print(f">>>   [{idx}] {q}")
        logger.info(f"   [{idx}] {q}")
    
    try:
        # Import necessary modules
        import asyncio
        from pathlib import Path
        from tavily_agent.tools import ToolManager
        from tavily_agent.file_io_manager import FileIOManager
        
        print(f">>> Creating ToolManager...")
        # Get or create the tool manager (synchronously)
        tool_manager = ToolManager()
        
        # Determine output directory for Tavily responses
        test_output_dir = FileIOManager.TEST_OUTPUT_DIR
        if test_output_dir:
            responses_dir = Path(test_output_dir) / "tavily_responses"
            responses_dir.mkdir(parents=True, exist_ok=True)
            print(f">>> Tavily responses will be saved to: {responses_dir}")
            logger.info(f"📁 [TAVILY RESPONSES] Directory: {responses_dir}")
        else:
            responses_dir = None
        
        # Execute all searches synchronously using the blocking call
        all_documents = []
        combined_content = ""
        success_count = 0
        
        for query in queries:
            try:
                print(f">>> Processing query: {query}")
                logger.info(f"🔍 [TAVILY SEARCH] Executing search for query: '{query}'")
                
                # Call Tavily search directly (synchronous wrapper)
                result = _execute_tavily_search(tool_manager, query, state.company_name)
                
                if result.get("success"):
                    success_count += 1
                    count = result.get("count", 0)
                    print(f">>> Query '{query}' returned {count} results")
                    # print(f">>> Tavily Response JSON:\n{json.dumps(result, indent=2, default=str)}")
                    logger.info(f"✅ [TAVILY RESULT] Query '{query}' returned {count} results")
                    # logger.info(f"📄 [TAVILY RESPONSE]\n{json.dumps(result, indent=2, default=str)}")
                    
                    # Save Tavily response to JSON file
                    if responses_dir:
                        try:
                            safe_query = "".join(c if c.isalnum() or c in " _-" else "_" for c in query).replace(" ", "_")
                            response_file = responses_dir / f"tavily_response_{state.company_name}_{safe_query}_{success_count}.json"
                            with open(response_file, "w") as f:
                                json.dump(result, f, indent=2, default=str)
                            print(f">>> ✅ Saved response to: {response_file.name}")
                            logger.info(f"💾 [TAVILY SAVE] Response saved to {response_file.name}")
                        except Exception as save_err:
                            logger.warning(f"⚠️  [TAVILY SAVE] Could not save response: {save_err}")
                    
                    all_documents.extend(result.get("results", []))
                    combined_content += result.get("raw_content", "") + "\n"
                else:
                    error = result.get("error", "unknown")
                    print(f">>> Query '{query}' failed: {error}")
                    print(f">>> Full Error Response:\n{json.dumps(result, indent=2, default=str)}")
                    logger.warning(f"⚠️  [TAVILY ERROR] Query '{query}' failed: {error}")
                    logger.warning(f"❌ [TAVILY ERROR DETAILS]\n{json.dumps(result, indent=2, default=str)}")
                    
                    # Save error response to JSON file
                    if responses_dir:
                        try:
                            safe_query = "".join(c if c.isalnum() or c in " _-" else "_" for c in query).replace(" ", "_")
                            error_file = responses_dir / f"tavily_error_{state.company_name}_{safe_query}_error.json"
                            with open(error_file, "w") as f:
                                json.dump(result, f, indent=2, default=str)
                            print(f">>> 📝 Error response saved to: {error_file.name}")
                            logger.info(f"💾 [TAVILY ERROR SAVE] Error response saved to {error_file.name}")
                        except Exception as save_err:
                            logger.warning(f"⚠️  [TAVILY SAVE] Could not save error response: {save_err}")
            
            except Exception as e:
                print(f">>> ERROR in search: {type(e).__name__}: {e}")
                logger.error(f"❌ [TAVILY EXCEPTION] Error executing query '{query}': {type(e).__name__}: {e}", exc_info=True)
                state.errors.append(f"Tavily search error for '{query}': {str(e)}")
        
        print(f">>> EXECUTE_SEARCHES COMPLETE: {success_count}/{len(queries)} successful, {len(all_documents)} total results")
        logger.info(f"📊 [EXECUTE SEARCH COMPLETE] Successfully executed {success_count}/{len(queries)} queries, found {len(all_documents)} total results")
        
        # Store results in format expected by LLM extraction chain
        # Ensure results contain title, content, url, etc.
        state.search_results = {
            "results": all_documents,  # Key must be "results" for extraction chain
            "combined_content": combined_content,
            "total_results": len(all_documents),
            "queries_executed": len(queries)
        }
        
    except Exception as e:
        print(f">>> ERROR in execute_searches: {type(e).__name__}: {e}")
        logger.error(f"❌ [EXECUTE SEARCH] Error in search execution: {type(e).__name__}: {e}", exc_info=True)
        state.errors.append(f"Search execution error: {str(e)}")
        state.search_results = {
            "documents": [],
            "combined_content": "",
            "total_results": 0,
            "queries_executed": 0
        }
    
    state.status = "updating"
    return state


async def extract_and_update_payload(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Extract relevant values from search results and update payload using LLM chain.
    Uses chained LLM calls: question generation → extraction → validation.
    """
    if not state.current_null_field:
        logger.warning(f"⚠️  [EXTRACT] No current null field to update")
        return state
    
    if not state.search_results:
        logger.warning(f"⚠️  [EXTRACT] No search results to extract from")
        return state
    
    field_name = state.current_null_field.get("field_name", "unknown")
    entity_type = state.current_null_field.get("entity_type", "unknown")
    entity_index = state.current_null_field.get("entity_index", 0)
    importance = state.current_null_field.get("importance", "medium")
    
    logger.info(f"\n💡 [EXTRACT] Extracting value for {entity_type}.{field_name} (index: {entity_index})")
    logger.debug(f"   Search results available: {state.search_results.get('total_results')} documents")
    
    try:
        # Get search results in format expected by extraction chain
        search_results = state.search_results.get("results", [])
        if not search_results:
            logger.warning(f"⚠️  [EXTRACT] No individual search results found")
            extracted_value = None
            confidence = 0.0
            reasoning = "No search results available"
        else:
            # Run the LLM extraction chain
            logger.info(f"🔗 [LLM CHAIN] Starting extraction chain with {len(search_results)} results")
            
            chain = LLMExtractionChain(llm_model=LLM_MODEL, temperature=LLM_TEMPERATURE)
            extraction_result: ChainedExtractionResult = await chain.run_extraction_chain(
                field_name=field_name,
                entity_type=entity_type,
                company_name=state.company_name,
                importance=importance,
                search_results=search_results
            )
            
            extracted_value = extraction_result.final_value
            confidence = extraction_result.confidence
            reasoning = extraction_result.reasoning
            
            logger.info(f"✅ [LLM CHAIN] Extraction complete:")
            logger.info(f"   Final Value: {repr(extracted_value)}")
            logger.info(f"   Confidence: {confidence:.2%}")
            logger.info(f"   Reasoning: {reasoning}")
            for step in extraction_result.chain_steps:
                logger.debug(f"   • {step}")
            
            # Store extraction result in state
            state.extracted_values[f"{field_name}_extraction_result"] = extraction_result.dict()
        
        # Update the payload with extracted value if confidence is sufficient
        if extracted_value is not None and confidence >= 0.5:
            logger.info(f"💾 [UPDATE] Updating payload with extracted value (confidence: {confidence:.2%})")
            
            try:
                if entity_type == "company_record":
                    # Update nested company_record field
                    if "company_record" not in state.current_payload:
                        logger.error(f"❌ [UPDATE] company_record not found in payload!")
                        state.errors.append(f"company_record not found")
                        return state
                    
                    company = state.current_payload["company_record"]
                    old_value = company.get(field_name)
                    company[field_name] = extracted_value
                    logger.info(f"📝 [UPDATE] company_record.{field_name}: {repr(old_value)} → {repr(extracted_value)}")
                    
                    # Add extraction metadata (separate from original provenance list)
                    if "_extraction_metadata" not in company:
                        company["_extraction_metadata"] = {}
                    
                    # Get source URLs from extraction result
                    source_urls = extraction_result.sources if 'extraction_result' in locals() else []
                    
                    company["_extraction_metadata"][field_name] = {
                        "source": "agentic_rag",
                        "tool": "tavily_llm_extraction",
                        "source_urls": source_urls,  # List of URLs that support this value
                        "extracted_at": datetime.now(timezone.utc).isoformat(),
                        "confidence": confidence,
                        "reasoning": reasoning
                    }
                    
                elif entity_type == "payload":
                    # Update top-level payload key
                    old_value = state.current_payload.get(field_name)
                    state.current_payload[field_name] = extracted_value
                    logger.info(f"📝 [UPDATE] {field_name}: {repr(old_value)} → {repr(extracted_value)}")
                else:
                    logger.error(f"❌ [UPDATE] Unknown entity_type: {entity_type}")
                
                # Track this update
                state.extracted_values[field_name] = extracted_value
                state.iteration += 1
                logger.info(f"   ✅ Tracked: extracted_values[{field_name}] = {repr(extracted_value)}")
                
            except Exception as e:
                logger.error(f"❌ [UPDATE] Error updating payload: {type(e).__name__}: {e}", exc_info=True)
                state.errors.append(f"Failed to update {field_name}: {str(e)}")
        else:
            logger.warning(f"⚠️  [UPDATE] Skipping update: value={extracted_value}, confidence={confidence:.2%}")
            state.iteration += 1
        
        # Remove from null_fields since we processed it
        original_count = len(state.null_fields)
        state.null_fields = [
            f for f in state.null_fields 
            if not (f.get("entity_type") == entity_type and 
                   f.get("field_name") == field_name and 
                   f.get("entity_index") == entity_index)
        ]
        removed_count = original_count - len(state.null_fields)
        logger.info(f"✅ [EXTRACT COMPLETE] Removed {removed_count} processed fields. Remaining: {len(state.null_fields)}")
        
    except Exception as e:
        logger.error(f"❌ [EXTRACT] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        state.errors.append(f"Extraction failed for {field_name}: {str(e)}")
        state.iteration += 1
    
    return state


def check_completion(state: PayloadEnrichmentState) -> str:
    """
    Check if we should continue or end the workflow.
    Returns either "continue" or END constant.
    
    STOP CONDITIONS (in order of precedence):
    1. status == "completed" (explicitly marked as done)
    2. No more null_fields to process (empty list)
    3. Reached max_iterations limit
    4. Too many errors (>5)
    """
    logger.info(f"\n🔍 [CHECK COMPLETION] Status check:")
    logger.info(f"   Status: {state.status}")
    logger.info(f"   Iteration: {state.iteration}/{state.max_iterations}")
    logger.info(f"   Remaining fields: {len(state.null_fields)}")
    logger.info(f"   Errors: {len(state.errors)}")
    logger.debug(f"   Current null field: {state.current_null_field}")
    
    # STOP CONDITION 1: Explicitly marked as completed
    if state.status == "completed":
        logger.info(f"🛑 [WORKFLOW END] ✅ Status is 'completed' - workflow finished")
        return END
    
    # STOP CONDITION 2: No more null fields to process
    if not state.null_fields or len(state.null_fields) == 0:
        logger.info(f"🛑 [WORKFLOW END] ✅ No more null fields to enrich")
        state.status = "completed"
        return END
    
    # STOP CONDITION 3: Reached maximum iterations
    if state.iteration >= state.max_iterations:
        logger.warning(f"⚠️  [WORKFLOW END] ⚠️  Reached max iterations limit ({state.iteration}/{state.max_iterations})")
        state.status = "completed"
        return END
    
    # STOP CONDITION 4: Critical errors occurred
    if len(state.errors) > 5:
        logger.error(f"🛑 [WORKFLOW END] ❌ Too many errors ({len(state.errors)}) - aborting")
        state.status = "completed"
        return END
    
    # Continue processing if all stop conditions are false
    logger.info(f"▶️  [WORKFLOW CONTINUE] {len(state.null_fields)} fields remaining - looping back to get_next_field")
    return "continue"


# ===========================
# Graph Construction
# ===========================

def build_enrichment_graph():
    """Build the LangGraph workflow."""
    
    graph = StateGraph(PayloadEnrichmentState)
    
    # Add nodes
    graph.add_node("analyze", analyze_payload)
    graph.add_node("get_next_field", get_next_null_field)
    graph.add_node("generate_queries", generate_search_queries)
    graph.add_node("execute_searches", execute_searches)
    graph.add_node("extract_update", extract_and_update_payload)
    
    # Add edges
    graph.set_entry_point("analyze")
    
    # After analyze, check if we need to continue or stop
    graph.add_conditional_edges(
        "analyze",
        check_completion,
        {
            "continue": "get_next_field",
            END: END
        }
    )
    
    # After get_next_field, check if we still have work
    graph.add_conditional_edges(
        "get_next_field",
        check_completion,
        {
            "continue": "generate_queries",
            END: END
        }
    )
    
    graph.add_edge("generate_queries", "execute_searches")
    graph.add_edge("execute_searches", "extract_update")
    
    # Add conditional edge after extraction
    graph.add_conditional_edges(
        "extract_update",
        check_completion,
        {
            "continue": "get_next_field",
            END: END
        }
    )
    
    return graph.compile()


def save_graph_visualization(graph, output_path: str = "graph_visualization.png"):
    """
    Save LangGraph structure as an image.
    
    Args:
        graph: Compiled LangGraph workflow
        output_path: Path to save the visualization
    """
    try:
        import os
        from pathlib import Path
        
        # Try to use graphviz if available
        try:
            png_data = graph.get_graph().draw_mermaid_png()
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "wb") as f:
                f.write(png_data)
            
            logger.info(f"✓ Graph visualization saved to: {output_file}")
            return str(output_file)
        except Exception as e:
            logger.warning(f"Could not generate PNG visualization: {e}")
            
            # Fallback: save as ASCII diagram
            try:
                ascii_diagram = graph.get_graph().draw_ascii()
                output_file = Path(output_path).with_suffix(".txt")
                
                with open(output_file, "w") as f:
                    f.write(ascii_diagram)
                
                logger.info(f"✓ Graph ASCII diagram saved to: {output_file}")
                return str(output_file)
            except Exception as e2:
                logger.warning(f"Could not save ASCII diagram: {e2}")
                return None
                
    except Exception as e:
        logger.error(f"Error saving graph visualization: {e}")
        return None


# Cross-module imports already done above
