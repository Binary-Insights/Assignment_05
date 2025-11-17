#!/usr/bin/env python
"""
Quick test script to verify FastMCP server is working.
Run this in a NEW terminal while the server is running in another terminal.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    """Test the MCP server."""
    
    print("\n" + "=" * 70)
    print("🧪 FastMCP Server Test")
    print("=" * 70)
    
    # Connect to the already-running server
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.mcp_server"]
    )
    
    try:
        print("\n📡 [1] Connecting to MCP server...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                
                print("✅ [2] Connected! Initializing session...")
                await session.initialize()
                print("✅ [3] Session initialized")
                
                # Test: List tools
                print("\n📋 [4] Listing available tools...")
                tools = await session.list_tools()
                print(f"✅ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"   • {tool.name}: {tool.description[:50]}...")
                
                # Test: Analyze payload
                print("\n🔍 [5] Testing analyze_payload tool...")
                result = await session.call_tool(
                    "analyze_payload",
                    {"company_name": "abridge"}
                )
                print("✅ Tool executed successfully!")
                
                # Parse and display result
                for content in result.content:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        print(f"\n   Response:")
                        print(f"   • Company: {data.get('company_name')}")
                        print(f"   • Total null fields: {data.get('total_null_fields')}")
                        
                        # Show summary by entity type
                        if data.get('null_fields_by_type'):
                            print(f"   • Fields by type:")
                            for entity_type, fields in data['null_fields_by_type'].items():
                                print(f"      - {entity_type}: {len(fields)} fields")
                        
                        if data.get('success'):
                            print(f"   ✅ Status: Success")
                
                # Test: List payloads resource
                print("\n📚 [6] Testing list_payloads resource...")
                resource = await session.read_resource("payloads://available")
                print("✅ Resource read successfully!")
                
                for content in resource.contents:
                    if hasattr(content, 'text'):
                        data = json.loads(content.text)
                        companies = data.get('companies', [])
                        print(f"\n   Available companies ({data.get('total_companies')}):")
                        for company in companies[:5]:
                            print(f"      • {company}")
                        if len(companies) > 5:
                            print(f"      • ... and {len(companies) - 5} more")
                
                # Test: Get enrichment workflow prompt
                print("\n📖 [7] Testing enrichment_workflow prompt...")
                prompt = await session.get_prompt(
                    "enrichment_workflow",
                    {"company_name": "abridge"}
                )
                print("✅ Prompt retrieved successfully!")
                
                for message in prompt.messages:
                    for content in message.content:
                        if hasattr(content, 'text'):
                            text = content.text
                            # Show first 400 chars
                            preview = text[:400].replace('\n', '\n   ')
                            print(f"\n   {preview}...")
                
                print("\n" + "=" * 70)
                print("✅ All tests passed!")
                print("=" * 70)
                print("\n📖 For complete documentation, see: FASTMCP_USAGE.md")
                print("🚀 To use with Claude Desktop, see: FASTMCP_IMPLEMENTATION_SUMMARY.md")
                print()
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("\n⚠️  Make sure the MCP server is running in another terminal:")
    print("   python -m src.mcp_server\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(0)
