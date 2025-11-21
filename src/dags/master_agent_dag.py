"""
Airflow DAG: Master Agent Orchestrator - Batch Enrichment Pipeline

End-to-end enrichment pipeline that:
1. Discovers all companies in data/payloads directory
2. Runs master orchestrator (Tavily + Payload agents) for each company
3. Generates comprehensive enrichment reports with versioning

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
from airflow.models import Variable

logger = logging.getLogger(__name__)

# Get project root
# DAG is at /app/src/dags/master_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configuration
MASTER_SCRIPT = PROJECT_ROOT / "src" / "master_agent" / "master.py"


def load_companies_from_payloads():
    """
    Load company slugs from data/payloads directory.
    
    Returns:
        List of company slugs to be enriched
    """
    try:
        logger.info("✓ Loading companies from data/payloads directory...")
        
        payloads_dir = PROJECT_ROOT / "data" / "payloads"
        
        if not payloads_dir.exists():
            logger.error(f"Payloads directory not found: {payloads_dir}")
            return []
        
        companies = set()
        
        # Find all company payload files (excluding versioned backups)
        for payload_file in sorted(payloads_dir.glob("*.json")):
            filename = payload_file.stem  # Get filename without extension
            
            # Skip versioned backup files (e.g., abridge_v1.json, abridge_v18.json)
            if "_v" in filename and filename.split("_v")[-1].isdigit():
                continue
            
            companies.add(filename)
            logger.info(f"Discovered company: {filename}")
        
        companies = sorted(list(companies))
        
        logger.info(f"✓ Found {len(companies)} companies to enrich")
        logger.info(f"  Companies: {', '.join(companies[:5])}{'...' if len(companies) > 5 else ''}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading companies from payloads: {e}", exc_info=True)
        raise


def run_master_orchestrator(
    company_slug: str,
    enable_tavily: bool = True,
    enable_payload: bool = True,
    verbose: bool = True
):
    """
    Run master orchestrator for a single company.
    
    This will:
    - Phase 1: Tavily Agent - Enrich company_record fields via web search
    - Phase 2: Payload Agent - Extract entities via Pinecone vector search
    - Merge results and generate comprehensive statistics
    - Auto-version payloads with backups
    
    Args:
        company_slug: The company identifier to enrich
        enable_tavily: Run Tavily agent (default: True)
        enable_payload: Run Payload agent (default: True)
        verbose: Enable verbose logging (default: True)
    """
    task_logger = logging.getLogger(__name__)
    
    try:
        task_logger.info("=" * 80)
        task_logger.info(f"🚀 MASTER ORCHESTRATOR - Starting enrichment for {company_slug}")
        task_logger.info("=" * 80)
        task_logger.info(f"   Tavily Agent: {'✅ ENABLED' if enable_tavily else '❌ DISABLED'}")
        task_logger.info(f"   Payload Agent: {'✅ ENABLED' if enable_payload else '❌ DISABLED'}")
        task_logger.info(f"   Verbose Logging: {'✅ ENABLED' if verbose else '❌ DISABLED'}")
        task_logger.info("")
        
        # Build command
        cmd = [
            sys.executable,
            "-u",  # Unbuffered output - critical for real-time logging to Airflow
            str(MASTER_SCRIPT),
            company_slug,
        ]
        
        # Add optional flags
        if verbose:
            cmd.append("--verbose")
        
        if not enable_tavily and enable_payload:
            cmd.append("--payload-only")
        elif enable_tavily and not enable_payload:
            cmd.append("--tavily-only")
        
        task_logger.info(f"Running: {' '.join(cmd)}")
        task_logger.info(f"Working directory: {PROJECT_ROOT}")
        task_logger.info(f"MASTER_SCRIPT path: {MASTER_SCRIPT}")
        task_logger.info(f"MASTER_SCRIPT exists: {MASTER_SCRIPT.exists()}")
        
        # Ensure environment variables are set
        required_env_vars = ['OPENAI_API_KEY', 'PINECONE_API_KEY', 'TAVILY_API_KEY']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            task_logger.warning(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        
        # Execute master orchestrator - stream output to Airflow logs
        task_logger.info("=" * 80)
        task_logger.info(f"MASTER ORCHESTRATOR OUTPUT START FOR {company_slug}")
        task_logger.info("=" * 80)
        
        # Use Popen for real-time streaming to Airflow logs
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env={**dict(os.environ), 'PYTHONUNBUFFERED': '1'},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        # Stream output line-by-line to Airflow task log
        for line in iter(process.stdout.readline, ''):
            if line:
                # Remove trailing newline and log
                task_logger.info(line.rstrip())
        
        # Wait for process to complete
        return_code = process.wait(timeout=1800)  # 30 minute timeout
        
        task_logger.info("=" * 80)
        task_logger.info(f"MASTER ORCHESTRATOR OUTPUT END FOR {company_slug}")
        task_logger.info(f"Return code: {return_code}")
        task_logger.info("=" * 80)
        
        if return_code != 0:
            error_msg = f"Master orchestrator failed for {company_slug} with return code {return_code}"
            task_logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        task_logger.info(f"✓ Master orchestrator complete for: {company_slug}")
        
        return {
            "company": company_slug,
            "status": "success",
            "tavily_enabled": enable_tavily,
            "payload_enabled": enable_payload
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Master orchestrator timeout for {company_slug} (1800s exceeded)"
        task_logger.error(error_msg, exc_info=True)
        
        # Kill the process
        if process:
            process.kill()
            process.wait()
        
        raise Exception(error_msg)
    except Exception as e:
        task_logger.error(f"Error running master orchestrator for {company_slug}: {str(e)}", exc_info=True)
        raise


def verify_enrichment_results():
    """
    Verify that all companies were successfully enriched.
    
    Checks:
    - Payload files exist and have valid structure
    - Versioned backups created
    - Entity counts and field completion
    """
    try:
        import json
        
        logger.info("🔍 Verifying enrichment results...")
        
        payloads_dir = PROJECT_ROOT / "data" / "payloads"
        
        if not payloads_dir.exists():
            raise RuntimeError(f"Payloads directory not found: {payloads_dir}")
        
        # Get all current payload files (non-versioned)
        payload_files = [
            f for f in sorted(payloads_dir.glob("*.json"))
            if not ("_v" in f.stem and f.stem.split("_v")[-1].isdigit())
        ]
        
        logger.info(f"✅ Found {len(payload_files)} payload files")
        
        total_fields_filled = 0
        total_entities = 0
        
        for payload_file in payload_files[:10]:  # Show details for first 10
            try:
                with open(payload_file, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                
                # Count filled fields in company_record
                company_record = payload.get("company_record", {})
                filled_fields = sum(1 for v in company_record.values() if v is not None and v != "")
                
                # Count entities
                entities = (
                    len(payload.get("events", [])) +
                    len(payload.get("products", [])) +
                    len(payload.get("leadership", [])) +
                    len(payload.get("snapshots", [])) +
                    len(payload.get("visibility", []))
                )
                
                total_fields_filled += filled_fields
                total_entities += entities
                
                logger.info(f"   • {payload_file.stem}: {filled_fields} fields, {entities} entities")
                
            except Exception as e:
                logger.warning(f"   ⚠️  Could not verify {payload_file.stem}: {e}")
        
        if len(payload_files) > 10:
            logger.info(f"   ... and {len(payload_files) - 10} more")
        
        logger.info(f"\n📊 Overall Statistics:")
        logger.info(f"   Total payloads: {len(payload_files)}")
        logger.info(f"   Average fields filled: {total_fields_filled / len(payload_files):.1f}")
        logger.info(f"   Average entities: {total_entities / len(payload_files):.1f}")
        
        # Check for versioned backups
        versioned_files = [
            f for f in payloads_dir.glob("*_v*.json")
            if "_v" in f.stem and f.stem.split("_v")[-1].isdigit()
        ]
        
        logger.info(f"\n📦 Versioning:")
        logger.info(f"   Versioned backups: {len(versioned_files)}")
        
        logger.info(f"\n✓ Enrichment verification complete")
        
        return {
            "status": "success",
            "total_payloads": len(payload_files),
            "total_backups": len(versioned_files),
            "avg_fields_filled": total_fields_filled / len(payload_files) if payload_files else 0,
            "avg_entities": total_entities / len(payload_files) if payload_files else 0
        }
    
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}", exc_info=True)
        raise RuntimeError(f"Enrichment verification failed: {e}")


# Default arguments for DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define DAG
with DAG(
    dag_id="master_agent_dag",
    description="Master Agent Orchestrator: Batch enrichment with Tavily + Payload agents",
    default_args=default_args,
    start_date=datetime(2025, 11, 20),
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=["master", "enrichment", "tavily", "payload", "batch"],
    max_active_runs=1,  # Only allow one active run
    params={
        "enable_tavily": True,
        "enable_payload": True,
        "verbose": True,
    },
) as dag:
    
    # Task 1: Load companies from payloads directory
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_payloads,
    )
    
    # Task 2: Dynamic task generation for each company
    # Each company gets its own master orchestrator task
    master_tasks = []
    
    # Load companies for dynamic task generation
    companies = []
    try:
        payloads_dir = PROJECT_ROOT / "data" / "payloads"
        if payloads_dir.exists():
            # Get non-versioned payload files
            for f in sorted(payloads_dir.glob("*.json")):
                if not ("_v" in f.stem and f.stem.split("_v")[-1].isdigit()):
                    companies.append(f.stem)
            logger.info(f"Loaded {len(companies)} companies from data/payloads for DAG creation")
    except Exception as e:
        logger.error(f"Failed to load companies for DAG creation: {e}")
        companies = []
    
    # If no companies found, log warning but continue
    if not companies:
        logger.warning("No companies found in data/payloads; DAG will have no enrichment tasks")
    
    # Create master orchestrator tasks for each company
    for i, company_slug in enumerate(companies):
        task_id = f"enrich_{company_slug}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=run_master_orchestrator,
            op_kwargs={
                "company_slug": company_slug,
                "enable_tavily": "{{ params.enable_tavily }}",
                "enable_payload": "{{ params.enable_payload }}",
                "verbose": "{{ params.verbose }}",
            },
            retries=2,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=30),  # 30 minutes per company
            pool="sequential_pool",  # Use sequential pool with 1 slot
            pool_slots=1,  # Only 1 concurrent execution per task
            queue="default",  # Use default queue
        )
        
        master_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            master_tasks[i - 1] >> task
    
    # Task 3: Verify enrichment results
    verify_results = PythonOperator(
        task_id="verify_enrichment_results",
        python_callable=verify_enrichment_results,
        trigger_rule="all_done",  # Run even if some tasks failed
    )
    
    # Define task dependencies
    if master_tasks:
        # If we have enrichment tasks, chain them sequentially and then verify
        load_companies >> master_tasks[0]
        master_tasks[-1] >> verify_results
    else:
        # If no tasks, go directly to verify
        load_companies >> verify_results
