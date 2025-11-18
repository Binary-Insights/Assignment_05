"""
Vector Database Manager for Pinecone integration.
Handles document storage, retrieval, deduplication, and metadata management.
"""

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
    EMBEDDING_MODEL,
    RAW_DATA_DIR,
    DEDUP_HASH_ALGORITHM,
    DEDUP_CHECK_ENABLED
)

logger = logging.getLogger(__name__)

# Define Document class locally if not available
class Document:
    """Simple document class for storing content and metadata."""
    def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class VectorDBManager:
    """Manages Pinecone vector database operations with deduplication."""
    
    def __init__(self):
        """Initialize Pinecone client and embeddings."""
        self.client = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self.client.Index(PINECONE_INDEX_NAME)
        self.embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        self.dedup_hashes: Dict[str, set] = {}
        logger.info(f"VectorDBManager initialized with index: {PINECONE_INDEX_NAME}")
    
    async def _compute_hash(self, content: str, algorithm: str = DEDUP_HASH_ALGORITHM) -> str:
        """Compute hash of content for deduplication."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: hashlib.new(algorithm, content.encode()).hexdigest()
        )
    
    async def _load_existing_hashes(self, company_id: str, tool_name: str) -> set:
        """Load existing document hashes from raw data directory."""
        company_dir = RAW_DATA_DIR / company_id / tool_name
        hashes = set()
        
        if company_dir.exists():
            for file in company_dir.glob("*.json"):
                try:
                    with open(file, "r") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "hash" in data:
                            hashes.add(data["hash"])
                except Exception as e:
                    logger.warning(f"Error reading hash from {file}: {e}")
        
        return hashes
    
    async def check_duplicate(
        self, 
        content: str, 
        company_id: str, 
        tool_name: str
    ) -> bool:
        """
        Check if content already exists in the system.
        
        Args:
            content: The content to check
            company_id: Company identifier
            tool_name: Source tool name
        
        Returns:
            True if duplicate exists, False otherwise
        """
        if not DEDUP_CHECK_ENABLED:
            return False
        
        content_hash = await self._compute_hash(content)
        existing_hashes = await self._load_existing_hashes(company_id, tool_name)
        
        return content_hash in existing_hashes
    
    async def add_documents(
        self,
        documents: List[Document],
        company_id: str,
        tool_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, int]:
        """
        Add documents to Pinecone with deduplication.
        
        Args:
            documents: List of LangChain Document objects
            company_id: Company identifier
            tool_name: Source tool name (e.g., 'tavily', 'web_search')
            metadata: Additional metadata for all documents
        
        Returns:
            Tuple of (added_count, skipped_count)
        """
        added_count = 0
        skipped_count = 0
        
        for doc in documents:
            try:
                # Check for duplicate
                is_duplicate = await self.check_duplicate(
                    doc.page_content,
                    company_id,
                    tool_name
                )
                
                if is_duplicate:
                    logger.info(f"Skipping duplicate document from {tool_name}")
                    skipped_count += 1
                    continue
                
                # Generate embedding
                embedding = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.embeddings.embed_query(doc.page_content)
                )
                
                # Prepare metadata
                base_metadata = metadata or {}
                doc_metadata = {
                    "company_id": company_id,
                    "tool_name": tool_name,
                    "source": doc.metadata.get("source", "unknown"),
                    "crawled_at": datetime.utcnow().isoformat(),
                    **base_metadata,
                    **doc.metadata
                }
                
                # Create unique ID
                doc_hash = await self._compute_hash(doc.page_content)
                vector_id = f"{company_id}_{tool_name}_{doc_hash[:12]}"
                
                # Upsert to Pinecone
                self.index.upsert(
                    vectors=[
                        (vector_id, embedding, doc_metadata)
                    ],
                    namespace=PINECONE_NAMESPACE
                )
                
                added_count += 1
                logger.debug(f"Added document: {vector_id}")
                
            except Exception as e:
                logger.error(f"Error adding document: {e}")
                continue
        
        logger.info(f"Added {added_count} documents, skipped {skipped_count} duplicates")
        return added_count, skipped_count
    
    async def search(
        self,
        query: str,
        company_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents in Pinecone.
        
        Args:
            query: Search query
            company_id: Company identifier
            top_k: Number of results to return
        
        Returns:
            List of search results with metadata
        """
        try:
            # Generate query embedding
            query_embedding = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.embeddings.embed_query(query)
            )
            
            # Search
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=PINECONE_NAMESPACE,
                filter={"company_id": {"$eq": company_id}},
                include_metadata=True
            )
            
            formatted_results = []
            for match in results.get("matches", []):
                formatted_results.append({
                    "id": match.get("id"),
                    "score": match.get("score"),
                    "metadata": match.get("metadata", {})
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching Pinecone: {e}")
            return []
    
    async def get_company_context(self, company_id: str) -> str:
        """
        Get all indexed content for a company as context.
        
        Args:
            company_id: Company identifier
        
        Returns:
            Concatenated context string
        """
        try:
            # Query all vectors for this company
            results = self.index.query(
                vector=[0] * 1536,  # Dummy vector for retrieval
                top_k=100,
                namespace=PINECONE_NAMESPACE,
                filter={"company_id": {"$eq": company_id}},
                include_metadata=True
            )
            
            context_parts = []
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})
                tool_name = metadata.get("tool_name", "unknown")
                context_parts.append(f"[{tool_name}] {metadata.get('source', 'N/A')}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting company context: {e}")
            return ""


# Global instance
_vector_db_manager: Optional[VectorDBManager] = None


async def get_vector_db_manager() -> VectorDBManager:
    """Get or create the global VectorDBManager instance."""
    global _vector_db_manager
    if _vector_db_manager is None:
        _vector_db_manager = VectorDBManager()
    return _vector_db_manager
