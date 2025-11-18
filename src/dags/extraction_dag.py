"""
Airflow DAG: Batch Structured Extraction Pipeline for All Companies

End-to-end structured extraction pipeline that:
1. Discovers all companies in data/raw directory
2. Runs structured_extraction_search.py for each company
3. Extracts structured data (Company, Events, Snapshots, Products, Leadership, Visibility)
4. Saves results as data/payloads/{company_id}.json
5. Verifies extraction completion and payload files

This DAG:
- Only extracts when files change or payload is missing (smart change detection)
- Uses semantic search via Pinecone to extract structured data
- Runs extraction tasks SEQUENTIALLY for all companies
- Provides full logging visibility in Airflow UI
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
# DAG is at /app/src/dags/extraction_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
EXTRACTION_SCRIPT = PROJECT_ROOT / "src" / "rag" / "structured_extraction_search.py"


def load_companies_from_raw_data():
    """
    Load company slugs from data/raw directory structure.
    
    Returns:
        List of company slugs to be processed for extraction
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
        
        logger.info(f"✓ Found {len(companies)} companies for extraction")
        logger.info(f"  Companies: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading companies from raw data: {e}", exc_info=True)
        raise


def extract_company_data(company_slug: str):
    """
    Extract structured data for a single company using semantic search.
    
    This script will:
    - Check if extraction is needed (file changes or missing payload)
    - Query Pinecone vector database for relevant context
    - Use instructor + OpenAI to extract structured data into Pydantic models
    - Extract: Company, Events, Snapshots, Products, Leadership, Visibility
    - Save results as data/payloads/{company_id}.json
    - Update extraction metadata with file hashes
    - Save metadata to data/metadata/{company_slug}/extraction_search_metadata.json
    
    Change Detection:
    - Skips extraction if no file changes AND payload exists
    - Re-extracts if source files changed (detected by SHA256 hash mismatch)
    - Re-extracts if payload file is missing (recovery mode)
    
    Args:
        company_slug: The company identifier to extract data for
    """
    task_logger = logging.getLogger(__name__)
    
    try:
        task_logger.info(f"Starting structured extraction for company: {company_slug}")
        
        cmd = [
            sys.executable,
            "-u",  # Unbuffered output - critical for real-time logging to Airflow
            str(EXTRACTION_SCRIPT),
            "--company-slug", company_slug,
            "--fallback-strategy", "pinecone_first",  # Prefer Pinecone, fallback to raw text
        ]
        
        task_logger.info(f"Running: {' '.join(cmd)}")
        task_logger.info(f"Working directory: {PROJECT_ROOT}")
        task_logger.info(f"EXTRACTION_SCRIPT path: {EXTRACTION_SCRIPT}")
        task_logger.info(f"EXTRACTION_SCRIPT exists: {EXTRACTION_SCRIPT.exists()}")
        
        # Execute extraction - capture output AND stream to logs
        task_logger.info("=" * 80)
        task_logger.info(f"EXTRACTION OUTPUT START FOR {company_slug}")
        task_logger.info("=" * 80)
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=900,  # 15 minute timeout per company (extraction takes longer than ingestion)
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
        task_logger.info(f"EXTRACTION OUTPUT END FOR {company_slug}")
        task_logger.info(f"Return code: {result.returncode}")
        task_logger.info("=" * 80)
        
        if result.returncode != 0:
            error_msg = f"Structured extraction failed for {company_slug} with return code {result.returncode}"
            task_logger.error(error_msg)
            if result.stderr:
                task_logger.error(f"Error details: {result.stderr}")
            raise RuntimeError(error_msg)
        
        task_logger.info(f"✓ Structured extraction complete for: {company_slug}")
        
        return {
            "company": company_slug,
            "status": "success"
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Extraction timeout for {company_slug} (900s exceeded)"
        task_logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    except Exception as e:
        task_logger.error(f"Error extracting data for {company_slug}: {str(e)}", exc_info=True)
        raise


def verify_extraction_completion():
    """
    Verify that extraction payloads were successfully created for all companies.
    
    Checks:
    - Payload files exist in data/payloads/
    - Extraction metadata files exist for companies
    - Summary statistics of extracted data
    """
    try:
        logger.info("🔍 Verifying extraction completion...")
        
        # Check payload files
        payloads_dir = PROJECT_ROOT / "data" / "payloads"
        if not payloads_dir.exists():
            logger.warning(f"Payloads directory not found: {payloads_dir}")
            payload_files = []
        else:
            payload_files = list(payloads_dir.glob("*.json"))
            logger.info(f"✅ Found {len(payload_files)} payload files")
            
            if payload_files:
                logger.info(f"   Payload files:")
                for payload_file in sorted(payload_files)[:10]:  # Show first 10
                    file_size = payload_file.stat().st_size / 1024  # KB
                    logger.info(f"     • {payload_file.name} ({file_size:.1f} KB)")
                if len(payload_files) > 10:
                    logger.info(f"     ... and {len(payload_files) - 10} more")
        
        # Check extraction metadata files
        metadata_dir = PROJECT_ROOT / "data" / "metadata"
        extraction_metadata_files = []
        if metadata_dir.exists():
            extraction_metadata_files = list(metadata_dir.glob("*/extraction_search_metadata.json"))
            logger.info(f"✅ Found {len(extraction_metadata_files)} extraction metadata files")
            
            if extraction_metadata_files:
                logger.info(f"   Extraction metadata files:")
                for meta_file in sorted(extraction_metadata_files)[:10]:  # Show first 10
                    logger.info(f"     • {meta_file.parent.name}/extraction_search_metadata.json")
                if len(extraction_metadata_files) > 10:
                    logger.info(f"     ... and {len(extraction_metadata_files) - 10} more")
        
        logger.info(f"✓ Extraction verification complete")
        
        return {
            "status": "success",
            "payload_files_count": len(payload_files),
            "extraction_metadata_count": len(extraction_metadata_files)
        }
    
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        raise RuntimeError(f"Extraction verification failed: {e}")


# Define DAG
with DAG(
    dag_id="extraction_payload_dag",
    description="Batch structured extraction pipeline: Extract structured data from all companies using semantic search",
    start_date=datetime(2025, 11, 6),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["rag", "pinecone", "extraction", "structured_data", "batch", "all_companies"],
    max_active_runs=1,  # Only allow one active run
) as dag:
    
    # Task 1: Load companies from raw data directory
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_raw_data,
    )
    
    # Task 2: Dynamic task generation for each company
    # Each company gets its own extraction task
    extraction_tasks = []
    
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
        logger.warning("No companies found in data/raw; DAG will have no extraction tasks")
    
    # Create extraction tasks for each company
    for i, company_slug in enumerate(companies):
        task_id = f"extract_{company_slug}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=extract_company_data,
            op_kwargs={
                "company_slug": company_slug,
            },
            retries=2,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=25),  # 25 minutes per company (extraction takes longer)
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",  # Use default queue
        )
        
        extraction_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            extraction_tasks[i - 1] >> task
    
    # Task 3: Verify extraction completion
    verify_completion = PythonOperator(
        task_id="verify_extraction_completion",
        python_callable=verify_extraction_completion,
        trigger_rule="all_done",  # Run even if some tasks failed
    )
    
    # Define task dependencies
    if extraction_tasks:
        # If we have extraction tasks, chain them sequentially and then verify
        load_companies >> extraction_tasks[0]
        extraction_tasks[-1] >> verify_completion
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_completion
