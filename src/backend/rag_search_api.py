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
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
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


# ===========================
# HITL Response Models
# ===========================

class ApprovalRequestModel(BaseModel):
    """Model for approval request."""
    approval_id: str
    company_name: str
    approval_type: str
    field_name: str
    extracted_value: Any
    confidence: float
    sources: List[str]
    reasoning: str
    metadata: Dict[str, Any]
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    reviewer_decision: Optional[str] = None
    approved_value: Any = None


class ApprovalActionRequest(BaseModel):
    """Request model for approval/rejection."""
    approved_value: Optional[Any] = None
    reviewer_decision: Optional[str] = None


class ApprovalStatsResponse(BaseModel):
    """Response model for approval queue stats."""
    total: int
    pending: int
    approved: int
    modified: int
    rejected: int
    by_type: Dict[str, int]


class HITLSettingsRequest(BaseModel):
    """Request model for HITL settings."""
    enabled: bool = False
    high_risk_fields: bool = True
    low_confidence: bool = True
    conflicting_info: bool = False
    entity_batch: bool = False
    pre_save: bool = False


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
            top_k=30,
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
#  HITL (Human-in-the-Loop) Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/hitl/approvals/pending", response_model=List[ApprovalRequestModel])
async def get_pending_approvals(
    company_name: Optional[str] = Query(None, description="Filter by company name")
):
    """
    Get all pending approval requests.
    
    Args:
        company_name: Optional filter by company
    
    Returns:
        List of pending approvals
    """
    try:
        # Import here to avoid circular dependencies
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        
        from tavily_agent.approval_queue import get_approval_queue
        
        queue = get_approval_queue()
        pending = queue.get_pending_approvals(company_name=company_name)
        
        return [ApprovalRequestModel(**approval.to_dict()) for approval in pending]
    
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting pending approvals: {str(e)}"
        )


