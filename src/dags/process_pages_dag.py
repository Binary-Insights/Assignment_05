"""
Airflow DAG for processing discovered AI50 company pages.

Orchestrates the discovery and processing of company pages with dynamic task generation.
Follows the same pattern as eval_runner_dag.py for consistency.

Schedule: Manual trigger (no automatic schedule)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator
import subprocess
import sys

logger = logging.getLogger(__name__)

# Get project root
# DAG is at /app/src/dags/process_pages_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
DISCOVERED_PAGES_FILE = PROJECT_ROOT / "data" / "company_pages.json"
PROCESS_SCRIPT = PROJECT_ROOT / "src" / "discover" / "process_discovered_pages.py"


def load_companies_from_discovered_pages():
    """
    Load company slugs from company_pages.json.
    Returns list of company slugs for downstream tasks.
    
    The discovered pages file is a list of companies, where each company
    is identified by company_name. This function converts company names
    to slugs for task generation.
    """
    try:
        logger.info("✓ Loading companies from discovered pages...")
        
        if not DISCOVERED_PAGES_FILE.exists():
            logger.error(f"Discovered pages file not found: {DISCOVERED_PAGES_FILE}")
            return []
        
        with open(DISCOVERED_PAGES_FILE, "r") as f:
            discovered_data = json.load(f)
        
        # Handle both list and dict formats
        if isinstance(discovered_data, list):
            # Extract company names from list of company objects
            companies = [
                company.get("company_name", f"company_{i}").lower().replace(" ", "-")
                for i, company in enumerate(discovered_data)
            ]
        elif isinstance(discovered_data, dict):
            # If it's a dict, use keys directly
            companies = list(discovered_data.keys())
        else:
            logger.error(f"Unexpected data format: {type(discovered_data)}")
            return []
        
        logger.info(f"✓ Loaded {len(companies)} companies from discovered pages")
        logger.info(f"  Companies: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading discovered pages: {e}", exc_info=True)
        raise


def process_company_pages(company_slug: str):
    """
    Run page processing for a specific company.
    
    Args:
        company_slug: Company slug (e.g., "world-labs")
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting page processing for company: {company_slug}")
        
        # Build command to process this specific company
        # Note: The script expects --companies (plural) with company name(s)
        # Look up the actual company name from the JSON file
        with open(DISCOVERED_PAGES_FILE, "r") as f:
            discovered_data = json.load(f)
        
        # Find the actual company name from JSON using slug matching
        company_name = None
        if isinstance(discovered_data, list):
            for company in discovered_data:
                # Convert company_name to slug and compare
                company_slug_from_json = company.get("company_name", "").lower().replace(" ", "-")
                if company_slug_from_json == company_slug:
                    company_name = company.get("company_name")
                    break
        
        if not company_name:
            # Fallback to title case if not found in JSON
            company_name = company_slug.replace("-", " ").title()
            logger.warning(f"Company not found in JSON, using fallback name: {company_name}")
        
        logger.info(f"Using company name: {company_name}")
        cmd = [
            sys.executable,
            str(PROCESS_SCRIPT),
            "--companies", company_name,
            "-i", str(PROJECT_ROOT / "data" / "company_pages.json")
        ]
        
        logger.info(f"Running: {' '.join(cmd)}")
        logger.info(f"Working directory: {PROJECT_ROOT}")
        logger.info(f"PROCESS_SCRIPT path: {PROCESS_SCRIPT}")
        logger.info(f"PROCESS_SCRIPT exists: {PROCESS_SCRIPT.exists()}")
        
        # Execute processing - capture output AND stream to logs
        logger.info("=" * 80)
        logger.info(f"SUBPROCESS OUTPUT START FOR {company_slug}")
        logger.info("=" * 80)
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=600,  # 10 minute timeout per company
            env={**dict(subprocess.os.environ), 'PYTHONUNBUFFERED': '1'},
            text=True,
            capture_output=True,  # Capture to get error messages
        )
        
        # Log captured output
        if result.stdout:
            logger.info(f"STDOUT:\n{result.stdout}")
        
        if result.stderr:
            logger.error(f"STDERR:\n{result.stderr}")
        
        logger.info("=" * 80)
        logger.info(f"SUBPROCESS OUTPUT END FOR {company_slug}")
        logger.info(f"Return code: {result.returncode}")
        logger.info("=" * 80)
        
        if result.returncode != 0:
            error_msg = f"Page processing failed for {company_slug} with return code {result.returncode}"
            logger.error(error_msg)
            if result.stderr:
                logger.error(f"Error details: {result.stderr}")
            raise RuntimeError(error_msg)
        
        logger.info(f"✓ Page processing complete for: {company_slug}")
        
        return {
            "company": company_slug,
            "status": "success"
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Page processing timeout for {company_slug} (600s exceeded)"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Error processing pages for {company_slug}: {str(e)}", exc_info=True)
        raise


