"""
FastAPI backend for RAG search endpoint.

Provides /rag/search endpoint for querying the Pinecone vector database.
Supports similarity search with configurable embedding providers.

Usage:
    python src/backend/rag_search_api.py
    
    # Or with custom settings:
    PINECONE_API_KEY=your-key \
    EMBEDDING_PROVIDER=hf \
    python src/backend/rag_search_api.py

Environment variables:
    PINECONE_API_KEY (required)
    PINECONE_INDEX_NAME (default: "bigdata-assignment-04")
    PINECONE_NAMESPACE (default: "default")
    EMBEDDING_PROVIDER (choices: "openai", "hf"; default: auto-detect)
    EMBEDDING_MODEL (default: "text-embedding-3-large" for OpenAI, "all-MiniLM-L6-v2" for HF)
    API_HOST (default: 0.0.0.0)
    API_PORT (default: 8000)
    VERBOSE (set to "1" to enable debug logging)
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
import logging
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
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

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

logger.info(f"PINECONE_INDEX_NAME: {os.environ.get('PINECONE_INDEX_NAME', 'bigdata-assignment-04')}")
logger.info(f"EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER or 'auto-detect'}")
logger.info(f"DATA_DIR: {DATA_DIR}")
logger.info(f"Seed file path: {DATA_DIR / 'forbes_ai50_seed.json'}")
logger.info(f"Data dir exists: {DATA_DIR.exists()}")
logger.info(f"Seed file exists: {(DATA_DIR / 'forbes_ai50_seed.json').exists()}")


# ─────────────────────────────────────────────────────────────────────────────
#  Embedding Functions
# ─────────────────────────────────────────────────────────────────────────────
def embed_query_openai(query: str, model: str = "text-embedding-3-large") -> List[float]:
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
        description="Pinecone index name (deprecated, uses PINECONE_INDEX_NAME env var)"
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
    
    id: str  # Pinecone IDs are strings like "abridge_blog_5_5794e918"
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
    context_results: List[ChunkResult] = Field(default_factory=list, description="Top-k context chunks retrieved from Pinecone")
    status: str = "success"
    message: Optional[str] = None


class DashboardStructuredResponse(BaseModel):
    """Response model for structured dashboard generation."""
    
    company_name: str
    company_slug: str
    markdown: str = Field(description="Dashboard markdown content")
    status: str = "success"
    message: Optional[str] = None


class MetricScore(BaseModel):
    """Individual metric score."""
    
    value: Optional[int] = None
    max_value: int
    percentage: Optional[float] = None


class EvaluationMetricsResponse(BaseModel):
    """Response model for evaluation metrics."""
    
    company_name: str
    company_slug: str
    pipeline_type: str  # "structured" or "rag"
    timestamp: str
    
    # Metric scores
    factual_accuracy: Optional[int] = Field(None, ge=0, le=3)
    schema_compliance: Optional[int] = Field(None, ge=0, le=2)
    provenance_quality: Optional[int] = Field(None, ge=0, le=2)
    hallucination_detection: Optional[int] = Field(None, ge=0, le=2)
    readability: Optional[int] = Field(None, ge=0, le=1)
    mrr_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Total score
    total_score: Optional[float] = Field(None, description="Total score out of 14")
    
    # Additional info
    notes: str = ""
    status: str = "success"


class ComparisonResponse(BaseModel):
    """Response model for pipeline comparison."""
    
    company_name: str
    company_slug: str
    structured: EvaluationMetricsResponse
    rag: EvaluationMetricsResponse
    winners: Dict[str, Optional[str]] = Field(
        description="Which pipeline wins for each metric ('structured', 'rag', or 'tie')"
    )
    status: str = "success"


# ─────────────────────────────────────────────────────────────────────────────
#  Pinecone Search Functions
# ─────────────────────────────────────────────────────────────────────────────
def search_pinecone(
    query_embedding: List[float],
    index_name: str = "bigdata-assignment-04",
    top_k: int = 5,
    threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Search Pinecone index for similar vectors.
    
    Args:
        query_embedding: Query vector
        index_name: Pinecone index name
        top_k: Number of results to return
        threshold: Similarity threshold (0-1)
    
    Returns:
        List of results with id, score, and metadata
    """
    if Pinecone is None:
        raise RuntimeError("pinecone-client not installed")

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY not set")
    
    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    
    namespace = os.environ.get("PINECONE_NAMESPACE", "default")
    
    logger.debug(f"Searching Pinecone index '{index_name}' (namespace '{namespace}') with top_k={top_k}")
    
    try:
        search_result = index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )
        
        results = []
        for match in search_result.get("matches", []):
            score = match.get("score", 0)
            # Apply threshold if specified
            if threshold is None or score >= threshold:
                results.append({
                    "id": match.get("id", ""),
                    "score": score,
                    "payload": match.get("metadata", {}),
                })
        
        logger.debug(f"Found {len(results)} results (threshold: {threshold})")
        return results
        
    except Exception as e:
        logger.error(f"Pinecone search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pinecone search failed: {str(e)}"
        )


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
    
    logger.info("Starting RAG Search API with Pinecone...")
    
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
        
        # Test Pinecone connection
        if Pinecone is not None:
            try:
                api_key = os.environ.get("PINECONE_API_KEY")
                if api_key:
                    pc = Pinecone(api_key=api_key)
                    index_name = os.environ.get("PINECONE_INDEX_NAME", "bigdata-assignment-04")
                    index = pc.Index(index_name)
                    stats = index.describe_index_stats()
                    logger.info(f"Connected to Pinecone index '{index_name}': {stats.total_vector_count} vectors")
            except Exception as e:
                logger.warning(f"Could not verify Pinecone connection: {e}")
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
    description="Vector similarity search against Pinecone vector database",
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
    pinecone_connected = False
    
    if Pinecone is not None:
        try:
            api_key = os.environ.get("PINECONE_API_KEY")
            if api_key:
                pc = Pinecone(api_key=api_key)
                index_name = os.environ.get("PINECONE_INDEX_NAME", "bigdata-assignment-04")
                index = pc.Index(index_name)
                stats = index.describe_index_stats()
                pinecone_connected = True
        except Exception:
            pinecone_connected = False
    
    return HealthResponse(
        status="ok" if pinecone_connected else "degraded",
        qdrant_url=os.environ.get("PINECONE_INDEX_NAME", "bigdata-assignment-04"),
        qdrant_connected=pinecone_connected,
    )


