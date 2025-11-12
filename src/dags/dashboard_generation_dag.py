"""
Dashboard Generation DAG - Orchestrate structured.md and rag.md generation for all 50 companies

This DAG:
1. Discovers all 50 AI50 companies from seed data
2. For each company, generates:
   - structured.md via POST /dashboard/structured
   - rag.md via POST /dashboard/rag
3. Saves both dashboards to data/llm_response/markdown/{company_slug}/

Schedule: Manual trigger only
Dependencies: FastAPI server must be running with /dashboard/structured and /dashboard/rag endpoints
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import json
import requests
import logging

logger = logging.getLogger(__name__)


def slugify(text):
    """Convert text to slug format."""
    return text.lower().replace(' ', '_').replace('-', '_')


def get_ai50_companies_from_seed():
    """Load valid AI50 companies from seed data."""
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
    """Discover valid AI50 companies with existing payloads."""
    logger = logging.getLogger(__name__)
    payloads_path = '/app/data/payloads'
    valid_companies = []
    
    if not os.path.exists(payloads_path):
        logger.warning(f"Payloads directory not found: {payloads_path}")
        return valid_companies
    
    for file_name in sorted(os.listdir(payloads_path)):
        if not file_name.endswith('.json'):
            continue
        
        slug = file_name[:-5]  # Remove .json
        
        if slug not in company_map:
            continue
        
        original_name = company_map[slug]
        valid_companies.append({
            'folder_name': slug,
            'company_name': original_name,
            'company_slug': slug
        })
        logger.info(f"Discovered: {original_name} (slug: {slug})")
    
    logger.info(f"Total companies with payloads: {len(valid_companies)}")
    return valid_companies


def generate_structured_dashboard(company_info):
    """
    Generate structured.md dashboard and JSON response for a company via FastAPI endpoint.
    
    Args:
        company_info: Dict with company_name and company_slug
    """
    company_name = company_info.get('company_name')
    company_slug = company_info.get('company_slug')
    
    logger = logging.getLogger(__name__)
    
    # Get FastAPI URL from environment or use default
    fastapi_url = os.environ.get('FASTAPI_URL', 'http://fastapi:8000')
    
    logger.info("=" * 70)
    logger.info(f"GENERATING STRUCTURED DASHBOARD: {company_name}")
    logger.info("=" * 70)
    logger.info(f"Company slug: {company_slug}")
    logger.info(f"FastAPI endpoint: {fastapi_url}/dashboard/structured")
    
    try:
        # Call FastAPI endpoint to generate structured dashboard
        response = requests.post(
            f"{fastapi_url}/dashboard/structured",
            params={"company_name": company_name},
            timeout=1200  # 20 minute timeout
        )
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract response data
            markdown_content = data.get('markdown', '')
            
            # Save markdown file
            markdown_dir = f'/app/data/llm_response/markdown/{company_slug}'
            os.makedirs(markdown_dir, exist_ok=True)
            
            markdown_path = f'{markdown_dir}/structured.md'
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"✅ Saved structured.md to {markdown_path}")
            logger.info(f"Markdown size: {len(markdown_content)} bytes")
            
            # Save JSON response with full API response structure
            json_dir = f'/app/data/llm_response/json/{company_slug}'
            os.makedirs(json_dir, exist_ok=True)
            
            json_path = f'{json_dir}/responses.json'
            
            # Create structured response object matching the expected format
            structured_response = {
                'company_name': data.get('company_name'),
                'company_slug': data.get('company_slug'),
                'pipeline_type': 'structured',
                'timestamp': datetime.now().isoformat() + 'Z',
                'markdown_file': f'markdown/{company_slug}/structured.md',
                'content': markdown_content
            }
            
            # Load or create responses.json with only the three required root-level keys
            response_data = {}
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Preserve only the required root-level keys
                    response_data = {
                        'company_slug': loaded_data.get('company_slug', company_slug),
                        'structured': loaded_data.get('structured', {}),
                        'rag': loaded_data.get('rag', {})
                    }
            else:
                response_data = {
                    'company_slug': company_slug,
                    'structured': {},
                    'rag': {}
                }
            
            # Add/update structured response
            response_data['structured'] = structured_response
            
            # Save updated responses.json with only required root-level keys
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Saved responses.json to {json_path}")
            logger.info(f"JSON size: {len(json.dumps(response_data))} bytes")
            
            return {
                'company_name': company_name,
                'company_slug': company_slug,
                'pipeline': 'structured',
                'status': 'success',
                'markdown_path': markdown_path,
                'markdown_size': len(markdown_content),
                'json_path': json_path,
                'json_size': len(json.dumps(response_data))
            }
        
        elif response.status_code == 202:
            logger.warning(f"⏳ Extraction in progress for {company_name}")
            raise Exception(f"Extraction in progress, please retry later")
        
        elif response.status_code == 404:
            error_detail = response.json().get('detail', 'Not found')
            logger.warning(f"⚠️ Payload not available: {error_detail}")
            raise Exception(f"Payload not available: {error_detail}")
        
        else:
            error_msg = response.text
            logger.error(f"❌ API error: {response.status_code}")
            logger.error(f"Response: {error_msg}")
            raise Exception(f"API error {response.status_code}: {error_msg}")
    
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Request timeout for {company_name}")
        raise Exception(f"Request timeout after 20 minutes")
    
    except Exception as e:
        logger.error(f"❌ Error generating structured dashboard: {e}")
        raise


def generate_rag_dashboard(company_info):
    """
    Generate rag.md dashboard and JSON response for a company via FastAPI endpoint.
    
    Args:
        company_info: Dict with company_name and company_slug
    """
    company_name = company_info.get('company_name')
    company_slug = company_info.get('company_slug')
    
    logger = logging.getLogger(__name__)
    
    # Get FastAPI URL from environment or use default
    fastapi_url = os.environ.get('FASTAPI_URL', 'http://fastapi:8000')
    
    logger.info("=" * 70)
    logger.info(f"GENERATING RAG DASHBOARD: {company_name}")
    logger.info("=" * 70)
    logger.info(f"Company slug: {company_slug}")
    logger.info(f"FastAPI endpoint: {fastapi_url}/dashboard/rag")
    
    try:
        # Call FastAPI endpoint to generate RAG dashboard
        response = requests.post(
            f"{fastapi_url}/dashboard/rag",
            params={"company_name": company_name},
            timeout=600  # 10 minute timeout for RAG
        )
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract response data
            markdown_content = data.get('markdown', '')
            
            # Save markdown file
            markdown_dir = f'/app/data/llm_response/markdown/{company_slug}'
            os.makedirs(markdown_dir, exist_ok=True)
            
            markdown_path = f'{markdown_dir}/rag.md'
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"✅ Saved rag.md to {markdown_path}")
            logger.info(f"Markdown size: {len(markdown_content)} bytes")
            
            # Save JSON response with full API response structure
            json_dir = f'/app/data/llm_response/json/{company_slug}'
            os.makedirs(json_dir, exist_ok=True)
            
            json_path = f'{json_dir}/responses.json'
            
            # Create RAG response object - note: context_results may not be in API response
            # so we'll try to extract it or leave empty
            rag_response = {
                'company_name': data.get('company_name'),
                'company_slug': data.get('company_slug'),
                'pipeline_type': 'rag',
                'timestamp': datetime.now().isoformat() + 'Z',
                'markdown_file': f'markdown/{company_slug}/rag.md',
                'content': markdown_content
            }
            
            # Add context_results if available in the response
            if 'context_results' in data:
                rag_response['context_results'] = data.get('context_results', [])
            
            # Load or create responses.json with only the three required root-level keys
            response_data = {}
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Preserve only the required root-level keys
                    response_data = {
                        'company_slug': loaded_data.get('company_slug', company_slug),
                        'structured': loaded_data.get('structured', {}),
                        'rag': loaded_data.get('rag', {})
                    }
            else:
                response_data = {
                    'company_slug': company_slug,
                    'structured': {},
                    'rag': {}
                }
            
            # Add/update RAG response
            response_data['rag'] = rag_response
            
            # Save updated responses.json with only required root-level keys
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Saved responses.json to {json_path}")
            logger.info(f"JSON size: {len(json.dumps(response_data))} bytes")
            
            return {
                'company_name': company_name,
                'company_slug': company_slug,
                'pipeline': 'rag',
                'status': 'success',
                'markdown_path': markdown_path,
                'markdown_size': len(markdown_content),
                'json_path': json_path,
                'json_size': len(json.dumps(response_data))
            }
        
        elif response.status_code == 404:
            error_detail = response.json().get('detail', 'Not found')
            logger.warning(f"⚠️ RAG collection not available: {error_detail}")
            raise Exception(f"RAG collection not available: {error_detail}")
        
        else:
            error_msg = response.text
            logger.error(f"❌ API error: {response.status_code}")
            logger.error(f"Response: {error_msg}")
            raise Exception(f"API error {response.status_code}: {error_msg}")
    
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Request timeout for {company_name}")
        raise Exception(f"Request timeout after 10 minutes")
    
    except Exception as e:
        logger.error(f"❌ Error generating RAG dashboard: {e}")
        raise


def log_generation_summary(**context):
    """Log summary of dashboard generation and generate master.json."""
    task_instance = context['task_instance']
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("DASHBOARD GENERATION SUMMARY")
    logger.info("=" * 70)
    
    # Get all task instances from this run
    dag_run = context['dag_run']
    task_instances = dag_run.get_task_instances()
    
    structured_count = 0
    rag_count = 0
    failed_count = 0
    company_summaries = {}
    
    for ti in task_instances:
        if ti.task_id.startswith('generate_structured_'):
            if ti.state == 'success':
                structured_count += 1
            elif ti.state == 'failed':
                failed_count += 1
        elif ti.task_id.startswith('generate_rag_'):
            if ti.state == 'success':
                rag_count += 1
            elif ti.state == 'failed':
                failed_count += 1
    
    logger.info(f"Structured dashboards generated: {structured_count}")
    logger.info(f"RAG dashboards generated: {rag_count}")
    logger.info(f"Failed tasks: {failed_count}")
    logger.info(f"Total dashboards: {structured_count + rag_count}")
    
    # Generate master.json
    master_json_path = '/app/data/llm_response/master.json'
    
    # Discover all company responses
    json_dir = '/app/data/llm_response/json'
    if os.path.exists(json_dir):
        master_data = {
            'generated_at': datetime.now().isoformat(),
            'total_companies': structured_count,
            'companies': {}
        }
        
        for company_slug in os.listdir(json_dir):
            company_path = os.path.join(json_dir, company_slug)
            if os.path.isdir(company_path):
                responses_path = os.path.join(company_path, 'responses.json')
                if os.path.exists(responses_path):
                    try:
                        with open(responses_path, 'r', encoding='utf-8') as f:
                            company_data = json.load(f)
                        master_data['companies'][company_slug] = company_data
                        logger.info(f"Added {company_slug} to master.json")
                    except Exception as e:
                        logger.warning(f"Failed to read {responses_path}: {e}")
        
        # Save master.json
        os.makedirs(os.path.dirname(master_json_path), exist_ok=True)
        with open(master_json_path, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Generated master.json with {len(master_data['companies'])} companies")
        logger.info(f"Master.json location: {master_json_path}")
    
    logger.info("=" * 70)
    
    return {
        'structured_generated': structured_count,
        'rag_generated': rag_count,
        'failed': failed_count,
        'total': structured_count + rag_count,
        'master_json_path': master_json_path
    }


# DAG Configuration
default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 11, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    dag_id='dashboard_generation_dag',
    default_args=default_args,
    description='Generate structured.md and rag.md dashboards for first 20 AI50 companies from seed data',
    schedule_interval=None,  # Manual trigger only
    catchup=False,
    tags=['ai50', 'dashboard', 'generation'],
)

# Discover valid companies
logger = logging.getLogger(__name__)
company_map = get_ai50_companies_from_seed()
all_valid_companies = discover_valid_companies(company_map)

# Process only the first 20 companies from seed data, but ensure world_labs is included
valid_companies = all_valid_companies[:20]

# If world_labs is not in the first 20, replace the last one with it
world_labs_in_list = any(c['company_slug'] == 'world_labs' for c in valid_companies)
if not world_labs_in_list:
    # Find world_labs in all_valid_companies and swap with the last company
    for i, company in enumerate(all_valid_companies):
        if company['company_slug'] == 'world_labs':
            valid_companies[-1] = company
            break

logger.info(f"DASHBOARD GENERATION DAG SETUP COMPLETE")
logger.info(f"Companies to process: {len(valid_companies)}")
for i, company in enumerate(valid_companies, 1):
    logger.info(f"  {i:2d}. {company['company_slug']} - {company['company_name']}")

# Create tasks for each company
structured_tasks = []
rag_tasks = []

for company_info in valid_companies:
    company_slug = company_info['company_slug']
    
    # Structured dashboard task
    structured_task = PythonOperator(
        task_id=f'generate_structured_{company_slug}',
        python_callable=generate_structured_dashboard,
        op_args=[company_info],
        dag=dag,
    )
    structured_tasks.append(structured_task)
    
    # RAG dashboard task
    rag_task = PythonOperator(
        task_id=f'generate_rag_{company_slug}',
        python_callable=generate_rag_dashboard,
        op_args=[company_info],
        dag=dag,
    )
    rag_tasks.append(rag_task)
    
    # Both dashboards can run in parallel for each company
    structured_task >> rag_task

# Summary task runs after all dashboards are generated
summary_task = PythonOperator(
    task_id='generation_summary',
    python_callable=log_generation_summary,
    provide_context=True,
    dag=dag,
)

# All RAG tasks must complete before summary
if rag_tasks:
    for task in rag_tasks:
        task >> summary_task
