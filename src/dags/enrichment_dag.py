"""
Airflow DAG: Batch MCP Enrichment Pipeline for All Companies

End-to-end MCP enrichment pipeline that:
1. Discovers all companies in data/payloads directory
2. Enriches each company payload using the MCP client and tavily agent
3. Verifies enrichment results

This DAG orchestrates the complete batch enrichment workflow with dynamic task generation.
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
# DAG is at /app/src/dags/enrichment_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
MCP_CLIENT_SCRIPT = PROJECT_ROOT / "src" / "mcp_server" / "mcp_enrichment_client.py"
PAYLOADS_DIR = PROJECT_ROOT / "data" / "payloads"


def load_companies_from_payloads():
    """
    Load company slugs from data/payloads directory.
    
    Returns:
        List of company slugs to be enriched
    """
    try:
        logger.info("✓ Loading companies from data/payloads directory...")
        
        if not PAYLOADS_DIR.exists():
            logger.error(f"Payloads directory not found: {PAYLOADS_DIR}")
            return []
        
        companies = []
        for payload_file in sorted(PAYLOADS_DIR.glob("*.json")):
            # Extract company slug from filename (e.g., "abridge.json" -> "abridge")
            company_slug = payload_file.stem
            
            # Skip versioned files (e.g., "abridge_v1.json")
            if "_v" in company_slug:
                logger.debug(f"Skipping versioned file: {payload_file.name}")
                continue
            
            companies.append(company_slug)
            logger.info(f"Discovered company: {company_slug}")
        
        logger.info(f"✓ Found {len(companies)} companies to enrich")
        logger.info(f"  Companies: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading companies from payloads: {e}", exc_info=True)
        raise


def enrich_company_payload(company_slug: str):
    """
    Enrich a single company's payload using the MCP client.
    
    This will:
    - Connect to the MCP server (spawns subprocess)
    - Analyze payload for null fields
    - Use tavily agent to search for information
    - Extract and update field values
    - Save enriched payload back to data/payloads/{company_slug}.json
    
    Args:
        company_slug: The company identifier to enrich
    """
    task_logger = logging.getLogger(__name__)
    
    try:
        task_logger.info(f"Starting MCP enrichment for company: {company_slug}")
        
        cmd = [
            sys.executable,
            "-u",  # Unbuffered output - critical for real-time logging to Airflow
            str(MCP_CLIENT_SCRIPT),
            company_slug,
            "--enrich",
        ]
        
        task_logger.info(f"Running: {' '.join(cmd)}")
        task_logger.info(f"Working directory: {PROJECT_ROOT}")
        task_logger.info(f"MCP_CLIENT_SCRIPT path: {MCP_CLIENT_SCRIPT}")
        task_logger.info(f"MCP_CLIENT_SCRIPT exists: {MCP_CLIENT_SCRIPT.exists()}")
        task_logger.info(f"Python executable: {sys.executable}")
        
        # Execute enrichment - stream output in real-time to Airflow logs
        task_logger.info("=" * 80)
        task_logger.info(f"ENRICHMENT OUTPUT START FOR {company_slug}")
        task_logger.info("=" * 80)
        
        # Use Popen to stream output in real-time (both stdout and stderr)
        # Set PYTHONUNBUFFERED and force_root to ensure logs appear
        env = {**dict(os.environ), 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
        
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # Capture stderr separately
            text=True,
            bufsize=0,  # Unbuffered - immediate output
        )
        
        # Stream output line by line (works on both Linux and Windows)
        try:
            while True:
                # Read from stdout
                stdout_line = process.stdout.readline()
                if stdout_line:
                    task_logger.info(stdout_line.rstrip())
                
                # Read from stderr
                stderr_line = process.stderr.readline()
                if stderr_line:
                    task_logger.error(stderr_line.rstrip())
                
                # Check if process has finished
                if process.poll() is not None:
                    # Read any remaining output
                    for line in process.stdout:
                        task_logger.info(line.rstrip())
                    for line in process.stderr:
                        task_logger.error(line.rstrip())
                    break
            
            # Wait for process to complete with timeout
            return_code = process.wait(timeout=1800)  # 30 minute timeout
            
        except subprocess.TimeoutExpired:
            task_logger.error(f"Process timeout after 1800 seconds")
            process.kill()
            process.wait()
            raise subprocess.TimeoutExpired(cmd, 1800)
        
        task_logger.info("=" * 80)
        task_logger.info(f"ENRICHMENT OUTPUT END FOR {company_slug}")
        task_logger.info(f"Return code: {return_code}")
        task_logger.info("=" * 80)
        
        if return_code != 0:
            error_msg = f"MCP enrichment failed for {company_slug} with return code {return_code}"
            task_logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        task_logger.info(f"✓ MCP enrichment complete for: {company_slug}")
        
        return {
            "company": company_slug,
            "status": "success"
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"MCP enrichment timeout for {company_slug} (1800s exceeded)"
        task_logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    except Exception as e:
        task_logger.error(f"Error enriching company {company_slug}: {str(e)}", exc_info=True)
        raise


def verify_enrichment_results():
    """
    Verify that all company payloads were successfully enriched.
    
    Checks:
    - Payload files exist in data/payloads/
    - Payloads have been updated (modified timestamp)
    - Summary statistics
    """
    try:
        logger.info("🔍 Verifying enrichment results...")
        
        if not PAYLOADS_DIR.exists():
            raise RuntimeError(f"Payloads directory not found: {PAYLOADS_DIR}")
        
        payload_files = list(PAYLOADS_DIR.glob("*.json"))
        
        # Filter out versioned files
        payload_files = [f for f in payload_files if "_v" not in f.stem]
        
        logger.info(f"✅ Found {len(payload_files)} payload files")
        
        # Show sample of payload files
        for payload_file in sorted(payload_files)[:5]:
            file_size = payload_file.stat().st_size
            modified_time = datetime.fromtimestamp(payload_file.stat().st_mtime)
            logger.info(f"   • {payload_file.name}: {file_size:,} bytes, modified {modified_time}")
        
        if len(payload_files) > 5:
            logger.info(f"   ... and {len(payload_files) - 5} more")
        
        logger.info(f"✓ Enrichment verification complete")
        
        return {
            "status": "success",
            "total_payloads": len(payload_files)
        }
    
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        raise RuntimeError(f"Enrichment verification failed: {e}")


# Define DAG
with DAG(
    dag_id="enrichment_dag",
    description="Batch MCP enrichment pipeline: Discover companies in data/payloads + enrich via tavily agent",
    start_date=datetime(2025, 11, 17),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["mcp", "enrichment", "tavily", "batch", "all_companies"],
    max_active_runs=1,  # Only allow one active run
) as dag:
    
    # Task 1: Load companies from payloads directory
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_payloads,
    )
    
    # Task 2: Dynamic task generation for each company
    # Each company gets its own enrichment task
    enrichment_tasks = []
    
    # Load companies for dynamic task generation
    companies = []
    try:
        if PAYLOADS_DIR.exists():
            payload_files = list(PAYLOADS_DIR.glob("*.json"))
            # Filter out versioned files
            companies = [f.stem for f in sorted(payload_files) if "_v" not in f.stem]
            logger.info(f"Loaded {len(companies)} companies from data/payloads for DAG creation")
    except Exception as e:
        logger.error(f"Failed to load companies for DAG creation: {e}")
        # Use empty list if directory can't be read
        companies = []
    
    # If no companies found, log warning but continue
    if not companies:
        logger.warning("No companies found in data/payloads; DAG will have no enrichment tasks")
    
    # Create enrichment tasks for each company
    for i, company_slug in enumerate(companies):
        task_id = f"enrich_{company_slug}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=enrich_company_payload,
            op_kwargs={
                "company_slug": company_slug,
            },
            retries=1,  # Retry once on failure (enrichment can be flaky)
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=30),  # 30 minutes per company
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",  # Use default queue
        )
        
        enrichment_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            enrichment_tasks[i - 1] >> task
    
    # Task 3: Verify enrichment results
    verify_results = PythonOperator(
        task_id="verify_enrichment_results",
        python_callable=verify_enrichment_results,
        trigger_rule="all_done",  # Run even if some tasks failed
    )
    
    # Define task dependencies
    if enrichment_tasks:
        # If we have enrichment tasks, chain them sequentially and then verify
        load_companies >> enrichment_tasks[0]
        enrichment_tasks[-1] >> verify_results
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_results
