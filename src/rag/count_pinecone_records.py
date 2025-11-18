#!/usr/bin/env python3
"""Pinecone Record Counter: Count records by metadata filters.

This script queries Pinecone to count records matching specific metadata criteria.
Supports flexible key-value filtering for any metadata field.

Usage:
  # Count records for a specific company
  python src/rag/count_pinecone_records.py --key company_slug --value abridge

  # Count records with specific page type
  python src/rag/count_pinecone_records.py --key page_type --value careers

  # Count records in a specific namespace
  python src/rag/count_pinecone_records.py --key company_slug --value world_labs --namespace default

  # Show all statistics
  python src/rag/count_pinecone_records.py --stats

  # Multiple filters (if needed in future)
  python src/rag/count_pinecone_records.py --key company_slug --value abridge --key page_type --value careers

Environment Variables:
  PINECONE_API_KEY (required)
  PINECONE_INDEX_NAME (default: "bigdata-assignment-04")
  PINECONE_NAMESPACE (default: "default")
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()


def setup_logging():
    """Setup logging for count script."""
    log_dir = "data/logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger('count_pinecone')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(f"{log_dir}/count_pinecone.log")
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
    """Initialize Pinecone client."""
    logger = logging.getLogger('count_pinecone')
    
    api_key = os.getenv('PINECONE_API_KEY')
    if not api_key:
        logger.error("PINECONE_API_KEY not set in environment")
        raise ValueError("PINECONE_API_KEY environment variable is required")
    
    index_name = os.getenv('PINECONE_INDEX_NAME', 'bigdata-assignment-04')
    logger.info(f"Connecting to Pinecone index: {index_name}")
    
    try:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        
        logger.info("Testing Pinecone connection...")
        stats = index.describe_index_stats()
        logger.info(f"✅ Successfully connected to Pinecone index '{index_name}'")
        logger.info(f"   Total vectors: {stats.total_vector_count}")
        
        return index
    except Exception as e:
        logger.error(f"Failed to connect to Pinecone: {e}")
        raise


def get_index_stats(pinecone_index):
    """Get current index statistics."""
    logger = logging.getLogger('count_pinecone')
    
    try:
        stats = pinecone_index.describe_index_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        return None


def count_records_by_metadata(
    pinecone_index,
    metadata_filters: Dict[str, str],
    namespace: Optional[str] = None
) -> int:
    """Count records matching metadata filters using query with filter.
    
    Note: Pinecone doesn't have a direct count API with metadata filters.
    We use query() with a dummy vector and top_k=10000 to get matching IDs,
    then count them. For production with >10k matches, you'd need pagination.
    
    Args:
        pinecone_index: Pinecone index instance
        metadata_filters: Dict of metadata key-value pairs to filter by
        namespace: Optional namespace to query (defaults to PINECONE_NAMESPACE env var)
    
    Returns:
        Count of matching records
    """
    logger = logging.getLogger('count_pinecone')
    
    if namespace is None:
        namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    
    try:
        # Build metadata filter for Pinecone query
        # Format: {"key1": "value1", "key2": "value2"}
        filter_dict = {key: {"$eq": value} for key, value in metadata_filters.items()}
        
        logger.info(f"Counting records in namespace '{namespace}' with filters: {metadata_filters}")
        logger.debug(f"Pinecone filter: {filter_dict}")
        
        # Get index stats to understand dimension
        stats = get_index_stats(pinecone_index)
        dimension = stats.dimension if stats else 1536  # Default to OpenAI embedding size
        
        # Create a dummy vector (all zeros) for querying
        dummy_vector = [0.0] * dimension
        
        # Query with metadata filter
        # top_k=10000 is Pinecone's max, but we only care about count
        # include_values=False and include_metadata=False for efficiency
        response = pinecone_index.query(
            vector=dummy_vector,
            filter=filter_dict,
            top_k=10000,
            namespace=namespace,
            include_values=False,
            include_metadata=True  # We'll include metadata to show sample results
        )
        
        matches = response.get('matches', [])
        count = len(matches)
        
        logger.info(f"✅ Found {count} records matching filters")
        
        # Show sample results if any found
        if count > 0:
            logger.info(f"\n📊 Sample Results (first 3):")
            for i, match in enumerate(matches[:3], 1):
                record_id = match.get('id', 'unknown')
                metadata = match.get('metadata', {})
                score = match.get('score', 0.0)
                logger.info(f"  {i}. ID: {record_id}")
                logger.info(f"     Metadata: {metadata}")
                logger.info(f"     Score: {score:.4f}")
        
        if count >= 10000:
            logger.warning("⚠️  Result count reached Pinecone's query limit (10,000)")
            logger.warning("    Actual count may be higher. Consider using --stats for namespace totals.")
        
        return count
        
    except Exception as e:
        logger.error(f"Failed to count records: {e}", exc_info=True)
        return 0


def display_stats(pinecone_index):
    """Display comprehensive Pinecone index statistics."""
    logger = logging.getLogger('count_pinecone')
    
    try:
        stats = get_index_stats(pinecone_index)
        
        if not stats:
            logger.warning("Could not retrieve index statistics")
            return
        
        logger.info(f"\n{'='*70}")
        logger.info("📊 PINECONE INDEX STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"Total vectors in index: {stats.total_vector_count:,}")
        logger.info(f"Dimension: {stats.dimension}")
        logger.info(f"Index fullness: {stats.index_fullness:.2%}")
        
        if stats.namespaces:
            logger.info(f"\n📁 Namespace breakdown:")
            for ns_name, ns_stats in sorted(stats.namespaces.items()):
                vector_count = ns_stats.get('vector_count', 0)
                logger.info(f"  • '{ns_name}': {vector_count:,} vectors")
        else:
            logger.info("\n📁 Namespaces: None (using default)")
        
        logger.info(f"{'='*70}\n")
        
    except Exception as e:
        logger.error(f"Failed to display stats: {e}")


def count_by_vector_id_prefix(
    pinecone_index,
    prefix: str,
    namespace: Optional[str] = None
) -> int:
    """Count records by vector ID prefix pattern.
    
    This is useful when vector IDs follow a pattern like:
    company_slug_page_type_hash
    
    Args:
        pinecone_index: Pinecone index instance
        prefix: ID prefix to match (e.g., "abridge_")
        namespace: Optional namespace
    
    Returns:
        Count of matching records
    """
    logger = logging.getLogger('count_pinecone')
    
    if namespace is None:
        namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    
    try:
        logger.info(f"Counting records with ID prefix '{prefix}' in namespace '{namespace}'")
        
        # Note: Pinecone doesn't support ID prefix filtering directly in queries
        # This is a limitation - we'd need to fetch all IDs and filter client-side
        # For now, use metadata filtering instead
        
        logger.warning("⚠️  ID prefix filtering requires fetching all vectors")
        logger.info("💡 Tip: Use --key and --value for metadata-based filtering instead")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to count by prefix: {e}")
        return 0


def main():
    logger = setup_logging()
    logger.info("=== Pinecone Record Counter ===\n")
    
    import argparse
    parser = argparse.ArgumentParser(
        description="Count Pinecone records by metadata filters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Count records for company 'abridge'
  python src/rag/count_pinecone_records.py --key company_slug --value abridge

  # Count records for specific page type
  python src/rag/count_pinecone_records.py --key page_type --value careers

  # Count with custom namespace
  python src/rag/count_pinecone_records.py --key company_slug --value world_labs --namespace custom_ns

  # Show overall statistics
  python src/rag/count_pinecone_records.py --stats

  # Multiple filters (both must match)
  python src/rag/count_pinecone_records.py \\
    --key company_slug --value abridge \\
    --key page_type --value about
        """
    )
    
    parser.add_argument(
        '--key',
        type=str,
        action='append',
        dest='keys',
        help='Metadata key to filter by (can specify multiple times)'
    )
    parser.add_argument(
        '--value',
        type=str,
        action='append',
        dest='values',
        help='Metadata value to match (must correspond to --key order)'
    )
    parser.add_argument(
        '--namespace',
        type=str,
        help='Pinecone namespace to query (default: from PINECONE_NAMESPACE env)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show overall index statistics'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug logging'
    )
    
    args = parser.parse_args()
    
    # Set verbose logging if requested
    if args.verbose:
        logging.getLogger('count_pinecone').setLevel(logging.DEBUG)
    
    try:
        # Initialize Pinecone client
        logger.info("Initializing Pinecone client...")
        pinecone_index = get_pinecone_client()
        logger.info("")
        
        # Handle stats display
        if args.stats:
            display_stats(pinecone_index)
            return
        
        # Validate key-value pairs
        if not args.keys and not args.values:
            logger.error("❌ Please specify --key and --value arguments or use --stats")
            parser.print_help()
            sys.exit(1)
        
        if args.keys and args.values:
            if len(args.keys) != len(args.values):
                logger.error("❌ Number of --key arguments must match number of --value arguments")
                sys.exit(1)
        
        # Build metadata filters
        metadata_filters = {}
        if args.keys and args.values:
            metadata_filters = dict(zip(args.keys, args.values))
        
        logger.info(f"🔍 Filtering by metadata: {metadata_filters}")
        
        # Count records
        count = count_records_by_metadata(
            pinecone_index,
            metadata_filters,
            namespace=args.namespace
        )
        
        # Display result
        logger.info(f"\n{'='*70}")
        logger.info(f"📈 RESULT")
        logger.info(f"{'='*70}")
        logger.info(f"Filters: {metadata_filters}")
        logger.info(f"Namespace: {args.namespace or os.getenv('PINECONE_NAMESPACE', 'default')}")
        logger.info(f"Record count: {count:,}")
        logger.info(f"{'='*70}\n")
        
        # Also show overall stats for context
        if count > 0:
            logger.info("💡 For comparison, here are the overall index stats:\n")
            display_stats(pinecone_index)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
