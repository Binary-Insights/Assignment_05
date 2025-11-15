"""
MCP Server Launch Script
Entry point for running the Agentic RAG MCP Server
"""

import asyncio
import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent.parent.parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),  # MCP uses stderr for logging
        logging.FileHandler(log_dir / "mcp_server.log")
    ]
)

logger = logging.getLogger(__name__)

from mcp_server.server import main


if __name__ == "__main__":
    """
    Run the MCP server.
    
    Usage:
        python -m mcp_server
    
    The server will:
    1. Initialize the security middleware
    2. Register all tools (search_company, extract_field, enrich_payload, analyze_null_fields)
    3. Register resources (company payloads and extractions)
    4. Register prompt templates (enrichment workflows)
    5. Start listening on stdio transport for MCP client connections
    
    Environment:
    - TAVILY_API_KEY: Required for search_company tool
    - OPENAI_API_KEY: Required for extract_field tool
    - LOG_LEVEL: Optional, defaults to INFO
    """
    try:
        logger.info("Launching MCP Server...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception(f"Server crashed: {e}")
        sys.exit(1)