@app.post("/rag/search", response_model=SearchResponse)
async def rag_search(request: SearchRequest) -> SearchResponse:
    """
    Search the RAG vector database for similar chunks using Pinecone.
    
    This endpoint:
    1. Embeds the query using the configured embedding provider
    2. Searches Pinecone for similar vectors
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
    
    logger.info(f"Search request: query='{request.query}', top_k={request.top_k}")
    
    try:
        # Embed the query
        logger.debug("Embedding query...")
        query_embedding = embed_fn(request.query)
        logger.debug(f"Query embedded: {len(query_embedding)} dimensions")
        
        # Search Pinecone
        logger.debug("Searching Pinecone...")
        index_name = os.environ.get("PINECONE_INDEX_NAME", "bigdata-assignment-04")
        results = search_pinecone(
            query_embedding=query_embedding,
            index_name=index_name,
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
                    id=chunk_results.__len__(),
                    similarity_score=result["score"],
                    text=text_preview,
                    metadata=payload,
                )
            )
        
        logger.info(f"Returning {len(chunk_results)} results")
        
        return SearchResponse(
            query=request.query,
            collection_name=index_name,
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


# ─────────────────────────────────────────────────────────────────────────────
#  Helper Functions for Flexible Filename Matching
# ─────────────────────────────────────────────────────────────────────────────
def find_payload_file(company_name: str) -> Optional[Path]:
    """
    Find payload file with flexible naming conventions.
    
    Tries multiple variations to handle different naming patterns:
    1. Full slug with hyphens: "coactive-ai.json"
    2. Full slug with underscores: "coactive_ai.json"
    3. Full slug no separators: "coactiveai.json"
    4. First word only: "coactive.json"
    5. Any file in payloads directory matching the first word
    
    Args:
        company_name: Company display name (e.g., "Coactive AI")
    
    Returns:
        Path to found payload file or None
    """
    payloads_dir = Path("data/payloads")
    
    if not payloads_dir.exists():
        logger.debug(f"Payloads directory not found: {payloads_dir}")
        return None
    
    # Generate various slug formats from company name
    base_slug = company_name.lower().replace(" ", "").replace("_", "").replace("-", "")
    first_word = company_name.lower().split()[0]  # Extract first word
    
    # Try different variations in priority order
    variants = [
        company_name.lower().replace(" ", "-").replace("_", "-"),  # coactive-ai
        company_name.lower().replace(" ", "_").replace("-", "_"),  # coactive_ai
        company_name.lower().replace(" ", "").replace("_", "").replace("-", ""),  # coactiveai
        first_word,  # coactive (first word only)
    ]
    
    logger.debug(f"Looking for payload file for '{company_name}'")
    logger.debug(f"  Trying variants: {variants}")
    
    for variant in variants:
        payload_file = payloads_dir / f"{variant}.json"
        if payload_file.exists():
            logger.info(f"✓ Found payload file: {payload_file}")
            return payload_file
    
    # Fallback: scan directory for files that start with the first word
    logger.debug(f"Direct lookup failed, scanning payloads directory for files starting with '{first_word}'...")
    
    try:
        for file in payloads_dir.glob(f"{first_word}*.json"):
            logger.info(f"✓ Found payload file by glob pattern: {file}")
            return file
    except Exception as e:
        logger.debug(f"Error scanning payloads directory: {e}")
    
    logger.debug(f"No payload file found for '{company_name}' after trying: {variants}")
    return None


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
    
    Workflow:
    1. Converts company name to slug format
    2. Checks if structured payload exists at data/payloads/<slug>.json
    3. If payload missing:
       - Runs: python src/rag/ingest_to_pinecone.py --company-slug {slug}
       - Runs: python src/rag/structured_extraction_search.py --company-slug {slug}
       - Verifies payload was created
    4. Generates dashboard from payload
    5. Returns formatted markdown dashboard
    
    Args:
        company_name: Display name of the company (e.g., 'World Labs')
    
    Returns:
        DashboardStructuredResponse with markdown dashboard
    
    Raises:
        HTTPException: 
            - 404: Payload not found or raw data missing
            - 500: Generation or extraction fails
    
    Example:
        POST /dashboard/structured?company_name=World%20Labs
        
        Response:
        {
            "company_name": "World Labs",
            "company_slug": "world-labs",
            "markdown": "# World Labs - Investor Diligence Dashboard\n...",
            "status": "success"
        }
    """
    logger.info(f"Structured dashboard request for: {company_name}")
    
    if generate_dashboard_from_payload is None:
        logger.error("structured_pipeline module not available")
        raise HTTPException(
            status_code=500,
            detail="Structured extraction module not available"
        )
    
    # Convert company name to slug format
    company_slug = company_name.lower().replace(" ", "-").replace("_", "-")
    
    # Try to find the payload file with flexible naming
    payload_path = find_payload_file(company_name)
    
    if payload_path is None:
        # Try alternate directory structures
        raw_data_path = Path(f"data/raw/{company_slug}")
        if not raw_data_path.exists():
            raw_data_path_alt = Path(f"data/raw/{company_slug.replace('-', '_')}")
            if not raw_data_path_alt.exists():
                logger.error(f"Raw data not found for {company_name}")
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"No structured payload and no raw data found for '{company_name}'. "
                        f"Please run the discovery pipeline first: "
                        f"`python src/discover/process_discovered_pages.py`"
                    )
                )
            raw_data_path = raw_data_path_alt
        
        logger.info(f"Payload missing for {company_name}, checking for raw data...")
        logger.info(f"Raw data found, starting extraction pipeline...")
        
        # STEP 1: Run ingestion script
        logger.info(f"STEP 1: Ingesting to Pinecone for {company_slug}...")
        ingest_cmd = [
            sys.executable,
            "src/rag/ingest_to_pinecone.py",
            "--company-slug", company_slug.replace("-", "_")
        ]
        
        try:
            result = subprocess.run(
                ingest_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Ingestion failed: {result.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Ingestion to Pinecone failed: {result.stderr[-500:]}"
                )
            
            logger.info(f"✓ Ingestion completed successfully")
        
        except subprocess.TimeoutExpired:
            logger.error(f"Ingestion timeout for {company_slug}")
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion timeout (exceeded 5 minutes)"
            )
        
        except Exception as e:
            logger.error(f"Ingestion error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed: {str(e)}"
            )
        
        # STEP 2: Run extraction script
        logger.info(f"STEP 2: Extracting structured data for {company_slug}...")
        extraction_cmd = [
            sys.executable,
            "src/rag/structured_extraction_search.py",
            "--company-slug", company_slug.replace("-", "_")
        ]
        
        try:
            result = subprocess.run(
                extraction_cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Extraction failed: {result.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Structured extraction failed: {result.stderr[-500:]}"
                )
            
            logger.info(f"✓ Extraction completed successfully")
        
        except subprocess.TimeoutExpired:
            logger.error(f"Extraction timeout for {company_slug}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction timeout (exceeded 10 minutes)"
            )
        
        except Exception as e:
            logger.error(f"Extraction error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction failed: {str(e)}"
            )
        
        # Try to find the newly created payload file
        payload_path = find_payload_file(company_name)
        
        if payload_path is None:
            logger.error(f"Extraction completed but payload not found for {company_name}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction completed but payload file was not created"
            )
        
        logger.info(f"✓ Payload successfully created at {payload_path}")
    else:
        logger.info(f"✓ Payload already exists for {company_name} at {payload_path}")
    
    try:
        # STEP 3: Generate dashboard from payload
        logger.info(f"STEP 3: Generating dashboard for {company_name}...")
        
        # Initialize LLM client
        llm_client = None
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {e}")
        
        # Generate dashboard from payload
        # Pass the actual found payload path to handle flexible naming
        dashboard_markdown = generate_dashboard_from_payload(
            company_name=company_name,
            company_slug=company_slug,
            llm_client=llm_client,
            llm_model="gpt-4o",
            temperature=0.1,  # Low temperature for deterministic output
            payload_file_path=payload_path  # Pass the found path
        )
        
        logger.info(f"✓ Successfully generated dashboard for {company_name}")
        
        return DashboardStructuredResponse(
            company_name=company_name,
            company_slug=company_slug,
            markdown=dashboard_markdown,
            status="success",
            message=f"Dashboard generated for {company_name}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except Exception as e:
        logger.error(f"Dashboard generation failed: {e}", exc_info=True)
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
    Generate investor-facing dashboard using Pinecone RAG retrieval and LLM generation.
    
    This endpoint:
    1. Converts company name to slug format
    2. Retrieves top-k context from Pinecone index
    3. Calls LLM with dashboard system prompt
    4. Returns formatted markdown with 8 required sections
    
    Args:
        company_name: Display name of the company (e.g., 'World Labs')
    
    Returns:
        DashboardRAGResponse with markdown dashboard
    
    Raises:
        HTTPException: If index not found or generation fails
    
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
        # Initialize Pinecone
        if Pinecone is None:
            raise RuntimeError("pinecone-client not installed")
        
        api_key = os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY not set")
        
        pc = Pinecone(api_key=api_key)
        index_name = os.environ.get("PINECONE_INDEX_NAME", "bigdata-assignment-04")
        
        # Initialize LLM client
        llm_client = None
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_client = OpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {e}")
        
        logger.info(f"Generating dashboard for {company_name} (slug: {company_slug}) using Pinecone")
        
        # Generate dashboard and retrieve context using Pinecone
        dashboard_markdown, search_results = generate_dashboard_with_retrieval(
            company_name=company_name,
            company_slug=company_slug,
            pinecone_index=pc.Index(index_name),
            llm_client=llm_client,
            llm_model="gpt-4o",
            top_k=10,
            temperature=0.1  # Low temperature for deterministic output
        )
        
        # Convert search results to ChunkResult format
        context_results = []
        for result in search_results:
            chunk_result = ChunkResult(
                id=result.get("id", "unknown"),  # Use actual Pinecone ID
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


@app.get("/evals/{company_slug}", response_model=ComparisonResponse)
async def get_evaluation_metrics(
    company_slug: str
) -> ComparisonResponse:
    """
    Get cached evaluation metrics for a company.
    
    Returns comparison of Structured vs RAG pipeline metrics.
    
    Args:
        company_slug: Company slug (e.g., 'world-labs')
    
    Returns:
        ComparisonResponse with metrics for both pipelines
    
    Raises:
        HTTPException: 404 if no evaluation results cached
    
    Example:
        GET /evals/world-labs
        
        Response:
        {
            "company_name": "World Labs",
            "company_slug": "world-labs",
            "structured": {
                "pipeline_type": "structured",
                "factual_accuracy": 3,
                "schema_compliance": 2,
                "provenance_quality": 2,
                "hallucination_detection": 2,
                "readability": 1,
                "mrr_score": 0.95,
                "total_score": 13.9
            },
            "rag": {
                "pipeline_type": "rag",
                "factual_accuracy": 2,
                "schema_compliance": 2,
                "provenance_quality": 1,
                "hallucination_detection": 1,
                "readability": 1,
                "mrr_score": 0.75,
                "total_score": 10.5
            },
            "winners": {
                "factual_accuracy": "structured",
                "schema_compliance": "tie",
                "provenance_quality": "structured",
                "hallucination_detection": "structured",
                "readability": "tie",
                "mrr_score": "structured"
            }
        }
    """
    logger.info(f"Evaluation metrics request for: {company_slug}")
    
    eval_dir = Path("data/eval")
    
    # Try both possible result filenames
    results_path = eval_dir / "results_llm_eval.json"
    if not results_path.exists():
        results_path = eval_dir / "results.json"
    
    # Check if results cache exists
    if not results_path.exists():
        logger.warning(f"Evaluation results not found. Checked: results_llm_eval.json and results.json")
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation results cached. Run 'python src/evals/result_evaluator.py --company {company_slug}' to generate."
        )
    
    try:
        # Load cached results
        with open(results_path) as f:
            all_results = json.load(f)
        
        if company_slug not in all_results:
            logger.warning(f"No results for company: {company_slug}")
            raise HTTPException(
                status_code=404,
                detail=f"No evaluation results for {company_slug}. Run evaluation to generate."
            )
        
        company_results = all_results[company_slug]
        
        # Load ground truth for company name
        ground_truth_path = eval_dir / "ground_truth.json"
        company_name = company_slug
        
        if ground_truth_path.exists():
            with open(ground_truth_path) as f:
                ground_truth = json.load(f)
                if company_slug in ground_truth:
                    company_name = ground_truth[company_slug].get("company_name", company_slug)
        
        # Construct metrics responses
        structured_data = company_results.get("structured", {})
        rag_data = company_results.get("rag", {})
        
        structured_metrics = EvaluationMetricsResponse(
            company_name=company_name,
            company_slug=company_slug,
            pipeline_type="structured",
            timestamp=structured_data.get("timestamp", ""),
            factual_accuracy=structured_data.get("factual_accuracy"),
            schema_compliance=structured_data.get("schema_compliance"),
            provenance_quality=structured_data.get("provenance_quality"),
            hallucination_detection=structured_data.get("hallucination_detection"),
            readability=structured_data.get("readability"),
            mrr_score=structured_data.get("mrr_score"),
            total_score=structured_data.get("total_score"),
            notes=structured_data.get("notes", "")
        )
        
        rag_metrics = EvaluationMetricsResponse(
            company_name=company_name,
            company_slug=company_slug,
            pipeline_type="rag",
            timestamp=rag_data.get("timestamp", ""),
            factual_accuracy=rag_data.get("factual_accuracy"),
            schema_compliance=rag_data.get("schema_compliance"),
            provenance_quality=rag_data.get("provenance_quality"),
            hallucination_detection=rag_data.get("hallucination_detection"),
            readability=rag_data.get("readability"),
            mrr_score=rag_data.get("mrr_score"),
            total_score=rag_data.get("total_score"),
            notes=rag_data.get("notes", "")
        )
        
        # Calculate winners for individual metrics
        winners = {}
        for metric in ["factual_accuracy", "schema_compliance", "provenance_quality",
                      "hallucination_detection", "readability", "mrr_score"]:
            struct_val = getattr(structured_metrics, metric, None)
            rag_val = getattr(rag_metrics, metric, None)
            
            if struct_val is not None and rag_val is not None:
                if struct_val > rag_val:
                    winners[metric] = "structured"
                elif rag_val > struct_val:
                    winners[metric] = "rag"
                else:
                    winners[metric] = "tie"
        
        # Calculate winner for total_score
        struct_total = structured_metrics.total_score
        rag_total = rag_metrics.total_score
        
        if struct_total is not None and rag_total is not None:
            if struct_total > rag_total:
                winners["total_score"] = "structured"
            elif rag_total > struct_total:
                winners["total_score"] = "rag"
            else:
                winners["total_score"] = "tie"
        
        logger.info(f"✓ Returning evaluation metrics for {company_slug}")
        logger.debug(f"  Winners: {winners}")
        
        return ComparisonResponse(
            company_name=company_name,
            company_slug=company_slug,
            structured=structured_metrics,
            rag=rag_metrics,
            winners=winners,
            status="success"
        )
        
    except FileNotFoundError as e:
        logger.error(f"Results file not found: {e}")
        raise HTTPException(
            status_code=404,
            detail="Evaluation results not available"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in results file: {e}")
        raise HTTPException(
            status_code=500,
            detail="Invalid evaluation results format"
        )
    except Exception as e:
        logger.error(f"Error retrieving evaluation metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving evaluation metrics: {str(e)}"
        )


@app.get("/evals", response_model=Dict[str, Any])
async def list_evaluations() -> Dict[str, Any]:
    """
    List all available evaluation results.
    
    Returns summary of cached evaluations.
    
    Returns:
        Dictionary with company slugs and available pipelines
    
    Example:
        GET /evals
        
        Response:
        {
            "total_companies": 3,
            "companies": [
                {
                    "slug": "world-labs",
                    "name": "World Labs",
                    "pipelines": ["structured", "rag"]
                },
                ...
            ]
        }
    """
    logger.info("Listing evaluation results")
    
    eval_dir = Path("data/eval")
    
    # Try both possible result filenames
    results_path = eval_dir / "results_llm_eval.json"
    if not results_path.exists():
        results_path = eval_dir / "results.json"
    
    ground_truth_path = eval_dir / "ground_truth.json"
    
    if not results_path.exists():
        logger.warning("No evaluation results cached")
        raise HTTPException(
            status_code=404,
            detail="No evaluation results cached yet"
        )
    
    try:
        # Load results
        with open(results_path) as f:
            results = json.load(f)
        
        # Load ground truth for company names
        ground_truth = {}
        if ground_truth_path.exists():
            with open(ground_truth_path) as f:
                ground_truth = json.load(f)
        
        # Build response
        companies = []
        for company_slug in sorted(results.keys()):
            company_name = company_slug
            if company_slug in ground_truth:
                company_name = ground_truth[company_slug].get("company_name", company_slug)
            
            pipelines = list(results[company_slug].keys())
            
            companies.append({
                "slug": company_slug,
                "name": company_name,
                "pipelines": pipelines
            })
        
        logger.info(f"✓ Found {len(companies)} evaluated companies")
        
        return {
            "total_companies": len(companies),
            "companies": companies,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error listing evaluations: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error listing evaluations: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    
    index_name = os.environ.get("PINECONE_INDEX_NAME", "bigdata-assignment-04")
    logger.info(f"Starting RAG Search API on {API_HOST}:{API_PORT}")
    logger.info(f"Pinecone Index: {index_name}")
    logger.info(f"API docs: http://{API_HOST}:{API_PORT}/docs")
    
    uvicorn.run(
        "rag_search_api:app",
        host=API_HOST,
        port=API_PORT,
        reload=os.environ.get("DEBUG", "0") == "1",
        log_level="debug" if log_level == logging.DEBUG else "info",
    )
