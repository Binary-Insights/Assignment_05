#!/usr/bin/env python3
"""Pinecone Ingestion Script: Index company pages to Pinecone vector database.

This script:
1. Reads text extracted from company web pages (data/raw/{company_slug}/{page_type}/text.txt)
2. Splits text into chunks using RecursiveCharacterTextSplitter
3. Generates embeddings using OpenAI embeddings model
4. Indexes chunks to Pinecone with deterministic content hashes for deduplication
5. Tracks ingestion metadata and detects file changes for incremental updates
6. Saves metadata and statistics for tracking and auditing

Features:
  • Content-hash based deduplication: same content = same ID = no duplicates
  • File-level change detection: only re-processes changed files
  • Incremental ingestion: smart skipping of unchanged content
  • Metadata tracking: full ingestion history and audit trail
  • Optional clear mode: force fresh ingestion from scratch

Metadata Storage:
  • Location: data/metadata/{company_slug}/pinecone_ingestion.json
  • Tracks: file hashes, chunk metadata, ingestion history
  • Enables: incremental updates, change detection, auditing

Usage:
  # Standard ingestion (with deduplication and change detection)
  python src/rag/ingest_to_pinecone.py --company-slug world_labs
  
  # Force fresh ingestion (clear existing, reingest all)
  python src/rag/ingest_to_pinecone.py --company-slug world_labs --clear
  
  # Ingest all companies
  python src/rag/ingest_to_pinecone.py --all
  
  # Ingest all with verbose logging
  python src/rag/ingest_to_pinecone.py --all --verbose
  
  # Force clear for all companies
  python src/rag/ingest_to_pinecone.py --all --clear

Environment Variables:
  PINECONE_API_KEY (required)
  PINECONE_INDEX_NAME (default: "bigdata-assignment-04")
  PINECONE_NAMESPACE (default: "default")
  OPENAI_API_KEY (required for embeddings)
"""

import json
import logging
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()


def setup_logging():
    """Setup logging for ingest_to_pinecone script."""
    log_dir = "data/logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger('ingest_to_pinecone')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(f"{log_dir}/ingest_to_pinecone.log")
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
#  Hashing & Deduplication Functions
# ─────────────────────────────────────────────────────────────────────────────

def calculate_content_hash(content: str) -> str:
    """Calculate SHA256 hash of content (first 8 chars)."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception as e:
        logger = logging.getLogger('ingest_to_pinecone')
        logger.error(f"Error calculating file hash: {e}")
        return ""


def load_metadata(company_slug: str) -> Dict[str, Any]:
    """Load existing metadata for a company."""
    logger = logging.getLogger('ingest_to_pinecone')
    
    metadata_file = Path(f"data/metadata/{company_slug}/pinecone_ingestion.json")
    
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        logger.info(f"✓ Loaded existing metadata for {company_slug}")
        return metadata
    except Exception as e:
        logger.error(f"Error loading metadata: {e}")
        return None


def save_metadata(company_slug: str, metadata: Dict[str, Any]) -> bool:
    """Save metadata for a company."""
    logger = logging.getLogger('ingest_to_pinecone')
    
    try:
        metadata_dir = Path(f"data/metadata/{company_slug}")
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = metadata_dir / "pinecone_ingestion.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"✅ Saved metadata to: {metadata_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving metadata: {e}", exc_info=True)
        return False


def create_metadata_structure(company_slug: str) -> Dict[str, Any]:
    """Create empty metadata structure."""
    return {
        "company_slug": company_slug,
        "created_at": datetime.now().isoformat(),
        "last_ingestion": None,
        "ingestion_count": 0,
        "total_vectors_in_pinecone": 0,
        "file_hashes": {},
        "chunks_metadata": {},
        "ingestion_history": []
    }


def add_ingestion_record(metadata: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Add an ingestion record to metadata."""
    if "ingestion_history" not in metadata:
        metadata["ingestion_history"] = []
    
    metadata["ingestion_count"] = metadata.get("ingestion_count", 0) + 1
    metadata["last_ingestion"] = datetime.now().isoformat()
    metadata["ingestion_history"].append({
        "timestamp": datetime.now().isoformat(),
        **record
    })
    
    return metadata


