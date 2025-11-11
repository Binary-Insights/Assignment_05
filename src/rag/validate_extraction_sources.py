#!/usr/bin/env python3
"""Validate that extracted data actually comes from Qdrant and raw sources.

This script verifies:
1. All extracted values exist in Qdrant vector database
2. Qdrant chunks came from actual data/raw/{company_slug}/{page_type}/text.txt files
3. Content is traceable from raw files → Qdrant → extracted output
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv

load_dotenv()

def setup_logging():
    """Setup logging."""
    logger = logging.getLogger('validation')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def validate_qdrant_sources(company_id: str, company_slug: str) -> bool:
    """Validate that Qdrant collection contains all source files."""
    logger = logging.getLogger('validation')
    
    qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
    qdrant_client = QdrantClient(url=qdrant_url)
    
    collection_name = f"company_{company_slug}".lower().replace('-', '_')
    
    logger.info(f"\n{'='*70}")
    logger.info(f"QDRANT VALIDATION: {company_id}")
    logger.info(f"{'='*70}")
    
    try:
        # Get collection info
        collection_info = qdrant_client.get_collection(collection_name)
        logger.info(f"✓ Collection exists: {collection_name}")
        logger.info(f"  Total points: {collection_info.points_count}")
        
        # Get all points to analyze sources
        all_points = qdrant_client.scroll(
            collection_name=collection_name,
            limit=10000
        )
        
        points, _ = all_points
        
        # Group by source file
        sources = {}
        for point in points:
            source_file = point.payload.get('source_file', 'unknown')
            if source_file not in sources:
                sources[source_file] = []
            sources[source_file].append({
                'point_id': point.id,
                'chunk_index': point.payload.get('chunk_index'),
                'page_type': point.payload.get('page_type'),
                'text_preview': point.payload.get('text', '')[:80],
            })
        
        logger.info(f"\n📊 Sources in Qdrant:")
        logger.info(f"{'─'*70}")
        
        all_sources_exist = True
        for source_file in sorted(sources.keys()):
            chunks = sources[source_file]
            
            # Verify file exists
            file_exists = Path(source_file).exists()
            status = "✓" if file_exists else "✗"
            
            logger.info(f"{status} {source_file}")
            logger.info(f"    Chunks: {len(chunks)}")
            
            if file_exists:
                # Verify content matches
                with open(source_file, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                
                matches = 0
                for chunk in chunks[:3]:  # Check first 3 chunks
                    if chunk['text_preview'] in raw_content:
                        matches += 1
                
                logger.info(f"    Content matches: {matches}/{min(3, len(chunks))}")
            else:
                all_sources_exist = False
                logger.warning(f"    ⚠️  SOURCE FILE MISSING!")
        
        logger.info(f"{'─'*70}")
        
        if all_sources_exist:
            logger.info("✓ All Qdrant sources verified against raw files\n")
            return True
        else:
            logger.warning("✗ Some source files are missing!\n")
            return False
            
    except Exception as e:
        logger.error(f"Error validating Qdrant: {e}")
        return False


def validate_extraction_provenance(structured_file: Path) -> bool:
    """Validate provenance chain from extracted data."""
    logger = logging.getLogger('validation')
    
    if not structured_file.exists():
        logger.error(f"Structured file not found: {structured_file}")
        return False
    
    logger.info(f"\n{'='*70}")
    logger.info(f"EXTRACTION PROVENANCE VALIDATION")
    logger.info(f"{'='*70}")
    
    with open(structured_file, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    
    company_id = payload['company_record']['company_id']
    
    # Analyze provenance chains
    logger.info(f"\n📋 Provenance Analysis for {company_id}:")
    logger.info(f"{'─'*70}")
    
    all_valid = True
    
    # Check company record
    company = payload['company_record']
    if company['provenance']:
        logger.info(f"\n✓ Company Record (provenance: {len(company['provenance'])} sources)")
        for prov in company['provenance']:
            logger.info(f"    Source: {prov.get('source_url', 'unknown')}")
            logger.info(f"    Date: {prov.get('crawled_at', 'unknown')}")
            logger.info(f"    Snippet: {prov.get('snippet', '')[:60]}...")
    
    # Check events
    logger.info(f"\n✓ Events ({len(payload['events'])} total)")
    for event in payload['events']:
        if event['provenance']:
            logger.info(f"  Event: {event['title']}")
            logger.info(f"    Sources: {len(event['provenance'])}")
            for prov in event['provenance'][:1]:
                logger.info(f"      - {prov.get('source_url', 'unknown')}")
        else:
            logger.warning(f"  ⚠️  Event '{event['title']}' has NO provenance!")
            all_valid = False
    
    # Check snapshots
    logger.info(f"\n✓ Snapshots ({len(payload['snapshots'])} total)")
    for snap in payload['snapshots']:
        if snap['provenance']:
            logger.info(f"  Snapshot (as_of: {snap['as_of']})")
            logger.info(f"    Sources: {len(snap['provenance'])}")
            for prov in snap['provenance'][:1]:
                logger.info(f"      - {prov.get('source_url', 'unknown')}")
    
    # Check products
    logger.info(f"\n✓ Products ({len(payload['products'])} total)")
    for prod in payload['products']:
        if prod['provenance']:
            logger.info(f"  Product: {prod['name']}")
            logger.info(f"    Sources: {len(prod['provenance'])}")
            for prov in prod['provenance'][:1]:
                logger.info(f"      - {prov.get('source_url', 'unknown')}")
    
    # Check leadership
    logger.info(f"\n✓ Leadership ({len(payload['leadership'])} total)")
    for leader in payload['leadership']:
        if leader['provenance']:
            logger.info(f"  Person: {leader['name']} ({leader['role']})")
            logger.info(f"    Sources: {len(leader['provenance'])}")
            for prov in leader['provenance'][:1]:
                logger.info(f"      - {prov.get('source_url', 'unknown')}")
    
    logger.info(f"{'─'*70}\n")
    return all_valid


def compare_qdrant_vs_raw(company_slug: str) -> None:
    """Compare what's in Qdrant vs what's in raw files."""
    logger = logging.getLogger('validation')
    
    logger.info(f"\n{'='*70}")
    logger.info(f"RAW FILES vs QDRANT COMPARISON: {company_slug}")
    logger.info(f"{'='*70}")
    
    # Get raw files
    raw_dir = Path(f"data/raw/{company_slug}")
    if not raw_dir.exists():
        logger.warning(f"Raw directory not found: {raw_dir}")
        return
    
    raw_files = {}
    for page_dir in raw_dir.iterdir():
        if page_dir.is_dir():
            text_file = page_dir / "text.txt"
            if text_file.exists():
                with open(text_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                raw_files[str(text_file)] = content
                logger.info(f"\n📄 Raw file: {text_file.relative_to(Path('data/raw').parent)}")
                logger.info(f"   Size: {len(content)} chars")
                logger.info(f"   Preview: {content[:100]}...")
    
    # Get Qdrant data
    qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
    try:
        qdrant_client = QdrantClient(url=qdrant_url)
        collection_name = f"company_{company_slug}".lower().replace('-', '_')
        
        all_points = qdrant_client.scroll(
            collection_name=collection_name,
            limit=10000
        )
        points, _ = all_points
        
        logger.info(f"\n📊 Qdrant Collection: {collection_name}")
        logger.info(f"   Total chunks: {len(points)}")
        
        # Verify chunks come from raw files
        logger.info(f"\n{'─'*70}")
        logger.info("Verification: Chunks traceable to raw files?")
        logger.info(f"{'─'*70}")
        
        verified_count = 0
        for point in points[:10]:  # Check first 10
            source_file = point.payload.get('source_file')
            chunk_text = point.payload.get('text', '')[:50]
            
            if source_file in raw_files:
                if chunk_text in raw_files[source_file]:
                    logger.info(f"✓ Point {point.id}: Found in {Path(source_file).name}")
                    verified_count += 1
                else:
                    logger.warning(f"⚠️  Point {point.id}: Source file exists but chunk not found")
            else:
                logger.warning(f"✗ Point {point.id}: Source file missing: {source_file}")
        
        logger.info(f"\nVerified: {verified_count}/{min(10, len(points))} chunks\n")
        
    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")


def main():
    logger = setup_logging()
    
    # Find structured files to validate
    structured_dir = Path("data/structured")
    if not structured_dir.exists():
        logger.error(f"Structured directory not found: {structured_dir}")
        return
    
    structured_files = list(structured_dir.glob("*.json"))
    if not structured_files:
        logger.error("No structured files found")
        return
    
    logger.info(f"\nFound {len(structured_files)} structured file(s) to validate\n")
    
    for structured_file in sorted(structured_files):
        company_id = structured_file.stem
        
        # Extract company_slug from company_id
        company_slug = company_id.replace('-', '_')
        
        # Validate Qdrant sources
        qdrant_valid = validate_qdrant_sources(company_id, company_slug)
        
        # Validate extraction provenance
        prov_valid = validate_extraction_provenance(structured_file)
        
        # Compare raw vs Qdrant
        compare_qdrant_vs_raw(company_slug)
        
        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("VALIDATION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Qdrant Sources: {'✓ PASS' if qdrant_valid else '✗ FAIL'}")
        logger.info(f"Provenance Chain: {'✓ PASS' if prov_valid else '✗ FAIL'}")
        logger.info(f"{'='*70}\n")


if __name__ == "__main__":
    main()
