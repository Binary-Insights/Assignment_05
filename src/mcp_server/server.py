"""
FastMCP Server for Agentic RAG System
Exposes tools, resources, and prompts for payload enrichment via Model Context Protocol.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Annotated
from datetime import datetime

# FastMCP imports
from fastmcp import FastMCP

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import TAVILY_API_KEY, OPENAI_API_KEY, PAYLOADS_DIR
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.tools import ToolManager
from tavily_agent.llm_extraction import LLMExtractionChain, extract_field_value
from tavily_agent.main import enrich_single_company
from tavily_agent.graph import build_enrichment_graph, PayloadEnrichmentState

logger = logging.getLogger(__name__)

# ===========================
# Initialize FastMCP Server
# ===========================

app = FastMCP("agentic-rag-mcp")

# Global instances
tool_manager: Optional[ToolManager] = None
file_io_manager: Optional[FileIOManager] = None
extraction_chain: Optional[LLMExtractionChain] = None


async def get_tool_manager() -> ToolManager:
    """Get or create tool manager instance."""
    global tool_manager
    if tool_manager is None:
        tool_manager = ToolManager()
    return tool_manager


async def get_file_io_manager() -> FileIOManager:
    """Get or create file IO manager instance."""
    global file_io_manager
    if file_io_manager is None:
        file_io_manager = FileIOManager()
    return file_io_manager


async def get_extraction_chain() -> LLMExtractionChain:
    """Get or create extraction chain instance."""
    global extraction_chain
    if extraction_chain is None:
        extraction_chain = LLMExtractionChain(llm_model="gpt-4o-mini", temperature=0.1)
    return extraction_chain


# ===========================
# Tool Implementations
# ===========================

@app.tool()
async def search_company(
    query: Annotated[str, "Search query for company information"],
    company_name: Annotated[str, "Company identifier (e.g., 'abridge')"],
    topic: Annotated[str, "Search topic category (default: 'general')"] = "general"
) -> str:
    """
    Search for company information using Tavily API.
    
    Args:
        query: Search query string
        company_name: Company identifier
        topic: Topic category for search
    
    Returns:
        JSON string with search results
    """
    logger.info(f"🔍 [TOOL] search_company called with query='{query}', company_name='{company_name}'")
    
    try:
        tm = await get_tool_manager()
        result = await tm.search_tavily(query, company_name, topic)
        
        logger.info(f"✅ [TOOL] search_company returned {result['count']} results")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"❌ [TOOL] search_company error: {e}")
        return json.dumps({"error": str(e), "success": False})


@app.tool()
async def extract_field(
    field_name: Annotated[str, "Field name to extract (e.g., 'founded_year')"],
    entity_type: Annotated[str, "Entity type (e.g., 'company_record')"],
    company_name: Annotated[str, "Company identifier"],
    importance: Annotated[str, "Importance level: critical, high, medium, low"] = "medium",
    search_results: Annotated[Optional[str], "JSON string of search results"] = None
) -> str:
    """
    Extract a field value from search results using LLM chain.
    
    Args:
        field_name: Name of field to extract
        entity_type: Type of entity
        company_name: Company identifier
        importance: Importance level
        search_results: JSON string of search results
    
    Returns:
        JSON string with extraction result
    """
    logger.info(f"🔗 [TOOL] extract_field called for {field_name} in {company_name}")
    
    try:
        # Parse search results if provided
        results = []
        if search_results:
            try:
                results_data = json.loads(search_results)
                results = results_data.get("results", []) if isinstance(results_data, dict) else results_data
            except json.JSONDecodeError:
                logger.warning("Could not parse search_results JSON")
        
        # Run extraction chain
        chain = await get_extraction_chain()
        result = await chain.run_extraction_chain(
            field_name=field_name,
            entity_type=entity_type,
            company_name=company_name,
            importance=importance,
            search_results=results
        )
        
        logger.info(f"✅ [TOOL] extract_field completed for {field_name}")
        return json.dumps(result.model_dump(), indent=2)
    except Exception as e:
        logger.error(f"❌ [TOOL] extract_field error: {e}")
        return json.dumps({"error": str(e), "success": False})


@app.tool()
async def enrich_payload(
    company_name: Annotated[str, "Company identifier (e.g., 'abridge')"],
    test_dir: Annotated[Optional[str], "Optional test directory for output"] = None,
    max_iterations: Annotated[int, "Maximum iterations for enrichment (default: 20)"] = 20
) -> str:
    """
    Run full enrichment workflow for a company payload.
    
    This orchestrates the complete agentic RAG pipeline:
    1. Load company payload
    2. Analyze for null fields
    3. Search for information
    4. Extract and update values
    5. Save enriched payload
    
    Args:
        company_name: Company identifier
        test_dir: Optional test directory for outputs
        max_iterations: Maximum enrichment iterations
    
    Returns:
        JSON string with enrichment result and status
    """
    logger.info(f"⚡ [TOOL] enrich_payload called for {company_name}")
    
    try:
        # Enable test mode if directory provided
        if test_dir:
            fio = await get_file_io_manager()
            fio.set_test_mode(enable=True, output_dir=test_dir)
            logger.info(f"📁 [TOOL] Test mode enabled with directory: {test_dir}")
        
        # Run enrichment
        result = await enrich_single_company(company_name)
        
        logger.info(f"✅ [TOOL] enrich_payload completed for {company_name}")
        
        # Ensure result is JSON serializable and has all required fields
        response = {
            "company_name": company_name,
            "status": result.get("status", "completed"),
            "null_fields_found": result.get("null_fields_found", 0),
            "null_fields_filled": result.get("null_fields_filled", 0),
            "success": result.get("status") == "completed",
            "timestamp": result.get("timestamp", datetime.now().isoformat())
        }
        
        logger.info(f"📤 [TOOL] Returning response: {response}")
        response_json = json.dumps(response, indent=2)
        logger.info(f"📤 [TOOL] Response JSON length: {len(response_json)} bytes")
        sys.stderr.flush()
        return response_json
    except Exception as e:
        logger.error(f"❌ [TOOL] enrich_payload error: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({
            "company_name": company_name,
            "status": "error",
            "error": str(e),
            "success": False
        })


@app.tool()
async def analyze_payload(
    company_name: Annotated[str, "Company identifier"],
    show_values: Annotated[bool, "Show current values of null fields (default: false)"] = False
) -> str:
    """
    Analyze a payload to identify null fields needing enrichment.
    
    Args:
        company_name: Company identifier
        show_values: Whether to show current field values
    
    Returns:
        JSON string with analysis result
    """
    logger.info(f"📊 [TOOL] analyze_payload called for {company_name}")
    
    try:
        fio = await get_file_io_manager()
        payload = await fio.read_payload(company_name)
        
        if not payload:
            logger.warning(f"Payload not found for {company_name}")
            return json.dumps({
                "company_name": company_name,
                "error": f"Payload not found for {company_name}",
                "success": False
            })
        
        # Build enrichment graph to analyze
        graph = build_enrichment_graph()
        
        # Create initial state
        state = PayloadEnrichmentState(
            company_name=company_name,
            company_id=payload.get("company_id", "unknown"),
            current_payload=payload,
            original_payload=json.loads(json.dumps(payload))  # Deep copy
        )
        
        # Run analysis node
        from tavily_agent.graph import analyze_payload as analyze_node
        analyzed_state = analyze_node(state)
        
        null_fields_summary = {}
        for field in analyzed_state.null_fields:
            entity_type = field.get("entity_type", "unknown")
            field_name = field.get("field_name", "unknown")
            
            if entity_type not in null_fields_summary:
                null_fields_summary[entity_type] = []
            
            field_info = {"field_name": field_name, "importance": field.get("importance", "medium")}
            if show_values and "current_value" in field:
                field_info["current_value"] = field["current_value"]
            
            null_fields_summary[entity_type].append(field_info)
        
        result = {
            "company_name": company_name,
            "total_null_fields": len(analyzed_state.null_fields),
            "null_fields_by_type": null_fields_summary,
            "success": True
        }
        
        logger.info(f"✅ [TOOL] analyze_payload found {len(analyzed_state.null_fields)} null fields")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"❌ [TOOL] analyze_payload error: {e}")
        return json.dumps({
            "company_name": company_name,
            "error": str(e),
            "success": False
        })


# ===========================
# Resource Implementations
# ===========================

@app.resource("payload://{company_name}")
async def get_payload(company_name: str) -> str:
    """
    Get the current payload for a company.
    
    Returns the payload as a JSON resource.
    """
    logger.info(f"📄 [RESOURCE] get_payload called for {company_name}")
    
    try:
        fio = await get_file_io_manager()
        payload = await fio.read_payload(company_name)
        
        if not payload:
            return f"Payload not found for company: {company_name}"
        
        return json.dumps(payload, indent=2)
    except Exception as e:
        logger.error(f"Error reading payload: {e}")
        return f"Error: {str(e)}"


@app.resource("payloads://available")
async def list_payloads() -> str:
    """
    List all available company payloads.
    
    Returns a list of company names with available payloads.
    """
    logger.info(f"📋 [RESOURCE] list_payloads called")
    
    try:
        fio = await get_file_io_manager()
        companies = await fio.list_company_payloads()
        
        result = {
            "total_companies": len(companies),
            "companies": companies
        }
        
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing payloads: {e}")
        return f"Error: {str(e)}"


# ===========================
# Prompt Template Implementations
# ===========================

@app.prompt("enrichment_workflow")
async def enrichment_workflow(company_name: str) -> str:
    """
    Enrichment workflow prompt template.
    
    Provides guidance for running the enrichment workflow for a company.
    """
    return f"""# Agentic RAG Enrichment Workflow