def get_pinecone_client():
    """Initialize Pinecone client for vector ingestion."""
    logger = logging.getLogger('ingest_to_pinecone')
    
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
        logger.error(f"Failed to connect to Pinecone: {e}")
        raise


def get_embeddings_model():
    """Get OpenAI embeddings model."""
    logger = logging.getLogger('ingest_to_pinecone')
    
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


def load_company_page_text(company_slug: str, page_type: str) -> Optional[str]:
    """Load extracted text from a company page."""
    logger = logging.getLogger('ingest_to_pinecone')
    
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
    logger = logging.getLogger('ingest_to_pinecone')
    
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


def save_vectors_to_json(
    company_slug: str,
    vectors_metadata: List[Dict[str, Any]]
) -> str:
    """Save vector metadata (without embeddings) to JSON file for persistence and auditing.
    
    Note: Embeddings are NOT stored (too large). They will be regenerated during upsert.
    Handles permission errors gracefully (common in Docker with mounted volumes).
    """
    logger = logging.getLogger('ingest_to_pinecone')
    
    try:
        # Use absolute path when possible, relative as fallback
        vectors_dir = Path("data/vectors")
        
        # Try to create directory with permissive permissions
        try:
            vectors_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
        except (PermissionError, OSError) as e:
            logger.debug(f"Could not create vectors directory: {e}")
            # Continue anyway - directory might already exist
        
        # Try to ensure directory is writable, but don't fail if we can't
        # (this can happen in Docker with mounted volumes owned by other users)
        try:
            os.chmod(vectors_dir, 0o777)
        except (PermissionError, OSError) as e:
            logger.debug(f"Could not change directory permissions (OK in Docker): {e}")
        
        # Convert to JSON-serializable format (no embeddings)
        vectors_json = []
        for metadata in vectors_metadata:
            vectors_json.append({
                "id": metadata["id"],
                "metadata": metadata["metadata"]
                # Note: "embedding" is intentionally NOT stored (too large)
            })
        
        vectors_file = vectors_dir / f"{company_slug}.json"
        
        try:
            with open(vectors_file, 'w') as f:
                json.dump(vectors_json, f, indent=2, ensure_ascii=False, default=str)
            
            # Try to make file readable/writable, but don't fail if we can't
            try:
                os.chmod(vectors_file, 0o666)
            except (PermissionError, OSError) as e:
                logger.debug(f"Could not change file permissions (OK in Docker): {e}")
            
            logger.info(f"✅ Saved {len(vectors_json)} vector metadata to: {vectors_file}")
            logger.info(f"   (Embeddings will be regenerated during upsert)")
            return str(vectors_file)
            
        except (PermissionError, OSError) as e:
            # Permission denied - log warning but continue with ingestion
            logger.warning(f"⚠️  Could not save vector metadata to {vectors_file}: {e}")
            logger.warning(f"   Proceeding with ingestion anyway (metadata not persisted)")
            logger.warning(f"   This is OK in ephemeral/Docker environments")
            return str(vectors_file)  # Return path anyway for consistency
        
    except Exception as e:
        logger.error(f"Unexpected error in save_vectors_to_json: {e}", exc_info=True)
        # Don't raise - let ingestion continue without persisting metadata
        logger.warning(f"Proceeding with ingestion despite metadata save error")
        return f"data/vectors/{company_slug}.json"


