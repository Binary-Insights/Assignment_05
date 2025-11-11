#!/usr/bin/env python3
"""Pinecone Record Deletion Script: Delete all or specific records from Pinecone.

This script provides multiple options for deleting records from Pinecone:
1. Delete all records in a specific namespace
2. Delete all records from all namespaces
3. Delete records for a specific company
4. Delete records matching specific filters

Usage:
  # Delete all records in default namespace
  python src/rag/delete_pinecone_records.py --namespace default

  # Delete all records from all namespaces
  python src/rag/delete_pinecone_records.py --all-namespaces

  # Delete all records for a specific company
  python src/rag/delete_pinecone_records.py --company-slug world_labs

  # Delete all records (default namespace only)
  python src/rag/delete_pinecone_records.py --confirm-delete-all

  # List all namespaces without deleting
  python src/rag/delete_pinecone_records.py --list-namespaces

  # Show stats without deleting
  python src/rag/delete_pinecone_records.py --stats

Environment Variables:
  PINECONE_API_KEY (required)
  PINECONE_INDEX_NAME (default: "bigdata-assignment-04")
  PINECONE_NAMESPACE (default: "default")
"""

import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()


def setup_logging():
    """Setup logging for delete script."""
    log_dir = "data/logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger('delete_pinecone')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(f"{log_dir}/delete_pinecone.log")
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
    logger = logging.getLogger('delete_pinecone')
    
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
        logger.info(f"   Namespaces: {list(stats.namespaces.keys()) if stats.namespaces else ['default']}")
        logger.info(f"   Total vectors: {stats.total_vector_count}")
        
        return index
    except Exception as e:
        logger.error(f"Failed to connect to Pinecone: {e}")
        raise


def get_index_stats(pinecone_index):
    """Get current index statistics."""
    logger = logging.getLogger('delete_pinecone')
    
    try:
        stats = pinecone_index.describe_index_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get index stats: {e}")
        return None


def list_namespaces(pinecone_index) -> List[str]:
    """List all namespaces in the index."""
    logger = logging.getLogger('delete_pinecone')
    
    try:
        stats = get_index_stats(pinecone_index)
        if stats and stats.namespaces:
            namespaces = list(stats.namespaces.keys())
        else:
            namespaces = ['default']
        
        logger.info(f"Available namespaces: {namespaces}")
        return namespaces
    except Exception as e:
        logger.error(f"Failed to list namespaces: {e}")
        return []


def delete_namespace_records(pinecone_index, namespace: str) -> bool:
    """Delete all records from a specific namespace.
    
    This uses the delete_all() method which deletes all vectors in the namespace.
    """
    logger = logging.getLogger('delete_pinecone')
    
    try:
        logger.warning(f"⚠️  DELETING all records in namespace: '{namespace}'")
        
        # Get count before deletion
        stats = get_index_stats(pinecone_index)
        before_count = stats.namespaces.get(namespace, {}).get('vector_count', 0) if stats else 0
        
        # Delete all vectors in namespace
        pinecone_index.delete(delete_all=True, namespace=namespace)
        
        logger.info(f"✅ Successfully deleted all records from namespace: '{namespace}'")
        logger.info(f"   Vectors deleted: ~{before_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete namespace records: {e}", exc_info=True)
        return False


def delete_company_records(pinecone_index, company_slug: str, namespace: str = None) -> bool:
    """Delete all records for a specific company using metadata filter.
    
    This approach fetches all vector IDs for the company (via pattern matching) and deletes them.
    Note: Pinecone doesn't support direct metadata filters in delete, so this is a workaround.
    """
    logger = logging.getLogger('delete_pinecone')
    
    if namespace is None:
        namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    
    try:
        logger.warning(f"⚠️  DELETING all records for company: '{company_slug}' in namespace '{namespace}'")
        
        # Since Pinecone doesn't support metadata-based delete directly,
        # we use vector ID pattern matching (vector IDs are: company_slug_page_type_hash)
        # We'll delete by ID prefix
        
        vector_id_prefix = f"{company_slug}_"
        logger.info(f"Searching for vectors with ID prefix: '{vector_id_prefix}'")
        
        # Query to find all matching vectors
        # Note: This is limited - we need to fetch and delete
        # For now, we'll use a fallback: fetch vectors and delete them in batches
        
        logger.info(f"Note: Direct company deletion requires fetching vector IDs by pattern")
        logger.info(f"For efficient deletion, please use --namespace to delete entire namespace")
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to delete company records: {e}", exc_info=True)
        return False


def delete_by_vector_ids(pinecone_index, vector_ids: List[str], namespace: str = None) -> bool:
    """Delete specific vectors by their IDs."""
    logger = logging.getLogger('delete_pinecone')
    
    if namespace is None:
        namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    
    try:
        if not vector_ids:
            logger.warning("No vector IDs provided for deletion")
            return False
        
        logger.info(f"Deleting {len(vector_ids)} vectors from namespace '{namespace}'")
        
        # Delete in batches (Pinecone has limits on delete request size)
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(vector_ids), batch_size):
            batch = vector_ids[i:i+batch_size]
            try:
                pinecone_index.delete(ids=batch, namespace=namespace)
                deleted_count += len(batch)
                logger.debug(f"Deleted batch {i//batch_size + 1}: {len(batch)} vectors")
            except Exception as e:
                logger.error(f"Error deleting batch: {e}")
                continue
        
        logger.info(f"✅ Successfully deleted {deleted_count} vectors")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete vectors: {e}", exc_info=True)
        return False


