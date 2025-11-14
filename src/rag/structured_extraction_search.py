#!/usr/bin/env python3
"""RAG-based Structured Extraction: Extract and normalize company data using semantic search.

This script:
1. Reads text extracted from company web pages (data/raw/{company_slug}/{page_type}/text.txt)
2. Queries Pinecone vector database to retrieve relevant context
3. Uses instructor + OpenAI to extract structured data into Pydantic models
4. Normalizes messy text data into clean, structured format
5. Saves results as data/payloads/{company_slug}/{company_id}.json

The extraction follows the schema defined in rag_models.py:
- Company (legal_name, website, headquarters, founding date, funding, etc.)
- Event (funding rounds, M&A, product releases, etc.)
- Snapshot (headcount, job openings, pricing, etc.)
- Product (description, pricing model, integrations, etc.)
- Leadership (founders, executives, roles, etc.)
- Visibility (news mentions, GitHub stars, ratings, etc.)

NOTE: This script expects Pinecone to be already indexed. Run ingest_to_pinecone.py first.

Usage:
  python src/rag/structured_extraction.py --company-slug world_labs
  python src/rag/structured_extraction.py --company-slug world_labs --verbose
  python src/rag/structured_extraction.py --all
"""

import json
import logging
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import instructor
from openai import OpenAI
from pydantic import BaseModel, ValidationError, Field
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings

# Import Pydantic models
sys.path.insert(0, str(Path(__file__).parent))
from rag_models import (
    Company, Event, Snapshot, Product, Leadership, Visibility, 
    Payload, Provenance
)

# Load environment variables
load_dotenv()

# Global configuration
FALLBACK_STRATEGY = 'pinecone_first'  # Can be: 'pinecone_only', 'raw_only', 'pinecone_first'
USE_RAW_TEXT = False  # Set to True to skip Pinecone and use raw text directly
PINECONE_SEARCH_LIMIT = 100  # Increased from 5 to get more results per query
PINECONE_MIN_SIMILARITY = 0.0  # Minimum similarity score (0.0 = accept all results)


def setup_logging(script_name: str = 'structured_extraction'):
    """Setup logging for extraction script."""
    log_dir = "data/logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(f"{log_dir}/{script_name}.log")
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# ─────────────────────────────────────────────────────────────────────────────
#  Flexible Payload File Lookup
# ─────────────────────────────────────────────────────────────────────────────
def find_payload_file(company_id_or_name: str) -> Optional[Path]:
    """
    Find payload file with flexible naming conventions.
    
    Tries multiple variations to handle different naming patterns:
    1. Exact match: "{company_id}.json"
    2. Full slug with hyphens: "company-name.json"
    3. Full slug with underscores: "company_name.json"
    4. Full slug no separators: "companyname.json"
    5. First word only: "company.json"
    6. Any file matching the first word with glob
    
    Args:
        company_id_or_name: Company ID or display name (e.g., "coactive" or "Coactive AI")
    
    Returns:
        Path to found payload file or None
    """
    logger = logging.getLogger('structured_extraction_search')
    
    payloads_dir = Path("data/payloads")
    
    if not payloads_dir.exists():
        logger.debug(f"Payloads directory not found: {payloads_dir}")
        return None
    
    # Generate variants from input
    first_word = company_id_or_name.lower().split()[0]
    
    # Build list of variants to try
    variants = [
        company_id_or_name.lower(),  # Exact as provided
        company_id_or_name.lower().replace(" ", "-").replace("_", "-"),  # With hyphens
        company_id_or_name.lower().replace(" ", "_").replace("-", "_"),  # With underscores
        company_id_or_name.lower().replace(" ", "").replace("_", "").replace("-", ""),  # No separators
        first_word,  # First word only
    ]
    
    # Remove duplicates while preserving order
    variants = list(dict.fromkeys(variants))
    
    logger.debug(f"Looking for payload file for '{company_id_or_name}'")
    logger.debug(f"  Trying variants: {variants}")
    
    # Try each variant directly
    for variant in variants:
        payload_file = payloads_dir / f"{variant}.json"
        if payload_file.exists():
            logger.info(f"✓ Found payload file: {payload_file}")
            return payload_file
    
    # Fallback: scan directory for files that start with the first word
    logger.debug(f"Direct lookup failed, scanning for files starting with '{first_word}'...")
    
    try:
        for file in payloads_dir.glob(f"{first_word}*.json"):
            logger.info(f"✓ Found payload file by glob pattern: {file}")
            return file
    except Exception as e:
        logger.debug(f"Error scanning payloads directory: {e}")
    
    logger.debug(f"No payload file found for '{company_id_or_name}'")
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Change Detection & Metadata Functions (for incremental extraction)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception as e:
        logger = logging.getLogger('structured_extraction')
        logger.error(f"Error calculating file hash: {e}")
        return ""


def load_extraction_metadata(company_slug: str) -> Optional[Dict[str, Any]]:
    """Load existing extraction metadata for a company."""
    logger = logging.getLogger('structured_extraction')
    
    metadata_file = Path(f"data/metadata/{company_slug}/extraction_search_metadata.json")
    
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        logger.info(f"✓ Loaded existing extraction metadata for {company_slug}")
        return metadata
    except Exception as e:
        logger.error(f"Error loading extraction metadata: {e}")
        return None


