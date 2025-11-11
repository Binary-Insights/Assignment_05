#!/usr/bin/env python3
"""Pinecone Ingestion Script: Index company pages to Pinecone vector database.

This script:
1. Reads text extracted from company web pages (data/raw/{company_slug}/{page_type}/text.txt)
2. Splits text into chunks using RecursiveCharacterTextSplitter
3. Generates embeddings using OpenAI embeddings model
4. Indexes chunks to Pinecone with metadata
5. Saves metadata and statistics for tracking

Usage:
  python src/rag/ingest_to_pinecone.py
  python src/rag/ingest_to_pinecone.py --company-slug world_labs --verbose
  python src/rag/ingest_to_pinecone.py --all --verbose
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import uuid4

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
    vectors_to_save: List[tuple]
) -> str:
    """Save vectors to JSON file for persistence and auditing."""
    logger = logging.getLogger('ingest_to_pinecone')
    
    try:
        vectors_dir = Path("data/vectors")
        vectors_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert vectors to JSON-serializable format
        vectors_json = []
        for vector_id, embedding, metadata in vectors_to_save:
            vectors_json.append({
                "id": vector_id,
                "embedding": embedding,  # Store as list
                "metadata": metadata
            })
        
        vectors_file = vectors_dir / f"{company_slug}.json"
        with open(vectors_file, 'w', encoding='utf-8') as f:
            json.dump(vectors_json, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"✅ Saved {len(vectors_json)} vectors to: {vectors_file}")
        return str(vectors_file)
        
    except Exception as e:
        logger.error(f"Error saving vectors to JSON: {e}", exc_info=True)
        raise


def load_vectors_from_json(company_slug: str) -> List[tuple]:
    """Load vectors from JSON file and convert back to tuple format."""
    logger = logging.getLogger('ingest_to_pinecone')
    
    vectors_file = Path("data/vectors") / f"{company_slug}.json"
    
    if not vectors_file.exists():
        logger.warning(f"Vectors file not found: {vectors_file}")
        return []
    
    try:
        with open(vectors_file, 'r', encoding='utf-8') as f:
            vectors_json = json.load(f)
        
        # Convert back to tuple format
        vectors_tuples = []
        for item in vectors_json:
            vector = (
                item["id"],
                item["embedding"],
                item["metadata"]
            )
            vectors_tuples.append(vector)
        
        logger.info(f"✅ Loaded {len(vectors_tuples)} vectors from: {vectors_file}")
        return vectors_tuples
        
    except Exception as e:
        logger.error(f"Error loading vectors from JSON: {e}", exc_info=True)
        raise


def index_company_pages_to_pinecone(
    company_slug: str, 
    pages_text: Dict[str, str],
    pinecone_index,
    embeddings
) -> Optional[str]:
    """Index company pages to Pinecone vector database.
    
    Process:
    1. Generate embeddings and save to data/vectors/{company_slug}.json
    2. Upsert vectors from JSON file to Pinecone
    """
    logger = logging.getLogger('ingest_to_pinecone')
    
    if not pinecone_index or not embeddings:
        logger.error("Pinecone index or embeddings not available")
        raise ValueError("Pinecone index and embeddings are required")
    
    try:
        namespace = os.getenv('PINECONE_NAMESPACE', 'default')
        logger.info(f"Using Pinecone namespace: '{namespace}'")
        
        # Split and embed text from all pages using same chunking strategy
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
        )
        
        vectors_to_upsert = []
        chunks_per_source = {}  # Track chunks per source file
        
        logger.info(f"\nIndexing source files for {company_slug}:")
        logger.info(f"{'─' * 60}")
        
        for page_type, text in pages_text.items():
            if not text:
                continue
            
            # Log source file information
            source_file = f"data/raw/{company_slug}/{page_type}/text.txt"
            logger.info(f"  📄 Source: {source_file}")
            logger.info(f"     Content size: {len(text)} characters")
            
            # Split text into chunks
            chunks = text_splitter.split_text(text)
            chunks_per_source[page_type] = len(chunks)
            logger.info(f"     Chunks created: {len(chunks)} (500 chars, 100 char overlap)")
            
            for chunk_idx, chunk in enumerate(chunks, 1):
                try:
                    # Generate embedding
                    embedding = embeddings.embed_query(chunk)
                    
                    # Create unique ID for the vector
                    vector_id = f"{company_slug}_{page_type}_{chunk_idx}_{str(uuid4())[:8]}"
                    
                    # Create vector tuple (id, embedding, metadata)
                    vector = (
                        vector_id,
                        embedding,
                        {
                            "text": chunk,
                            "page_type": page_type,
                            "company_slug": company_slug,
                            "source_file": source_file,
                            "chunk_index": chunk_idx,
                            "indexed_at": datetime.now().isoformat()
                        }
                    )
                    vectors_to_upsert.append(vector)
                except Exception as e:
                    logger.warning(f"Failed to embed chunk {chunk_idx} from {page_type}: {e}")
                    continue
            
            logger.info(f"     ✓ Processed {page_type}\n")
        
        if vectors_to_upsert:
            # Step 1: Save vectors to JSON file
            logger.info(f"\nStep 1: Saving vectors to JSON")
            logger.info(f"{'─' * 60}")
            vectors_file = save_vectors_to_json(company_slug, vectors_to_upsert)
            
            # Step 2: Load vectors from JSON and upsert to Pinecone
            logger.info(f"\nStep 2: Upserting vectors from JSON to Pinecone")
            logger.info(f"{'─' * 60}")
            logger.info(f"Loading vectors from {vectors_file}...")
            vectors_from_file = load_vectors_from_json(company_slug)
            
            logger.info(f"Upserting {len(vectors_from_file)} vectors to Pinecone...")
            upsert_response = pinecone_index.upsert(
                vectors=vectors_from_file,
                namespace=namespace
            )
            logger.info(f"✅ Upserted {len(vectors_from_file)} vectors to Pinecone")
            
            # Summary logging
            logger.info(f"\n{'─' * 60}")
            logger.info(f"✓ Successfully indexed {len(vectors_to_upsert)} total chunks")
            logger.info(f"  • Saved to: data/vectors/{company_slug}.json")
            logger.info(f"  • Upserted to Pinecone namespace: '{namespace}'")
            logger.info(f"\nBreakdown by source:")
            for source, count in sorted(chunks_per_source.items()):
                logger.info(f"  • {source:15} → {count:3} chunks")
            logger.info(f"{'─' * 60}\n")
        
        return namespace
        
    except Exception as e:
        logger.error(f"Error indexing to Pinecone: {e}", exc_info=True)
        raise


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


def ingest_company(company_slug: str, verbose: bool = False) -> bool:
    """Ingest a single company's pages to Pinecone."""
    logger = logging.getLogger('ingest_to_pinecone')
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Ingesting Company: {company_slug}")
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
        
        # Index company pages to Pinecone
        namespace = index_company_pages_to_pinecone(
            company_slug, 
            pages_text,
            pinecone_index,
            embeddings
        )
        
        logger.info(f"✓ Successfully ingested {company_slug} to Pinecone (namespace: {namespace})")
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
    
    args = parser.parse_args()
    
    try:
        if args.company_slug:
            # Ingest specific company
            logger.info(f"Ingesting specific company: {args.company_slug}")
            success = ingest_company(args.company_slug, args.verbose)
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
            logger.info(f"{'='*60}\n")
            
            results = []
            for idx, company_slug in enumerate(companies, 1):
                logger.info(f"[{idx}/{len(companies)}] {company_slug}")
                success = ingest_company(company_slug, args.verbose)
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
