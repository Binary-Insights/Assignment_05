"""
Airflow DAG: Batch RAG Pipeline for All 50 Forbes AI Companies

End-to-end RAG pipeline that:
1. Discovers all companies in data/raw directory
2. Ingests all company pages into Pinecone vector database with deduplication

This DAG orchestrates the complete batch ingestion workflow with dynamic task generation.
"""

import os
import sys
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# Get project root
# DAG is at /app/src/dags/ingest_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
INGEST_SCRIPT = PROJECT_ROOT / "src" / "rag" / "ingest_to_pinecone.py"


def load_companies_from_raw_data():
    """
    Load company slugs from data/raw directory structure.
    
    Returns:
        List of company slugs to be ingested
    """
    try:
        logger.info("✓ Loading companies from data/raw directory...")
        
        raw_dir = PROJECT_ROOT / "data" / "raw"
        
        if not raw_dir.exists():
            logger.error(f"Raw data directory not found: {raw_dir}")
            return []
        
        companies = []
        for company_dir in sorted(raw_dir.iterdir()):
            if company_dir.is_dir():
                company_slug = company_dir.name
                companies.append(company_slug)
                logger.info(f"Discovered company: {company_slug}")
        
        logger.info(f"✓ Found {len(companies)} companies to ingest")
        logger.info(f"  Companies: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading companies from raw data: {e}", exc_info=True)
        raise