def save_extraction_metadata(company_slug: str, metadata: Dict[str, Any]) -> bool:
    """Save extraction metadata for a company."""
    logger = logging.getLogger('structured_extraction')
    
    try:
        metadata_dir = Path(f"data/metadata/{company_slug}")
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = metadata_dir / "extraction_search_metadata.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"✅ Saved extraction metadata to: {metadata_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving extraction metadata: {e}", exc_info=True)
        return False


def check_if_extraction_needed(company_slug: str, pages_text: Dict[str, str]) -> tuple:
    """Check if extraction is needed based on file changes or missing payload.
    
    Returns Tuple of (needed: bool, reason: str):
    - (True, "first_time") if no extraction metadata exists yet
    - (True, "files_changed") if any file hash has changed
    - (True, "payload_missing") if payload file doesn't exist
    - (False, "unchanged") if all files unchanged and payload exists
    
    This ensures extraction runs when:
    1. First time processing a company
    2. Source files have changed (detected by hash mismatch)
    3. Payload file is missing (incomplete previous run or manual deletion)
    """
    logger = logging.getLogger('structured_extraction')
    
    # Load existing metadata
    metadata = load_extraction_metadata(company_slug)
    
    if metadata is None:
        logger.info(f"No extraction metadata found - extraction needed (first time)")
        return True, "first_time"
    
    old_file_hashes = metadata.get("file_hashes", {})
    
    # Check if any files have changed
    logger.info(f"\nChecking file changes for extraction:")
    logger.info(f"{'─' * 60}")
    
    any_changed = False
    for page_type in pages_text.keys():
        source_file = f"data/raw/{company_slug}/{page_type}/text.txt"
        file_hash = calculate_file_hash(source_file)
        old_hash = old_file_hashes.get(page_type)
        
        if old_hash != file_hash:
            logger.info(f"  📄 {page_type}: CHANGED")
            any_changed = True
        else:
            logger.info(f"  📄 {page_type}: UNCHANGED")
    
    logger.info(f"{'─' * 60}")
    
    if any_changed:
        logger.info(f"✓ File changes detected - extraction needed")
        return True, "files_changed"
    
    # Files haven't changed - now check if payload file actually exists on disk
    logger.info(f"\nChecking if payload file exists:")
    logger.info(f"{'─' * 60}")
    
    payloads_dir = Path("data/payloads")
    payload_exists = False
    
    # Get company_id from metadata if available
    company_id = metadata.get("company_id") if metadata else None
    
    if payloads_dir.exists():
        # If we have company_id from metadata, check for that specific file
        if company_id:
            payload_file = payloads_dir / f"{company_id}.json"
            if payload_file.exists():
                logger.info(f"  ✓ Found payload file: {payload_file.name}")
                payload_exists = True
            else:
                logger.info(f"  ✗ Payload file missing: {payload_file.name}")
                payload_exists = False
        else:
            # No company_id in metadata yet
            # This means we've never successfully extracted before
            # So we should ALWAYS extract now (can't verify payload for unknown company_id)
            logger.info(f"  ⚠️  No company_id in metadata - cannot verify specific payload file")
            logger.info(f"  (Company ID is only known after first extraction)")
            
            extraction_history = metadata.get("extraction_history", []) if metadata else []
            
            if not extraction_history or len(extraction_history) == 0:
                # No history at all - definitely needs extraction
                logger.info(f"  No extraction history - needs extraction")
                payload_exists = False
            else:
                # Has extraction history but no company_id
                # This is inconsistent state - could be incomplete extraction
                # Be safe and require re-extraction
                logger.info(f"  ⚠️  Extraction history exists but company_id is missing!")
                logger.info(f"  This could mean extraction was incomplete or metadata corrupted")
                logger.info(f"  Requiring re-extraction to ensure consistency")
                payload_exists = False
    else:
        logger.info(f"  Payloads directory doesn't exist - payload missing")
        payload_exists = False
    
    logger.info(f"{'─' * 60}")
    
    if not payload_exists:
        logger.info(f"✓ Payload file missing - extraction needed")
        return True, "payload_missing"
    
    logger.info(f"✓ No file changes and payload exists - skipping extraction")
    return False, "unchanged"


def update_extraction_metadata(company_slug: str, pages_text: Dict[str, str]) -> Dict[str, Any]:
    """Update extraction metadata with new file hashes."""
    logger = logging.getLogger('structured_extraction')
    
    # Load existing metadata or create new
    metadata = load_extraction_metadata(company_slug)
    if metadata is None:
        metadata = {
            "company_slug": company_slug,
            "created_at": datetime.now().isoformat(),
            "last_extraction": None,
            "extraction_count": 0,
            "file_hashes": {},
            "extraction_history": []
        }
    
    # Update file hashes
    new_file_hashes = {}
    for page_type in pages_text.keys():
        source_file = f"data/raw/{company_slug}/{page_type}/text.txt"
        file_hash = calculate_file_hash(source_file)
        new_file_hashes[page_type] = file_hash
    
    metadata["file_hashes"] = new_file_hashes
    metadata["last_extraction"] = datetime.now().isoformat()
    metadata["extraction_count"] = metadata.get("extraction_count", 0) + 1
    
    # Add to history
    if "extraction_history" not in metadata:
        metadata["extraction_history"] = []
    
    metadata["extraction_history"].append({
        "timestamp": datetime.now().isoformat(),
        "files_checked": len(pages_text),
        "status": "completed"
    })
    
    # Save updated metadata
    save_extraction_metadata(company_slug, metadata)
    
    return metadata


def get_llm_client():
    """Initialize OpenAI client with instructor patch."""
    logger = logging.getLogger('structured_extraction')
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not set in environment")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    # Create base OpenAI client
    base_client = OpenAI(api_key=api_key)
    
    # Patch with instructor - this modifies the client in place and returns it
    try:
        client = instructor.patch(
            base_client,
            mode=instructor.Mode.TOOLS,  # Use TOOLS mode for better compatibility
        )
        logger.info("Initialized OpenAI client with instructor (TOOLS mode)")
    except Exception as e:
        logger.warning(f"Failed to patch with TOOLS mode, trying MD_JSON: {e}")
        try:
            client = instructor.patch(
                base_client,
                mode=instructor.Mode.MD_JSON,
            )
            logger.info("Initialized OpenAI client with instructor (MD_JSON mode)")
        except Exception as e2:
            logger.warning(f"Failed to patch with MD_JSON mode, using standard: {e2}")
            client = instructor.patch(base_client)
            logger.info("Initialized OpenAI client with instructor (standard mode)")
    
    return client


def get_pinecone_client():
    """Initialize Pinecone client for vector search."""
    logger = logging.getLogger('structured_extraction')
    
    # Get Pinecone configuration from environment
    api_key = os.getenv('PINECONE_API_KEY')
    if not api_key:
        logger.error("PINECONE_API_KEY not set in environment")
        raise ValueError("PINECONE_API_KEY environment variable is required")
    
    index_name = os.getenv('PINECONE_INDEX_NAME', 'bigdata-assignment-04')
    logger.info(f"Attempting to connect to Pinecone index: {index_name}")
    
    try:
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Get index reference
        index = pc.Index(index_name)
        
        # Test connection by getting index stats
        try:
            logger.info("Testing Pinecone connection...")
            stats = index.describe_index_stats()
            logger.info(f"✅ Successfully connected to Pinecone index '{index_name}'")
            logger.info(f"   Namespaces: {list(stats.namespaces.keys()) if stats.namespaces else 'default'}")
            logger.info(f"   Total vectors: {stats.total_vector_count}")
            return index
        except Exception as test_error:
            logger.error(f"❌ Failed to verify Pinecone connection: {test_error}")
            raise
    except Exception as e:
        logger.warning(f"Failed to connect to Pinecone: {e}")
        logger.info("Will proceed without vector search (using raw text instead)")
        return None


def get_embeddings_model():
    """Get OpenAI embeddings model."""
    logger = logging.getLogger('structured_extraction')
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not set for embeddings")
        raise ValueError("OPENAI_API_KEY required for embeddings")
    
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            api_key=api_key
        )
        logger.debug("Initialized OpenAI embeddings model (text-embedding-3-large, dimension: 3072)")
        return embeddings
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        raise


