"""
Airflow DAG for running LLM pipeline evaluations.

Evaluates all companies in ground_truth.json with both 'structured' and 'rag' pipelines.
Uses Python tasks to execute evaluation commands for each company/pipeline combination.

Schedule: Manual trigger (no automatic schedule)
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import subprocess
import sys

logger = logging.getLogger(__name__)

# Get project root
# DAG is at /app/src/dags/eval_runner_dag.py, so go up 3 levels to /app
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Evaluation configuration
GROUND_TRUTH_FILE = PROJECT_ROOT / "data" / "eval" / "ground_truth.json"
EVAL_SCRIPT = PROJECT_ROOT / "src" / "evals" / "result_evaluator.py"
RESPONSE_DIR = PROJECT_ROOT / "data" / "llm_response" / "json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "eval" / "results_llm_eval.json"


def load_companies_from_ground_truth():
    """
    Load company slugs from ground_truth.json.
    Returns list of company slugs for downstream tasks.
    """
    try:
        logger.info("✓ Loading companies from ground truth...")
        
        if not GROUND_TRUTH_FILE.exists():
            logger.error(f"Ground truth file not found: {GROUND_TRUTH_FILE}")
            return []
        
        with open(GROUND_TRUTH_FILE, "r") as f:
            ground_truth = json.load(f)
        
        companies = list(ground_truth.keys())
        logger.info(f"✓ Loaded {len(companies)} companies from ground truth")
        logger.info(f"  Companies: {', '.join(companies)}")
        
        return companies
    
    except Exception as e:
        logger.error(f"❌ Error loading ground truth: {e}", exc_info=True)
        raise


def evaluate_company_pipeline(company_slug: str):
    """
    Run evaluation for a specific company (evaluates both pipelines).
    
    Args:
        company_slug: Company slug (e.g., "world-labs")
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting evaluation for company: {company_slug}")
        
        # Build command using result_evaluator.py flags
        cmd = [
            sys.executable,
            str(EVAL_SCRIPT),
            "--company", company_slug,
            "--ground-truth", str(GROUND_TRUTH_FILE),
            "--response-dir", str(RESPONSE_DIR),
            "--output", str(OUTPUT_FILE)
        ]
        
        logger.info(f"Running: {' '.join(cmd)}")
        logger.info(f"Working directory: {PROJECT_ROOT}")
        logger.info(f"EVAL_SCRIPT path: {EVAL_SCRIPT}")
        logger.info(f"EVAL_SCRIPT exists: {EVAL_SCRIPT.exists()}")
        
        # Execute evaluation - capture output AND stream to logs
        logger.info("=" * 80)
        logger.info(f"SUBPROCESS OUTPUT START FOR {company_slug}")
        logger.info("=" * 80)
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=600,  # 10 minute timeout
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
            error_msg = f"Evaluation failed for {company_slug} with return code {result.returncode}"
            logger.error(error_msg)
            if result.stderr:
                logger.error(f"Error details: {result.stderr}")
            raise RuntimeError(error_msg)
        
        logger.info(f"✓ Evaluation complete for: {company_slug}")
        
        return {
            "company": company_slug,
            "status": "success"
        }
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Evaluation timeout for {company_slug} (600s exceeded)"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Error evaluating {company_slug}: {str(e)}", exc_info=True)
        raise


def generate_comparison_report():
    """
    Generate batch evaluation report for all companies.
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Generating batch evaluation report...")
        
        cmd = [
            sys.executable,
            str(EVAL_SCRIPT),
            "--batch",
            "--ground-truth", str(GROUND_TRUTH_FILE),
            "--response-dir", str(RESPONSE_DIR),
            "--output", str(OUTPUT_FILE)
        ]
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        # Execute - stream output instead of capturing
        logger.info("=" * 80)
        logger.info("BATCH EVALUATION OUTPUT START")
        logger.info("=" * 80)
        
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=3600,  # 60 minute timeout for batch evaluation
            text=True,
            # Don't capture - let output stream to Airflow logs directly
        )
        
        logger.info("=" * 80)
        logger.info("BATCH EVALUATION OUTPUT END")
        logger.info(f"Return code: {result.returncode}")
        logger.info("=" * 80)
        
        if result.returncode != 0:
            error_msg = f"Batch evaluation failed with return code {result.returncode}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        logger.info("✓ Batch evaluation and report generated")
        
        return {"status": "success", "message": "Batch evaluation complete"}
    
    except subprocess.TimeoutExpired as e:
        logger.error(f"❌ Batch evaluation timeout (3600s exceeded)", exc_info=True)
        raise Exception(f"Batch evaluation timeout: {str(e)}")
    except Exception as e:
        logger.error(f"Error generating batch report: {str(e)}", exc_info=True)
        raise


# Define DAG
with DAG(
    dag_id="eval_runner_dag",
    description="Run LLM pipeline evaluations for all companies",
    start_date=datetime(2025, 11, 7),
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=["evaluation", "ml_pipeline", "quality_assurance"],
    max_active_runs=1,  # Only allow one active run
) as dag:
    
    # Task 1: Load companies from ground truth
    load_companies = PythonOperator(
        task_id="load_companies",
        python_callable=load_companies_from_ground_truth,
    )
    
    # Task 2: Dynamic task generation for each company
    # result_evaluator.py evaluates both pipelines for each company
    evaluation_tasks = []
    
    # Load ground truth for dynamic task generation
    companies = []
    try:
        if GROUND_TRUTH_FILE.exists():
            with open(GROUND_TRUTH_FILE, "r") as f:
                ground_truth = json.load(f)
            companies = list(ground_truth.keys())
            logger.info(f"Loaded {len(companies)} companies from ground_truth.json for DAG creation")
    except Exception as e:
        logger.error(f"Failed to load ground truth for DAG creation: {e}")
        # Use default companies for testing if file can't be loaded
        companies = ["world-labs"]
    
    # If still empty (file doesn't exist), use defaults
    if not companies:
        logger.warning("No companies found; using default test companies")
        companies = ["world-labs"]
    
    # Create evaluation tasks for each company (evaluates both pipelines per company)
    for i, company_slug in enumerate(companies):
        task_id = f"evaluate_{company_slug}"
        
        task = PythonOperator(
            task_id=task_id,
            python_callable=evaluate_company_pipeline,
            op_kwargs={
                "company_slug": company_slug,
            },
            retries=2,  # Retry up to 2 times on failure
            retry_delay=timedelta(minutes=5),  # Wait 5 minutes between retries
            execution_timeout=timedelta(minutes=15),  # 15 minutes per evaluation
            pool="sequential_pool",  # Use sequential pool
            pool_slots=1,  # Only 1 concurrent execution
            queue="default",  # Use default queue
        )
        
        evaluation_tasks.append(task)
        
        # Create explicit dependencies to make tasks run sequentially
        if i > 0:
            # Each task depends on the previous one
            evaluation_tasks[i - 1] >> task
    
    # Task 3: Generate comparison report
    generate_report = PythonOperator(
        task_id="generate_comparison_report",
        python_callable=generate_comparison_report,
        trigger_rule="all_done",  # Run even if some evaluations failed
    )
    
    # Define task dependencies
    if evaluation_tasks:
        # If we have evaluation tasks, chain them sequentially and then generate report
        load_companies >> evaluation_tasks[0]
        evaluation_tasks[-1] >> generate_report
    else:
        # If no tasks, go directly to report
        load_companies >> generate_report