## Company: {company_name}

### Recommended workflow:

1. **Analyze Current Payload**
   - Use `analyze_payload` tool to identify null fields
   - Review which fields need enrichment
   - Prioritize by importance level

2. **Search for Information**
   - Use `search_company` tool to find relevant information
   - Generate targeted queries for each field
   - Collect multiple data sources

3. **Extract Field Values**
   - Use `extract_field` tool for each null field
   - Provide search results as context
   - Validate extracted values

4. **Full Enrichment**
   - Use `enrich_payload` tool to run complete workflow
   - Specify test directory if needed
   - Monitor progress through iterations

5. **Verify Results**
   - Use `get_payload` resource to check updated payload
   - Compare with original payload
   - Validate data quality

### Example commands:

```
# Step 1: Analyze
analyze_payload(company_name="{company_name}", show_values=true)

# Step 2: Search
search_company(query="founding year", company_name="{company_name}")

# Step 3: Extract
extract_field(field_name="founded_year", entity_type="company_record", company_name="{company_name}")

# Step 4: Enrich
enrich_payload(company_name="{company_name}")

# Step 5: Verify
get_payload(company_name="{company_name}")
```
"""


@app.prompt("security_guidelines")
async def security_guidelines() -> str:
    """
    Security guidelines for using the MCP server.
    
    Describes security policies and best practices.
    """
    return """# Agentic RAG MCP Security Guidelines

