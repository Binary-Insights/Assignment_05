"""
RAG Search Adapter Protocol — Formalize interface for vector search tools.

This module provides:
- RagSearchAdapter: Protocol defining expected signature for rag_search_tool
- create_pinecone_adapter: Live Pinecone implementation
"""

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class RagSearchAdapter(Protocol):
    """
    Protocol for RAG search tools used in payload vector fills.
    
    Any callable matching this signature can be passed as rag_search_tool:
        (company_id: str, query: str, top_k: int) -> List[Dict[str, Any]]
    
    Expected return structure:
    [
        {
            "text" or "snippet": str,  # actual text chunk
            "metadata": {
                "source_url": str,
                "crawled_at": str (ISO),
                "chunk_id": str (optional),
                ...
            }
        },
        ...
    ]
    """
    
    def __call__(
        self,
        company_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search vector DB for relevant chunks matching query.
        
        Args:
            company_id: Company identifier (may be used for namespace filtering)
            query: Natural language search query
            top_k: Number of top results to return
            
        Returns:
            List of dicts with text/snippet and metadata
        """
        ...


# Pinecone adapter factory (implements RagSearchAdapter protocol)
def create_pinecone_adapter(
    index_name: str = None,
    api_key: str = None,
    environment: str = None,
    embedding_model: str = None,
    namespace: str = None,
) -> RagSearchAdapter:
    """
    Create a Pinecone RAG search adapter.
    
    Args:
        index_name: Pinecone index name (defaults to PINECONE_INDEX_NAME env var)
        api_key: Pinecone API key (defaults to PINECONE_API_KEY env var)
        environment: Pinecone environment (defaults to PINECONE_ENVIRONMENT env var)
        embedding_model: OpenAI embedding model (defaults to PINECONE_EMBEDDING_MODEL env var)
        namespace: Optional namespace filter
        
    Returns:
        Callable matching RagSearchAdapter protocol
    """
    import os
    from pinecone import Pinecone
    from openai import OpenAI
    
    # Load from env if not provided
    index_name = index_name or os.getenv("PINECONE_INDEX_NAME")
    api_key = api_key or os.getenv("PINECONE_API_KEY")
    environment = environment or os.getenv("PINECONE_ENVIRONMENT")
    embedding_model = embedding_model or os.getenv("PINECONE_EMBEDDING_MODEL", "text-embedding-3-large")
    # Use same namespace as ingestion if not explicitly provided
    if namespace is None:
        namespace = os.getenv("PINECONE_NAMESPACE")
    
    if not all([index_name, api_key]):
        raise ValueError("Pinecone index_name and api_key required (from args or env vars)")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    
    # Initialize OpenAI for embeddings
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def embed_query(text: str) -> list:
        """Generate embedding vector for query text."""
        response = openai_client.embeddings.create(
            model=embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def pinecone_search(company_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search Pinecone index for relevant chunks.
        
        Args:
            company_id: Company identifier (used for namespace filtering if enabled)
            query: Natural language search query
            top_k: Number of top results to return
            
        Returns:
            List of dicts with text/snippet and metadata
        """
        try:
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"[RAG SEARCH] company_id='{company_id}', query='{query}', top_k={top_k}")
            
            # Generate query embedding
            vector = embed_query(query)
            logger.debug(f"[RAG SEARCH] Generated embedding vector of length {len(vector)}")
            
            # Normalize company_id to match company_slug format (hyphens to underscores)
            company_slug = company_id.replace("-", "_").lower()
            
            logger.debug(f"[RAG SEARCH] Normalized company_slug='{company_slug}'")
            
            # Query Pinecone (use namespace if specified, or filter by company_slug metadata)
            query_params = {
                "vector": vector,
                "top_k": top_k,
                "include_metadata": True,
            }
            
            if namespace:
                query_params["namespace"] = namespace
            
            # Filter by company_slug if provided (metadata field from ingestion)
            # Only apply filter if company_id is not empty
            if company_slug and company_slug.strip():
                query_params["filter"] = {"company_slug": {"$eq": company_slug}}
                logger.info(f"[RAG SEARCH] Applying Pinecone filter: {query_params['filter']}")
            else:
                logger.info(f"[RAG SEARCH] No company filter applied - searching all vectors")
            
            results = index.query(**query_params)
            
            logger.info(f"[RAG SEARCH] Pinecone returned {len(results.matches)} matches")
            if results.matches:
                logger.info(f"[RAG SEARCH] First match score: {results.matches[0].score:.4f}")
                logger.debug(f"[RAG SEARCH] First match text: {results.matches[0].metadata.get('text', '')[:100]}...")
            else:
                logger.warning(f"[RAG SEARCH] NO MATCHES FOUND!")
                logger.warning(f"[RAG SEARCH]   Query: '{query}'")
                logger.warning(f"[RAG SEARCH]   Filter: {query_params.get('filter', 'none')}")
                logger.warning(f"[RAG SEARCH]   Top_k: {top_k}")
            
            # Format results
            chunks = []
            for match in results.matches:
                chunk = {
                    "text": match.metadata.get("text", "") or match.metadata.get("content", ""),
                    "snippet": match.metadata.get("text", "") or match.metadata.get("content", ""),
                    "metadata": {
                        "source_url": match.metadata.get("source_url", "unknown"),
                        "crawled_at": match.metadata.get("crawled_at"),
                        "chunk_id": match.id,
                        "score": match.score,
                    }
                }
                chunks.append(chunk)
            
            logger.debug(f"Returning {len(chunks)} formatted chunks")
            return chunks
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Pinecone search failed: {e}")
            logger.debug(f"Query params: {query_params if 'query_params' in locals() else 'not set'}")
            return []
    
    return pinecone_search

