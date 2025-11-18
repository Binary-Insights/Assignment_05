#!/usr/bin/env python
"""
FastMCP Client for Agentic RAG Enrichment
Demonstrates how to use the MCP server to enrich company payloads via the tavily agent.

Usage:
    python mcp_enrichment_client.py abridge                                    # Analyze only
    python mcp_enrichment_client.py abridge --enrich                          # Full enrichment
    python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/test     # Enrichment with test directory
    python mcp_enrichment_client.py abridge --search "founding year"          # Search only
    python mcp_enrichment_client.py abridge --extract founded_year company_record --search-results '{"results": [...]}'

Examples:
    # 1. Analyze abridge payload
    python mcp_enrichment_client.py abridge

    # 2. Run full enrichment with test directory
    python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/agentic_rag_test

    # 3. Search for company information
    python mcp_enrichment_client.py abridge --search "Abridge AI healthcare company"

    # 4. Extract a specific field
    python mcp_enrichment_client.py abridge --extract founded_year company_record

    # 5. Complete workflow: analyze → search → extract → enrich
    python mcp_enrichment_client.py abridge --workflow
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


class MCPEnrichmentClient:
    """Client for interacting with the FastMCP Agentic RAG server."""
    
    def __init__(self, test_dir: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            test_dir: Optional test directory for output storage
        """
        self.test_dir = Path(test_dir) if test_dir else None
        self.session = None
        self.stdio_context = None
        self.read_stream = None
        self.write_stream = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "test_dir": str(self.test_dir) if self.test_dir else None,
            "operations": []
        }
    
    async def connect(self):
        """Connect to the MCP server."""
        logger.info("=" * 70)
        logger.info("🔌 [CLIENT] Connecting to FastMCP Server...")
        logger.info("=" * 70)
        logger.info("⚠️  NOTE: This requires the MCP server to already be running!")
        logger.info("   Start server in another terminal: python -m src.mcp_server")
        logger.info("=" * 70)
        
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"],
            env=None  # Inherit environment from parent
        )
        
        self.stdio_context = stdio_client(server_params)
        self.read_stream, self.write_stream = await self.stdio_context.__aenter__()
        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        
        logger.info("✅ Connected to FastMCP server")
        logger.info("🚀 Session initialized\n")
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if hasattr(self, 'stdio_context'):
                await self.stdio_context.__aexit__(None, None, None)
        except Exception as e:
            logger.debug(f"Cleanup error (ignored): {e}")
    
    async def analyze_payload(self, company_name: str, show_values: bool = False) -> dict:
        """
        Analyze a payload to identify null fields.
        
        Args:
            company_name: Company identifier
            show_values: Whether to show current field values
        
        Returns:
            Analysis result
        """
        logger.info(f"📊 [ANALYZE] Analyzing payload for {company_name}...")
        
        try:
            result = await self.session.call_tool(
                "analyze_payload",
                {
                    "company_name": company_name,
                    "show_values": show_values
                }
            )
            
            # Parse result
            for content in result.content:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    
                    operation = {
                        "operation": "analyze_payload",
                        "company": company_name,
                        "status": "success" if data.get("success") else "failed",
                        "null_fields": data.get("total_null_fields", 0),
                        "fields_by_type": data.get("null_fields_by_type", {})
                    }
                    self.results["operations"].append(operation)
                    
                    logger.info(f"✅ [ANALYZE] Found {data.get('total_null_fields')} null fields")
                    
                    # Print summary by type
                    for entity_type, fields in data.get("null_fields_by_type", {}).items():
                        logger.info(f"   • {entity_type}: {len(fields)} fields")
                        for field in fields[:3]:
                            logger.info(f"      - {field.get('field_name')}")
                        if len(fields) > 3:
                            logger.info(f"      - ... and {len(fields) - 3} more")
                    
                    return data
        
        except Exception as e:
            logger.error(f"❌ [ANALYZE] Error: {e}")
            self.results["operations"].append({
                "operation": "analyze_payload",
                "company": company_name,
                "status": "error",
                "error": str(e)
            })
            raise
    
    async def search_company(self, query: str, company_name: str, topic: str = "general") -> dict:
        """
        Search for company information.
        
        Args:
            query: Search query
            company_name: Company identifier
            topic: Search topic
        
        Returns:
            Search results
        """
        logger.info(f"🔍 [SEARCH] Searching for: {query[:50]}...")
        
        try:
            result = await self.session.call_tool(
                "search_company",
                {
                    "query": query,
                    "company_name": company_name,
                    "topic": topic
                }
            )
            
            # Parse result
            for content in result.content:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    
                    operation = {
                        "operation": "search_company",
                        "company": company_name,
                        "query": query,
                        "status": "success" if data.get("success") else "failed",
                        "result_count": data.get("count", 0)
                    }
                    self.results["operations"].append(operation)
                    
                    logger.info(f"✅ [SEARCH] Found {data.get('count')} results")
                    
                    # Print first 2 results
                    for idx, result in enumerate(data.get("results", [])[:2], 1):
                        logger.info(f"   Result {idx}: {result.get('title', 'N/A')[:60]}...")
                    
                    if len(data.get("results", [])) > 2:
                        logger.info(f"   ... and {len(data['results']) - 2} more results")
                    
                    return data
        
        except Exception as e:
            logger.error(f"❌ [SEARCH] Error: {e}")
            self.results["operations"].append({
                "operation": "search_company",
                "company": company_name,
                "status": "error",
                "error": str(e)
            })
            raise
    
    async def extract_field(
        self,
        field_name: str,
        entity_type: str,
        company_name: str,
        importance: str = "medium",
        search_results: Optional[str] = None
    ) -> dict:
        """
        Extract a field value using LLM.
        
        Args:
            field_name: Field name to extract
            entity_type: Entity type
            company_name: Company identifier
            importance: Importance level
            search_results: JSON string of search results
        
        Returns:
            Extraction result
        """
        logger.info(f"🔗 [EXTRACT] Extracting {field_name} from {entity_type}...")
        
        try:
            result = await self.session.call_tool(
                "extract_field",
                {
                    "field_name": field_name,
                    "entity_type": entity_type,
                    "company_name": company_name,
                    "importance": importance,
                    "search_results": search_results
                }
            )
            
            # Parse result
            for content in result.content:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    
                    operation = {
                        "operation": "extract_field",
                        "field": field_name,
                        "entity_type": entity_type,
                        "status": "success" if not data.get("error") else "failed",
                        "extracted_value": data.get("final_value"),
                        "confidence": data.get("confidence", 0)
                    }
                    self.results["operations"].append(operation)
                    
                    if data.get("final_value"):
                        logger.info(f"✅ [EXTRACT] Extracted: {data.get('final_value')[:50]}")
                        logger.info(f"   Confidence: {data.get('confidence', 0):.2%}")
                    else:
                        logger.info(f"⚠️  [EXTRACT] No value extracted")
                    
                    return data
        
        except Exception as e:
            logger.error(f"❌ [EXTRACT] Error: {e}")
            self.results["operations"].append({
                "operation": "extract_field",
                "field": field_name,
                "status": "error",
                "error": str(e)
            })
            raise
    
    async def enrich_payload(
        self,
        company_name: str,
        max_iterations: int = 20
    ) -> dict:
        """
        Run full enrichment workflow.
        
        Args:
            company_name: Company identifier
            max_iterations: Maximum iterations
        
        Returns:
            Enrichment result
        """
        logger.info(f"⚡ [ENRICH] Starting full enrichment for {company_name}...")
        logger.info(f"   Max iterations: {max_iterations}")
        if self.test_dir:
            logger.info(f"   Test directory: {self.test_dir}")
        
        try:
            result = await self.session.call_tool(
                "enrich_payload",
                {
                    "company_name": company_name,
                    "test_dir": str(self.test_dir) if self.test_dir else None,
                    "max_iterations": max_iterations
                }
            )
            
            # Parse result
            for content in result.content:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    
                    operation = {
                        "operation": "enrich_payload",
                        "company": company_name,
                        "status": data.get("status", "unknown"),
                        "null_fields_found": data.get("null_fields_found", 0),
                        "null_fields_filled": data.get("null_fields_filled", 0),
                        "success": data.get("success", False)
                    }
                    self.results["operations"].append(operation)
                    
                    logger.info(f"✅ [ENRICH] Enrichment completed")
                    logger.info(f"   Status: {data.get('status')}")
                    logger.info(f"   Null fields found: {data.get('null_fields_found')}")
                    logger.info(f"   Null fields filled: {data.get('null_fields_filled')}")
                    
                    return data
        
        except Exception as e:
            logger.error(f"❌ [ENRICH] Error: {e}")
            self.results["operations"].append({
                "operation": "enrich_payload",
                "company": company_name,
                "status": "error",
                "error": str(e)
            })
            raise
    
    async def get_payload(self, company_name: str) -> dict:
        """
        Get current payload for a company.
        
        Args:
            company_name: Company identifier
        
        Returns:
            Payload data
        """
        logger.info(f"📄 [PAYLOAD] Retrieving payload for {company_name}...")
        
        try:
            resource = await self.session.read_resource(f"payload://{company_name}")
            
            for content in resource.contents:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    logger.info(f"✅ [PAYLOAD] Retrieved payload")
                    logger.info(f"   Company ID: {data.get('company_id', 'N/A')}")
                    logger.info(f"   Keys: {', '.join(data.keys())}")
                    return data
        
        except Exception as e:
            logger.error(f"❌ [PAYLOAD] Error: {e}")
            raise
    
    async def list_payloads(self) -> dict:
        """
        List all available payloads.
        
        Returns:
            List of payloads
        """
        logger.info(f"📋 [PAYLOADS] Listing all available payloads...")
        
        try:
            resource = await self.session.read_resource("payloads://available")
            
            for content in resource.contents:
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    logger.info(f"✅ [PAYLOADS] Found {data.get('total_companies')} companies")
                    for company in data.get("companies", []):
                        logger.info(f"   • {company}")
                    return data
        
        except Exception as e:
            logger.error(f"❌ [PAYLOADS] Error: {e}")
            raise
    
    def save_results(self):
        """Save results to test directory."""
        if not self.test_dir:
            logger.info("ℹ️  No test directory specified, skipping results save")
            return
        
        self.test_dir.mkdir(parents=True, exist_ok=True)
        results_file = self.test_dir / "mcp_client_results.json"
        
        logger.info(f"\n💾 [SAVE] Saving results to {results_file}")
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"✅ [SAVE] Results saved successfully")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="FastMCP Client for Agentic RAG Enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze payload
  python mcp_enrichment_client.py abridge
  
  # Full enrichment with test directory
  python mcp_enrichment_client.py abridge --enrich --test-dir /tmp/agentic_rag_test
  
  # Search for information
  python mcp_enrichment_client.py abridge --search "founding year"
  
  # Complete workflow
  python mcp_enrichment_client.py abridge --workflow
        """
    )
    
    parser.add_argument("company", help="Company identifier (e.g., 'abridge')")
    parser.add_argument("--test-dir", help="Test directory for output storage")
    parser.add_argument("--enrich", action="store_true", help="Run full enrichment workflow")
    parser.add_argument("--search", help="Search query")
    parser.add_argument("--extract", nargs=2, metavar=("FIELD", "ENTITY"), help="Extract field from entity")
    parser.add_argument("--workflow", action="store_true", help="Run complete workflow (analyze → search → extract → enrich)")
    parser.add_argument("--max-iterations", type=int, default=20, help="Max iterations for enrichment (default: 20)")
    
    args = parser.parse_args()
    
    # Create client
    client = MCPEnrichmentClient(test_dir=args.test_dir)
    
    try:
        # Connect to server
        await client.connect()
        
        # Run operations based on arguments
        if args.workflow:
            # Complete workflow
            logger.info("\n🔄 [WORKFLOW] Running complete enrichment workflow...\n")
            
            # 1. Analyze
            await client.analyze_payload(args.company)
            
            # 2. Search for each field
            logger.info("")
            search_queries = [
                f"{args.company} founding information",
                f"{args.company} headquarters location",
                f"{args.company} company categories"
            ]
            search_results = None
            for query in search_queries[:1]:  # Just first search for demo
                search_results = await client.search_company(query, args.company)
                logger.info("")
            
            # 3. Extract field
            if search_results:
                await client.extract_field(
                    "founded_year",
                    "company_record",
                    args.company,
                    search_results=json.dumps(search_results)
                )
                logger.info("")
            
            # 4. Full enrichment
            await client.enrich_payload(args.company, args.max_iterations)
            
        elif args.enrich:
            # Full enrichment
            await client.enrich_payload(args.company, args.max_iterations)
        
        elif args.search:
            # Search only
            await client.search_company(args.search, args.company)
        
        elif args.extract:
            # Extract only
            field_name, entity_type = args.extract
            await client.extract_field(field_name, entity_type, args.company)
        
        else:
            # Analyze only (default)
            await client.analyze_payload(args.company)
        
        # Get updated payload
        logger.info("")
        await client.get_payload(args.company)
        
        # Save results
        logger.info("")
        client.save_results()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ All operations completed successfully!")
        logger.info("=" * 70)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
