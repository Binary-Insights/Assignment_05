"""
Trigger the tavily agent via MCP server with test directory support.
Allows running enrichment workflow through MCP interface with custom test paths.
"""

import asyncio
import json
import sys
from pathlib import Path
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def trigger_tavily_agent(company_name: str, test_dir: str = None):
    """
    Trigger the tavily agent via MCP server.
    
    Args:
        company_name: Company to enrich (e.g., 'abridge')
        test_dir: Optional test directory path
    """
    
    try:
        # Connect to MCP server
        print(f"\n{'='*70}")
        print(f"🔌 Connecting to MCP server...")
        print(f"{'='*70}\n")
        
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server!")
                print(f"✅ Session initialized!\n")
                
                # Build arguments for enrich_payload
                arguments = {
                    "company_name": company_name,
                    "max_iterations": 2
                }
                
                # Call enrich_payload tool
                print(f"{'='*70}")
                print(f"🚀 Triggering enrichment for: {company_name}")
                if test_dir:
                    print(f"📁 Test directory: {test_dir}")
                print(f"{'='*70}\n")
                
                result = await session.call_tool(
                    "enrich_payload",
                    arguments
                )
                
                # Parse and display result
                print(f"Raw result: {result}")
                print(f"Result content: {result.content}")
                
                if not result.content or len(result.content) == 0:
                    print("❌ No content in result!")
                    sys.exit(1)
                
                content = result.content[0].text
                
                if not content or content.strip() == "":
                    print("❌ Empty content in response!")
                    print(f"Result object: {result}")
                    sys.exit(1)
                
                print(f"Content received: {content[:200]}...")  # Print first 200 chars
                enrichment_result = json.loads(content)
                
                print(f"\n{'='*70}")
                print(f"✅ Enrichment Complete!")
                print(f"{'='*70}\n")
                print(json.dumps(enrichment_result, indent=2))
                
                # Print summary
                if "status" in enrichment_result:
                    print(f"\n{'='*70}")
                    print(f"📊 Status: {enrichment_result.get('status')}")
                    if "null_fields_found" in enrichment_result:
                        print(f"🔍 Null fields found: {enrichment_result.get('null_fields_found')}")
                    if "null_fields_filled" in enrichment_result:
                        print(f"✏️  Null fields filled: {enrichment_result.get('null_fields_filled')}")
                    if "errors" in enrichment_result and enrichment_result.get('errors'):
                        print(f"⚠️  Errors: {enrichment_result.get('errors')}")
                    print(f"{'='*70}\n")
                
                return enrichment_result
    
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Trigger tavily agent enrichment via MCP server"
    )
    parser.add_argument(
        "company",
        help="Company name to enrich (e.g., 'abridge')"
    )
    parser.add_argument(
        "--test-dir",
        help="Test directory path (e.g., '/mnt/c/Users/.../tmp/agentic_rag_test')",
        default=None
    )
    
    args = parser.parse_args()
    
    await trigger_tavily_agent(args.company, args.test_dir)

if __name__ == "__main__":
    asyncio.run(main())