def search_pinecone_for_context(
    query: str,
    company_slug: str,
    pinecone_index,
    embeddings: Optional[OpenAIEmbeddings],
    limit: int = 100,
    min_similarity: float = 0.0
) -> List[Dict[str, Any]]:
    """Search Pinecone for relevant context using semantic search with lenient matching."""
    logger = logging.getLogger('structured_extraction')
    
    # Log parameters
    logger.debug(f"🔍 search_pinecone_for_context called with:")
    logger.debug(f"    query: {query}")
    logger.debug(f"    company_slug: {company_slug}")
    logger.debug(f"    limit: {limit}")
    logger.debug(f"    min_similarity: {min_similarity}")
    logger.debug(f"    has_index: {pinecone_index is not None}")
    logger.debug(f"    has_embeddings: {embeddings is not None}")
    
    if not pinecone_index or not embeddings:
        logger.debug("Cannot search Pinecone - index/embeddings missing")
        return []
    
    namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    
    try:
        # Generate embedding for query
        query_embedding = embeddings.embed_query(query)
        
        # Search Pinecone and filter by company using vector_id prefix
        logger.debug(f"🔍 Searching Pinecone (namespace '{namespace}'): '{query}' for company '{company_slug}'")
        
        # Query with higher top_k to account for cross-company results that we'll filter out
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=limit * 3,  # Get 3x results to filter
            namespace=namespace,
            include_metadata=True
        )
        
        # Extract context from results with full source tracking
        # Filter to only include vectors for this specific company
        context_docs = []
        for idx, match in enumerate(results.matches, 1):
            # Filter by company - vector IDs are prefixed with company_slug
            vector_id = match.id.lower()
            company_slug_lower = company_slug.lower()
            
            # Check if this vector belongs to the current company
            if not vector_id.startswith(f"{company_slug_lower}_"):
                logger.debug(f"  ❌ Skipping {vector_id} - not from {company_slug}")
                continue
            
            # Filter by minimum similarity
            if match.score >= min_similarity:
                doc = {
                    "text": match.metadata.get("text", ""),
                    "page_type": match.metadata.get("page_type", ""),
                    "score": match.score,
                    "source_file": match.metadata.get("source_file", ""),
                    "chunk_index": match.metadata.get("chunk_index", ""),
                    "vector_id": match.id,
                }
                context_docs.append(doc)
                logger.debug(f"  🎯 Rank {len(context_docs)}: {doc['source_file']} (chunk {doc['chunk_index']}, similarity: {match.score:.3f})")
            
            # Stop after collecting enough results
            if len(context_docs) >= limit:
                break
        
        logger.debug(f"✅ Pinecone search returned {len(context_docs)} documents (filtered by min_similarity >= {min_similarity})")
        return context_docs
        
    except Exception as e:
        logger.warning(f"❌ Error searching Pinecone: {e}")
        return []


def log_extraction_sources(
    extraction_type: str,
    company_id: str,
    search_queries: List[str],
    context_docs: List[Dict[str, Any]]
) -> None:
    """Log detailed source information for validation."""
    logger = logging.getLogger('structured_extraction')
    
    if not context_docs:
        logger.warning(f"  ⚠️  No Pinecone sources found for {extraction_type}")
        return
    
    logger.info(f"\n  📊 {extraction_type.upper()} - Source Validation:")
    logger.info(f"  {'─' * 70}")
    
    # Group by source file
    sources_by_file = {}
    for doc in context_docs:
        source_file = doc.get('source_file', 'unknown')
        if source_file not in sources_by_file:
            sources_by_file[source_file] = []
        sources_by_file[source_file].append(doc)
    
    # Log each source
    for source_file in sorted(sources_by_file.keys()):
        docs = sources_by_file[source_file]
        logger.info(f"  Source: {source_file}")
        logger.info(f"    Chunks used: {len(docs)}")
        for doc in docs:
            logger.info(f"      • Vector ID {doc['vector_id']}: chunk {doc['chunk_index']} (similarity: {doc['score']:.3f})")
        logger.info(f"    Content preview: {docs[0]['text'][:100]}...")
    
    logger.info(f"  {'─' * 70}\n")


def build_enriched_context(context_docs: List[Dict[str, Any]]) -> tuple:
    """Build enriched context text with chunk tracking information.
    
    Returns:
        Tuple of (enriched_context_text: str, chunk_mapping: Dict[str, List[str]])
        where chunk_mapping maps source_url (page_type) to list of chunk identifiers
    """
    logger = logging.getLogger('structured_extraction')
    
    if not context_docs:
        return "", {}
    
    # Build enriched context with explicit chunk references
    enriched_parts = []
    chunk_mapping = {}  # Maps page_type to list of chunk IDs
    
    for doc in context_docs:
        page_type = doc.get('page_type', 'unknown')
        chunk_index = doc.get('chunk_index', 0)
        vector_id = doc.get('vector_id', '')
        text = doc.get('text', '')
        score = doc.get('score', 0.0)
        
        # Create chunk identifier combining vector_id and chunk_index for traceability
        chunk_id = f"{vector_id}#{chunk_index}"
        
        # Track chunk IDs per page type for provenance
        if page_type not in chunk_mapping:
            chunk_mapping[page_type] = []
        if chunk_id not in chunk_mapping[page_type]:
            chunk_mapping[page_type].append(chunk_id)
        
        # Format context with chunk metadata
        enriched_parts.append(
            f"[{page_type} - Chunk #{chunk_index} (ID: {vector_id}, Relevance: {score:.2f})]\n{text}\n"
        )
    
    enriched_context = "\n---\n".join(enriched_parts)
    
    logger.debug(f"Built enriched context with {len(context_docs)} chunks across {len(chunk_mapping)} page types")
    
    return enriched_context, chunk_mapping


def should_use_fallback(context_docs: List[Dict[str, Any]], extraction_type: str) -> bool:
    """Determine if fallback should be used based on strategy and context availability."""
    logger = logging.getLogger('structured_extraction')
    
    global FALLBACK_STRATEGY
    
    if context_docs:
        # We have context, no fallback needed
        return False
    
    # No context available, check strategy
    if FALLBACK_STRATEGY == 'pinecone_only':
        logger.error(f"❌ Strategy 'pinecone_only': No Pinecone results for {extraction_type}, FAILING")
        return False
    elif FALLBACK_STRATEGY == 'raw_only':
        logger.warning(f"⚠️  Strategy 'raw_only': Ignoring Pinecone, using raw text for {extraction_type}")
        return True
    elif FALLBACK_STRATEGY == 'pinecone_first':
        logger.warning(f"⚠️  Strategy 'pinecone_first': Fallback to raw text for {extraction_type}")
        return True
    
    return False


