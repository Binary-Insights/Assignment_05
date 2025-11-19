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
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
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

from tavily_agent.config import (
    LLM_MODEL, LLM_TEMPERATURE, MAX_ITERATIONS, OPENAI_API_KEY,
    HITL_ENABLED, HITL_HIGH_RISK_FIELDS, HITL_LOW_CONFIDENCE,
    HITL_CONFIDENCE_THRESHOLD, HIGH_RISK_FIELDS
)
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.vector_db_manager import VectorDBManager, get_vector_db_manager
from tavily_agent.tools import get_tool_manager
from tavily_agent.llm_extraction import LLMExtractionChain, ChainedExtractionResult
from tavily_agent.approval_queue import (
    get_approval_queue, ApprovalType, ApprovalStatus
)

# Import Pydantic models for structured entity extraction
from rag.rag_models import Event, Leadership, Visibility, Product, Snapshot, Provenance

logger = logging.getLogger(__name__)

# ===========================
# Global Checkpointer for HITL
# ===========================
# Use a single MemorySaver instance across all workflow runs
# This ensures checkpoints persist when resuming after approval
_global_checkpointer = MemorySaver()


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
    extraction_result: Optional[Dict[str, Any]] = None  # Current field's extraction result for HITL
    
    # Vector DB context
    vector_context: str = ""
    
    # Processing state
    status: str = "initialized"  # initialized, analyzing, searching, updating, completed
    errors: List[str] = Field(default_factory=list)
    
    # Human-in-the-Loop state
    pending_approval_id: Optional[str] = None
    hitl_enabled: bool = False
    hitl_settings: Dict[str, Any] = Field(default_factory=dict)  # Mixed types: bool + float for confidence_threshold


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
        # Load HITL settings from persistent file
        from tavily_agent.config import load_hitl_settings
        hitl_config = load_hitl_settings()
        state.hitl_enabled = hitl_config["enabled"]
        state.hitl_settings = hitl_config
        
        logger.info(f"\n🔧 [HITL CONFIG] Loaded settings: enabled={state.hitl_enabled}")
        logger.info(f"   High-risk fields: {hitl_config['high_risk_fields']}")
        logger.info(f"   Low confidence: {hitl_config['low_confidence']}")
        logger.info(f"   Threshold: {hitl_config['confidence_threshold']}")
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
        
        # Also check top-level payload keys for list-based entities
        # These are special: events, leadership, products, snapshots, visibility
        # We want to ALWAYS extract these from Tavily to enrich existing entities
        entity_lists = ['events', 'leadership', 'products', 'snapshots', 'visibility']
        logger.info(f"   📦 Checking entity lists for Tavily extraction...")
        
        for entity_type in entity_lists:
            if entity_type in payload:
                current_count = len(payload[entity_type]) if isinstance(payload[entity_type], list) else 0
                logger.info(f"   📋 {entity_type}: currently has {current_count} items")
                
                # ALWAYS add these for Tavily extraction to supplement existing entities
                # entity_index == -1 triggers entity extraction via instructor+GPT-4o
                null_fields.append({
                    "entity_type": entity_type,
                    "field_name": entity_type,  # The list itself
                    "entity_index": -1,  # -1 triggers extract_and_insert_entities()
                    "current_value": current_count,
                    "importance": "high"
                })
                logger.info(f"      ✅ QUEUED for Tavily entity extraction (will supplement existing {current_count} items)")
            else:
                # Entity list doesn't exist yet - create it
                logger.info(f"   📋 {entity_type}: not found - will create new list")
                payload[entity_type] = []
                null_fields.append({
                    "entity_type": entity_type,
                    "field_name": entity_type,
                    "entity_index": -1,
                    "current_value": 0,
                    "importance": "high"
                })
                logger.info(f"      ✅ QUEUED for Tavily entity extraction (new list)")

        
        # Also check other top-level scalar keys for completeness
        logger.info(f"   📦 Checking {len(payload)} top-level payload keys...")
        for key, value in payload.items():
            # Skip nested structures, entity lists (handled above), and special keys
            if isinstance(value, (dict, list)) or key.startswith('_') or key in ['company_record', 'llm_responses', 'enrichment_history', 'metadata', 'events', 'leadership', 'products', 'snapshots', 'visibility']:
                logger.debug(f"   🏷️  {key}: [SKIPPED - special/nested/entity-list]")
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
            logger.info(f"   🛑 No null or entity fields found - marking workflow as complete")
        
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
        # Always save to data/raw/{company}/tavily/ for proper pipeline integration
        project_root = Path(__file__).parent.parent.parent
        responses_dir = project_root / "data" / "raw" / state.company_name / "tavily"
        responses_dir.mkdir(parents=True, exist_ok=True)
        print(f">>> Tavily responses will be saved to: {responses_dir}")
        logger.info(f"📁 [TAVILY RESPONSES] Directory: {responses_dir}")
        
        # Execute all searches synchronously using the blocking call
        all_documents = []
        combined_content = ""
        success_count = 0
        all_search_responses = []  # Collect all responses to save in single JSON
        
        for query in queries:
            try:
                print(f">>> Processing query: {query}")
                logger.info(f"🔍 [TAVILY SEARCH] Executing search for query: '{query}'")
                
                # Call Tavily search directly (synchronous wrapper)
                result = _execute_tavily_search(tool_manager, query, state.company_name)
                
                # Add query metadata to result for consolidated JSON
                result['query'] = query
                result['query_index'] = len(all_search_responses) + 1
                all_search_responses.append(result)
                
                if result.get("success"):
                    success_count += 1
                    count = result.get("count", 0)
                    print(f">>> Query '{query}' returned {count} results")
                    logger.info(f"✅ [TAVILY RESULT] Query '{query}' returned {count} results")
                    
                    all_documents.extend(result.get("results", []))
                    combined_content += result.get("raw_content", "") + "\n"
                else:
                    error = result.get("error", "unknown")
                    print(f">>> Query '{query}' failed: {error}")
                    logger.warning(f"⚠️  [TAVILY ERROR] Query '{query}' failed: {error}")
            
            except Exception as e:
                print(f">>> ERROR in search: {type(e).__name__}: {e}")
                logger.error(f"❌ [TAVILY EXCEPTION] Error executing query '{query}': {type(e).__name__}: {e}", exc_info=True)
                state.errors.append(f"Tavily search error for '{query}': {str(e)}")
                
                # Add error to responses collection
                all_search_responses.append({
                    'query': query,
                    'query_index': len(all_search_responses) + 1,
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
        
        # Save all search responses to a SINGLE consolidated JSON file (append mode)
        if all_search_responses and responses_dir:
            try:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                consolidated_file = responses_dir / "tavily_all_sessions.json"
                
                # Create new session entry
                session_data = {
                    'session_id': timestamp,
                    'timestamp': timestamp,
                    'company': state.company_name,
                    'total_queries': len(queries),
                    'successful_queries': success_count,
                    'failed_queries': len(queries) - success_count,
                    'total_results': len(all_documents),
                    'search_responses': all_search_responses
                }
                
                # Load existing sessions or create new structure
                if consolidated_file.exists():
                    try:
                        with open(consolidated_file, 'r', encoding='utf-8') as f:
                            all_sessions = json.load(f)
                        
                        # Ensure it's a dict with sessions array
                        if not isinstance(all_sessions, dict) or 'sessions' not in all_sessions:
                            logger.warning(f"⚠️  Existing file has unexpected format, creating new structure")
                            all_sessions = {
                                'company': state.company_name,
                                'sessions': []
                            }
                    except Exception as read_err:
                        logger.warning(f"⚠️  Error reading existing file: {read_err}, creating new structure")
                        all_sessions = {
                            'company': state.company_name,
                            'sessions': []
                        }
                else:
                    # New file
                    all_sessions = {
                        'company': state.company_name,
                        'sessions': []
                    }
                
                # Append new session
                all_sessions['sessions'].append(session_data)
                all_sessions['last_updated'] = timestamp
                all_sessions['total_sessions'] = len(all_sessions['sessions'])
                
                # Save updated file
                with open(consolidated_file, 'w', encoding='utf-8') as f:
                    json.dump(all_sessions, f, indent=2, ensure_ascii=False, default=str)
                
                print(f">>> ✅ Appended session {timestamp} to: {consolidated_file.name} (total sessions: {all_sessions['total_sessions']})")
                logger.info(f"💾 [TAVILY SAVE] Appended session to {consolidated_file.name}")
                logger.info(f"   Session ID: {timestamp}, Queries: {len(queries)}, Results: {len(all_documents)}")
                logger.info(f"   Total sessions in file: {all_sessions['total_sessions']}")
            except Exception as save_err:
                logger.warning(f"⚠️  [TAVILY SAVE] Could not save consolidated responses: {save_err}")
        
        print(f">>> EXECUTE_SEARCHES COMPLETE: {success_count}/{len(queries)} successful, {len(all_documents)} total results")
        logger.info(f"📊 [EXECUTE SEARCH COMPLETE] Successfully executed {success_count}/{len(queries)} queries, found {len(all_documents)} total results")
        
        # Ingest Tavily results to Pinecone (if any results were saved)
        if success_count > 0 and responses_dir:
            try:
                logger.info(f"🔄 [PINECONE INGEST] Ingesting Tavily results to Pinecone...")
                
                # Import the ingestion function
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from rag.ingest_to_pinecone import ingest_all_tavily_json_for_company
                
                # Ingest all Tavily JSONs for this company
                ingest_summary = ingest_all_tavily_json_for_company(state.company_name)
                
                if ingest_summary.get('success'):
                    logger.info(
                        f"✅ [PINECONE INGEST] Successfully ingested Tavily data: "
                        f"{ingest_summary.get('total_added', 0)} vectors added, "
                        f"{ingest_summary.get('total_skipped', 0)} duplicates skipped"
                    )
                else:
                    logger.warning(
                        f"⚠️  [PINECONE INGEST] Ingestion completed with issues: "
                        f"{ingest_summary.get('error', 'unknown error')}"
                    )
            except Exception as ingest_err:
                logger.error(f"❌ [PINECONE INGEST] Error ingesting to Pinecone: {ingest_err}", exc_info=True)
                # Don't fail the whole workflow if ingestion fails
                state.errors.append(f"Pinecone ingestion error: {str(ingest_err)}")
        
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


async def extract_and_insert_entities(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Extract structured entities from Tavily search results and insert into payload lists.
    
    Uses instructor library + Pydantic models to structure Tavily data into:
    - events: Event objects (funding, acquisitions, partnerships, etc.)
    - leadership: Leadership objects (executives, founders, board members)
    - products: Product objects (software, services, APIs)
    - snapshots: Snapshot objects (headcount, hiring, growth metrics)
    - visibility: Visibility objects (news mentions, sentiment, github stars)
    
    Args:
        state: PayloadEnrichmentState with current_null_field containing:
            - field_name: The entity type to extract (e.g., "events", "leadership")
            - entity_index: -1 (indicates list extraction mode)
    
    Returns:
        Updated state with extracted entities inserted into appropriate payload list
    """
    field_name = state.current_null_field.get("field_name", "unknown")
    company_name = state.company_name
    company_id = state.current_payload.get("company_record", {}).get("company_id", "unknown")
    
    logger.info(f"\n🔍 [ENTITY EXTRACTION] Starting entity extraction for '{field_name}'")
    logger.info(f"   Company: {company_name} (ID: {company_id})")
    logger.info(f"   Tavily search results available: {state.search_results.get('total_results', 0)}")
    
    # Map entity type to Pydantic model
    entity_model_map = {
        "events": Event,
        "leadership": Leadership,
        "products": Product,
        "snapshots": Snapshot,
        "visibility": Visibility
    }
    
    if field_name not in entity_model_map:
        logger.error(f"❌ [ENTITY EXTRACTION] Unknown entity type: {field_name}")
        state.errors.append(f"Unknown entity type for extraction: {field_name}")
        return state
    
    entity_model = entity_model_map[field_name]
    logger.info(f"   Using Pydantic model: {entity_model.__name__}")
    
    try:
        # Get Tavily search results
        search_results = state.search_results.get("results", [])
        if not search_results:
            logger.warning(f"⚠️  [ENTITY EXTRACTION] No search results to extract from")
            return state
        
        # Combine search results into context for LLM
        combined_context = "\n\n".join([
            f"Source: {doc.get('url', 'unknown')}\n"
            f"Title: {doc.get('title', 'N/A')}\n"
            f"Content: {doc.get('content', 'N/A')}"
            for doc in search_results[:10]  # Limit to top 10 to avoid token overflow
        ])
        
        logger.info(f"   Combined context length: {len(combined_context)} characters")
        logger.info(f"🤖 [LLM] Calling GPT-4o with instructor for structured extraction...")
        
        # Initialize instructor-patched OpenAI client
        import instructor
        from openai import OpenAI
        from pydantic import BaseModel, Field
        from typing import List
        
        client = instructor.from_openai(OpenAI(api_key=OPENAI_API_KEY))
        
        # Create a wrapper model for multiple entities
        class EntityExtractionResult(BaseModel):
            """Container for extracted entities from Tavily search results."""
            entities: List[entity_model] = Field(
                default_factory=list,
                description=f"List of {field_name} extracted from search results"
            )
            extraction_reasoning: str = Field(
                description="Brief explanation of extraction logic and entity count"
            )
        
        # Build extraction prompt
        extraction_prompt = f"""You are analyzing Tavily search results for **{company_name}** (Company ID: {company_id}).

Your task: Extract structured **{field_name}** entities from the search results below.

**Entity Type**: {entity_model.__name__}
**Expected Fields**: Review the Pydantic model schema carefully and extract all available information.

**Instructions**:
1. Read through all search results carefully
2. Identify information related to {field_name} for {company_name}
3. Structure each relevant piece of information according to the {entity_model.__name__} schema
4. Include provenance (source_url, snippet) for each extracted entity
5. If multiple {field_name} are found, extract all of them
6. If no relevant {field_name} found, return an empty list

**Search Results**:

{combined_context}

**Important Notes**:
- Only extract {field_name} specifically for {company_name}, not competitors or unrelated companies
- Ensure all required fields in the Pydantic model are populated (use None/"" if unavailable)
- Include source URLs in the provenance field
- Be precise: extract factual information, don't infer or speculate
- For dates: use ISO format (YYYY-MM-DD) when possible

Extract the {field_name} entities now.
"""
        
        # Call LLM with instructor for structured extraction
        extraction_result: EntityExtractionResult = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.2,  # Low temperature for factual extraction
            response_model=EntityExtractionResult,
            messages=[
                {"role": "system", "content": "You are a precise data extraction assistant. Extract structured entities from search results according to the Pydantic schema provided."},
                {"role": "user", "content": extraction_prompt}
            ]
        )
        
        extracted_entities = extraction_result.entities
        reasoning = extraction_result.extraction_reasoning
        
        logger.info(f"✅ [LLM] Extraction complete!")
        logger.info(f"   Entities extracted: {len(extracted_entities)}")
        logger.info(f"   Reasoning: {reasoning}")
        
        # Insert extracted entities into payload
        if not extracted_entities:
            logger.info(f"   ℹ️  No {field_name} found in search results")
        else:
            # Ensure the list exists in payload
            if field_name not in state.current_payload:
                state.current_payload[field_name] = []
            
            # Convert Pydantic objects to dicts and append
            current_count = len(state.current_payload[field_name])
            for entity in extracted_entities:
                state.current_payload[field_name].append(entity.model_dump())
            
            new_count = len(state.current_payload[field_name])
            logger.info(f"   📝 Inserted {new_count - current_count} new {field_name} into payload")
            logger.info(f"   📊 Total {field_name} in payload: {new_count}")
            
            # Track extraction in state
            state.extracted_values[field_name] = {
                "entity_count": len(extracted_entities),
                "reasoning": reasoning,
                "extraction_timestamp": str(datetime.now())
            }
        
        logger.info(f"✅ [ENTITY EXTRACTION] Completed for '{field_name}'")
        
    except Exception as e:
        logger.error(f"❌ [ENTITY EXTRACTION] Error extracting {field_name}: {type(e).__name__}: {e}", exc_info=True)
        state.errors.append(f"Entity extraction error for {field_name}: {str(e)}")
    
    return state


async def extract_and_update_payload(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Extract relevant values from search results and update payload using LLM chain.
    Uses chained LLM calls: question generation → extraction → validation.
    
    Special handling for entity_index == -1: triggers entity list extraction from Tavily responses.
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
    
    # SPECIAL CASE: entity_index == -1 means this is a request to extract entities from Tavily
    if entity_index == -1:
        logger.info(f"\n🔍 [ENTITY EXTRACTION] Detected entity list extraction request for '{field_name}'")
        return await extract_and_insert_entities(state)
    
    # NORMAL CASE: scalar field extraction
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
            
            # Store extraction result in state for HITL assessment
            state.extraction_result = extraction_result.dict()
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
        
        # Note: extraction_result will be cleared in assess_risk_and_route after HITL check
        
    except Exception as e:
        logger.error(f"❌ [EXTRACT] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        state.errors.append(f"Extraction failed for {field_name}: {str(e)}")
        state.iteration += 1
    
    return state


# ===========================
# Human-in-the-Loop Nodes
# ===========================

def assess_risk_and_route(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Assess if current extraction requires human approval based on HITL settings.
    Creates approval request if needed.
    """
    if not state.hitl_enabled:
        logger.info(f"ℹ️  [HITL] HITL disabled - auto-approving all updates")
        return state
    
    field_name = state.current_null_field.get("field_name", "unknown")
    extracted_result = state.extraction_result
    
    if not extracted_result:
        logger.info(f"ℹ️  [HITL] No extraction result for {field_name} - skipping risk assessment")
        return state
    
    confidence = extracted_result.get("confidence", 1.0)
    final_value = extracted_result.get("final_value")
    sources = extracted_result.get("sources", [])
    reasoning = extracted_result.get("reasoning", "")
    
    requires_approval = False
    approval_type = None
    
    # Check 1: High-risk field
    if state.hitl_settings.get("high_risk_fields", False) and field_name in HIGH_RISK_FIELDS:
        requires_approval = True
        approval_type = ApprovalType.HIGH_RISK_FIELD
        logger.info(f"⚠️  [HITL RISK] High-risk field detected: {field_name}")
    
    # Check 2: Low confidence
    elif state.hitl_settings.get("low_confidence", False) and confidence < HITL_CONFIDENCE_THRESHOLD:
        requires_approval = True
        approval_type = ApprovalType.LOW_CONFIDENCE
        logger.info(f"⚠️  [HITL RISK] Low confidence detected: {confidence:.2%} < {HITL_CONFIDENCE_THRESHOLD:.2%}")
    
    if requires_approval:
        # Create approval request
        approval_queue = get_approval_queue()
        approval_id = approval_queue.create_approval(
            company_name=state.company_name,
            approval_type=approval_type,
            field_name=field_name,
            extracted_value=final_value,
            confidence=confidence,
            sources=sources,
            reasoning=reasoning,
            metadata={
                "entity_type": state.current_null_field.get("entity_type"),
                "importance": state.current_null_field.get("importance")
            }
        )
        
        state.pending_approval_id = approval_id
        state.status = "waiting_approval"
        
        logger.info(f"⏸️  [HITL] Created approval request: {approval_id}")
        logger.info(f"   Field: {field_name}, Type: {approval_type.value}")
        logger.info(f"   Value: {final_value}, Confidence: {confidence:.2%}")
    else:
        logger.info(f"✅ [HITL] No approval required for {field_name}")
        state.pending_approval_id = None
    
    # Clear extraction_result after assessment to avoid reuse for next field
    state.extraction_result = None
    
    return state


async def wait_for_approval(state: PayloadEnrichmentState) -> PayloadEnrichmentState:
    """
    Check if approval has been granted.
    If still pending, interrupt the workflow to pause execution.
    Workflow will resume when approval is processed.
    
    Args:
        state: Current enrichment state
    
    Returns:
        Updated state with approval status, or interrupt signal
    """
    if not state.pending_approval_id:
        logger.info("   ⏭️  No pending approval")
        return state
    
    approval_queue = get_approval_queue()
    approval = approval_queue.get_approval(state.pending_approval_id)
    
    if not approval:
        logger.warning(f"   ⚠️  Approval {state.pending_approval_id} not found")
        state.pending_approval_id = None
        return state
    
    logger.info(f"   📋 [HITL] Checking approval status: {approval.status.value}")
    
    if approval.status == ApprovalStatus.PENDING:
        logger.info(f"   ⏸️  [HITL] Waiting for approval - INTERRUPTING WORKFLOW")
        logger.info(f"   💾 [HITL] State saved to checkpoint - workflow can be resumed")
        # Interrupt the workflow - this pauses execution
        # When approval is processed, workflow can be resumed from this point
        interrupt(
            {
                "type": "approval_required",
                "approval_id": state.pending_approval_id,
                "field_name": approval.field_name,
                "company_name": state.company_name,
                "message": f"Waiting for approval of {approval.field_name}"
            }
        )
    
    elif approval.status == ApprovalStatus.APPROVED:
        logger.info(f"   ✅ [HITL] Approval granted: {state.pending_approval_id}")
        # Use approved value if modified, otherwise original
        final_value = approval.approved_value or approval.extracted_value
        
        # Update payload with approved value
        field_name = approval.field_name
        state.current_payload["company_record"][field_name] = final_value
        state.extracted_values[field_name] = final_value
        
        logger.info(f"   📝 [HITL] Updated {field_name} with approved value: {final_value}")
        
        # Save updated payload to disk to prevent re-processing on workflow resume
        try:
            file_io = FileIOManager()
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, create a task
                asyncio.create_task(file_io.save_payload(state.company_name, state.current_payload))
            else:
                # Otherwise run synchronously
                asyncio.run(file_io.save_payload(state.company_name, state.current_payload))
            logger.info(f"   💾 [HITL] Saved approved value to payload file: {field_name}")
        except Exception as save_err:
            logger.error(f"   ❌ [HITL] Failed to save payload to disk: {save_err}")
            # Don't fail the workflow, but log the error
        
        # Remove field from null_fields to prevent re-processing
        original_count = len(state.null_fields)
        state.null_fields = [
            f for f in state.null_fields 
            if f.get("field_name") != field_name
        ]
        removed_count = original_count - len(state.null_fields)
        logger.info(f"   🗑️  [HITL] Removed {removed_count} field(s) from queue. Remaining: {len(state.null_fields)}")
        
        state.pending_approval_id = None
        
    elif approval.status == ApprovalStatus.REJECTED:
        logger.info(f"   ❌ [HITL] Approval rejected: {state.pending_approval_id}")
        
        # Mark field as explicitly rejected in payload (keep as null)
        field_name = approval.field_name
        # Keep the field as null in the payload (user chose to reject)
        state.current_payload["company_record"][field_name] = None
        
        # Save updated payload to disk to prevent re-processing on workflow resume
        try:
            file_io = FileIOManager()
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(file_io.save_payload(state.company_name, state.current_payload))
            else:
                asyncio.run(file_io.save_payload(state.company_name, state.current_payload))
            logger.info(f"   💾 [HITL] Saved rejection (null) to payload file: {field_name}")
        except Exception as save_err:
            logger.error(f"   ❌ [HITL] Failed to save payload to disk: {save_err}")
        
        # Remove field from null_fields even if rejected (skip this field)
        original_count = len(state.null_fields)
        state.null_fields = [
            f for f in state.null_fields 
            if f.get("field_name") != field_name
        ]
        removed_count = original_count - len(state.null_fields)
        logger.info(f"   🗑️  [HITL] Removed {removed_count} rejected field(s). Remaining: {len(state.null_fields)}")
        
        state.pending_approval_id = None
    
    return state


def route_after_extraction(state: PayloadEnrichmentState) -> str:
    """
    Route after extraction based on HITL status.
    Returns: "check_approval" if approval needed, "continue" otherwise
    """
    if state.pending_approval_id:
        logger.info(f"🔀 [ROUTE] Approval required - routing to wait_for_approval")
        return "wait_approval"
    else:
        logger.info(f"🔀 [ROUTE] No approval needed - continuing to check_completion")
        return "continue"


def route_after_approval(state: PayloadEnrichmentState) -> str:
    """
    Route after approval check.
    Returns: "wait" if still pending, "continue" if approved/rejected
    """
    if state.pending_approval_id:
        # Still waiting
        logger.info(f"🔀 [ROUTE] Still waiting for approval - pausing workflow")
        return END  # Pause workflow - will resume via API
    else:
        logger.info(f"🔀 [ROUTE] Approval complete - continuing")
        return "continue"


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
    logger.info(f"   Pending approval: {state.pending_approval_id}")
    logger.debug(f"   Current null field: {state.current_null_field}")
    
    # STOP CONDITION 0: Waiting for approval (workflow paused)
    if state.status == "waiting_approval" and state.pending_approval_id:
        logger.info(f"⏸️  [WORKFLOW PAUSED] Waiting for approval: {state.pending_approval_id}")
        return END  # Pause - will resume via API
    
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

def build_enrichment_graph(with_checkpointing: bool = False):
    """Build the LangGraph workflow.
    
    Args:
        with_checkpointing: Enable checkpointing for HITL pause/resume support
    
    Returns:
        Compiled graph with optional checkpointing
    """
    
    graph = StateGraph(PayloadEnrichmentState)
    
    # Add nodes
    graph.add_node("analyze", analyze_payload)
    graph.add_node("get_next_field", get_next_null_field)
    graph.add_node("generate_queries", generate_search_queries)
    graph.add_node("execute_searches", execute_searches)
    graph.add_node("extract_update", extract_and_update_payload)
    
    # HITL nodes
    graph.add_node("assess_risk", assess_risk_and_route)
    graph.add_node("wait_approval", wait_for_approval)
    
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
    
    # After extraction, assess risk for HITL
    graph.add_edge("extract_update", "assess_risk")
    
    # After risk assessment, route to approval or continue
    graph.add_conditional_edges(
        "assess_risk",
        route_after_extraction,
        {
            "wait_approval": "wait_approval",
            "continue": "get_next_field"
        }
    )
    
    # After approval check, either wait (pause) or continue
    graph.add_conditional_edges(
        "wait_approval",
        route_after_approval,
        {
            "continue": "get_next_field",
            END: END  # Pause workflow if still pending
        }
    )
    
    # Compile with optional checkpointing
    if with_checkpointing:
        logger.info("✅ [GRAPH] Checkpointing enabled for HITL pause/resume (using global checkpointer)")
        return graph.compile(checkpointer=_global_checkpointer)
    else:
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
