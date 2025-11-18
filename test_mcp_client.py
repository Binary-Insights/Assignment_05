"""
Test client for Agentic RAG MCP Server
Demonstrates how to interact with the running MCP server
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_server_connection():
    """Test basic connection to MCP server."""
    logger.info("=" * 70)
    logger.info("🧪 [TEST] MCP Server Connection Test")
    logger.info("=" * 70)
    
    try:
        # Connect to server via stdio with StdioServerParameters
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"]
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                logger.info("✅ Connected to MCP server")
                
                # Initialize session
                await session.initialize()
                logger.info("✅ Session initialized")
                
                # Get server capabilities
                capabilities = session.get_capabilities()
                logger.info(f"✅ Server capabilities: {capabilities}")
                
                # List available tools
                tools = await session.list_tools()
                logger.info(f"✅ Available tools ({len(tools)} total):")
                for tool in tools:
                    logger.info(f"   - {tool.name}: {tool.description}")
                
                return True
                
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}", exc_info=True)
        return False


async def test_search_company_tool():
    """Test the search_company tool."""
    logger.info("\n" + "=" * 70)
    logger.info("🧪 [TEST] search_company Tool")
    logger.info("=" * 70)
    
    try:
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"]
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call search_company tool
                logger.info("🔍 Calling search_company...")
                result = await session.call_tool(
                    "search_company",
                    {
                        "company_name": "OpenAI",
                        "query": "founded year headquarters",
                        "topic": "company_info"
                    }
                )
                
                logger.info(f"✅ Tool result: {result}")
                
                # Try to parse as JSON
                try:
                    if result.content and len(result.content) > 0:
                        response_text = result.content[0].text
                        response_json = json.loads(response_text)
                        logger.info(f"📊 Parsed response: {json.dumps(response_json, indent=2)[:500]}...")
                except Exception as e:
                    logger.warning(f"Could not parse response as JSON: {e}")
                
                return True
                
    except Exception as e:
        logger.error(f"❌ search_company test failed: {e}", exc_info=True)
        return False


async def test_analyze_null_fields_tool():
    """Test the analyze_null_fields tool."""
    logger.info("\n" + "=" * 70)
    logger.info("🧪 [TEST] analyze_null_fields Tool")
    logger.info("=" * 70)
    
    try:
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"]
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call analyze_null_fields tool
                logger.info("📊 Calling analyze_null_fields...")
                result = await session.call_tool(
                    "analyze_null_fields",
                    {
                        "company_name": "test_company"
                    }
                )
                
                logger.info(f"✅ Tool result: {result}")
                
                # Try to parse as JSON
                try:
                    if result.content and len(result.content) > 0:
                        response_text = result.content[0].text
                        response_json = json.loads(response_text)
                        logger.info(f"📊 Parsed response: {json.dumps(response_json, indent=2)}")
                except Exception as e:
                    logger.warning(f"Could not parse response as JSON: {e}")
                
                return True
                
    except Exception as e:
        logger.error(f"❌ analyze_null_fields test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all tests."""
    logger.info("🚀 Starting MCP Server Test Suite\n")
    
    tests = [
        ("Connection Test", test_server_connection),
        ("search_company Tool", test_search_company_tool),
        ("analyze_null_fields Tool", test_analyze_null_fields_tool),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
        
        # Small delay between tests
        await asyncio.sleep(0.5)
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📋 Test Summary")
    logger.info("=" * 70)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    passed_count = sum(1 for v in results.values() if v)
    logger.info(f"\n📊 {passed_count}/{len(results)} tests passed")
    
    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
