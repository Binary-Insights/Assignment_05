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
from airflow.decorators import task

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------
BASE_DIR = Path("/app")  # Mounted workspace directory in Docker
PYTHON_EXE = sys.executable  # Use current Python interpreter from Airflow environment

default_args = {
    "owner": "ai50_data_team",
    "depends_on_past": False,
    "retries": 0,  # Disable retries for now so we can see actual errors
    "retry_delay": timedelta(minutes=5),
}

logger = logging.getLogger("structured_extraction_dag")
logger.setLevel(logging.INFO)

# -------------------------------------------------------------------
# DAG Definition
# -------------------------------------------------------------------
with DAG(
    dag_id="extraction_payload_dag",
    description="Batch structured extraction pipeline: Extract structured data from all companies using semantic search",
    default_args=default_args,
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 11, 6),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,  # ← IMPORTANT: Limit to 1 active task at a time (forces sequential execution)
    tags=["rag", "pinecone", "extraction", "structured_data", "batch", "all_companies"],
) as dag:

    # =====================================================
    # 1️⃣ Discover all companies in data/raw
    # =====================================================
    @task(task_id="discover_companies")
    def discover_companies():
        """
        Discover all companies from data/raw directory structure.
        
        Returns:
            List of company slugs to be processed for extraction
        """
        raw_dir = Path(str(BASE_DIR)) / "data" / "raw"
        
        if not raw_dir.exists():
            logger.warning(f"Raw data directory not found: {raw_dir}")
            return []
        
        companies = []
        for company_dir in sorted(raw_dir.iterdir()):
            if company_dir.is_dir():
                company_slug = company_dir.name
                companies.append(company_slug)
                logger.info(f"Discovered company: {company_slug}")
        
        logger.info(f"✅ Found {len(companies)} companies for extraction")
        return companies

    # =====================================================
    # 2️⃣ Extract each company's structured data (dynamic)
    # =====================================================
    @task(task_id="extract_company_data")
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
        # Get the task logger inside the function (Airflow context)
        import logging
        task_logger = logging.getLogger(f"extract_company_data_{company_slug}")
        
        try:
            cmd = [
                PYTHON_EXE,
                "-u",  # Unbuffered output - critical for real-time logging to Airflow
                "src/rag/structured_extraction_search.py",
                "--company-slug", company_slug,
                "--fallback-strategy", "pinecone_first",  # Prefer Pinecone, fallback to raw text
            ]
            
            task_logger.info(f"🚀 Running structured extraction for {company_slug}")
            task_logger.info(f"   Command: {' '.join(cmd)}")
            task_logger.info(f"   Working directory: {BASE_DIR}")
            task_logger.info(f"   Python executable: {PYTHON_EXE}")
            
            # Run subprocess with output capturing so we can log it to Airflow
            # This ensures all subprocess logs appear in the Airflow UI task logs
            res = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                env=os.environ.copy(),  # Pass current environment (includes OPENAI_API_KEY, PINECONE_API_KEY, etc)
                timeout=900,  # 15 minute timeout per company (extraction takes longer than ingestion)
                stdout=subprocess.PIPE,  # Capture stdout
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True  # Return as string, not bytes
            )
            
            # Log all subprocess output to Airflow so it appears in UI
            if res.stdout:
                task_logger.info(f"=== {company_slug.upper()} EXTRACTION OUTPUT ===")
                for line in res.stdout.split('\n'):
                    if line.strip():  # Skip empty lines
                        task_logger.info(line)
                task_logger.info(f"=== END {company_slug.upper()} OUTPUT ===")
            
            if res.returncode != 0:
                task_logger.error(f"❌ Structured extraction failed for {company_slug} (exit code: {res.returncode})")
                raise RuntimeError(f"Structured extraction failed for {company_slug} with exit code {res.returncode}")
            
            # Log summary
            task_logger.info(f"✅ Structured extraction completed for {company_slug}")
            
            return {
                "status": "success",
                "company_slug": company_slug,
                "message": f"{company_slug} structured data extracted and saved to payload"
            }
        
        except subprocess.TimeoutExpired as e:
            task_logger.error(f"❌ Extraction timeout for {company_slug}: {e}")
            raise RuntimeError(f"Extraction timeout for {company_slug}")
        except Exception as e:
            task_logger.error(f"❌ Unexpected error during extraction for {company_slug}: {str(e)}")
            raise RuntimeError(f"Extraction failed for {company_slug}: {str(e)}")

    # =====================================================
    # 3️⃣ Verify extraction completion
    # =====================================================
    @task(task_id="verify_extraction_completion")
    def verify_extraction_completion():
        """
        Verify that extraction payloads were successfully created for all companies.
        
        Checks:
        - Payload files exist in data/payloads/
        - Extraction metadata files exist for companies
        - Summary statistics of extracted data
        """
        logger.info("🔍 Verifying extraction completion")
        
        try:
            # Check payload files
            payloads_dir = Path("data/payloads")
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
            metadata_dir = Path("data/metadata")
            if metadata_dir.exists():
                extraction_metadata_files = list(metadata_dir.glob("*/extraction_search_metadata.json"))
                logger.info(f"✅ Found {len(extraction_metadata_files)} extraction metadata files")
                
                if extraction_metadata_files:
                    logger.info(f"   Extraction metadata files:")
                    for meta_file in sorted(extraction_metadata_files)[:10]:  # Show first 10
                        logger.info(f"     • {meta_file.parent.name}/extraction_search_metadata.json")
                    if len(extraction_metadata_files) > 10:
                        logger.info(f"     ... and {len(extraction_metadata_files) - 10} more")
            
            return {
                "status": "success",
                "payload_files_count": len(payload_files),
                "extraction_metadata_count": len(extraction_metadata_files) if metadata_dir.exists() else 0
            }
        
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            raise RuntimeError(f"Extraction verification failed: {e}")

    # =====================================================
    # DAG Orchestration - SEQUENTIAL EXECUTION
    # =====================================================
    # Discover all companies first
    companies_list = discover_companies()
    
    # Extract structured data for each company sequentially
    extraction_tasks = extract_company_data.expand(
        company_slug=companies_list
    )
    
    # Verify extraction completion
    verify_task = verify_extraction_completion()

    # Pipeline: Discover → Extract (sequentially) → Verify
    # The key is to use cross_downstream to chain expanded tasks sequentially
    companies_list >> extraction_tasks >> verify_task
