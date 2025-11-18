"""
FastMCP Server Launch Script
Entry point for running the Agentic RAG FastMCP Server
"""

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

from mcp_server.server import app


if __name__ == "__main__":
    """
    Run the FastMCP server.
    
    Usage:
        python -m mcp_server
    
    The server will:
    1. Initialize FastMCP with all tools and resources
    2. Register tools:
       - search_company: Search company information via Tavily
       - extract_field: Extract field values using LLM chain
       - enrich_payload: Run complete enrichment workflow
       - analyze_payload: Analyze payloads for null fields
    3. Register resources:
       - get_payload: Get company payload
       - list_payloads: List available payloads
    4. Register prompt templates:
       - enrichment_workflow: Enrichment workflow guidance
       - security_guidelines: Security best practices
    5. Start listening on stdio transport for MCP client connections
    
    Environment:
    - TAVILY_API_KEY: Required for search_company tool
    - OPENAI_API_KEY: Required for extract_field tool
    - LOG_LEVEL: Optional, defaults to INFO
    
    FastMCP Benefits:
    - Simpler decorator-based API (@app.tool(), @app.resource(), @app.prompt())
    - Automatic type inference from function signatures
    - Built-in serialization for JSON responses
    - No manual error handling in registration
    """
    try:
        logger.info("🚀 Launching Agentic RAG FastMCP Server...")
        logger.info(f"   Project Root: {Path(__file__).parent.parent.parent}")
        logger.info(f"   Logs Directory: {log_dir}")
        
        # Run the FastMCP server
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Server crashed: {e}")
        sys.exit(1)
