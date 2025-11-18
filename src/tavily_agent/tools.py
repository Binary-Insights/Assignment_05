"""
Tool definitions for Agentic RAG system.
Implements Tavily search using direct API calls to avoid LangSmith automatic tracing.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
from pathlib import Path
import httpx

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import TAVILY_API_KEY, TOOL_TIMEOUT
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.vector_db_manager import VectorDBManager

logger = logging.getLogger(__name__)

# Import Document from vector_db_manager to avoid circular imports
from tavily_agent.vector_db_manager import Document


class ToolManager:
    """Manages tool execution and result processing."""
    
    def __init__(self):
        """Initialize tool manager with Tavily API key (direct HTTP calls, no LangChain wrapper)."""
        self.tavily_api_key = TAVILY_API_KEY
        self.tavily_api_url = "https://api.tavily.com/search"
        self.file_io = FileIOManager()
    
    async def search_tavily(
        self,
        query: str,
        company_name: str,
        topic: str = "general"
    ) -> Dict[str, Any]:
        """
        Execute Tavily search using direct HTTP API call.
        Does NOT use LangChain's TavilySearchResults wrapper to avoid automatic LangSmith tracing.
        
        Args:
            query: Search query
            company_name: Company identifier
            topic: Search topic (for categorization)
        
        Returns:
            Dictionary with results and metadata
        """
        logger.info(f"🔍 [TAVILY SEARCH] Starting search for query: '{query}'")
        logger.debug(f"   Company: {company_name}, Topic: {topic}")
        
        try:
            # Use direct HTTP API call to avoid LangChain wrapper tracing
            logger.info(f"⏳ [TAVILY] Executing Tavily API call (timeout: {TOOL_TIMEOUT}s)...")
            
            async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
                response = await client.post(
                    self.tavily_api_url,
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "max_results": 5,
                        "include_answer": True
                    }
                )
                response.raise_for_status()
                api_response = response.json()
            
            logger.info(f"✅ [TAVILY] API call successful")
            
            # Process results
            processed_results = []
            raw_content = ""
            
            logger.info(f"📊 [TAVILY RESPONSE] Processing API response...")
            
            # Extract results from Tavily API response
            results = api_response.get("results", [])
            logger.info(f"📈 [TAVILY] Found {len(results)} results")
            
            for idx, result in enumerate(results):
                title = result.get('title', 'N/A')
                content = result.get('content', '')
                url = result.get('url', '')
                logger.info(f"   [{idx+1}] Title: {title}")
                logger.debug(f"       URL: {url}")
                logger.debug(f"       Content preview: {content[:100]}...")
                
                processed_result = {
                    "title": title,
                    "content": content,
                    "url": url
                }
                processed_results.append(processed_result)
                raw_content += f"\n{title}\n{content}\n"
            
            logger.info(f"💾 [TAVILY] Saving {len(processed_results)} results to disk...")
            # Save raw data
            output_data = {
                "query": query,
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat(),
                "result_count": len(processed_results),
                "results": processed_results
            }
            
            await self.file_io.save_raw_data(
                company_name=company_name,
                tool_name="tavily",
                data=output_data,
                content=raw_content
            )
            logger.info(f"✅ [TAVILY] Results saved successfully")
            
            logger.info(f"🎯 [TAVILY COMPLETE] Query '{query}' returned {len(processed_results)} results")
            
            return {
                "tool": "tavily",
                "query": query,
                "results": processed_results,
                "raw_content": raw_content,
                "count": len(processed_results),
                "success": True
            }
            
        except asyncio.TimeoutError:
            logger.error(f"⏱️ [TAVILY ERROR] Search timed out after {TOOL_TIMEOUT}s for query: {query}")
            return {
                "tool": "tavily",
                "query": query,
                "results": [],
                "raw_content": "",
                "count": 0,
                "success": False,
                "error": "Search timeout"
            }
        except Exception as e:
            logger.error(f"❌ [TAVILY ERROR] Search failed: {type(e).__name__}: {e}", exc_info=True)
            return {
                "tool": "tavily",
                "query": query,
                "results": [],
                "raw_content": "",
                "count": 0,
                "success": False,
                "error": str(e)
            }
    
    async def process_search_results_to_documents(
        self,
        search_results: Dict[str, Any]
    ) -> List[Document]:
        """
        Convert search results to LangChain Document objects.
        
        Args:
            search_results: Results from search_tavily
        
        Returns:
            List of Document objects
        """
        documents = []
        
        for result in search_results.get("results", []):
            if isinstance(result, dict):
                content = result.get("content", "") or result.get("title", "")
                url = result.get("url", "")
                
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": url,
                        "tool": search_results.get("tool", "unknown"),
                        "title": result.get("title", ""),
                        "crawled_at": datetime.utcnow().isoformat()
                    }
                )
                documents.append(doc)
        
        return documents
    
    async def execute_batch_searches(
        self,
        queries: List[str],
        company_name: str
    ) -> Dict[str, Any]:
        """
        Execute multiple searches concurrently.
        
        Args:
            queries: List of search queries
            company_name: Company identifier
        
        Returns:
            Combined results from all searches
        """
        logger.info(f"🔄 [BATCH SEARCH] Starting batch search with {len(queries)} queries")
        for idx, q in enumerate(queries, 1):
            logger.info(f"   [{idx}/{len(queries)}] {q}")
        
        # Create tasks for concurrent execution
        logger.info(f"⚙️  [BATCH] Creating {len(queries)} concurrent search tasks...")
        tasks = [
            self.search_tavily(query, company_name)
            for query in queries
        ]
        
        # Run concurrently
        logger.info(f"🚀 [BATCH] Executing {len(queries)} searches concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"✅ [BATCH] All {len(queries)} searches completed")
        
        # Process results
        all_documents = []
        combined_content = ""
        success_count = 0
        error_count = 0
        
        logger.info(f"📋 [BATCH] Processing {len(results)} search results...")
        for idx, result in enumerate(results, 1):
            if isinstance(result, Exception):
                error_count += 1
                logger.error(f"   [{idx}] ❌ Error: {type(result).__name__}: {result}")
                continue
            
            if result.get("success"):
                success_count += 1
                query = result.get("query", "unknown")
                count = result.get("count", 0)
                logger.info(f"   [{idx}] ✅ '{query}': {count} results")
                docs = await self.process_search_results_to_documents(result)
                all_documents.extend(docs)
                combined_content += result.get("raw_content", "") + "\n"
            else:
                error_count += 1
                query = result.get("query", "unknown")
                error = result.get("error", "unknown")
                logger.warning(f"   [{idx}] ⚠️  '{query}': {error}")
        
        logger.info(f"📊 [BATCH COMPLETE] Success: {success_count}, Failed: {error_count}, Total documents: {len(all_documents)}")
        
        return {
            "documents": all_documents,
            "combined_content": combined_content,
            "total_results": len(all_documents),
            "queries_executed": len(queries)
        }


# Global instance
_tool_manager: Optional[ToolManager] = None


async def get_tool_manager() -> ToolManager:
    """Get or create the global ToolManager instance."""
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolManager()
    return _tool_manager


# NOTE: Tavily search is NOT decorated with @tool or @traceable
# All Tavily calls are integrated into the LangGraph nodes under the main trace
async def tavily_search_helper(query: str) -> str:
    """
    Helper function for Tavily search (not used as LangChain tool).
    Kept for reference/backwards compatibility.
    
    Args:
        query: The search query
    
    Returns:
        Search results as string
    """
    tool_manager = await get_tool_manager()
    result = await tool_manager.search_tavily(query, "unknown")
    return json.dumps(result, indent=2)
