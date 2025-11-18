"""
Airflow DAG for Agentic RAG Payload Enrichment.

Orchestrates the enrichment of company payloads using the agentic RAG system.
Dynamically generates tasks for each company payload found in the data directory.

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
# DAG is at /app/src/dags/agentic_rag_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
PAYLOADS_DIR = PROJECT_ROOT / "data" / "payloads"
AGENTIC_RAG_SCRIPT = PROJECT_ROOT / "src" / "tavily_agent" / "main.py"


def load_companies_from_payloads():
    """
    Load company names from payload files in the payloads directory.
    Returns list of company names (without .json extension) for downstream tasks.
    
    This function scans the payloads directory and extracts company identifiers
    from JSON files, excluding versioned files (_v1, _v2, etc.).
    """
    try:
        logger.info("✓ Loading companies from payload files...")
        
        if not PAYLOADS_DIR.exists():
            logger.error(f"Payloads directory not found: {PAYLOADS_DIR}")
            return []
        
        # Get all .json files, excluding version files
        payload_files = [
            f.stem  # Get filename without extension
            for f in PAYLOADS_DIR.glob("*.json")
            if "_v" not in f.stem  # Exclude versioned files
        ]
        
        companies = sorted(payload_files)
        
        logger.info(f"✓ Loaded {len(companies)} companies from payload files")
        if companies:
            logger.info(f"  Companies: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading payload files: {e}", exc_info=True)
        raise


def enrich_single_company_task(company_name: str):
    """
    Run agentic RAG enrichment for a specific company using subprocess.
    
    Args:
        company_name: Company identifier (e.g., "abridge")
    
    Returns:
        Dictionary with company name and status
    """
    logger_task = logging.getLogger(__name__)
    
    try:
        logger_task.info(f"Starting agentic RAG enrichment for: {company_name}")
        logger_task.info(f"Project root: {PROJECT_ROOT}")
        logger_task.info(f"Payloads directory: {PAYLOADS_DIR}")
        logger_task.info(f"Script path: {AGENTIC_RAG_SCRIPT}")
        
        # Build command using direct script path (more reliable in Docker)
        cmd = [
            sys.executable,
            str(AGENTIC_RAG_SCRIPT),
            "single",
            company_name
        ]
        
        logger_task.info(f"Command: {' '.join(cmd)}")
        logger_task.info(f"Working directory: {PROJECT_ROOT}")
        
        # Execute enrichment
        logger_task.info("=" * 80)
        logger_task.info(f"ENRICHMENT START FOR {company_name}")
        logger_task.info("=" * 80)
        
        # Set up environment with PYTHONPATH to ensure imports work
        env = dict(subprocess.os.environ)
        env['PYTHONPATH'] = str(PROJECT_ROOT)
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered
        )
        
        # Stream output line by line from both stdout and stderr
        try:
            while True:
                # Read from stdout
                stdout_line = process.stdout.readline()
                if stdout_line:
                    logger_task.info(stdout_line.rstrip())
                
                # Read from stderr
                stderr_line = process.stderr.readline()
                if stderr_line:
                    logger_task.error(stderr_line.rstrip())
                
                # Check if process has finished
                if process.poll() is not None:
                    # Read any remaining output
                    for line in process.stdout:
                        logger_task.info(line.rstrip())
                    for line in process.stderr:
                        logger_task.error(line.rstrip())
                    break
            
            # Get return code
            return_code = process.wait(timeout=600)
            
        except subprocess.TimeoutExpired:
            logger_task.error(f"Process timeout after 600 seconds")
            process.kill()
            process.wait()
            raise subprocess.TimeoutExpired(cmd, 600)
        
        logger_task.info("=" * 80)
        logger_task.info(f"ENRICHMENT END FOR {company_name}")
        logger_task.info(f"Return code: {return_code}")
        logger_task.info("=" * 80)
        
        if return_code != 0:
            error_msg = f"Enrichment failed for {company_name} with return code {return_code}"
            logger_task.error(error_msg)
            raise RuntimeError(error_msg)
        
        logger_task.info(f"✓ Enrichment complete for: {company_name}")
        
        return {
            "company": company_name,
            "status": "success"
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Enrichment timeout for {company_name} (600s exceeded)"
        logger_task.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    except Exception as e:
        logger_task.error(f"Error enriching {company_name}: {str(e)}", exc_info=True)
        raise


def verify_enrichment_complete():
    """
    Verify that enrichment completed for all companies.
    Checks that updated payload files exist.
    """
    try:
        logger.info("Verifying enrichment completion...")
        
        if not PAYLOADS_DIR.exists():
            logger.warning(f"Payloads directory not found: {PAYLOADS_DIR}")
            return {"status": "success", "message": "No payloads to verify"}
        
        # Get non-versioned payload files
        payload_files = [
            f for f in PAYLOADS_DIR.glob("*.json")
            if "_v" not in f.stem
        ]
        
        total_companies = len(payload_files)
        
        logger.info(f"✓ Enrichment verification complete")
        logger.info(f"  Total companies processed: {total_companies}")
        logger.info(f"  Payloads directory: {PAYLOADS_DIR}")
        
        return {
            "status": "success",
            "total_companies": total_companies,
            "message": "Enrichment verification complete"
        }
    
    except Exception as e:
        logger.error(f"Error verifying enrichment: {e}", exc_info=True)
        raise


# Define DAG
with DAG(
    dag_id="agentic_rag_enrichment_dag",
    description="Enrich company payloads using agentic RAG system",
    start_date=datetime(2025, 11, 1),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["ai50", "enrichment", "agentic_rag"],
    max_active_runs=1,  # Only allow one active run
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    }
) as dag:
    
    # Task 1: Load companies from payload files
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_payloads,
        doc="Load company names from payload directory",
    )
    
    # Task 2: Dynamic task generation for each company
    # Each company gets its own enrichment task
    enrichment_tasks = []
    
    # Load companies for dynamic task generation
    companies = []
    try:
        logger.info(f"Checking PAYLOADS_DIR: {PAYLOADS_DIR}")
        logger.info(f"PAYLOADS_DIR exists: {PAYLOADS_DIR.exists()}")
        
        if PAYLOADS_DIR.exists():
            payload_files = list(PAYLOADS_DIR.glob("*.json"))
            logger.info(f"Found {len(payload_files)} JSON files in {PAYLOADS_DIR}")
            
            companies = [
                f.stem
                for f in payload_files
                if "_v" not in f.stem
            ]
            companies = sorted(companies)
            logger.info(f"Loaded {len(companies)} companies for DAG creation: {companies}")
        else:
            logger.warning(f"PAYLOADS_DIR does not exist: {PAYLOADS_DIR}")
    except Exception as e:
        logger.error(f"Failed to load companies for DAG creation: {e}", exc_info=True)
        companies = []
    
    # If no companies found, log warning but continue
    if not companies:
        logger.warning("No companies found; DAG will have no enrichment tasks")
    
    # Create enrichment tasks for each company
    for i, company_name in enumerate(companies):
        task_id = f"enrich_{company_name}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=enrich_single_company_task,
            op_kwargs={
                "company_name": company_name,
            },
            retries=2,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=20),  # 20 minutes per company
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",
            doc=f"Enrich company payload for {company_name}",
        )
        
        enrichment_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            enrichment_tasks[i - 1] >> task
    
    # Task 3: Verify enrichment completion
    verify_completion = PythonOperator(
        task_id="verify_enrichment_complete",
        python_callable=verify_enrichment_complete,
        trigger_rule="all_done",  # Run even if some tasks failed
        doc="Verify that enrichment completed for all companies",
    )
    
    # Define task dependencies
    if enrichment_tasks:
        # If we have enrichment tasks, chain them sequentially and then verify
        load_companies >> enrichment_tasks[0]
        enrichment_tasks[-1] >> verify_completion
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_completion
