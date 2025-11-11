"""
FastAPI backend for RAG search endpoint.

Provides /rag/search endpoint for querying the Qdrant vector database.
Supports similarity search with configurable embedding providers.

Usage:
    python src/backend/rag_search_api.py
    
    # Or with custom settings:
    QDRANT_URL=http://localhost:6333 \
    EMBEDDING_PROVIDER=hf \
    python src/backend/rag_search_api.py

Environment variables:
    QDRANT_URL (default: http://localhost:6333)
    QDRANT_API_KEY (default: "")
    EMBEDDING_PROVIDER (choices: "openai", "hf"; default: auto-detect)
    EMBEDDING_MODEL (default: "text-embedding-3-small" for OpenAI, "all-MiniLM-L6-v2" for HF)
    API_HOST (default: 0.0.0.0)
    API_PORT (default: 8000)
    VERBOSE (set to "1" to enable debug logging)
"""

from __future__ import annotations

import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

# Import RAG extraction utilities
try:
    import sys
    from pathlib import Path as PathlibPath
    sys.path.insert(0, str(PathlibPath(__file__).resolve().parent.parent / "rag"))
    from rag_pipeline import generate_dashboard_with_retrieval
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import rag_pipeline: {e}")
    generate_dashboard_with_retrieval = None

# Import Structured pipeline utilities
try:
    import sys
    from pathlib import Path as PathlibPath
    sys.path.insert(0, str(PathlibPath(__file__).resolve().parent.parent / "structured"))
    from structured_pipeline import generate_dashboard_from_payload
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import structured_pipeline: {e}")
    generate_dashboard_from_payload = None


# ─────────────────────────────────────────────────────────────────────────────
#  Configuration & Logging
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
#  Configuration & Logging
# ─────────────────────────────────────────────────────────────────────────────
log_level = logging.INFO
if os.environ.get("VERBOSE", "0") in ("1", "true", "True"):
    log_level = logging.DEBUG

# Setup logging with both console and file handlers
log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.flush()  # Ensure immediate flush