def load_company_page_text(company_slug: str, page_type: str) -> Optional[str]:
    """Load extracted text from a company page."""
    logger = logging.getLogger('structured_extraction')
    
    text_file = f"data/raw/{company_slug}/{page_type}/text.txt"
    
    if not Path(text_file).exists():
        logger.debug(f"Text file not found: {text_file}")
        return None
    
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        logger.debug(f"Loaded text from {text_file}: {len(text)} chars")
        return text
    except Exception as e:
        logger.error(f"Failed to load text from {text_file}: {e}")
        return None


def load_all_company_pages(company_slug: str) -> Dict[str, str]:
    """Load all extracted text pages for a company."""
    logger = logging.getLogger('structured_extraction')
    
    company_raw_dir = Path(f"data/raw/{company_slug}")
    if not company_raw_dir.exists():
        logger.warning(f"Company directory not found: {company_raw_dir}")
        return {}
    
    pages_text = {}
    page_types = [d.name for d in company_raw_dir.iterdir() if d.is_dir()]
    
    for page_type in sorted(page_types):
        text = load_company_page_text(company_slug, page_type)
        if text:
            pages_text[page_type] = text
            logger.info(f"Loaded {page_type} page: {len(text)} chars")
    
    logger.info(f"Loaded {len(pages_text)} pages for {company_slug}")
    return pages_text


def extract_company_info(
    client, 
    company_name: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> Optional[Company]:
    """Extract company information using LLM with instructor and Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"🏢 Extracting company info for {company_name}...")
    
    # Build search queries for company information
    search_queries = [
        f"company {company_name} legal name brand headquarters location founded",
        f"{company_name} website URL domain",
        f"{company_name} categories industry vertical",
        f"{company_name} funding raised valuation investment round",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    chunk_mapping = {}
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for company info")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_name, pinecone_index, embeddings, limit=3)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info(f"🏢 Using {len(context_docs)} Pinecone documents for company extraction")
            # Use enriched context with chunk information
            context_text, chunk_mapping = build_enriched_context(context_docs)
        else:
            logger.error("🏢 ❌ No Pinecone results for company info - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    # Log extraction sources for validation
    log_extraction_sources("Company Info", company_name, search_queries, context_docs)
    
    # Build list of available page types for provenance guidance
    available_pages = list(pages_text.keys()) if pages_text else ["about", "product", "blog", "careers"]
    page_list_str = ", ".join(available_pages)
    
    # Build chunk ID reference for prompt
    chunk_ids_ref = "\n".join([
        f"  • {page_type}: {', '.join(ids)}"
        for page_type, ids in chunk_mapping.items()
    ]) if chunk_mapping else "None available"
    
    prompt = f"""Extract company information for "{company_name}" from the following web content and context:

{context_text}

Return a structured Company record with all available information.

IMPORTANT INSTRUCTIONS:
- Use ONLY explicitly stated information
- Generate company_id from the website domain (e.g., "world-labs" from "worldlabs.ai")
- Use null for missing fields
- Do NOT infer or guess
- Standardize dates to YYYY-MM-DD format

PROVENANCE FIELD:
- For each field extracted, create a Provenance entry with:
  - source_url: Use ONLY these page type values: {page_list_str}
  - crawled_at: Set to today's date in YYYY-MM-DD format
  - snippet: A brief quote from the source supporting this field (optional)
  - chunk_id: List of chunk identifiers from the context that supported extracting this field. Reference the chunk IDs shown above.
- Do NOT create URLs or use page names not in the list above
- If you extract from multiple pages/chunks for one field, include all relevant chunk IDs in the list
- For example: chunk_id: ["vector_id#0", "vector_id#1"] if multiple chunks supported a field

Available chunk IDs by page type:
{chunk_ids_ref}"""
    
    try:
        # Use instructor's patched client with response_model
        company = client.chat.completions.create(
            model="gpt-4o",
            response_model=Company,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for consistency
        )
        logger.info(f"🏢 ✓ Successfully extracted company: {company.legal_name if hasattr(company, 'legal_name') else 'Unknown'}")
        return company
    except ValidationError as e:
        logger.error(f"🏢 Validation error extracting company: {e}")
        return None
    except Exception as e:
        logger.error(f"🏢 Error extracting company info: {e}", exc_info=True)
        return None


def extract_events(
    client, 
    company_slug: str,  # Changed from company_id to company_slug
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Event]:
    """Extract events (funding, M&A, partnerships, etc.) using LLM and Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"📅 Extracting events for {company_slug}...")
    
    # Build search queries for events - using content from pages
    search_queries = [
        f"{company_slug} funding investment raised capital",
        f"{company_slug} announcement news update",
        f"{company_slug} partnership integration collaboration",
        f"{company_slug} product launch release",
        f"{company_slug} team hiring expansion",
        f"Series funding round investment",
    ]
    
    # Fallback queries if primary queries return no results
    fallback_queries = [
        "funding",
        "investment",
        "money",
        "capital",
        "announcement",
        "partnership",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    chunk_mapping = {}
    
    global USE_RAW_TEXT
    global FALLBACK_STRATEGY
    global PINECONE_SEARCH_LIMIT
    global PINECONE_MIN_SIMILARITY
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for events")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search with primary queries
        logger.debug(f"Trying primary search queries for events...")
        for query in search_queries:
            docs = search_pinecone_for_context(
                query, company_slug, pinecone_index, embeddings, 
                limit=PINECONE_SEARCH_LIMIT,
                min_similarity=PINECONE_MIN_SIMILARITY
            )
            context_docs.extend(docs)
        
        # If no results, try fallback queries
        if not context_docs:
            logger.info(f"No results with primary queries, trying fallback queries...")
            for query in fallback_queries:
                docs = search_pinecone_for_context(
                    query, company_slug, pinecone_index, embeddings, 
                    limit=PINECONE_SEARCH_LIMIT,
                    min_similarity=PINECONE_MIN_SIMILARITY
                )
                context_docs.extend(docs)
        
        if context_docs:
            logger.info(f"📅 Using {len(context_docs)} Pinecone documents for events extraction")
            # Use enriched context with chunk information
            context_text, chunk_mapping = build_enriched_context(context_docs)
        else:
            # No Pinecone results - check fallback strategy
            if FALLBACK_STRATEGY == 'pinecone_only':
                logger.error("📅 ❌ No Pinecone results for events - ABORTING (pinecone_only strategy)")
                raise ValueError("No Pinecone context available for events")
            else:
                logger.warning(f"📅 ⚠️  No Pinecone results for events - Falling back to raw text ({FALLBACK_STRATEGY})")
                context_text = json.dumps(pages_text, indent=2)[:3000]
    
    # Build chunk ID reference for prompt
    chunk_ids_ref = "\n".join([
        f"  • {page_type}: {', '.join(ids)}"
        for page_type, ids in chunk_mapping.items()
    ]) if chunk_mapping else "None (using raw text fallback)"
    
    prompt = f"""Extract all significant events for company "{company_slug}" from the web content:

{context_text}

Include:
- Funding rounds (Series A/B/C, seed, etc.) with amounts and dates
- M&A activities (acquisitions, mergers)
- Product launches and releases
- Partnerships and integrations
- Key hires and leadership changes
- Layoffs and restructuring
- Major milestones and achievements

For each event MUST include:
- event_id: Unique identifier for event
- company_id: The company identifier
- occurred_on: Date in YYYY-MM-DD format
- event_type: MUST be one of ONLY these values: 'funding', 'mna', 'product_release', 'integration', 'partnership', 'customer_win', 'leadership_change', 'regulatory', 'security_incident', 'pricing_change', 'layoff', 'hiring_spike', 'office_open', 'office_close', 'benchmark', 'open_source_release', 'contract_award', 'other'
  * CRITICAL: Do NOT use custom event types like 'policy', 'announcement', etc.
  * If event doesn't fit above categories, use 'other' instead
- title: Brief event title
- description: Detailed description (optional)
- For funding events, include amount_usd and valuation_usd
- Use only explicitly stated information
- Use null for missing fields

PROVENANCE FIELD FOR EACH EVENT:
- source_url: Page type only (e.g., "blog", "product", "careers") - NOT vector IDs
- crawled_at: Date in YYYY-MM-DD format
- chunk_id: List of chunk identifiers that supported extracting this event
  * Format: ["vector_id#chunk_index", ...] 
  * Examples: ["abridge_blog_f1388ab9#2.0", "abridge_careers_c3a0a730#25.0"]

Available chunk IDs by page type:
{chunk_ids_ref}

Return a list of Event objects."""
    
    try:
        # Define a wrapper model to handle list return
        class EventList(BaseModel):
            events: List[Event] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=EventList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"📅 ✓ Extracted {len(result.events)} events")
        return result.events
    except Exception as e:
        logger.warning(f"📅 Error extracting events: {e}")
        return []