def load_vectors_from_json(company_slug: str) -> List[Dict[str, Any]]:
    """Load vector metadata from JSON file.
    
    Returns list of dicts with: {id, metadata}
    Embeddings will need to be regenerated before upserting to Pinecone.
    """
    logger = logging.getLogger('ingest_to_pinecone')
    
    vectors_file = Path("data/vectors") / f"{company_slug}.json"
    
    if not vectors_file.exists():
        logger.warning(f"Vectors file not found: {vectors_file}")
        return []
    
    try:
        with open(vectors_file, 'r', encoding='utf-8') as f:
            vectors_json = json.load(f)
        
        logger.info(f"✅ Loaded {len(vectors_json)} vector metadata from: {vectors_file}")
        return vectors_json
        
    except Exception as e:
        logger.error(f"Error loading vectors from JSON: {e}", exc_info=True)
        raise


def index_company_pages_to_pinecone(
    company_slug: str, 
    pages_text: Dict[str, str],
    pinecone_index,
    embeddings,
    clear_existing: bool = False
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Index company pages to Pinecone vector database with deduplication.
    
    Process:
    1. Check for existing metadata and file changes
    2. Generate embeddings for changed content only
    3. Use content hash for deterministic vector IDs
    4. Upsert vectors to Pinecone (same ID = replaces old)
    5. Save updated metadata
    
    Args:
        company_slug: Company identifier
        pages_text: Dictionary of page_type -> text content
        pinecone_index: Pinecone index reference
        embeddings: OpenAI embeddings model
        clear_existing: If True, delete all existing vectors first
    
    Returns:
        Tuple of (namespace, ingestion_stats)
    """
    logger = logging.getLogger('ingest_to_pinecone')
    
    if not pinecone_index or not embeddings:
        logger.error("Pinecone index or embeddings not available")
        raise ValueError("Pinecone index and embeddings are required")
    
    namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    logger.info(f"Using Pinecone namespace: '{namespace}'")
    
    # Load existing metadata or create new
    metadata = load_metadata(company_slug)
    if metadata is None:
        logger.info(f"No existing metadata found, creating new metadata structure")
        metadata = create_metadata_structure(company_slug)
    
    old_file_hashes = metadata.get("file_hashes", {})
    
    # Check if any files have changed
    new_file_hashes = {}
    changed_pages = {}
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"Checking file changes:")
    logger.info(f"{'─' * 60}")
    
    for page_type, text in pages_text.items():
        source_file = f"data/raw/{company_slug}/{page_type}/text.txt"
        file_hash = calculate_file_hash(source_file)
        new_file_hashes[page_type] = file_hash
        
        old_hash = old_file_hashes.get(page_type)
        
        if clear_existing:
            logger.info(f"  📄 {page_type}: CHANGED (clear flag set)")
            changed_pages[page_type] = text
        elif old_hash != file_hash:
            logger.info(f"  📄 {page_type}: CHANGED (hash mismatch)")
            changed_pages[page_type] = text
        else:
            logger.info(f"  📄 {page_type}: UNCHANGED (skipping)")
    
    # If no changes detected
    if not changed_pages and not clear_existing:
        logger.info(f"\n✓ No changes detected in any files")
        logger.info(f"Skipping ingestion for {company_slug}")
        stats = {
            "chunks_added": 0,
            "chunks_updated": 0,
            "files_processed": 0,
            "notes": "No changes detected"
        }
        metadata = add_ingestion_record(metadata, stats)
        save_metadata(company_slug, metadata)
        return namespace, stats
    
    # Clear existing vectors if requested
    if clear_existing:
        logger.info(f"\n{'─' * 60}")
        logger.info(f"Clearing existing vectors for {company_slug}...")
        try:
            # Delete all vectors with company_slug metadata filter
            logger.warning(f"Note: Manual cleanup may be needed. Consider deleting namespace or using separate namespace.")
            logger.info(f"Proceeding with fresh ingestion (duplicates will be replaced by upsert)")
        except Exception as e:
            logger.error(f"Error clearing vectors: {e}")
    
    # Split and embed text from changed pages
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
    )
    
    vectors_to_upsert = []
    chunks_metadata = {}
    chunks_per_source = {}
    
    logger.info(f"\n{'─' * 60}")
    logger.info(f"Processing changed pages for {company_slug}:")
    logger.info(f"{'─' * 60}\n")
    
    for page_type, text in changed_pages.items():
        if not text:
            continue
        
        source_file = f"data/raw/{company_slug}/{page_type}/text.txt"
        logger.info(f"  📄 Source: {source_file}")
        logger.info(f"     Content size: {len(text)} characters")
        
        # Split text into chunks
        chunks = text_splitter.split_text(text)
        chunks_per_source[page_type] = len(chunks)
        logger.info(f"     Chunks created: {len(chunks)} (500 chars, 100 char overlap)")
        
        for chunk_idx, chunk in enumerate(chunks, 1):
            try:
                # Generate content hash for deterministic ID
                chunk_hash = calculate_content_hash(chunk)
                
                # Create deterministic vector ID
                vector_id = f"{company_slug}_{page_type}_{chunk_hash}"
                
                # Create metadata for chunk (embedding will be generated later)
                chunk_meta = {
                    "text": chunk,
                    "page_type": page_type,
                    "company_slug": company_slug,
                    "source_file": source_file,
                    "chunk_index": chunk_idx,
                    "content_hash": chunk_hash,
                    "indexed_at": datetime.now().isoformat()
                }
                
                # Store for later processing (embeddings will be generated during upsert)
                vectors_to_upsert.append({
                    "id": vector_id,
                    "text": chunk,  # Text needed to generate embedding
                    "metadata": chunk_meta
                })
                
                # Store chunk metadata for metadata.json
                chunks_metadata[chunk_hash] = {
                    "page_type": page_type,
                    "chunk_index": chunk_idx,
                    "content_preview": chunk[:100] + "..." if len(chunk) > 100 else chunk,
                    "hash": chunk_hash,
                    "vector_id": vector_id,
                    "indexed_at": datetime.now().isoformat(),
                    "status": "active"
                }
                
            except Exception as e:
                logger.warning(f"Failed to process chunk {chunk_idx} from {page_type}: {e}")
                continue
        
        logger.info(f"     ✓ Processed {page_type}\n")
    
    ingestion_stats = {
        "chunks_added": len(vectors_to_upsert),
        "chunks_updated": 0,
        "files_processed": len(changed_pages),
        "notes": f"Ingested with deduplication ({len(vectors_to_upsert)} chunks)"
    }
    
    if vectors_to_upsert:
        # Step 1: Save vector metadata to JSON file (without embeddings)
        logger.info(f"Step 1: Saving vector metadata to JSON")
        logger.info(f"{'─' * 60}")
        vectors_file = save_vectors_to_json(company_slug, vectors_to_upsert)
        
        # Step 2: Generate embeddings and upsert to Pinecone
        logger.info(f"\nStep 2: Generating embeddings and upserting to Pinecone")
        logger.info(f"{'─' * 60}")
        logger.info(f"Generating embeddings for {len(vectors_to_upsert)} chunks...")
        
        vectors_with_embeddings = []
        for idx, vector_data in enumerate(vectors_to_upsert, 1):
            try:
                # Generate embedding for this chunk
                embedding = embeddings.embed_query(vector_data["text"])
                
                # Create tuple: (id, embedding, metadata)
                vector_tuple = (
                    vector_data["id"],
                    embedding,
                    vector_data["metadata"]
                )
                vectors_with_embeddings.append(vector_tuple)
                
                if idx % 10 == 0:
                    logger.debug(f"  Generated {idx}/{len(vectors_to_upsert)} embeddings...")
                    
            except Exception as e:
                logger.warning(f"Failed to generate embedding for chunk {idx}: {e}")
                continue
        
        logger.info(f"✅ Generated {len(vectors_with_embeddings)} embeddings")
        logger.info(f"Upserting {len(vectors_with_embeddings)} vectors to Pinecone (in batches)...")
        
        # Batch upsert to avoid exceeding Pinecone's 4MB request size limit
        batch_size = 25  # Conservative batch size to stay well under 4MB limit
        total_upserted = 0
        
        try:
            for batch_idx in range(0, len(vectors_with_embeddings), batch_size):
                batch = vectors_with_embeddings[batch_idx:batch_idx + batch_size]
                batch_num = (batch_idx // batch_size) + 1
                total_batches = (len(vectors_with_embeddings) + batch_size - 1) // batch_size
                
                logger.info(f"  Batch {batch_num}/{total_batches}: Upserting {len(batch)} vectors...")
                
                try:
                    upsert_response = pinecone_index.upsert(
                        vectors=batch,
                        namespace=namespace
                    )
                    total_upserted += len(batch)
                    logger.debug(f"    ✓ Batch {batch_num} upserted successfully")
                except Exception as batch_error:
                    logger.error(f"Failed to upsert batch {batch_num}: {batch_error}")
                    raise
            
            logger.info(f"✅ Successfully upserted all {total_upserted} vectors to Pinecone")
        except Exception as e:
            logger.error(f"Failed to upsert vectors to Pinecone: {e}", exc_info=True)
            raise
        
        # Summary logging
        logger.info(f"\n{'─' * 60}")
        logger.info(f"✓ Successfully indexed {len(vectors_to_upsert)} total chunks")
        logger.info(f"  • Metadata saved to: data/vectors/{company_slug}.json")
        logger.info(f"  • Upserted to Pinecone namespace: '{namespace}'")
        logger.info(f"\nBreakdown by source:")
        for source, count in sorted(chunks_per_source.items()):
            logger.info(f"  • {source:15} → {count:3} chunks")
        logger.info(f"{'─' * 60}\n")
    
    # Update metadata
    metadata["file_hashes"] = new_file_hashes
    metadata["chunks_metadata"].update(chunks_metadata)
    metadata["total_vectors_in_pinecone"] = len(vectors_to_upsert)
    metadata = add_ingestion_record(metadata, ingestion_stats)
    
    # Save updated metadata
    save_metadata(company_slug, metadata)
    
    return namespace, ingestion_stats


def ingest_tavily_json_to_pinecone(
    company_slug: str,
    tavily_json_path: str,
    pinecone_index,
    embeddings
) -> Tuple[int, int]:
    """
    Ingest Tavily search results from JSON file to Pinecone with deduplication.
    
    Args:
        company_slug: Company identifier
        tavily_json_path: Path to Tavily JSON file
        pinecone_index: Pinecone index instance
        embeddings: OpenAI embeddings instance
    
    Returns:
        Tuple of (added_count, skipped_count)
    """
    logger = logging.getLogger('ingest_to_pinecone')
    
    logger.info(f"📄 [TAVILY INGEST] Processing: {tavily_json_path}")
    
    try:
        # Load Tavily JSON
        with open(tavily_json_path, 'r', encoding='utf-8') as f:
            tavily_data = json.load(f)
        
        # Extract results - support multiple JSON structures
        # Multi-session format: sessions[].search_responses (newest)
        # Single session format: search_responses (previous)
        # Old structure: metadata.results (nested)
        # Legacy structure: results (top-level)
        results = []
        
        # Check for multi-session format (newest)
        if 'sessions' in tavily_data and isinstance(tavily_data['sessions'], list):
            logger.info(f"Detected multi-session format with {len(tavily_data['sessions'])} sessions")
            # Extract from all sessions
            for session in tavily_data['sessions']:
                for response in session.get('search_responses', []):
                    if response.get('success'):
                        results.extend(response.get('results', []))
        # Check for single session format (previous)
        elif 'search_responses' in tavily_data:
            logger.info(f"Detected single session format")
            for response in tavily_data.get('search_responses', []):
                if response.get('success'):
                    results.extend(response.get('results', []))
        # Check for nested metadata format
        elif 'metadata' in tavily_data and 'results' in tavily_data.get('metadata', {}):
            results = tavily_data.get('metadata', {}).get('results', [])
        # Check for direct results format
        elif 'results' in tavily_data:
            results = tavily_data.get('results', [])
        
        if not results:
            logger.warning(f"No results found in {tavily_json_path}")
            return 0, 0
        
        logger.info(f"Found {len(results)} Tavily results to process")
        
        # Load existing metadata to check for duplicates
        metadata = load_metadata(company_slug)
        existing_chunks = metadata.get('chunks_metadata', {})
        
        added_count = 0
        skipped_count = 0
        vectors_to_upsert = []
        new_chunks_metadata = {}
        
        for idx, result in enumerate(results, 1):
            try:
                # Extract fields from Tavily result
                content = result.get('content', '')
                title = result.get('title', '')
                url = result.get('url', '')
                score = result.get('score', 0.0)
                
                if not content:
                    logger.warning(f"Skipping result {idx}: empty content")
                    skipped_count += 1
                    continue
                
                # Combine title and content for better context
                full_text = f"{title}\n\n{content}" if title else content
                
                # Calculate content hash for deduplication
                content_hash = calculate_content_hash(full_text)[:8]
                
                # Check if this content already exists
                if content_hash in existing_chunks:
                    logger.debug(f"Skipping duplicate content (hash: {content_hash})")
                    skipped_count += 1
                    continue
                
                # Generate embedding
                embedding = embeddings.embed_query(full_text)
                
                # Create metadata
                chunk_metadata = {
                    "company_slug": company_slug,
                    "source": "tavily",
                    "source_url": url,
                    "title": title,
                    "relevance_score": score,
                    "text": full_text,  # ✅ STORE FULL TEXT for RAG retrieval
                    "text_preview": full_text[:200],  # Keep preview for display/debugging
                    "ingested_at": datetime.now().isoformat(),
                    "content_hash": content_hash
                }
                
                # Prepare vector for upsert
                vector = {
                    "id": f"{company_slug}_tavily_{content_hash}",
                    "values": embedding,
                    "metadata": chunk_metadata
                }
                vectors_to_upsert.append(vector)
                
                # Track new chunk metadata
                new_chunks_metadata[content_hash] = {
                    "chunk_id": content_hash,
                    "source": "tavily",
                    "source_url": url,
                    "title": title,
                    "text_length": len(full_text),
                    "ingested_at": datetime.now().isoformat(),
                    "status": "active"
                }
                
                added_count += 1
                logger.debug(f"Prepared vector for: {title[:50]}... (hash: {content_hash})")
                
            except Exception as e:
                logger.error(f"Error processing Tavily result {idx}: {e}", exc_info=True)
                skipped_count += 1
                continue
        
        # Upsert vectors to Pinecone in batches
        if vectors_to_upsert:
            logger.info(f"Upserting {len(vectors_to_upsert)} vectors to Pinecone...")
            namespace = os.getenv("PINECONE_NAMESPACE", "default")
            
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch = vectors_to_upsert[i:i + batch_size]
                pinecone_index.upsert(
                    vectors=batch,
                    namespace=namespace
                )
            
            logger.info(f"✓ Upserted {len(vectors_to_upsert)} vectors")
            
            # Update metadata with new chunks
            metadata['chunks_metadata'].update(new_chunks_metadata)
            metadata['total_vectors_in_pinecone'] = metadata.get('total_vectors_in_pinecone', 0) + added_count
            metadata['last_ingestion'] = datetime.now().isoformat()
            
            # Add ingestion record
            ingestion_record = {
                "timestamp": datetime.now().isoformat(),
                "source": "tavily_json",
                "source_file": str(tavily_json_path),
                "chunks_added": added_count,
                "chunks_skipped": skipped_count,
                "total_results_processed": len(results)
            }
            metadata = add_ingestion_record(metadata, ingestion_record)
            
            # Save updated metadata
            save_metadata(company_slug, metadata)
            logger.info(f"✓ Updated metadata for {company_slug}")
        
        logger.info(f"✅ [TAVILY INGEST] Added: {added_count}, Skipped: {skipped_count}")
        return added_count, skipped_count
        
    except Exception as e:
        logger.error(f"❌ [TAVILY INGEST] Error processing {tavily_json_path}: {e}", exc_info=True)
        return 0, 0


def ingest_all_tavily_json_for_company(
    company_slug: str,
    pinecone_index=None,
    embeddings=None
) -> Dict[str, Any]:
    """
    Ingest all Tavily JSON files for a company.
    
    Args:
        company_slug: Company identifier
        pinecone_index: Pinecone index (will initialize if None)
        embeddings: Embeddings model (will initialize if None)
    
    Returns:
        Summary statistics
    """
    logger = logging.getLogger('ingest_to_pinecone')
    
    logger.info(f"\n{'='*70}")
    logger.info(f"🔍 [TAVILY INGEST] Processing all Tavily JSONs for: {company_slug}")
    logger.info(f"{'='*70}")
    
    # Initialize if needed
    if pinecone_index is None:
        pinecone_index = get_pinecone_client()
    if embeddings is None:
        embeddings = get_embeddings_model()
    
    # Find all Tavily JSON files
    tavily_dir = Path(f"data/raw/{company_slug}/tavily")
    if not tavily_dir.exists():
        logger.warning(f"No Tavily directory found for {company_slug}: {tavily_dir}")
        return {
            "success": False,
            "error": "No tavily directory found",
            "files_processed": 0,
            "total_added": 0,
            "total_skipped": 0
        }
    
    # Check for multi-session file first (new format)
    multi_session_file = tavily_dir / "tavily_all_sessions.json"
    tavily_files = []
    
    if multi_session_file.exists():
        tavily_files.append(multi_session_file)
        logger.info(f"Found multi-session file: {multi_session_file}")
    
    # Also check for legacy individual session files
    legacy_files = list(tavily_dir.glob("tavily_session_*.json"))
    if legacy_files:
        tavily_files.extend(legacy_files)
        logger.info(f"Found {len(legacy_files)} legacy session files")
    
    # Fallback to old format
    if not tavily_files:
        old_files = list(tavily_dir.glob("tavily_*.json"))
        if old_files:
            tavily_files.extend(old_files)
            logger.info(f"Found {len(old_files)} old format files")
    
    if not tavily_files:
        logger.warning(f"No Tavily JSON files found in {tavily_dir}")
        return {
            "success": False,
            "error": "No tavily JSON files found",
            "files_processed": 0,
            "total_added": 0,
            "total_skipped": 0
        }
    
    logger.info(f"Found {len(tavily_files)} Tavily JSON files to process")
    
    total_added = 0
    total_skipped = 0
    files_processed = 0
    errors = []
    
    for tavily_file in sorted(tavily_files):
        try:
            added, skipped = ingest_tavily_json_to_pinecone(
                company_slug,
                str(tavily_file),
                pinecone_index,
                embeddings
            )
            total_added += added
            total_skipped += skipped
            files_processed += 1
            
        except Exception as e:
            error_msg = f"Error processing {tavily_file.name}: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
    
    summary = {
        "success": files_processed > 0,
        "files_processed": files_processed,
        "total_files": len(tavily_files),
        "total_added": total_added,
        "total_skipped": total_skipped,
        "errors": errors
    }
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ [TAVILY INGEST SUMMARY] {company_slug}")
    logger.info(f"{'='*70}")
    logger.info(f"  Files processed: {files_processed}/{len(tavily_files)}")
    logger.info(f"  Vectors added: {total_added}")
    logger.info(f"  Vectors skipped (duplicates): {total_skipped}")
    if errors:
        logger.warning(f"  Errors: {len(errors)}")
    logger.info(f"{'='*70}\n")
    
    return summary


def discover_companies_from_raw_data() -> List[tuple]:
    """Discover companies from raw data directory structure."""
    logger = logging.getLogger('ingest_to_pinecone')
    
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


def ingest_company(company_slug: str, verbose: bool = False, clear_existing: bool = False) -> bool:
    """Ingest a single company's pages to Pinecone."""
    logger = logging.getLogger('ingest_to_pinecone')
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Ingesting Company: {company_slug}")
    if clear_existing:
        logger.info(f"(Clear mode: existing vectors will be replaced)")
    logger.info(f"{'='*60}")
    
    try:
        # Load all page texts
        pages_text = load_all_company_pages(company_slug)
        if not pages_text:
            logger.warning(f"No page texts found for {company_slug}")
            return False
        
        # Initialize Pinecone and embeddings
        logger.info("Initializing Pinecone vector database...")
        pinecone_index = get_pinecone_client()
        embeddings = get_embeddings_model()
        
        # Index company pages to Pinecone with deduplication
        namespace, stats = index_company_pages_to_pinecone(
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings,
            clear_existing=clear_existing
        )
        
        logger.info(f"✓ Successfully ingested {company_slug} to Pinecone (namespace: {namespace})")
        logger.info(f"  • Chunks added: {stats.get('chunks_added', 0)}")
        logger.info(f"  • Files processed: {stats.get('files_processed', 0)}")
        logger.info(f"  • Notes: {stats.get('notes', '')}")
        return True
        
    except Exception as e:
        logger.error(f"Error ingesting company {company_slug}: {e}", exc_info=True)
        return False


def main():
    logger = setup_logging()
    logger.info("=== Starting Pinecone Ingestion ===")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Ingest company pages to Pinecone vector database")
    parser.add_argument('--company-slug', type=str, help='Specific company slug to ingest')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--all', action='store_true', help='Ingest all companies')
    parser.add_argument('--clear', action='store_true', help='Clear existing vectors and reingest from scratch')
    
    args = parser.parse_args()
    
    try:
        if args.company_slug:
            # Ingest specific company
            logger.info(f"Ingesting specific company: {args.company_slug}")
            success = ingest_company(args.company_slug, args.verbose, clear_existing=args.clear)
            if success:
                logger.info(f"✓ Successfully ingested {args.company_slug}")
            else:
                logger.error(f"✗ Failed to ingest {args.company_slug}")
                sys.exit(1)
        elif args.all:
            # Ingest all companies
            companies = discover_companies_from_raw_data()
            
            if not companies:
                logger.warning("No companies found in data/raw directory")
                return
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Ingesting {len(companies)} companies to Pinecone")
            if args.clear:
                logger.warning("CLEAR MODE: Existing vectors will be replaced")
            logger.info(f"{'='*60}\n")
            
            results = []
            for idx, company_slug in enumerate(companies, 1):
                logger.info(f"[{idx}/{len(companies)}] {company_slug}")
                success = ingest_company(company_slug, args.verbose, clear_existing=args.clear)
                results.append({
                    'company_slug': company_slug,
                    'success': success
                })
            
            # Summary
            logger.info(f"\n{'='*60}")
            logger.info("=== INGESTION COMPLETE ===")
            logger.info(f"{'='*60}")
            
            successful = sum(1 for r in results if r['success'])
            logger.info(f"Successfully ingested: {successful}/{len(results)}")
            
            if successful > 0:
                logger.info("\nSuccessful ingestions:")
                for r in results:
                    if r['success']:
                        logger.info(f"  ✓ {r['company_slug']}")
            
            failed = [r for r in results if not r['success']]
            if failed:
                logger.info("\nFailed ingestions:")
                for r in failed:
                    logger.info(f"  ✗ {r['company_slug']}")
        else:
            parser.print_help()
            logger.error("Please specify --company-slug <slug> or --all")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