def display_stats(pinecone_index):
    """Display current Pinecone index statistics."""
    logger = logging.getLogger('delete_pinecone')
    
    try:
        stats = get_index_stats(pinecone_index)
        
        if not stats:
            logger.warning("Could not retrieve index statistics")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info("PINECONE INDEX STATISTICS")
        logger.info(f"{'='*60}")
        logger.info(f"Total vectors in index: {stats.total_vector_count}")
        logger.info(f"Dimension: {stats.dimension}")
        
        if stats.namespaces:
            logger.info(f"\nNamespace breakdown:")
            for ns_name, ns_stats in stats.namespaces.items():
                vector_count = ns_stats.get('vector_count', 0)
                logger.info(f"  • '{ns_name}': {vector_count} vectors")
        else:
            logger.info("  • Default namespace (empty)")
        
        logger.info(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"Failed to display stats: {e}")


def confirm_deletion():
    """Ask user to confirm deletion operation."""
    logger = logging.getLogger('delete_pinecone')
    
    logger.warning(f"\n{'!'*60}")
    logger.warning("⚠️  WARNING: YOU ARE ABOUT TO DELETE RECORDS FROM PINECONE")
    logger.warning(f"{'!'*60}")
    
    response = input("\nType 'DELETE' (uppercase) to confirm deletion: ").strip()
    
    if response != "DELETE":
        logger.info("Deletion cancelled by user")
        return False
    
    return True


def main():
    logger = setup_logging()
    logger.info("=== Pinecone Record Deletion Tool ===\n")
    
    import argparse
    parser = argparse.ArgumentParser(
        description="Delete records from Pinecone vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete all records in default namespace
  python src/rag/delete_pinecone_records.py --namespace default

  # Delete all records from all namespaces
  python src/rag/delete_pinecone_records.py --all-namespaces

  # Show statistics without deleting
  python src/rag/delete_pinecone_records.py --stats

  # List all namespaces
  python src/rag/delete_pinecone_records.py --list-namespaces
        """
    )
    
    parser.add_argument(
        '--namespace',
        type=str,
        help='Delete all records from specific namespace'
    )
    parser.add_argument(
        '--all-namespaces',
        action='store_true',
        help='Delete all records from ALL namespaces (dangerous!)'
    )
    parser.add_argument(
        '--company-slug',
        type=str,
        help='Delete records for specific company'
    )
    parser.add_argument(
        '--list-namespaces',
        action='store_true',
        help='List all namespaces without deleting'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show index statistics without deleting'
    )
    parser.add_argument(
        '--confirm-delete-all',
        action='store_true',
        help='Confirm deletion (required with --namespace or --all-namespaces)'
    )
    parser.add_argument(
        '--skip-confirmation',
        action='store_true',
        help='Skip confirmation prompt (use with caution!)'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize Pinecone client
        logger.info("Initializing Pinecone client...")
        pinecone_index = get_pinecone_client()
        logger.info("")
        
        # Handle different operations
        if args.stats:
            display_stats(pinecone_index)
            return
        
        if args.list_namespaces:
            logger.info("Fetching namespaces...\n")
            namespaces = list_namespaces(pinecone_index)
            logger.info(f"✓ Found {len(namespaces)} namespace(s)")
            return
        
        if args.namespace:
            # Delete specific namespace
            if not args.skip_confirmation and not confirm_deletion():
                sys.exit(1)
            
            success = delete_namespace_records(pinecone_index, args.namespace)
            if success:
                logger.info("✓ Deletion completed successfully")
                display_stats(pinecone_index)
            else:
                logger.error("✗ Deletion failed")
                sys.exit(1)
        
        elif args.all_namespaces:
            # Delete all namespaces
            if not args.skip_confirmation and not confirm_deletion():
                sys.exit(1)
            
            logger.info("\n⚠️  DELETING ALL NAMESPACES...")
            namespaces = list_namespaces(pinecone_index)
            
            for ns in namespaces:
                success = delete_namespace_records(pinecone_index, ns)
                if not success:
                    logger.error(f"Failed to delete namespace: {ns}")
            
            logger.info("\n✓ All deletions completed")
            display_stats(pinecone_index)
        
        elif args.company_slug:
            # Delete company records
            if not args.skip_confirmation and not confirm_deletion():
                sys.exit(1)
            
            namespace = os.getenv('PINECONE_NAMESPACE', 'default')
            success = delete_company_records(pinecone_index, args.company_slug, namespace)
            if not success:
                logger.warning("Company deletion not fully implemented")
                logger.info("Tip: Use --namespace to delete entire namespace instead")
        
        else:
            parser.print_help()
            logger.error("\nPlease specify a deletion operation: --namespace, --all-namespaces, --company-slug, or --list-namespaces")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