def extract_snapshots(
    client, 
    company_slug: str,  # Changed from company_id to company_slug
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Snapshot]:
    """Extract business snapshots (headcount, products, pricing, etc.) using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"📸 Extracting snapshots for {company_slug}...")
    
    # Search queries for snapshot data - using content from pages
    search_queries = [
        f"{company_slug} team size headcount employees",
        f"{company_slug} pricing model plans features",
        f"{company_slug} products services offerings",
        f"{company_slug} hiring jobs positions openings",
        f"{company_slug} customers clients enterprise",
        f"AI artificial intelligence technology platform",
    ]
    
    # Fallback queries if primary queries return no results
    fallback_queries = [
        "team",
        "headcount",
        "employees",
        "pricing",
        "products",
        "hiring",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    chunk_mapping = {}
    
    global USE_RAW_TEXT
    global FALLBACK_STRATEGY
    global PINECONE_SEARCH_LIMIT
    global PINECONE_MIN_SIMILARITY
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for snapshots")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search with primary queries
        logger.debug(f"Trying primary search queries for snapshots...")
        for query in search_queries:
            docs = search_pinecone_for_context(
                query, company_slug, pinecone_index, embeddings,
                limit=PINECONE_SEARCH_LIMIT,
                min_similarity=PINECONE_MIN_SIMILARITY
            )
            context_docs.extend(docs)
        
        # If no results, try fallback queries
        if not context_docs:
            logger.info(f"No results with primary queries, trying fallback queries...")
            for query in fallback_queries:
                docs = search_pinecone_for_context(
                    query, company_slug, pinecone_index, embeddings,
                    limit=PINECONE_SEARCH_LIMIT,
                    min_similarity=PINECONE_MIN_SIMILARITY
                )
                context_docs.extend(docs)
        
        if context_docs:
            logger.info(f"📸 Using {len(context_docs)} Pinecone documents for snapshots extraction")
            # Use enriched context with chunk information
            context_text, chunk_mapping = build_enriched_context(context_docs)
        else:
            # No Pinecone results - check fallback strategy
            if FALLBACK_STRATEGY == 'pinecone_only':
                logger.error("📸 ❌ No Pinecone results for snapshots - ABORTING (pinecone_only strategy)")
                raise ValueError("No Pinecone context available for snapshots")
            else:
                logger.warning(f"📸 ⚠️  No Pinecone results for snapshots - Falling back to raw text ({FALLBACK_STRATEGY})")
                context_text = json.dumps(pages_text, indent=2)[:3000]
    
    # Build chunk ID reference for prompt
    chunk_ids_ref = "\n".join([
        f"  • {page_type}: {', '.join(ids)}"
        for page_type, ids in chunk_mapping.items()
    ]) if chunk_mapping else "None (using raw text fallback)"
    
    prompt = f"""Extract business snapshot information for company "{company_slug}" from web content:

{context_text}

Extract current/recent:
- Headcount total and growth percentage
- Job openings count by department (engineering, sales, etc.)
- Hiring focus areas
- Pricing tiers and pricing model
- Active products
- Geographic presence (countries/regions)

PROVENANCE FIELD FOR EACH SNAPSHOT:
- source_url: Page type only (e.g., "careers", "product", "blog") - NOT vector IDs or chunk references
- crawled_at: Date in YYYY-MM-DD format
- chunk_id: List of chunk identifiers that supported extracting this snapshot data
  * Format: ["vector_id#chunk_index", ...]
  * Examples: ["abridge_careers_0b8a84fe#1.0", "abridge_product_12345678#3.0"]

Available chunk IDs by page type:
{chunk_ids_ref}