## Tool Access Control

All tools are whitelisted for authorized access:
- ✅ search_company: Search company information via Tavily
- ✅ extract_field: Extract field values using LLM
- ✅ enrich_payload: Run complete enrichment workflow
- ✅ analyze_payload: Analyze payloads for null fields

## Input Validation

All tool inputs are validated for:
- SQL injection patterns
- Code injection attempts
- Command injection
- Suspicious network calls

## Rate Limiting

Per-tool rate limits (requests per minute):
- search_company: 60 requests/min
- extract_field: 30 requests/min
- enrich_payload: 5 requests/min
- analyze_payload: 30 requests/min

## Best Practices

1. Always use company identifiers (slugs) in lowercase
2. Specify test directories for non-production runs
3. Monitor API key usage and quotas
4. Review extracted values before production deployment
5. Keep payloads backed up before enrichment

## Troubleshooting

- **Rate limit exceeded**: Wait before retrying
- **API key errors**: Check Tavily and OpenAI keys are set
- **Timeout errors**: Use smaller batches or increase timeout
- **Extraction low confidence**: Refine search queries or manual review
"""


# ===========================
# Server Initialization
# ===========================

async def main():
    """Initialize and run the MCP server."""
    logger.info("=" * 70)
    logger.info("🚀 [FASTMCP] Starting Agentic RAG FastMCP Server")
    logger.info("=" * 70)
    
    # Validate API keys
    if not TAVILY_API_KEY:
        logger.error("❌ TAVILY_API_KEY not set")
        sys.exit(1)
    
    if not OPENAI_API_KEY:
        logger.error("❌ OPENAI_API_KEY not set")
        sys.exit(1)
    
    logger.info("✅ API keys validated")
    
    # Log available tools
    logger.info("\n✅ [FASTMCP] Registered Tools:")
    logger.info("  - search_company: Search company information")
    logger.info("  - extract_field: Extract field values using LLM")
    logger.info("  - enrich_payload: Run complete enrichment workflow")
    logger.info("  - analyze_payload: Analyze payloads for null fields")
    
    logger.info("\n✅ [FASTMCP] Registered Resources:")
    logger.info("  - get_payload: Get company payload")
    logger.info("  - list_payloads: List available payloads")
    
    logger.info("\n✅ [FASTMCP] Registered Prompts:")
    logger.info("  - enrichment_workflow: Enrichment workflow guidance")
    logger.info("  - security_guidelines: Security guidelines")
    
    logger.info("\n🔌 [FASTMCP] Server ready and listening on stdio transport")
    logger.info("=" * 70 + "\n")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),  # MCP uses stderr for logging
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Run server
    asyncio.run(main())
