"""
Airflow DAG: Batch RAG Pipeline for All 50 Forbes AI Companies

End-to-end RAG pipeline that:
1. Runs experimental_framework.py for all 50 companies
2. Ingests all company pages into Pinecone vector database with deduplication

This DAG orchestrates the complete batch processing workflow.
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

logger = logging.getLogger("rag_batch_ingestion_dag")
logger.setLevel(logging.INFO)

# -------------------------------------------------------------------
# DAG Definition
# -------------------------------------------------------------------
with DAG(
    dag_id="ingest_dag",
    description="Batch RAG pipeline: experimental_framework for all 50 companies + ingest to Pinecone",
    default_args=default_args,
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 11, 6),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,  # ← IMPORTANT: Limit to 1 active task at a time (forces sequential execution)
    tags=["rag", "pinecone", "batch", "all_companies"],
) as dag:

    # =====================================================
    # 2️⃣ Discover all companies in data/raw
    # =====================================================
    @task(task_id="discover_companies")
    def discover_companies():
        """
        Discover all companies from data/raw directory structure.
        
        Returns:
            List of company slugs to be ingested
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
        
        logger.info(f"✅ Found {len(companies)} companies to ingest")
        return companies

    # =====================================================
    # 2b️⃣ Ingest each company into Pinecone (dynamic)
    # =====================================================
    @task(task_id="ingest_company_to_pinecone")
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
        # Get the task logger inside the function (Airflow context)
        import logging
        task_logger = logging.getLogger(f"ingest_company_to_pinecone_{company_slug}")
        
        cmd = [
            PYTHON_EXE,
            "-u",  # Unbuffered output - critical for real-time logging to Airflow
            "src/rag/ingest_to_pinecone.py",
            "--company-slug", company_slug,
        ]
        
        task_logger.info(f"🚀 Running Pinecone ingestion for {company_slug}: {' '.join(cmd)}")
        task_logger.info(f"⏳ Ingesting {company_slug} pages into Pinecone with deduplication...")
        
        # Run subprocess with output capturing so we can log it to Airflow
        # This ensures all subprocess logs appear in the Airflow UI task logs
        res = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            env=os.environ.copy(),  # Pass current environment (includes OPENAI_API_KEY, etc)
            timeout=600,  # 10 minute timeout per company
            stdout=subprocess.PIPE,  # Capture stdout
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True  # Return as string, not bytes
        )
        
        # Log all subprocess output to Airflow so it appears in UI
        if res.stdout:
            task_logger.info(f"=== {company_slug.upper()} INGESTION OUTPUT ===")
            for line in res.stdout.split('\n'):
                if line.strip():  # Skip empty lines
                    task_logger.info(line)
            task_logger.info(f"=== END {company_slug.upper()} OUTPUT ===")
        
        if res.returncode != 0:
            task_logger.error(f"❌ Pinecone ingestion failed for {company_slug} (exit code: {res.returncode})")
            raise RuntimeError(f"Pinecone ingestion failed for {company_slug}")
        
        # Log summary
        task_logger.info(f"✅ Pinecone ingestion completed for {company_slug}")
        
        return {
            "status": "success",
            "company_slug": company_slug,
            "message": f"{company_slug} ingested into Pinecone with deduplication"
        }

    # =====================================================
    # 3️⃣ Verify Pinecone index
    # =====================================================
    @task(task_id="verify_pinecone_index")
    def verify_pinecone_index():
        """
        Verify that all company pages were successfully ingested into Pinecone.
        
        Checks:
        - Pinecone connection and index health
        - Total vector count across all namespaces
        - Metadata file existence for each company
        """
        from pinecone import Pinecone
        import os
        
        logger.info("🔍 Verifying Pinecone index")
        
        try:
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
            from pathlib import Path
            metadata_dir = Path("data/metadata")
            if metadata_dir.exists():
                company_metadata_dirs = [d for d in metadata_dir.iterdir() if d.is_dir()]
                logger.info(f"   Metadata files for {len(company_metadata_dirs)} companies")
                for company_dir in sorted(company_metadata_dirs)[:5]:  # Show first 5
                    logger.info(f"     • {company_dir.name}")
                if len(company_metadata_dirs) > 5:
                    logger.info(f"     ... and {len(company_metadata_dirs) - 5} more")
            
            return {
                "status": "success",
                "index_name": index_name,
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension
            }
        
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            raise RuntimeError(f"Pinecone verification failed: {e}")

    # =====================================================
    # DAG Orchestration - SEQUENTIAL EXECUTION
    # =====================================================
    # Discover all companies first
    companies_list = discover_companies()
    
    # Ingest each company sequentially using pool constraint
    # All tasks use the same pool with 1 slot = sequential execution
    ingest_tasks = ingest_company_to_pinecone.expand(
        company_slug=companies_list
    )
    
    # Verify Pinecone index
    verify_task = verify_pinecone_index()

    # Pipeline: Discover companies → Ingest each company → Verify
    companies_list >> ingest_tasks >> verify_task
