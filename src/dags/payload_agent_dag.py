"""
Airflow DAG for Payload Agent Processing.

Orchestrates the processing of company payloads using the LangGraph-based payload agent.
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
# DAG is at /app/src/dags/payload_agent_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
PAYLOADS_DIR = PROJECT_ROOT / "data" / "payloads"
PAYLOAD_AGENT_SCRIPT = PROJECT_ROOT / "src" / "payload_agent" / "payload_agent.py"


def load_companies_from_payloads():
    """
    Load company names from payload files in the payloads directory.
    Returns list of company names (without .json extension) for downstream tasks.
    
    This function scans the payloads directory and extracts company identifiers
    from JSON files, excluding versioned files (_v1, _v2, etc.).
    """
    try:
        logger.info("=" * 80)
        logger.info("TASK: LOAD COMPANIES FROM PAYLOADS")
        logger.info("=" * 80)
        logger.info(f"Scanning directory: {PAYLOADS_DIR}")
        
        if not PAYLOADS_DIR.exists():
            logger.error(f"❌ Payloads directory not found: {PAYLOADS_DIR}")
            return []
        
        # Get all .json files, excluding version files
        payload_files = [
            f.stem  # Get filename without extension
            for f in PAYLOADS_DIR.glob("*.json")
            if "_v" not in f.stem  # Exclude versioned files
        ]
        
        companies = sorted(payload_files)
        
        logger.info(f"✅ Successfully loaded {len(companies)} companies from payload files")
        if companies:
            logger.info(f"📋 First 10 companies: {', '.join(companies[:10])}")
            if len(companies) > 10:
                logger.info(f"📋 ... and {len(companies) - 10} more companies")
            logger.info(f"📋 Full company list: {', '.join(companies)}")
        else:
            logger.warning("⚠️  No companies found in payloads directory")
        
        logger.info("=" * 80)
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading payload files: {e}", exc_info=True)
        raise


def process_single_company_task(company_name: str):
    """
    Run payload agent processing for a specific company using subprocess.
    
    Args:
        company_name: Company identifier (e.g., "abridge")
    
    Returns:
        Dictionary with company name and status
    """
    logger_task = logging.getLogger(__name__)
    
    try:
        logger_task.info("=" * 80)
        logger_task.info(f"🚀 TASK: PROCESS COMPANY - {company_name.upper()}")
        logger_task.info("=" * 80)
        logger_task.info(f"📂 Project root: {PROJECT_ROOT}")
        logger_task.info(f"📂 Payloads directory: {PAYLOADS_DIR}")
        logger_task.info(f"📜 Script path: {PAYLOAD_AGENT_SCRIPT}")
        logger_task.info(f"🐍 Python executable: {sys.executable}")
        
        # Build command using direct script path (more reliable in Docker)
        cmd = [
            sys.executable,
            str(PAYLOAD_AGENT_SCRIPT),
            company_name
        ]
        
        logger_task.info(f"⚙️  Command: {' '.join(cmd)}")
        logger_task.info(f"📁 Working directory: {PROJECT_ROOT}")
        
        # Execute processing
        logger_task.info("")
        logger_task.info("=" * 80)
        logger_task.info(f"▶️  PAYLOAD AGENT PROCESSING START FOR {company_name.upper()}")
        logger_task.info("=" * 80)
        logger_task.info("")
        
        # Set up environment with PYTHONPATH to ensure imports work
        env = dict(subprocess.os.environ)
        env['PYTHONPATH'] = str(PROJECT_ROOT)
        env['PYTHONUNBUFFERED'] = '1'
        
        # Track start time
        from time import time
        start_time = time()
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=600,  # 10 minute timeout per company
            env=env,
            text=True,
            capture_output=False,  # Don't capture - let it stream to Airflow logs
        )
        
        # Calculate duration
        duration = time() - start_time
        minutes, seconds = divmod(int(duration), 60)
        
        logger_task.info("")
        logger_task.info("=" * 80)
        logger_task.info(f"⏹️  PAYLOAD AGENT PROCESSING END FOR {company_name.upper()}")
        logger_task.info(f"⏱️  Duration: {minutes}m {seconds}s")
        logger_task.info(f"📊 Return code: {result.returncode}")
        logger_task.info("=" * 80)
        
        if result.returncode != 0:
            error_msg = f"❌ Payload agent processing failed for {company_name} with return code {result.returncode}"
            logger_task.error(error_msg)
            logger_task.error(f"💥 This will be retried (retry attempts remaining: check task instance)")
            raise RuntimeError(error_msg)
        
        logger_task.info(f"✅ Payload agent processing complete for: {company_name}")
        logger_task.info(f"📝 Check data/payloads/{company_name}_v2.json for updated payload")
        logger_task.info("")
        
        return {
            "company": company_name,
            "status": "success",
            "duration_seconds": int(duration)
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"⏰ Payload agent processing timeout for {company_name} (600s exceeded)"
        logger_task.error("=" * 80)
        logger_task.error(error_msg)
        logger_task.error(f"💡 Consider increasing execution_timeout in DAG configuration")
        logger_task.error("=" * 80)
        raise Exception(error_msg)
    except Exception as e:
        logger_task.error("=" * 80)
        logger_task.error(f"❌ Error in payload agent for {company_name}: {str(e)}")
        logger_task.error("=" * 80)
        logger_task.error("Full traceback:", exc_info=True)
        raise


def verify_processing_complete():
    """
    Verify that payload agent processing completed for all companies.
    Checks that updated payload files (_v2.json) exist.
    """
    try:
        logger.info("=" * 80)
        logger.info("TASK: VERIFY PROCESSING COMPLETION")
        logger.info("=" * 80)
        logger.info(f"📂 Checking directory: {PAYLOADS_DIR}")
        
        if not PAYLOADS_DIR.exists():
            logger.warning(f"⚠️  Payloads directory not found: {PAYLOADS_DIR}")
            return {"status": "success", "message": "No payloads to verify"}
        
        # Get non-versioned payload files
        payload_files = [
            f for f in PAYLOADS_DIR.glob("*.json")
            if "_v" not in f.stem
        ]
        
        # Check for _v2 versions (updated payloads)
        updated_files = [
            f for f in PAYLOADS_DIR.glob("*_v2.json")
        ]
        
        total_companies = len(payload_files)
        updated_companies = len(updated_files)
        success_rate = (updated_companies / total_companies * 100) if total_companies > 0 else 0
        
        logger.info("")
        logger.info("📊 PROCESSING SUMMARY:")
        logger.info(f"   Total companies: {total_companies}")
        logger.info(f"   Successfully processed: {updated_companies}")
        logger.info(f"   Success rate: {success_rate:.1f}%")
        logger.info(f"   Output directory: {PAYLOADS_DIR}")
        logger.info("")
        
        if updated_companies > 0:
            logger.info("✅ Updated payload files (_v2.json):")
            for i, f in enumerate(sorted(updated_files)[:10], 1):
                logger.info(f"   {i}. {f.name}")
            if len(updated_files) > 10:
                logger.info(f"   ... and {len(updated_files) - 10} more files")
        
        if updated_companies < total_companies:
            missing_count = total_companies - updated_companies
            logger.warning("")
            logger.warning(f"⚠️  {missing_count} companies may not have been processed")
            logger.warning("   Check task logs for failures")
        
        logger.info("=" * 80)
        logger.info("✅ PAYLOAD AGENT PROCESSING VERIFICATION COMPLETE")
        logger.info("=" * 80)
        
        return {
            "status": "success",
            "total_companies": total_companies,
            "updated_companies": updated_companies,
            "success_rate": f"{success_rate:.1f}%",
            "message": "Payload agent processing verification complete"
        }
    
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Error verifying payload agent processing: {e}")
        logger.error("=" * 80)
        logger.error("Full traceback:", exc_info=True)
        raise


# Define DAG
with DAG(
    dag_id="payload_agent_processing_dag",
    description="Process company payloads using LangGraph payload agent with autonomous tool selection",
    start_date=datetime(2025, 11, 1),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["ai50", "processing", "payload_agent", "langgraph", "react"],
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
    # Each company gets its own processing task
    processing_tasks = []
    
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
            logger.info(f"Loaded {len(companies)} companies for DAG creation: {companies[:5]}{'...' if len(companies) > 5 else ''}")
        else:
            logger.warning(f"PAYLOADS_DIR does not exist: {PAYLOADS_DIR}")
    except Exception as e:
        logger.error(f"Failed to load companies for DAG creation: {e}", exc_info=True)
        companies = []
    
    # If no companies found, log warning but continue
    if not companies:
        logger.warning("No companies found; DAG will have no processing tasks")
    
    # Create processing tasks for each company
    for i, company_name in enumerate(companies):
        task_id = f"process_payload_{company_name}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=process_single_company_task,
            op_kwargs={
                "company_name": company_name,
            },
            retries=2,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=20),  # 20 minutes per company
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",
            doc=f"Run LangGraph payload agent for {company_name} (autonomous tool selection)",
        )
        
        processing_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            processing_tasks[i - 1] >> task
    
    # Task 3: Verify processing completion
    verify_completion = PythonOperator(
        task_id="verify_payload_agent_processing_complete",
        python_callable=verify_processing_complete,
        trigger_rule="all_done",  # Run even if some tasks failed
        doc="Verify that payload agent processing completed for all companies",
    )
    
    # Define task dependencies
    if processing_tasks:
        # If we have processing tasks, chain them sequentially and then verify
        load_companies >> processing_tasks[0]
        processing_tasks[-1] >> verify_completion
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_completion