@app.post("/hitl/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    action: ApprovalActionRequest,
    background_tasks: BackgroundTasks
):
    """
    Approve an approval request and automatically resume the workflow.
    
    Args:
        approval_id: ID of approval to approve
        action: Approval action details
        background_tasks: FastAPI background tasks for workflow resumption
    
    Returns:
        Success message
    """
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        
        from tavily_agent.approval_queue import get_approval_queue
        
        queue = get_approval_queue()
        
        # Get the approval to find the company name
        approval = queue.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        
        # Approve the request
        success = queue.approve(
            approval_id=approval_id,
            approved_value=action.approved_value,
            reviewer_decision=action.reviewer_decision
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Failed to approve")
        
        logger.info(f"✅ [API] Approved: {approval_id} for {approval.company_name}")
        
        # Find the task_id for this company and resume workflow
        task_id = None
        for tid, task in enrichment_tasks.items():
            if (task["company_name"] == approval.company_name and 
                task["status"] == "waiting_approval"):
                task_id = tid
                break
        
        if task_id:
            logger.info(f"▶️  [API] Auto-resuming workflow for task {task_id}")
            background_tasks.add_task(resume_enrichment_from_checkpoint, approval.company_name, task_id)
            
            return {
                "status": "success",
                "message": f"Approval {approval_id} approved and workflow resumed",
                "approval_id": approval_id,
                "task_id": task_id,
                "auto_resumed": True
            }
        else:
            logger.warning(f"⚠️  [API] No waiting task found for {approval.company_name}")
            return {
                "status": "success",
                "message": f"Approval {approval_id} approved (no active workflow to resume)",
                "approval_id": approval_id,
                "auto_resumed": False
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error approving request: {str(e)}"
        )


@app.post("/hitl/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    action: ApprovalActionRequest,
    background_tasks: BackgroundTasks
):
    """
    Reject an approval request and automatically resume the workflow.
    
    Args:
        approval_id: ID of approval to reject
        action: Rejection action details
        background_tasks: FastAPI background tasks for workflow resumption
    
    Returns:
        Success message
    """
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        
        from tavily_agent.approval_queue import get_approval_queue
        
        queue = get_approval_queue()
        
        # Get the approval to find the company name
        approval = queue.get_approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        
        # Reject the request
        success = queue.reject(
            approval_id=approval_id,
            reviewer_decision=action.reviewer_decision
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Failed to reject")
        
        logger.info(f"❌ [API] Rejected: {approval_id} for {approval.company_name}")
        
        # Find the task_id for this company and resume workflow
        task_id = None
        for tid, task in enrichment_tasks.items():
            if (task["company_name"] == approval.company_name and 
                task["status"] == "waiting_approval"):
                task_id = tid
                break
        
        if task_id:
            logger.info(f"▶️  [API] Auto-resuming workflow for task {task_id}")
            background_tasks.add_task(resume_enrichment_from_checkpoint, approval.company_name, task_id)
            
            return {
                "status": "success",
                "message": f"Approval {approval_id} rejected and workflow resumed",
                "approval_id": approval_id,
                "task_id": task_id,
                "auto_resumed": True
            }
        else:
            logger.warning(f"⚠️  [API] No waiting task found for {approval.company_name}")
            return {
                "status": "success",
                "message": f"Approval {approval_id} rejected (no active workflow to resume)",
                "approval_id": approval_id,
                "auto_resumed": False
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error rejecting request: {str(e)}"
        )


@app.get("/hitl/stats", response_model=ApprovalStatsResponse)
async def get_approval_stats():
    """Get approval queue statistics."""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        
        from tavily_agent.approval_queue import get_approval_queue
        
        queue = get_approval_queue()
        stats = queue.get_stats()
        
        return ApprovalStatsResponse(**stats)
    
    except Exception as e:
        logger.error(f"Error getting approval stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting approval stats: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Agentic RAG Enrichment Endpoints (HITL-enabled with checkpointing)
# ─────────────────────────────────────────────────────────────────────────────

# Global task tracking
enrichment_tasks: Dict[str, Dict[str, Any]] = {}

class EnrichmentTaskResponse(BaseModel):
    """Response for enrichment task creation."""
    task_id: str
    company_name: str
    status: str
    message: str

class EnrichmentStatusResponse(BaseModel):
    """Response for enrichment status check."""
    task_id: str
    company_name: str
    status: str  # started, running, waiting_approval, completed, failed
    message: Optional[str] = None
    approval_id: Optional[str] = None
    field_name: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ResumeWorkflowRequest(BaseModel):
    """Request to resume workflow after approval."""
    approval_id: str

async def resume_enrichment_from_checkpoint(company_name: str, task_id: str):
    """
    Resume enrichment workflow from checkpoint after HITL approval/rejection.
    Does NOT restart the workflow - continues from the saved checkpoint.
    """
    try:
        logger.info(f"🔄 [RESUME] Resuming task {task_id} for {company_name} from checkpoint")
        enrichment_tasks[task_id]["status"] = "running"
        enrichment_tasks[task_id]["message"] = "Resuming from checkpoint..."
        
        # Import graph builder
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        from tavily_agent.graph import build_enrichment_graph
        from tavily_agent.file_io_manager import FileIOManager
        from tavily_agent.graph import PayloadEnrichmentState
        
        # Build graph with same checkpointer
        logger.info(f"🔧 [RESUME] Rebuilding graph with checkpointing for {company_name}")
        graph = build_enrichment_graph(with_checkpointing=True)
        
        # Resume from checkpoint using config with same thread_id
        config = {
            "configurable": {"thread_id": task_id},
            "recursion_limit": 100
        }
        
        logger.info(f"▶️  [RESUME] Continuing workflow from checkpoint with thread_id={task_id}")
        
        try:
            # Get the current state from checkpoint first
            state_snapshot = graph.get_state(config)
            if not state_snapshot or not state_snapshot.values:
                logger.error(f"❌ [RESUME] No checkpoint found for thread_id={task_id}")
                enrichment_tasks[task_id]["status"] = "failed"
                enrichment_tasks[task_id]["message"] = "No checkpoint found to resume from"
                return
            
            logger.info(f"✅ [RESUME] Loaded checkpoint state, resuming workflow...")
            
            # Resume by invoking with None - graph will continue from checkpoint
            # Using stream to handle interrupt properly
            final_state = None
            async for event in graph.astream(None, config=config, stream_mode="values"):
                # In "values" mode, we get the full state after each node
                final_state = event
                logger.debug(f"[RESUME] State update received")
            
            if final_state is None:
                logger.warning(f"⚠️  [RESUME] No state received from stream")
                return
            
            # Convert to state object
            final_state_obj = PayloadEnrichmentState(**final_state)
            
            # Check if we hit another interrupt
            if final_state_obj.pending_approval_id:
                logger.info(f"⏸️  [RESUME] Workflow paused again - waiting for approval: {final_state_obj.pending_approval_id}")
                enrichment_tasks[task_id]["status"] = "waiting_approval"
                enrichment_tasks[task_id]["approval_id"] = final_state_obj.pending_approval_id
                enrichment_tasks[task_id]["message"] = "Waiting for human approval"
                
                # Get approval details
                from tavily_agent.approval_queue import get_approval_queue
                queue = get_approval_queue()
                approval = queue.get_approval(final_state_obj.pending_approval_id)
                if approval:
                    enrichment_tasks[task_id]["field_name"] = approval.field_name
                
                return
            
            # Workflow completed
            logger.info(f"✅ [RESUME] Workflow completed for {company_name}")
            
            # Save result
            file_io = FileIOManager()
            await file_io.save_payload(company_name, final_state_obj.current_payload)
            
            enrichment_tasks[task_id]["status"] = "completed"
            enrichment_tasks[task_id]["message"] = "Enrichment completed successfully"
            enrichment_tasks[task_id]["result"] = {
                "fields_updated": len(final_state_obj.extracted_values),
                "iterations": final_state_obj.iteration
            }
            
        except Exception as workflow_error:
            # Check if this is an interrupt (normal for HITL)
            if "interrupt" in str(workflow_error).lower():
                logger.info(f"⏸️  [RESUME] Workflow interrupted for approval")
                enrichment_tasks[task_id]["status"] = "waiting_approval"
                enrichment_tasks[task_id]["message"] = "Waiting for human approval"
            else:
                raise
        
    except Exception as e:
        logger.error(f"❌ [RESUME] Error resuming workflow: {e}", exc_info=True)
        enrichment_tasks[task_id]["status"] = "failed"
        enrichment_tasks[task_id]["message"] = f"Resume failed: {str(e)}"
        enrichment_tasks[task_id]["error"] = str(e)


async def run_enrichment_with_checkpointing(company_name: str, task_id: str):
    """
    Run enrichment workflow with checkpointing enabled.
    This allows the workflow to pause when HITL approval is needed.
    """
    try:
        logger.info(f"🚀 [ENRICHMENT] Starting task {task_id} for {company_name}")
        enrichment_tasks[task_id]["status"] = "running"
        enrichment_tasks[task_id]["message"] = "Initializing workflow..."
        
        # Import main enrichment logic
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        from tavily_agent.main import AgenticRAGOrchestrator
        from tavily_agent.file_io_manager import FileIOManager
        from tavily_agent.graph import PayloadEnrichmentState
        
        # Initialize orchestrator with checkpointing
        orchestrator = AgenticRAGOrchestrator()
        orchestrator.graph = None  # Will rebuild with checkpointing
        
        logger.info(f"🔧 [ENRICHMENT] Building graph with checkpointing for {company_name}")
        from tavily_agent.graph import build_enrichment_graph
        orchestrator.graph = build_enrichment_graph(with_checkpointing=True)
        
        # Load payload
        logger.info(f"📥 [ENRICHMENT] Loading payload for {company_name}")
        file_io = FileIOManager()
        payload = await file_io.read_payload(company_name)
        
        if not payload:
            raise ValueError(f"Could not load payload for {company_name}")
        
        # Create initial state
        state = PayloadEnrichmentState(
            company_name=company_name,
            company_id=payload.get("company_record", {}).get("company_id", company_name),
            current_payload=json.loads(json.dumps(payload, default=str)),
            original_payload=json.loads(json.dumps(payload, default=str))
        )
        
        # Execute workflow with thread/config for checkpointing
        config = {
            "configurable": {"thread_id": task_id},
            "recursion_limit": 100
        }
        
        enrichment_tasks[task_id]["message"] = "Executing workflow..."
        logger.info(f"▶️  [ENRICHMENT] Invoking workflow for {company_name} with thread_id={task_id}")
        
        try:
            # This will pause if interrupt() is called
            final_state = await orchestrator.graph.ainvoke(state.dict(), config=config)
            
            # Convert back to state object
            final_state_obj = PayloadEnrichmentState(**final_state)
            
            # Check if we hit an interrupt (HITL pause)
            if final_state_obj.pending_approval_id:
                logger.info(f"⏸️  [ENRICHMENT] Workflow paused - waiting for approval: {final_state_obj.pending_approval_id}")
                enrichment_tasks[task_id]["status"] = "waiting_approval"
                enrichment_tasks[task_id]["approval_id"] = final_state_obj.pending_approval_id
                enrichment_tasks[task_id]["message"] = "Waiting for human approval"
                
                # Get approval details
                from tavily_agent.approval_queue import get_approval_queue
                queue = get_approval_queue()
                approval = queue.get_approval(final_state_obj.pending_approval_id)
                if approval:
                    enrichment_tasks[task_id]["field_name"] = approval.field_name
                
                return
            
            # Workflow completed
            logger.info(f"✅ [ENRICHMENT] Workflow completed for {company_name}")
            
            # Save result
            await file_io.save_payload(company_name, final_state_obj.current_payload)
            
            enrichment_tasks[task_id]["status"] = "completed"
            enrichment_tasks[task_id]["message"] = "Enrichment completed successfully"
            enrichment_tasks[task_id]["result"] = {
                "fields_updated": len(final_state_obj.extracted_values),
                "iterations": final_state_obj.iteration
            }
            
        except Exception as workflow_error:
            # Check if this is an interrupt (normal for HITL)
            if "interrupt" in str(workflow_error).lower():
                logger.info(f"⏸️  [ENRICHMENT] Workflow interrupted for approval")
                enrichment_tasks[task_id]["status"] = "waiting_approval"
                enrichment_tasks[task_id]["message"] = "Waiting for human approval"
            else:
                raise
        
    except Exception as e:
        logger.error(f"❌ [ENRICHMENT] Task {task_id} failed: {e}", exc_info=True)
        enrichment_tasks[task_id]["status"] = "failed"
        enrichment_tasks[task_id]["error"] = str(e)
        enrichment_tasks[task_id]["message"] = f"Enrichment failed: {str(e)}"


@app.post("/enrich/company/{company_name}", response_model=EnrichmentTaskResponse)
async def trigger_enrichment(company_name: str, background_tasks: BackgroundTasks):
    """
    Trigger agentic RAG enrichment for a company with HITL support.
    
    This endpoint:
    1. Starts enrichment in background
    2. Returns immediately with task_id
    3. Workflow will pause if HITL approval needed
    4. Use /enrich/status/{task_id} to check progress
    """
    task_id = str(uuid.uuid4())
    
    # Initialize task tracking
    enrichment_tasks[task_id] = {
        "task_id": task_id,
        "company_name": company_name,
        "status": "started",
        "message": "Task created",
        "approval_id": None,
        "field_name": None,
        "result": None,
        "error": None
    }
    
    # Start enrichment in background
    background_tasks.add_task(run_enrichment_with_checkpointing, company_name, task_id)
    
    logger.info(f"📋 [API] Created enrichment task {task_id} for {company_name}")
    
    return EnrichmentTaskResponse(
        task_id=task_id,
        company_name=company_name,
        status="started",
        message=f"Enrichment task created for {company_name}. Use /enrich/status/{task_id} to check progress."
    )


@app.get("/enrich/status/{task_id}", response_model=EnrichmentStatusResponse)
async def get_enrichment_status(task_id: str):
    """
    Check status of an enrichment task.
    
    Status values:
    - started: Task created but not yet running
    - running: Workflow executing
    - waiting_approval: Paused, waiting for HITL approval
    - completed: Successfully finished
    - failed: Error occurred
    """
    if task_id not in enrichment_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = enrichment_tasks[task_id]
    
    return EnrichmentStatusResponse(
        task_id=task_id,
        company_name=task["company_name"],
        status=task["status"],
        message=task.get("message"),
        approval_id=task.get("approval_id"),
        field_name=task.get("field_name"),
        result=task.get("result"),
        error=task.get("error")
    )


@app.post("/enrich/resume/{task_id}")
async def resume_enrichment(task_id: str, background_tasks: BackgroundTasks):
    """
    Resume a paused enrichment workflow after approval is processed.
    
    This is called automatically after approval/rejection in the HITL dashboard.
    """
    if task_id not in enrichment_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = enrichment_tasks[task_id]
    
    if task["status"] != "waiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not waiting for approval (current status: {task['status']})"
        )
    
    logger.info(f"▶️  [API] Resuming task {task_id} for {task['company_name']}")
    
    # Resume workflow from checkpoint
    background_tasks.add_task(run_enrichment_with_checkpointing, task["company_name"], task_id)
    
    return {
        "task_id": task_id,
        "status": "resuming",
        "message": "Workflow resuming from checkpoint"
    }


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