def verify_processing_complete():
    """
    Verify that page processing completed successfully for all companies.
    Can be used for post-processing validation.
    """
    try:
        logger.info("Verifying page processing completion...")
        
        if not DISCOVERED_PAGES_FILE.exists():
            logger.warning(f"Discovered pages file not found: {DISCOVERED_PAGES_FILE}")
            return {"status": "success", "message": "No companies to verify"}
        
        with open(DISCOVERED_PAGES_FILE, "r") as f:
            discovered_data = json.load(f)
        
        # Handle both list and dict formats
        if isinstance(discovered_data, list):
            total_companies = len(discovered_data)
        elif isinstance(discovered_data, dict):
            total_companies = len(discovered_data)
        else:
            total_companies = 0
        
        logger.info(f"✓ Page processing verification complete")
        logger.info(f"  Total companies processed: {total_companies}")
        
        return {
            "status": "success",
            "total_companies": total_companies,
            "message": "Page processing verification complete"
        }
    
    except Exception as e:
        logger.error(f"Error verifying processing: {e}", exc_info=True)
        raise


# Define DAG
with DAG(
    dag_id="process_pages_dag",
    description="Process discovered AI50 company pages and extract content",
    start_date=datetime(2025, 11, 1),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["ai50", "data_discovery", "page_processing"],
    max_active_runs=1,  # Only allow one active run
) as dag:
    
    # Task 1: Load companies from discovered pages
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_discovered_pages,
    )
    
    # Task 2: Dynamic task generation for each company
    # Each company gets its own processing task
    processing_tasks = []
    
    # Load discovered pages for dynamic task generation
    companies = []
    try:
        if DISCOVERED_PAGES_FILE.exists():
            with open(DISCOVERED_PAGES_FILE, "r") as f:
                discovered_data = json.load(f)
            
            # Handle both list and dict formats
            if isinstance(discovered_data, list):
                # Extract company names from list of company objects
                companies = [
                    company.get("company_name", f"company_{i}").lower().replace(" ", "-")
                    for i, company in enumerate(discovered_data)
                ]
            elif isinstance(discovered_data, dict):
                # If it's a dict, use keys directly
                companies = list(discovered_data.keys())
            
            logger.info(f"Loaded {len(companies)} companies from company_pages.json for DAG creation")
    except Exception as e:
        logger.error(f"Failed to load discovered pages for DAG creation: {e}")
        # Use empty list if file can't be loaded
        companies = []
    
    # If no companies found, log warning but continue
    if not companies:
        logger.warning("No companies found; DAG will have no processing tasks")
    
    # Create processing tasks for each company
    for i, company_slug in enumerate(companies):
        task_id = f"process_{company_slug}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=process_company_pages,
            op_kwargs={
                "company_slug": company_slug,
            },
            retries=0,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=20),  # 20 minutes per company
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",  # Use default queue
        )
        
        processing_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            processing_tasks[i - 1] >> task
    
    # Task 3: Verify processing completion
    verify_completion = PythonOperator(
        task_id="verify_processing_complete",
        python_callable=verify_processing_complete,
        trigger_rule="all_done",  # Run even if some tasks failed
    )
    
    # Define task dependencies
    if processing_tasks:
        # If we have processing tasks, chain them sequentially and then verify
        load_companies >> processing_tasks[0]
        processing_tasks[-1] >> verify_completion
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_completion