Return a list of Snapshot objects with as_of date set to today.
Use only explicitly stated information. Use null for missing fields."""
    
    try:
        class SnapshotList(BaseModel):
            snapshots: List[Snapshot] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=SnapshotList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"📸 ✓ Extracted {len(result.snapshots)} snapshots")
        return result.snapshots
    except Exception as e:
        logger.warning(f"📸 Error extracting snapshots: {e}")
        return []


def extract_products(
    client, 
    company_slug: str,  # Changed from company_id to company_slug
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Product]:
    """Extract product information using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"🛍️  Extracting products for {company_slug}...")
    
    # Search queries for product data - using content from pages
    search_queries = [
        f"{company_slug} product features description",
        f"{company_slug} pricing cost plans",
        f"{company_slug} integration API platform",
        f"{company_slug} use cases applications capabilities",
        f"{company_slug} technology innovation",
        f"artificial intelligence computer vision pixel",
    ]
    
    # Fallback queries if primary queries return no results
    fallback_queries = [
        "product",
        "features",
        "pricing",
        "integration",
        "capability",
        "pixel",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    chunk_mapping = {}
    
    global USE_RAW_TEXT
    global FALLBACK_STRATEGY
    global PINECONE_SEARCH_LIMIT
    global PINECONE_MIN_SIMILARITY
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for products")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search with primary queries
        logger.debug(f"Trying primary search queries for products...")
        for query in search_queries:
            docs = search_pinecone_for_context(
                query, company_slug, pinecone_index, embeddings,
                limit=PINECONE_SEARCH_LIMIT,
                min_similarity=PINECONE_MIN_SIMILARITY
            )
            context_docs.extend(docs)
        
        # If no results, try fallback queries
        if not context_docs:
            logger.info(f"No results with primary queries, trying fallback queries...")
            for query in fallback_queries:
                docs = search_pinecone_for_context(
                    query, company_slug, pinecone_index, embeddings,
                    limit=PINECONE_SEARCH_LIMIT,
                    min_similarity=PINECONE_MIN_SIMILARITY
                )
                context_docs.extend(docs)
        
        if context_docs:
            logger.info(f"🛍️  Using {len(context_docs)} Pinecone documents for products extraction")
            # Use enriched context with chunk information
            context_text, chunk_mapping = build_enriched_context(context_docs)
        else:
            # No Pinecone results - check fallback strategy
            if FALLBACK_STRATEGY == 'pinecone_only':
                logger.error("🛍️  ❌ No Pinecone results for products - ABORTING (pinecone_only strategy)")
                raise ValueError("No Pinecone context available for products")
            else:
                logger.warning(f"🛍️  ⚠️  No Pinecone results for products - Falling back to raw text ({FALLBACK_STRATEGY})")
                context_text = json.dumps(pages_text, indent=2)[:3000]
    
    # Build chunk ID reference for prompt
    chunk_ids_ref = "\n".join([
        f"  • {page_type}: {', '.join(ids)}"
        for page_type, ids in chunk_mapping.items()
    ]) if chunk_mapping else "None (using raw text fallback)"
    
    prompt = f"""Extract product information for company "{company_slug}" from web content:

{context_text}

For each product, extract:
- Product name and description
- Pricing model (seat, usage, tiered, etc.)
- Public pricing tiers and cost
- Integration partners and APIs
- GitHub repositories and open source projects
- Reference customers and case studies
- License type

PROVENANCE FIELD FOR EACH PRODUCT:
- source_url: Page type only (e.g., "product", "blog", "careers") - NOT vector IDs or chunk references
- crawled_at: Date in YYYY-MM-DD format
- chunk_id: List of chunk identifiers that supported extracting this product info
  * Format: ["vector_id#chunk_index", ...]
  * Examples: ["abridge_product_12345678#2.0", "abridge_blog_87654321#5.0"]

Available chunk IDs by page type:
{chunk_ids_ref}

Return a list of Product objects. Use only explicitly stated information."""
    
    try:
        class ProductList(BaseModel):
            products: List[Product] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=ProductList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"🛍️  ✓ Extracted {len(result.products)} products")
        return result.products
    except Exception as e:
        logger.warning(f"🛍️  Error extracting products: {e}")
        return []


def extract_leadership(
    client, 
    company_slug: str,  # Changed from company_id to company_slug
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Leadership]:
    """Extract leadership and team information using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"👥 Extracting leadership for {company_slug}...")
    
    # Search queries for leadership data - using content from pages
    search_queries = [
        f"{company_slug} founder CEO co-founder",
        f"{company_slug} team leadership executive",
        f"{company_slug} management leadership roles",
        f"{company_slug} LinkedIn profile education background",
        f"{company_slug} advisors investors board members",
        f"founding team members leaders executives",
    ]
    
    # Fallback queries if primary queries return no results
    fallback_queries = [
        "founder",
        "CEO",
        "executive",
        "team",
        "LinkedIn",
        "leader",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    global FALLBACK_STRATEGY
    global PINECONE_SEARCH_LIMIT
    global PINECONE_MIN_SIMILARITY
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for leadership")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search with primary queries
        logger.debug(f"Trying primary search queries for leadership...")
        for query in search_queries:
            docs = search_pinecone_for_context(
                query, company_slug, pinecone_index, embeddings,
                limit=PINECONE_SEARCH_LIMIT,
                min_similarity=PINECONE_MIN_SIMILARITY
            )
            context_docs.extend(docs)
        
        # If no results, try fallback queries
        if not context_docs:
            logger.info(f"No results with primary queries, trying fallback queries...")
            for query in fallback_queries:
                docs = search_pinecone_for_context(
                    query, company_slug, pinecone_index, embeddings,
                    limit=PINECONE_SEARCH_LIMIT,
                    min_similarity=PINECONE_MIN_SIMILARITY
                )
                context_docs.extend(docs)
        
        if context_docs:
            logger.info(f"👥 Using {len(context_docs)} Pinecone results for leadership extraction")
            # Use enriched context with chunk information
            context_text, chunk_mapping = build_enriched_context(context_docs)
        else:
            # No Pinecone results - check fallback strategy
            if FALLBACK_STRATEGY == 'pinecone_only':
                logger.error("👥 ❌ No Pinecone results for leadership - ABORTING (pinecone_only strategy)")
                raise ValueError("No Pinecone context available for leadership")
            else:
                logger.warning(f"👥 ⚠️  No Pinecone results for leadership - Falling back to raw text ({FALLBACK_STRATEGY})")
                context_text = json.dumps(pages_text, indent=2)[:3000]
                chunk_mapping = {}
    
    # Build chunk ID reference for prompt
    chunk_ids_ref = "\n".join([
        f"  • {page_type}: {', '.join(ids)}"
        for page_type, ids in chunk_mapping.items()
    ]) if chunk_mapping else "None (using raw text fallback)"
    
    prompt = f"""Extract leadership and key team members for company "{company_slug}" from web content:

{context_text}