# File handler
log_dir = Path("data/logs")
log_dir.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(log_dir / "rag_search_api.log")
file_handler.setFormatter(log_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(log_level)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

# Configuration from environment
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", None)  # None = auto-detect
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", None)  # None = use defaults
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Data directory - go up 2 levels from src/backend/ to reach data/
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

logger.info(f"QDRANT_URL: {QDRANT_URL}")
logger.info(f"EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER or 'auto-detect'}")
logger.info(f"DATA_DIR: {DATA_DIR}")
logger.info(f"Seed file path: {DATA_DIR / 'forbes_ai50_seed.json'}")
logger.info(f"Data dir exists: {DATA_DIR.exists()}")
logger.info(f"Seed file exists: {(DATA_DIR / 'forbes_ai50_seed.json').exists()}")


# ─────────────────────────────────────────────────────────────────────────────
#  Embedding Functions
# ─────────────────────────────────────────────────────────────────────────────
def embed_query_openai(query: str, model: str = "text-embedding-3-small") -> List[float]:
    """Embed a query using OpenAI API."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set for OpenAI embeddings")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(input=[query], model=model)
    return response.data[0].embedding


def embed_query_hf(query: str, model: str = "all-MiniLM-L6-v2") -> List[float]:
    """Embed a query using HuggingFace sentence-transformers."""
    from sentence_transformers import SentenceTransformer

    model_instance = SentenceTransformer(model)
    embeddings = model_instance.encode([query], show_progress_bar=False)
    return embeddings[0].tolist()


def choose_embedding_provider(
    prefer_openai: bool = True, hf_model: str = "all-MiniLM-L6-v2"
) -> tuple[callable, str, str]:
    """
    Choose embedding provider and return (embed_fn, provider_name, model_name).
    
    Returns:
        Tuple of (embed_function, provider_name, model_name)
    """
    if prefer_openai and os.environ.get("OPENAI_API_KEY"):
        try:
            import openai  # Quick check
            model = EMBEDDING_MODEL or "text-embedding-3-small"
            return embed_query_openai, "openai", model
        except Exception as e:
            logger.warning(f"OpenAI import failed: {e}, will try HuggingFace")

    try:
        import sentence_transformers
        model = EMBEDDING_MODEL or hf_model
        return (lambda q: embed_query_hf(q, model=model)), f"hf", model
    except Exception:
        raise RuntimeError(
            "No embedding provider available. "
            "Install sentence-transformers or set OPENAI_API_KEY."
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    """Request model for RAG search."""
    
    query: str = Field(..., min_length=1, description="Search query")
    collection_name: str = Field(
        default="rag_chunks",
        description="Qdrant collection to search"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of top results to return"
    )
    threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Similarity score threshold (0-1). None = no threshold"
    )


class ChunkResult(BaseModel):
    """A single search result chunk."""
    
    id: int
    similarity_score: float
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response model for RAG search."""
    
    query: str
    collection_name: str
    results: List[ChunkResult]
    total_results: int
    provider: str
    model: str


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    qdrant_url: str
    qdrant_connected: bool


class StructuredDataResponse(BaseModel):
    """Response model for structured company data."""
    
    company_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    status: str = "success"
    message: Optional[str] = None


class CompanyInfo(BaseModel):
    """Individual company info from seed data."""
    
    company_name: str
    website: str
    linkedin: str
    hq_city: str
    hq_country: str
    category: Optional[str] = None
    url_verified: bool
    source: str


class CompaniesListResponse(BaseModel):
    """Response model for companies list."""
    
    total: int
    companies: List[CompanyInfo]


class DashboardRAGResponse(BaseModel):
    """Response model for RAG dashboard generation."""
    
    company_name: str
    company_slug: str
    markdown: str = Field(description="Dashboard markdown content")
    context_results: List[ChunkResult] = Field(default_factory=list, description="Top-k context chunks retrieved from Qdrant")
    status: str = "success"
    message: Optional[str] = None


class DashboardStructuredResponse(BaseModel):
    """Response model for structured dashboard generation."""
    
    company_name: str
    company_slug: str
    markdown: str = Field(description="Dashboard markdown content")
    status: str = "success"
    message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
#  Qdrant Search Functions
# ─────────────────────────────────────────────────────────────────────────────
def search_qdrant(
    query_embedding: List[float],
    collection_name: str,
    top_k: int = 5,
    threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Search Qdrant collection for similar vectors.
    
    Args:
        query_embedding: Query vector
        collection_name: Qdrant collection name
        top_k: Number of results to return
        threshold: Similarity threshold (0-1)
    
    Returns:
        List of results with id, score, and payload
    """
    if QdrantClient is None:
        raise RuntimeError("qdrant-client not installed")

    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    
    # Suppress warnings about client version mismatch
    logger.debug(f"Searching collection '{collection_name}' with top_k={top_k}")
    
    try:
        search_result = client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=threshold,
        )
        
        results = []
        for point in search_result:
            results.append({
                "id": point.id,
                "score": point.score,
                "payload": point.payload or {},
            })
        
        logger.debug(f"Found {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Qdrant search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Qdrant search failed: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  FastAPI Application Lifespan
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    global embed_fn, provider_name, model_name
    
    logger.info("Starting RAG Search API...")
    
    try:
        # Determine provider preference
        prefer_openai = True
        if EMBEDDING_PROVIDER == "hf":
            prefer_openai = False
        elif EMBEDDING_PROVIDER == "openai":
            prefer_openai = True
        
        embed_fn, provider_name, model_name = choose_embedding_provider(
            prefer_openai=prefer_openai,
            hf_model="all-MiniLM-L6-v2"
        )
        
        logger.info(f"Using embedding provider: {provider_name} ({model_name})")
        
        # Test Qdrant connection
        if QdrantClient is not None:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
            try:
                info = client.get_collection("rag_chunks")
                logger.info(f"Connected to Qdrant collection 'rag_chunks': {info.points_count} points")
            except Exception as e:
                logger.warning(f"Could not verify Qdrant collection: {e}")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down RAG Search API...")


# ─────────────────────────────────────────────────────────────────────────────
#  FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RAG Search API",
    description="Vector similarity search against Qdrant database",
    version="1.0.0",
    lifespan=lifespan,
)

# Initialize embedding provider at module level
embed_fn = None
provider_name = None
model_name = None


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    qdrant_connected = False
    
    if QdrantClient is not None:
        try:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
            client.get_collection("qdrant")  # Try to get collections
            qdrant_connected = True
        except Exception:
            qdrant_connected = False
    
    return HealthResponse(
        status="ok",
        qdrant_url=QDRANT_URL,
        qdrant_connected=qdrant_connected,
    )


@app.post("/rag/search", response_model=SearchResponse)
async def rag_search(request: SearchRequest) -> SearchResponse:
    """
    Search the RAG vector database for similar chunks.
    
    This endpoint:
    1. Embeds the query using the configured embedding provider
    2. Searches Qdrant for similar vectors
    3. Returns top-k chunks with metadata
    
    Query examples:
    - "funding and investment" - retrieves chunks about company funding
    - "leadership team" - retrieves chunks about company leaders
    - "what is spatial intelligence?" - retrieves relevant topic chunks
    - "careers and job opportunities" - retrieves job-related chunks
    
    Args:
        request: SearchRequest with query, collection_name, top_k, threshold
    
    Returns:
        SearchResponse with results
    
    Raises:
        HTTPException: If embedding or search fails
    """
    if embed_fn is None:
        raise HTTPException(
            status_code=500,
            detail="Embedding provider not initialized"
        )
    
    logger.info(f"Search request: query='{request.query}', collection='{request.collection_name}', top_k={request.top_k}")
    
    try:
        # Embed the query
        logger.debug("Embedding query...")
        query_embedding = embed_fn(request.query)
        logger.debug(f"Query embedded: {len(query_embedding)} dimensions")
        
        # Search Qdrant
        logger.debug("Searching Qdrant...")
        results = search_qdrant(
            query_embedding=query_embedding,
            collection_name=request.collection_name,
            top_k=request.top_k,
            threshold=request.threshold,
        )
        
        # Convert results to response model
        chunk_results = []
        for result in results:
            payload = result.get("payload", {})
            chunk_text = payload.get("text", "")
            
            # Extract just the first 500 chars for preview (full text available in metadata)
            text_preview = chunk_text[:500] if len(chunk_text) > 500 else chunk_text
            
            chunk_results.append(
                ChunkResult(
                    id=result["id"],
                    similarity_score=result["score"],
                    text=text_preview,
                    metadata=payload,
                )
            )
        
        logger.info(f"Returning {len(chunk_results)} results")
        
        return SearchResponse(
            query=request.query,
            collection_name=request.collection_name,
            results=chunk_results,
            total_results=len(chunk_results),
            provider=provider_name,
            model=model_name,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "RAG Search API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "search": "/rag/search",
            "companies": "/companies",
            "dashboard": "/dashboard/structured",
            "docs": "/docs",
            "redoc": "/redoc",
        },
        "provider": provider_name,
        "model": model_name,
    }


@app.get("/companies", response_model=CompaniesListResponse)
async def list_companies() -> CompaniesListResponse:
    """
    Get the list of Forbes AI50 seed companies.
    
    Returns:
        CompaniesListResponse with all companies from the seed data
    
    Example:
        GET /companies
        
        Response:
        {
            "total": 50,
            "companies": [
                {
                    "company_name": "World Labs",
                    "website": "https://worldlabs.ai/",
                    "linkedin": "https://www.linkedin.com/company/world-labs",
                    "hq_city": "San Francisco",
                    "hq_country": "United States",
                    "category": null,
                    "url_verified": true,
                    "source": "auto_search"
                },
                ...
            ]
        }
    """
    logger.info("Companies list request")
    
    seed_path = DATA_DIR / "forbes_ai50_seed.json"
    
    if not seed_path.exists():
        logger.warning(f"Companies seed file not found: {seed_path}")
        raise HTTPException(
            status_code=404,
            detail=f"Companies seed file not found: {seed_path}"
        )
    
    try:
        seed_data = json.loads(seed_path.read_text())
        
        # Validate and parse companies
        companies = [CompanyInfo(**company) for company in seed_data]
        
        logger.info(f"Successfully loaded {len(companies)} companies")
        
        return CompaniesListResponse(
            total=len(companies),
            companies=companies
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {seed_path}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON format in seed file: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"Invalid company data format: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid company data format: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error loading companies: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error loading companies: {str(e)}"
        )




@app.post("/dashboard/structured", response_model=DashboardStructuredResponse)
async def generate_structured_dashboard(
    company_name: str = Query(
        ...,
        min_length=1,
        description="Company name (e.g., 'World Labs', 'Anthropic')"
    )
) -> DashboardStructuredResponse:
    """
    Generate investor-facing dashboard from structured payload JSON.
    
    This endpoint:
    1. Converts company name to slug format
    2. Loads structured payload from data/payloads/<slug>.json
    3. Calls LLM with dashboard system prompt
    4. Returns formatted markdown dashboard
    
    Args:
        company_name: Display name of the company (e.g., 'World Labs')
    
    Returns:
        DashboardStructuredResponse with markdown dashboard
    
    Raises:
        HTTPException: If payload not found or generation fails
    
    Example:
        POST /dashboard/structured?company_name=World%20Labs
        
        Response:
        {
            "company_name": "World Labs",
            "company_slug": "world-labs",
            "markdown": "# World Labs - Investor Diligence Dashboard\n\n## Company Overview\n...",
            "status": "success"
        }
    """
    logger.info(f"Structured dashboard request for company: {company_name}")
    
    if generate_dashboard_from_payload is None:
        logger.error("structured_pipeline module not available")
        raise HTTPException(
            status_code=500,
            detail="Structured extraction module not available"
        )
    
    # Convert company name to slug format
    company_slug = company_name.lower().replace(" ", "-").replace("_", "-")
    
    try:
        # Initialize LLM client
        llm_client = None
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {e}")
        
        logger.info(f"Generating structured dashboard for {company_name} (slug: {company_slug})")
        
        # Generate dashboard from payload with deterministic temperature
        dashboard_markdown = generate_dashboard_from_payload(
            company_name=company_name,
            company_slug=company_slug,
            llm_client=llm_client,
            llm_model="gpt-4o",
            temperature=0.1  # Low temperature for deterministic output
        )
        
        logger.info(f"Successfully generated structured dashboard for {company_name}")
        
        return DashboardStructuredResponse(
            company_name=company_name,
            company_slug=company_slug,
            markdown=dashboard_markdown,
            status="success",
            message=f"Structured dashboard generated successfully for {company_name}"
        )
        
    except FileNotFoundError as e:
        logger.warning(f"Payload file not found for {company_name}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"No structured payload found for company '{company_name}'. "
                   f"Please run the structured extraction pipeline first."
        )
    except Exception as e:
        logger.error(f"Structured dashboard generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard generation failed: {str(e)}"
        )


@app.post("/dashboard/rag", response_model=DashboardRAGResponse)
async def generate_rag_dashboard(
    company_name: str = Query(
        ...,
        min_length=1,
        description="Company name (e.g., 'World Labs', 'Anthropic')"
    )
) -> DashboardRAGResponse:
    """
    Generate investor-facing dashboard using RAG retrieval and LLM generation.
    
    This endpoint:
    1. Converts company name to slug format
    2. Retrieves top-k context from Qdrant collection
    3. Calls LLM with dashboard system prompt
    4. Returns formatted markdown with 8 required sections
    
    Args:
        company_name: Display name of the company (e.g., 'World Labs')
    
    Returns:
        DashboardRAGResponse with markdown dashboard
    
    Raises:
        HTTPException: If collection not found or generation fails
    
    Example:
        POST /dashboard/rag?company_name=World%20Labs
        
        Response:
        {
            "company_name": "World Labs",
            "company_slug": "world-labs",
            "markdown": "# World Labs - Investor Diligence Dashboard\n\n## Company Overview\n...",
            "status": "success"
        }
    """
    logger.info(f"Dashboard RAG request for company: {company_name}")
    
    if generate_dashboard_with_retrieval is None:
        logger.error("rag_pipeline module not available")
        raise HTTPException(
            status_code=500,
            detail="RAG extraction module not available"
        )
    
    # Convert company name to slug format
    company_slug = company_name.lower().replace(" ", "-").replace("_", "-")
    
    try:
        # Initialize Qdrant client
        if QdrantClient is None:
            raise RuntimeError("qdrant-client not installed")
        
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None, check_compatibility=False)
        
        # Initialize LLM client
        llm_client = None
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {e}")
        
        logger.info(f"Generating dashboard for {company_name} (slug: {company_slug})")
        
        # Generate dashboard and retrieve context
        dashboard_markdown, search_results = generate_dashboard_with_retrieval(
            company_name=company_name,
            company_slug=company_slug,
            qdrant_client=client,
            llm_client=llm_client,
            llm_model="gpt-4o",
            top_k=10,
            temperature=0.1  # Low temperature for deterministic output
        )
        
        # Convert search results to ChunkResult format
        context_results = []
        for result in search_results:
            chunk_result = ChunkResult(
                id=context_results.__len__(),
                similarity_score=result.get("similarity_score", 0.0),
                text=result.get("text", ""),
                metadata=result.get("metadata", {})
            )
            context_results.append(chunk_result)
        
        logger.info(f"Successfully generated dashboard for {company_name} with {len(context_results)} context results")
        
        return DashboardRAGResponse(
            company_name=company_name,
            company_slug=company_slug,
            markdown=dashboard_markdown,
            context_results=context_results,
            status="success",
            message=f"Dashboard generated successfully for {company_name}"
        )
        
    except Exception as e:
        logger.error(f"Dashboard generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard generation failed: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting RAG Search API on {API_HOST}:{API_PORT}")
    logger.info(f"Qdrant URL: {QDRANT_URL}")
    logger.info(f"API docs: http://{API_HOST}:{API_PORT}/docs")
    
    uvicorn.run(
        "rag_search_api:app",
        host=API_HOST,
        port=API_PORT,
        reload=os.environ.get("DEBUG", "0") == "1",
        log_level="debug" if log_level == logging.DEBUG else "info",
    )
