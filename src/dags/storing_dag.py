from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import subprocess
import logging
import json

def get_valid_ai50_companies():
    """
    Dynamically discover valid AI50 company folders from data/raw.
    Validates companies against the seed data list.
    Handles name matching with slugified folder names.
    """
    logger = logging.getLogger(__name__)
    base_dir = '/opt/airflow/workspace'
    raw_data_path = os.path.join(base_dir, 'data', 'raw')
    seed_file_path = os.path.join(base_dir, 'data', 'forbes_ai50_seed.json')
    
    def slugify(text):
        """Convert text to slug format (lowercase, underscores instead of spaces)."""
        return text.lower().replace(' ', '_').replace('-', '_')
    
    valid_companies = []
    
    # Load AI50 companies from seed data for validation
    try:
        with open(seed_file_path, 'r') as f:
            seed_data = json.load(f)
            # Create mapping of slugified names to original company_name
            valid_company_map = {}
            for item in seed_data:
                company_name = item.get('company_name')
                if company_name:
                    slugified = slugify(company_name)
                    valid_company_map[slugified] = company_name
                    logger.debug(f"Seed: {company_name} → {slugified}")
    except Exception as e:
        logger.error(f"Failed to load forbes_ai50_seed.json: {e}")
        return []
    
    logger.info(f"Loaded {len(valid_company_map)} companies from seed data")
    
    # Check if raw data directory exists
    if not os.path.exists(raw_data_path):
        logger.warning(f"Raw data directory not found: {raw_data_path}")
        return []
    
    # Discover folders in data/raw/
    for folder_name in os.listdir(raw_data_path):
        folder_path = os.path.join(raw_data_path, folder_name)
        if not os.path.isdir(folder_path):
            continue
        
        # Validate company exists in AI50 list (by slugified name)
        if folder_name not in valid_company_map:
            logger.debug(f"Folder {folder_name} is not a valid AI50 company, skipping")
            continue
        
        # Check if there are any files to upload
        try:
            has_content = False
            for root, dirs, files in os.walk(folder_path):
                if files:
                    has_content = True
                    break
            
            if not has_content:
                logger.debug(f"No raw content found for {folder_name} in {folder_path}")
                continue
        except Exception as e:
            logger.warning(f"Error checking raw content for {folder_name}: {e}")
            continue
        
        # Use the original company_name from seed data, but store the folder_name
        original_company_name = valid_company_map[folder_name]
        valid_companies.append({
            'folder_name': folder_name,
            'company_name': original_company_name
        })
        logger.info(f"✅ Valid AI50 company found: {original_company_name} (folder: {folder_name})")
    
    logger.info(f"Total valid AI50 companies found for storing: {len(valid_companies)}")
    return valid_companies