For each person, extract:
- Full name
- Current role (CEO, CTO, CPO, Founder, Executive, etc.)
- Whether they are a founder
- Start date at company
- Education background and university
- LinkedIn profile URL
- Previous companies/roles and employment history

PROVENANCE FIELD FOR EACH PERSON:
- source_url: Page type only (e.g., "careers", "about", "blog") - NOT vector IDs or chunk references
- crawled_at: Date in YYYY-MM-DD format
- chunk_id: List of chunk identifiers that supported extracting this leadership info
  * Format: ["vector_id#chunk_index", ...]
  * Examples: ["abridge_careers_c3a0a730#25.0", "abridge_about_6858d285#10.0"]

Available chunk IDs by page type:
{chunk_ids_ref}

Generate person_id from full name (e.g., john-doe from John Doe).
Return a list of Leadership objects. Use only explicitly stated information."""
    
    try:
        class LeadershipList(BaseModel):
            leadership: List[Leadership] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=LeadershipList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"👥 ✓ Extracted {len(result.leadership)} leadership members")
        return result.leadership
    except Exception as e:
        logger.warning(f"👥 Error extracting leadership: {e}")
        return []


def extract_visibility(
    client, 
    company_slug: str,  # Changed from company_id to company_slug
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> Optional[Visibility]:
    """Extract visibility and public metrics using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"⭐ Extracting visibility for {company_slug}...")
    
    # Search queries for visibility data - using content from pages
    search_queries = [
        f"{company_slug} news mentions press coverage",
        f"{company_slug} GitHub repository stars",
        f"{company_slug} awards recognition industry",
        f"{company_slug} media coverage publicity",
        f"{company_slug} social media followers engagement",
        f"industry recognition metrics impact",
    ]
    
    # Fallback queries if primary queries return no results
    fallback_queries = [
        "news",
        "award",
        "GitHub",
        "rating",
        "recognition",
        "mention",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    chunk_mapping = {}
    
    global USE_RAW_TEXT
    global FALLBACK_STRATEGY
    global PINECONE_SEARCH_LIMIT
    global PINECONE_MIN_SIMILARITY
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for visibility")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search with primary queries
        logger.debug(f"Trying primary search queries for visibility...")
        for query in search_queries:
            docs = search_pinecone_for_context(
                query, company_slug, pinecone_index, embeddings,
                limit=PINECONE_SEARCH_LIMIT,
                min_similarity=PINECONE_MIN_SIMILARITY
            )
            context_docs.extend(docs)
        
        # If no results, try fallback queries
        if not context_docs:
            logger.info(f"No results with primary queries, trying fallback queries...")
            for query in fallback_queries:
                docs = search_pinecone_for_context(
                    query, company_slug, pinecone_index, embeddings,
                    limit=PINECONE_SEARCH_LIMIT,
                    min_similarity=PINECONE_MIN_SIMILARITY
                )
                context_docs.extend(docs)
        
        if context_docs:
            logger.info(f"⭐ Using {len(context_docs)} Pinecone documents for visibility extraction")
            # Use enriched context with chunk information
            context_text, chunk_mapping = build_enriched_context(context_docs)
        else:
            # No Pinecone results - check fallback strategy
            if FALLBACK_STRATEGY == 'pinecone_only':
                logger.error("⭐ ❌ No Pinecone results for visibility - ABORTING (pinecone_only strategy)")
                raise ValueError("No Pinecone context available for visibility")
            else:
                logger.warning(f"⭐ ⚠️  No Pinecone results for visibility - Falling back to raw text ({FALLBACK_STRATEGY})")
                context_text = json.dumps(pages_text, indent=2)[:3000]
    
    # Build chunk ID reference for prompt
    chunk_ids_ref = "\n".join([
        f"  • {page_type}: {', '.join(ids)}"
        for page_type, ids in chunk_mapping.items()
    ]) if chunk_mapping else "None (using raw text fallback)"
    
    prompt = f"""Extract visibility and public metrics for company "{company_slug}" from web content:

{context_text}

Extract:
- News mentions or press coverage indicators (count and sentiment)
- Sentiment indicators (positive/negative/neutral)
- GitHub repository stars or popularity metrics
- Glassdoor rating if available
- Awards or industry recognition
- Social media followers if mentioned

PROVENANCE FIELD:
- source_url: Page type only (e.g., "blog", "product", "careers") - NOT vector IDs or chunk references
- crawled_at: Date in YYYY-MM-DD format
- chunk_id: List of chunk identifiers that supported extracting these visibility metrics
  * Format: ["vector_id#chunk_index", ...]
  * Examples: ["abridge_blog_f1388ab9#2.0", "abridge_careers_c3a0a730#25.0"]

Available chunk IDs by page type:
{chunk_ids_ref}

Return a Visibility object with as_of set to today. Use only explicitly stated metrics."""
    
    try:
        visibility = client.chat.completions.create(
            model="gpt-4o",
            response_model=Visibility,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"⭐ ✓ Extracted visibility metrics")
        return visibility
    except Exception as e:
        logger.warning(f"⭐ Error extracting visibility: {e}")
        return None


def process_company(company_slug: str, verbose: bool = False):
    """Process a single company: extract structured data using Pinecone vector search.
    
    This function:
    1. Checks if source files have changed since last extraction
    2. Skips extraction if no changes detected
    3. Runs full extraction only if files changed or first-time extraction
    4. Saves results and updates metadata
    """
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Company: {company_slug}")
    logger.info(f"{'='*60}")
    
    pinecone_index = None
    embeddings = None
    namespace = None
    
    try:
        # Load all page texts
        pages_text = load_all_company_pages(company_slug)
        if not pages_text:
            logger.warning(f"No page texts found for {company_slug}")
            return None
        
        # ─────────────────────────────────────────────────────────────────────
        # CHECK IF EXTRACTION IS NEEDED (based on file changes or missing payload)
        # ─────────────────────────────────────────────────────────────────────
        extraction_needed, reason = check_if_extraction_needed(company_slug, pages_text)
        
        if not extraction_needed:
            logger.info(f"\n✓ Skipping extraction for {company_slug} (no file changes and payload exists)")
            # Return a success indicator instead of None (skipping is SUCCESS, not failure)
            return {
                "status": "skipped",
                "reason": reason,
                "company_slug": company_slug,
                "message": "Extraction not needed - files unchanged and payload exists"
            }
        
        # Log why extraction is needed
        reason_text = {
            "first_time": "first-time extraction",
            "files_changed": "source files have changed",
            "payload_missing": "payload file is missing"
        }.get(reason, "unknown reason")
        
        logger.info(f"✓ Extraction needed - {reason_text}\n")
        
        # Initialize LLM client
        client = get_llm_client()
        
        # Initialize Pinecone and embeddings (for searching, not indexing)
        logger.info("Initializing Pinecone for semantic search...")
        try:
            pinecone_index = get_pinecone_client()
            embeddings = get_embeddings_model()
        except Exception as e:
            logger.warning(f"Could not initialize Pinecone: {e}")
            logger.warning("Will use raw text mode instead")
            global USE_RAW_TEXT
            USE_RAW_TEXT = True
        
        # Extract structured data
        logger.info("Starting structured extraction with semantic search...")
        
        # 1. Extract company info
        company = extract_company_info(
            client, 
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        if not company:
            logger.error(f"Failed to extract company info for {company_slug}")
            return None
        
        company_id = company.company_id
        logger.info(f"Company ID: {company_id}")
        
        # 2. Extract events
        events = extract_events(
            client, 
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 3. Extract snapshots
        snapshots = extract_snapshots(
            client, 
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 4. Extract products
        products = extract_products(
            client, 
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 5. Extract leadership
        leadership = extract_leadership(
            client, 
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 6. Extract visibility
        visibility_list = []
        visibility = extract_visibility(
            client, 
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        if visibility:
            visibility_list = [visibility]
        
        # Create payload
        payload = Payload(
            company_record=company,
            events=events,
            snapshots=snapshots,
            products=products,
            leadership=leadership,
            visibility=visibility_list,
            notes=f"Extracted with semantic search via Pinecone on {datetime.now().isoformat()}"
        )
        
        # Save results to data/payloads/
        payloads_dir = Path("data/payloads") 
        payloads_dir.mkdir(parents=True, exist_ok=True)
        
        payload_file = payloads_dir / f"{company_slug}.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(payload.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"\n✓ Saved extraction results to: {payload_file}")
        
        logger.info(f"  Company: {company.legal_name}")
        logger.info(f"  Events: {len(events)}")
        logger.info(f"  Snapshots: {len(snapshots)}")
        logger.info(f"  Products: {len(products)}")
        logger.info(f"  Leadership: {len(leadership)}")
        logger.info(f"  Visibility: {len(visibility_list)}")
        
        # ─────────────────────────────────────────────────────────────────────
        # UPDATE EXTRACTION METADATA (mark as extracted, save file hashes)
        # ─────────────────────────────────────────────────────────────────────
        update_extraction_metadata(company_slug, pages_text)
        
        # ALSO SAVE the company_id to metadata so we can verify the payload exists later
        metadata = load_extraction_metadata(company_slug)
        if metadata:
            metadata["company_id"] = company_id  # Store for later verification
            save_extraction_metadata(company_slug, metadata)
        
        logger.info(f"✓ Updated extraction metadata for {company_slug}")
        
        return payload
        
    except Exception as e:
        logger.error(f"Error processing company {company_slug}: {e}", exc_info=True)
        return None


def discover_companies_from_raw_data() -> List[str]:
    """Discover companies from raw data directory structure."""
    logger = logging.getLogger('structured_extraction')
    
    raw_dir = Path("data/raw")
    companies = []
    
    if not raw_dir.exists():
        logger.warning(f"Raw data directory not found: {raw_dir}")
        return companies
    
    for company_dir in raw_dir.iterdir():
        if company_dir.is_dir():
            company_slug = company_dir.name
            companies.append(company_slug)
    
    logger.info(f"Discovered {len(companies)} companies from raw data")
    return companies


def main():
    logger = setup_logging('structured_extraction')
    logger.info("=== Starting Structured Extraction (RAG with Pinecone) ===")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Extract structured data from web scrapes using semantic search")
    parser.add_argument('--company-slug', type=str, help='Specific company slug to process')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--all', action='store_true', help='Process all companies')
    parser.add_argument(
        '--fallback-strategy',
        type=str,
        choices=['pinecone_only', 'raw_only', 'pinecone_first'],
        default='pinecone_only',
        help='Strategy for handling Pinecone failures: pinecone_only (fail if no Pinecone), raw_only (always use raw text), pinecone_first (prefer Pinecone, fallback to raw)'
    )
    
    args = parser.parse_args()
    
    # Store fallback strategy globally for use in extraction functions
    global FALLBACK_STRATEGY
    FALLBACK_STRATEGY = args.fallback_strategy
    logger.info(f"Fallback strategy: {args.fallback_strategy}")
    
    try:
        if args.company_slug:
            # Process specific company
            logger.info(f"Processing specific company: {args.company_slug}")
            result = process_company(args.company_slug, args.verbose)
            if result:
                # Check if it was skipped or successfully processed
                if isinstance(result, dict) and result.get("status") == "skipped":
                    logger.info(f"✓ Skipped extraction for {args.company_slug} (no changes needed)")
                else:
                    logger.info(f"✓ Successfully processed {args.company_slug}")
            else:
                logger.error(f"✗ Failed to process {args.company_slug}")
                sys.exit(1)
        elif args.all:
            # Process all companies
            companies = discover_companies_from_raw_data()
            
            if not companies:
                logger.warning("No companies found in data/raw directory")
                return
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {len(companies)} companies")
            logger.info(f"{'='*60}\n")
            
            results = []
            for idx, company_slug in enumerate(companies, 1):
                logger.info(f"[{idx}/{len(companies)}] {company_slug}")
                result = process_company(company_slug, args.verbose)
                if result:
                    # Check if it was skipped or successfully processed
                    if isinstance(result, dict) and result.get("status") == "skipped":
                        results.append({
                            'company_slug': company_slug,
                            'success': True,
                            'status': 'skipped'
                        })
                    else:
                        results.append({
                            'company_slug': company_slug,
                            'success': True,
                            'company_id': result.company_record.company_id if hasattr(result, 'company_record') else None
                        })
                else:
                    results.append({
                        'company_slug': company_slug,
                        'success': False
                    })
            
            # Summary
            logger.info(f"\n{'='*60}")
            logger.info("=== EXTRACTION COMPLETE ===")
            logger.info(f"{'='*60}")
            
            successful = sum(1 for r in results if r['success'])
            logger.info(f"Successfully processed: {successful}/{len(results)}")
            
            if successful > 0:
                logger.info("\nSuccessful companies:")
                for r in results:
                    if r['success']:
                        logger.info(f"  ✓ {r['company_slug']} → {r['company_id']}")
            
            failed = [r for r in results if not r['success']]
            if failed:
                logger.info("\nFailed companies:")
                for r in failed:
                    logger.info(f"  ✗ {r['company_slug']}")
        else:
            parser.print_help()
            logger.error("Please specify --company-slug <slug>, --all, or use --help")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