def ingest_company_to_pinecone(company_slug: str):
    """
    Ingest a single company's pages into Pinecone vector database.
    
    This script will:
    - Read extracted text from data/raw/{company_slug}/{page_type}/text.txt
    - Split text into chunks (500 chars, 100 char overlap)
    - Generate embeddings using OpenAI text-embedding-3-large
    - Create deterministic vector IDs based on content hash
    - Upsert to Pinecone with three-level deduplication:
      * Content hash: same content = same ID = no duplicates
      * File hash: detect changes, only re-process changed files
      * Incremental ingestion: smart skipping of unchanged content
    - Save metadata to data/metadata/{company_slug}/pinecone_ingestion.json
    
    Args:
        company_slug: The company identifier to ingest
    """
    task_logger = logging.getLogger(__name__)
    
    try:
        task_logger.info(f"Starting Pinecone ingestion for company: {company_slug}")
        
        cmd = [
            sys.executable,
            "-u",  # Unbuffered output - critical for real-time logging to Airflow
            str(INGEST_SCRIPT),
            "--company-slug", company_slug,
        ]
        
        task_logger.info(f"Running: {' '.join(cmd)}")
        task_logger.info(f"Working directory: {PROJECT_ROOT}")
        task_logger.info(f"INGEST_SCRIPT path: {INGEST_SCRIPT}")
        task_logger.info(f"INGEST_SCRIPT exists: {INGEST_SCRIPT.exists()}")
        
        # Execute ingestion - capture output AND stream to logs
        task_logger.info("=" * 80)
        task_logger.info(f"INGEST OUTPUT START FOR {company_slug}")
        task_logger.info("=" * 80)
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=600,  # 10 minute timeout per company
            env={**dict(os.environ), 'PYTHONUNBUFFERED': '1'},
            text=True,
            capture_output=True,  # Capture to get error messages
        )
        
        # Log captured output
        if result.stdout:
            task_logger.info(f"STDOUT:\n{result.stdout}")
        
        if result.stderr:
            task_logger.error(f"STDERR:\n{result.stderr}")
        
        task_logger.info("=" * 80)
        task_logger.info(f"INGEST OUTPUT END FOR {company_slug}")
        task_logger.info(f"Return code: {result.returncode}")
        task_logger.info("=" * 80)
        
        if result.returncode != 0:
            error_msg = f"Pinecone ingestion failed for {company_slug} with return code {result.returncode}"
            task_logger.error(error_msg)
            if result.stderr:
                task_logger.error(f"Error details: {result.stderr}")
            raise RuntimeError(error_msg)
        
        task_logger.info(f"✓ Pinecone ingestion complete for: {company_slug}")
        
        return {
            "company": company_slug,
            "status": "success"
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Pinecone ingestion timeout for {company_slug} (600s exceeded)"
        task_logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    except Exception as e:
        task_logger.error(f"Error ingesting company {company_slug} into Pinecone: {str(e)}", exc_info=True)
        raise


def verify_pinecone_index():
    """
    Verify that all company pages were successfully ingested into Pinecone.
    
    Checks:
    - Pinecone connection and index health
    - Total vector count across all namespaces
    - Metadata file existence for each company
    """
    try:
        from pinecone import Pinecone
        
        logger.info("🔍 Verifying Pinecone index...")
        
        # Initialize Pinecone client
        api_key = os.getenv('PINECONE_API_KEY')
        if not api_key:
            raise RuntimeError("PINECONE_API_KEY not set")
        
        pc = Pinecone(api_key=api_key)
        index_name = os.getenv('PINECONE_INDEX_NAME', 'bigdata-assignment-04')
        index = pc.Index(index_name)
        
        # Get index stats
        logger.info(f"✅ Connected to Pinecone index '{index_name}'")
        stats = index.describe_index_stats()
        
        logger.info(f"✅ Index statistics:")
        logger.info(f"   Total vectors: {stats.total_vector_count}")
        logger.info(f"   Dimension: {stats.dimension}")
        
        if stats.namespaces:
            logger.info(f"   Namespaces:")
            for ns_name, ns_stats in stats.namespaces.items():
                vector_count = ns_stats.get('vector_count', 0)
                logger.info(f"     • '{ns_name}': {vector_count} vectors")
        
        # Verify metadata files exist
        metadata_dir = PROJECT_ROOT / "data" / "metadata"
        if metadata_dir.exists():
            company_metadata_dirs = [d for d in metadata_dir.iterdir() if d.is_dir()]
            logger.info(f"   Metadata files for {len(company_metadata_dirs)} companies")
            for company_dir in sorted(company_metadata_dirs)[:5]:  # Show first 5
                logger.info(f"     • {company_dir.name}")
            if len(company_metadata_dirs) > 5:
                logger.info(f"     ... and {len(company_metadata_dirs) - 5} more")
        
        logger.info(f"✓ Pinecone index verification complete")
        
        return {
            "status": "success",
            "index_name": index_name,
            "total_vectors": stats.total_vector_count,
            "dimension": stats.dimension
        }
    
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        raise RuntimeError(f"Pinecone verification failed: {e}")


# Define DAG
with DAG(
    dag_id="ingest_dag",
    description="Batch RAG pipeline: Discover companies in data/raw + ingest to Pinecone",
    start_date=datetime(2025, 11, 6),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["rag", "pinecone", "batch", "all_companies"],
    max_active_runs=1,  # Only allow one active run
) as dag:
    
    # Task 1: Load companies from raw data directory
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_raw_data,
    )
    
    # Task 2: Dynamic task generation for each company
    # Each company gets its own ingestion task
    ingest_tasks = []
    
    # Load companies for dynamic task generation
    companies = []
    try:
        raw_dir = PROJECT_ROOT / "data" / "raw"
        if raw_dir.exists():
            companies = [d.name for d in sorted(raw_dir.iterdir()) if d.is_dir()]
            logger.info(f"Loaded {len(companies)} companies from data/raw for DAG creation")
    except Exception as e:
        logger.error(f"Failed to load companies for DAG creation: {e}")
        # Use empty list if directory can't be read
        companies = []
    
    # If no companies found, log warning but continue
    if not companies:
        logger.warning("No companies found in data/raw; DAG will have no ingestion tasks")
    
    # Create ingestion tasks for each company
    for i, company_slug in enumerate(companies):
        task_id = f"ingest_{company_slug}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=ingest_company_to_pinecone,
            op_kwargs={
                "company_slug": company_slug,
            },
            retries=2,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=15),  # 15 minutes per company
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",  # Use default queue
        )
        
        ingest_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            ingest_tasks[i - 1] >> task
    
    # Task 3: Verify Pinecone index
    verify_index = PythonOperator(
        task_id="verify_pinecone_index",
        python_callable=verify_pinecone_index,
        trigger_rule="all_done",  # Run even if some tasks failed
    )
    
    # Define task dependencies
    if ingest_tasks:
        # If we have ingestion tasks, chain them sequentially and then verify
        load_companies >> ingest_tasks[0]
        ingest_tasks[-1] >> verify_index
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_index
