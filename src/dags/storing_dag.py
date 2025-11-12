"""Airflow DAG to store AI50 company data to S3"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import subprocess
import logging
import json


def slugify(text):
    """Convert text to slug format."""
    return text.lower().replace(' ', '_').replace('-', '_')


def get_ai50_companies_from_seed():
    """Load valid AI50 companies from seed data."""
    logger = logging.getLogger(__name__)
    seed_file = '/app/data/forbes_ai50_seed.json'
    
    if not os.path.exists(seed_file):
        logger.error(f"Seed file not found: {seed_file}")
        return {}
    
    try:
        with open(seed_file, 'r') as f:
            seed_data = json.load(f)
        
        company_map = {}
        for item in seed_data:
            company_name = item.get('company_name')
            if company_name:
                slug = slugify(company_name)
                company_map[slug] = company_name
        
        logger.info(f"Loaded {len(company_map)} AI50 companies from seed data")
        return company_map
        
    except Exception as e:
        logger.error(f"Failed to load seed data: {e}")
        return {}


def discover_valid_companies(company_map):
    """Discover valid AI50 companies with existing raw data."""
    logger = logging.getLogger(__name__)
    raw_data_path = '/app/data/raw'
    valid_companies = []
    
    if not os.path.exists(raw_data_path):
        logger.warning(f"Raw data directory not found: {raw_data_path}")
        return valid_companies
    
    for folder_name in sorted(os.listdir(raw_data_path)):
        folder_path = os.path.join(raw_data_path, folder_name)
        
        if not os.path.isdir(folder_path):
            continue
        
        if folder_name not in company_map:
            continue
        
        try:
            has_files = any(files for _, _, files in os.walk(folder_path))
            if not has_files:
                continue
        except Exception as e:
            logger.warning(f"Error checking {folder_name}: {e}")
            continue
        
        original_name = company_map[folder_name]
        valid_companies.append({
            'folder_name': folder_name,
            'company_name': original_name
        })
        logger.info(f"Discovered: {original_name} (folder: {folder_name})")
    
    logger.info(f"Total companies to process: {len(valid_companies)}")
    return valid_companies


def upload_company_to_s3(company_info):
    """Upload raw data and metadata for single company to S3."""
    folder_name = company_info.get('folder_name')
    company_name = company_info.get('company_name')
    
    logger = logging.getLogger(__name__)
    base_dir = '/app'
    uploader_script = os.path.join(base_dir, 'src', 'store', 's3_uploader.py')
    bucket = os.environ.get('S3_BUCKET_NAME', 'damg-assignment-04-airflow')
    
    logger.info("=" * 70)
    logger.info(f"UPLOADING COMPANY DATA: {company_name}")
    logger.info("=" * 70)
    
    if not os.environ.get('AWS_ACCESS_KEY_ID'):
        raise Exception("AWS_ACCESS_KEY_ID not configured")
    if not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        raise Exception("AWS_SECRET_ACCESS_KEY not configured")
    
    upload_tasks = [
        {
            'local': os.path.join(base_dir, 'data', 'raw', folder_name),
            's3_prefix': f'raw/{folder_name}',
            'description': 'Raw HTML pages'
        },
        {
            'local': os.path.join(base_dir, 'data', 'metadata', folder_name),
            's3_prefix': f'metadata/{folder_name}',
            'description': 'Metadata'
        }
    ]
    
    try:
        os.chdir(base_dir)
        total_files = 0
        
        for task in upload_tasks:
            local_path = task['local']
            s3_prefix = task['s3_prefix']
            
            if not os.path.exists(local_path):
                logger.info(f"Skipping (not found): {s3_prefix}")
                continue
            
            file_count = sum(len(files) for _, _, files in os.walk(local_path))
            
            if file_count == 0:
                logger.info(f"Skipping (empty): {s3_prefix}")
                continue
            
            logger.info(f"Uploading {s3_prefix}: {file_count} files")
            
            result = subprocess.run(
                [
                    'python', uploader_script,
                    '--local_folder', local_path,
                    '--bucket', bucket,
                    '--prefix', s3_prefix
                ],
                capture_output=True,
                text=True,
                timeout=900
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Upload failed: {error_msg}")
                raise Exception(f"S3 upload failed for {s3_prefix}")
            
            logger.info(f"Uploaded: {file_count} files to {s3_prefix}")
            total_files += file_count
        
        logger.info(f"COMPANY UPLOAD COMPLETE: {company_name} ({total_files} files)")
        return f"Success: {company_name}: {total_files} files"
        
    except subprocess.TimeoutExpired:
        logger.error(f"Upload timeout for {company_name}")
        raise
    except Exception as e:
        logger.error(f"Error uploading {company_name}: {e}")
        raise


def upload_consolidated_data_backup():
    """Upload consolidated data backup: payloads, llm_response, eval."""
    logger = logging.getLogger(__name__)
    base_dir = '/app'
    uploader_script = os.path.join(base_dir, 'src', 'store', 's3_uploader.py')
    bucket = os.environ.get('S3_BUCKET_NAME', 'damg-assignment-04-airflow')
    
    logger.info("=" * 70)
    logger.info("CONSOLIDATED DATA BACKUP TO S3")
    logger.info("=" * 70)
    
    backup_folders = [
        {
            'local': os.path.join(base_dir, 'data', 'payloads'),
            's3_prefix': 'data/payloads',
            'description': 'Structured extractions (50 companies)'
        },
        {
            'local': os.path.join(base_dir, 'data', 'llm_response'),
            's3_prefix': 'data/llm_response',
            'description': 'Markdown dashboards'
        },
        {
            'local': os.path.join(base_dir, 'data', 'eval'),
            's3_prefix': 'data/eval',
            'description': 'Evaluation results'
        }
    ]
    
    try:
        os.chdir(base_dir)
        total_files = 0
        total_size = 0
        
        for folder_info in backup_folders:
            local_path = folder_info['local']
            s3_prefix = folder_info['s3_prefix']
            description = folder_info['description']
            
            if not os.path.exists(local_path):
                logger.info(f"Skipping (not found): {s3_prefix}")
                continue
            
            file_count = 0
            folder_size = 0
            
            for root, dirs, files in os.walk(local_path):
                for filename in files:
                    file_count += 1
                    file_path = os.path.join(root, filename)
                    try:
                        folder_size += os.path.getsize(file_path)
                    except OSError:
                        pass
            
            if file_count == 0:
                logger.info(f"Skipping (empty): {s3_prefix}")
                continue
            
            size_mb = folder_size / (1024 * 1024)
            logger.info(f"Backing up {s3_prefix}: {file_count} files ({size_mb:.2f} MB)")
            
            result = subprocess.run(
                [
                    'python', uploader_script,
                    '--local_folder', local_path,
                    '--bucket', bucket,
                    '--prefix', s3_prefix
                ],
                capture_output=True,
                text=True,
                timeout=900
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Backup failed: {error_msg}")
                raise Exception(f"Backup failed for {s3_prefix}")
            
            logger.info(f"Backed up {file_count} files ({size_mb:.2f} MB)")
            total_files += file_count
            total_size += size_mb
        
        logger.info(f"BACKUP COMPLETE: {total_files} files ({total_size:.2f} MB)")
        return f"Backup complete: {total_files} files"
        
    except subprocess.TimeoutExpired:
        logger.error("Backup timeout")
        raise
    except Exception as e:
        logger.error(f"Backup error: {e}")
        raise


default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 11, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    dag_id='store_ai50_data_dag',
    default_args=default_args,
    description='Store AI50 company data (raw + metadata) and consolidated backup to S3',
    schedule_interval=None,
    catchup=False,
    tags=['ai50', 'store', 's3', 'backup'],
)


logger = logging.getLogger(__name__)
company_map = get_ai50_companies_from_seed()
valid_companies = discover_valid_companies(company_map)

logger.info(f"STORING DAG SETUP: {len(valid_companies)} companies")

company_tasks = []
for company_info in valid_companies:
    folder_name = company_info['folder_name']
    
    task = PythonOperator(
        task_id=f'store_{folder_name}',
        python_callable=upload_company_to_s3,
        op_args=[company_info],
        dag=dag,
    )
    company_tasks.append(task)

backup_task = PythonOperator(
    task_id='consolidated_data_backup',
    python_callable=upload_consolidated_data_backup,
    dag=dag,
)

if company_tasks:
    # All company tasks must complete before backup runs
    for task in company_tasks:
        task >> backup_task
else:
    logger.warning("No companies to process, backup task will run standalone")
