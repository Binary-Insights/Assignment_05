"""
MCP Server for Agentic RAG System
Exposes tools, resources, and prompts for payload enrichment
"""

import json
import logging
import sys
from typing import Any
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import existing agent code
from tavily_agent.tools import ToolManager, get_tool_manager
from tavily_agent.llm_extraction import LLMExtractionChain
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.main import enrich_single_company
from tavily_agent.config import LLM_MODEL, LLM_TEMPERATURE
from tavily_agent.graph import PayloadEnrichmentState, analyze_payload

from mcp_server.security import security_middleware

logger = logging.getLogger(__name__)

# ===========================
# Server Entry Point
# ===========================

async def main():
    """Run the MCP server using stdio transport."""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent
    
    logger.info("=" * 70)
    logger.info("🚀 [MCP] Starting Agentic RAG MCP Server")
    logger.info("=" * 70)
    
    # Create server instance
    server = Server("agentic-rag-mcp")
    
    # ===========================
    # Tool Handlers
    # ===========================
    
    @server.call_tool()
    async def search_company(arguments: dict) -> list:
        """
        Search for company information via Tavily.
        Reuses: tavily_agent.tools.ToolManager.search_tavily()
        """
        try:
            company_name = arguments.get("company_name", "")
            query = arguments.get("query", "")
            topic = arguments.get("topic", "general")
            
            logger.info(f"🔍 [MCP] search_company called: {company_name}, {query}")
            
            # Security check
            can_execute, reason = security_middleware.can_execute_tool(
                "search_company",
                arguments,
                requester_role="user"
            )
            if not can_execute:
                return [TextContent(type="text", text=json.dumps({"error": f"Security check failed: {reason}"}))]
            
            # Call existing Tavily search
            logger.info(f"📡 [MCP] Calling Tavily for query: {query}")
            tool_manager = await get_tool_manager()
            result = await tool_manager.search_tavily(
                query=query,
                company_name=company_name,
                topic=topic
            )
            
            logger.info(f"✅ [MCP] Tavily search returned {result.get('count', 0)} results")
            return [TextContent(type="text", text=json.dumps(result, default=str))]
            
        except Exception as e:
            logger.error(f"❌ [MCP] search_company failed: {e}", exc_info=True)
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    
    @server.call_tool()
    async def extract_field(arguments: dict) -> list:
        """
        Extract value for a field using LLM chain.
        Reuses: tavily_agent.llm_extraction.LLMExtractionChain
        """
        try:
            field_name = arguments.get("field_name", "")
            company_name = arguments.get("company_name", "")
            search_results = arguments.get("search_results", [])
            importance = arguments.get("importance", "high")
            
            logger.info(f"🔗 [MCP] extract_field called with field: {field_name}")
            
            # Security check
            can_execute, reason = security_middleware.can_execute_tool(
                "extract_field",
                arguments,
                requester_role="user"
            )
            if not can_execute:
                return [TextContent(type="text", text=json.dumps({"error": f"Security check failed: {reason}"}))]
            
            # Run extraction chain
            logger.info(f"⚙️  [MCP] Running LLM extraction chain")
            chain = LLMExtractionChain(
                llm_model=LLM_MODEL,
                temperature=LLM_TEMPERATURE
            )
            extraction_result = await chain.run_extraction_chain(
                field_name=field_name,
                entity_type="company_record",
                company_name=company_name,
                importance=importance,
                search_results=search_results
            )
            
            logger.info(f"✅ [MCP] Extraction complete: confidence={extraction_result.confidence}")
            
            return [TextContent(type="text", text=json.dumps({
                "field_name": extraction_result.field_name,
                "value": extraction_result.final_value,
                "confidence": extraction_result.confidence,
                "reasoning": extraction_result.reasoning,
                "sources": extraction_result.sources,
                "steps": extraction_result.chain_steps,
                "status": "success"
            }, default=str))]
            
        except Exception as e:
            logger.error(f"❌ [MCP] extract_field failed: {e}", exc_info=True)
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    
    @server.call_tool()
    async def enrich_payload(arguments: dict) -> list:
        """
        Run full enrichment workflow for a company.
        Reuses: tavily_agent.main.enrich_single_company()
        """
        try:
            company_name = arguments.get("company_name", "")
            max_iterations = arguments.get("max_iterations", 20)
            
            logger.info(f"🚀 [MCP] enrich_payload called for: {company_name}")
            
            # Security check (sensitive tool - requires admin/system role)
            can_execute, reason = security_middleware.can_execute_tool(
                "enrich_payload",
                arguments,
                requester_role="system"  # MCP calls are system-level
            )
            if not can_execute:
                return [TextContent(type="text", text=json.dumps({"error": f"Security check failed: {reason}"}))]
            
            # Run enrichment
            logger.info(f"⚙️  [MCP] Starting enrichment workflow")
            result = await enrich_single_company(company_name)
            
            logger.info(f"✅ [MCP] Enrichment complete: status={result.get('status')}")
            
            return [TextContent(type="text", text=json.dumps(result, default=str))]
            
        except Exception as e:
            logger.error(f"❌ [MCP] enrich_payload failed: {e}", exc_info=True)
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    
    @server.call_tool()
    async def analyze_null_fields(arguments: dict) -> list:
        """
        Analyze payload to find null fields.
        Reuses: tavily_agent.graph.analyze_payload()
        """
        try:
            company_name = arguments.get("company_name", "")
            
            logger.info(f"📊 [MCP] analyze_null_fields called for: {company_name}")
            
            # Security check
            can_execute, reason = security_middleware.can_execute_tool(
                "analyze_null_fields",
                arguments,
                requester_role="user"
            )
            if not can_execute:
                return [TextContent(type="text", text=json.dumps({"error": f"Security check failed: {reason}"}))]
            
            # Read payload
            logger.info(f"📂 [MCP] Reading payload for {company_name}")
            payload = await FileIOManager.read_payload(company_name)
            if not payload:
                return [TextContent(type="text", text=json.dumps({"error": f"Payload not found for {company_name}"}))]
            
            # Analyze using existing logic
            state = PayloadEnrichmentState(
                company_name=company_name,
                company_id=payload.get("company_record", {}).get("company_id", "unknown"),
                current_payload=payload,
                original_payload=json.loads(json.dumps(payload))  # Deep copy
            )
            
            # Run analysis
            logger.info(f"🔍 [MCP] Analyzing null fields")
            analyzed_state = analyze_payload(state)
            
            logger.info(f"✅ [MCP] Analysis complete: {len(analyzed_state.null_fields)} null fields found")
            
            return [TextContent(type="text", text=json.dumps({
                "company_name": company_name,
                "null_fields_count": len(analyzed_state.null_fields),
                "null_fields": analyzed_state.null_fields,
                "status": "success"
            }, default=str))]
            
        except Exception as e:
            logger.error(f"❌ [MCP] analyze_null_fields failed: {e}", exc_info=True)
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    
    logger.info("✅ [MCP] Tools registered:")
    logger.info("  - search_company")
    logger.info("  - extract_field")
    logger.info("  - enrich_payload")
    logger.info("  - analyze_null_fields")
    
    logger.info("🔌 [MCP] Starting stdio transport...")
    
    # Run the server with stdio transport
    logger.info("✅ [MCP] Server running and ready for requests")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
