"""
Quick MCP Server Verification - Connection Only
Verifies server is running and responsive
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def quick_test():
    """Quick connection and initialization test."""
    try:
        logger.info("🔌 Connecting to MCP server...")
        
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_server"]
        )
        async with stdio_client(server_params) as (read, write):
            logger.info("✅ Connected!")
            
            async with ClientSession(read, write) as session:
                logger.info("🤝 Initializing session...")
                await session.initialize()
                logger.info("✅ Session initialized!")
                
                logger.info("\n🎉 MCP Server is working correctly!")
                logger.info("   • Server is responsive")
                logger.info("   • Session initialization successful")
                logger.info("   • Ready for client connections")
                return True
                
    except asyncio.TimeoutError:
        logger.error("❌ Timeout connecting to server")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(asyncio.wait_for(quick_test(), timeout=30))
        sys.exit(0 if success else 1)
    except asyncio.TimeoutError:
        logger.error("❌ Test timeout (>30s)")
        sys.exit(1)