def run_store_ai50_data(company_info):
    """
    Upload raw data and metadata for a given AI50 company to S3.
    Uploads HTML files, links, metadata, and provenance from:
    - data/raw/{company_info['folder_name']}
    - data/metadata/{company_info['folder_name']}
    """
    # Handle both old format (string) and new format (dict) for backward compatibility
    if isinstance(company_info, str):
        folder_name = company_info
        company_name = company_info
    else:
        folder_name = company_info['folder_name']
        company_name = company_info['company_name']
    
    logger = logging.getLogger(__name__)
    base_dir = '/opt/airflow/workspace'
    script_path = os.path.join(base_dir, 'scripts', 'store', 's3_uploader.py')
    bucket = os.environ.get('S3_BUCKET_NAME', 'damg-assignment-04-airflow')
    
    # Log bucket being used for debugging
    logger.info(f"Using S3 bucket from env: {bucket}")
    logger.info(f"Company: {company_name} (folder: {folder_name})")
    
    # Pre-flight checks for AWS credentials
    logger.info("Performing pre-flight AWS credential checks...")
    aws_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
    logger.info(f"AWS_ACCESS_KEY_ID configured: {'✅ Yes' if aws_key else '❌ NO - NOT SET'}")
    logger.info(f"AWS_SECRET_ACCESS_KEY configured: {'✅ Yes' if aws_secret else '❌ NO - NOT SET'}")
    logger.info(f"AWS_DEFAULT_REGION: {os.environ.get('AWS_DEFAULT_REGION', 'not set')}")
    
    # Test boto3 availability and S3 connection
    try:
        import boto3
        logger.info(f"boto3 available: ✅ Yes (version {boto3.__version__})")
        
        # Test boto3 connection
        test_session = boto3.Session()
        test_client = test_session.client('s3', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
        test_client.head_bucket(Bucket=bucket)
        logger.info(f"✅ S3 bucket accessible: {bucket}")
    except Exception as e:
        logger.error(f"❌ boto3 test failed: {e}")
        raise Exception(f"S3 connection test failed: {e}")
    
    # Define both raw and metadata folders to upload
    folders_to_upload = [
        {
            'local_path': os.path.join(base_dir, 'data', 'raw', folder_name),
            's3_prefix': f'raw/{folder_name}'
        },
        {
            'local_path': os.path.join(base_dir, 'data', 'metadata', folder_name),
            's3_prefix': f'metadata/{folder_name}'
        }
    ]
    
    try:
        os.chdir(base_dir)
        
        for folder_info in folders_to_upload:
            local_folder = folder_info['local_path']
            prefix = folder_info['s3_prefix']
            
            # Pre-flight checks
            if not os.path.exists(local_folder):
                logger.warning(f"⏭️  Folder not found, skipping: {local_folder}")
                continue
            
            # Check if there's actually content to upload
            has_content = False
            file_count = 0
            try:
                for root, dirs, files in os.walk(local_folder):
                    for file in files:
                        file_count += 1
                        has_content = True
                
                if not has_content:
                    logger.warning(f"⏭️  No files found in {local_folder}, skipping")
                    continue
                
                logger.info(f"Found {file_count} files to upload in {prefix}")
            except Exception as e:
                logger.warning(f"Error checking content in {local_folder}: {e}")
                continue
            
            logger.info(f"📤 Uploading {prefix} data for {company_name} to S3")
            logger.info(f"   Local folder: {local_folder}")
            logger.info(f"   S3 destination: s3://{bucket}/{prefix}")
            
            result = subprocess.run([
                'python', script_path,
                '--local_folder', local_folder,
                '--bucket', bucket,
                '--prefix', prefix
            ], capture_output=True, text=True, timeout=900)
            
            if result.stdout:
                logger.info(f"S3 upload output for {prefix}:\n{result.stdout}")
            
            if result.returncode != 0:
                logger.error(f"❌ S3 upload error for {prefix}: {result.stderr}")
                raise Exception(f"Store failed for {prefix}: {result.stderr}")
            else:
                logger.info(f"✅ Successfully uploaded {prefix} ({file_count} files)")
        
        return f"✅ Store Success: {company_name} (raw + metadata)"
        
    except subprocess.TimeoutExpired:
        logger.error(f"⏱️  S3 upload timeout for {company_name} (exceeded 15 minutes)")
        raise Exception(f"Store timeout for {company_name}")
    except Exception as e:
        logger.error(f"❌ Store error for {company_name}: {str(e)}")
        raise

default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 11, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'store_ai50_data_dag',
    default_args=default_args,
    description='Store AI50 company raw and metadata to S3 - dynamically discovers valid companies',
    schedule_interval=None,
    catchup=False,
    tags=['ai50', 'store', 's3'],
)

# Dynamically discover valid AI50 companies
AI50_COMPANIES = get_valid_ai50_companies()

store_tasks = []
for company_info in AI50_COMPANIES:
    folder_name = company_info['folder_name']
    company_name = company_info['company_name']
    store_task = PythonOperator(
        task_id=f'store_ai50_{folder_name.lower()}',
        python_callable=run_store_ai50_data,
        op_args=[company_info],
        dag=dag,
    )
    store_tasks.append(store_task)

# Log the discovered companies for debugging
company_names = [c['company_name'] for c in AI50_COMPANIES]
logging.getLogger(__name__).info(f"DAG will process {len(AI50_COMPANIES)} AI50 companies: {company_names}")
