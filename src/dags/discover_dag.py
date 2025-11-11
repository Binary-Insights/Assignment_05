from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import subprocess
import logging

def run_discover_ai50():
    logger = logging.getLogger(__name__)
    base_dir = '/opt/airflow/workspace'
    script_path = os.path.join(base_dir, 'src', 'discover', 'fetch_ai50.py')
    try:
        os.chdir(base_dir)
        result = subprocess.run(['python', script_path], capture_output=True, text=True, timeout=600)
        logger.info(result.stdout)
        if result.returncode != 0:
            logger.error(result.stderr)
            raise Exception(f"Discover AI50 failed: {result.stderr}")
        return "Discover AI50 Success"
    except Exception as e:
        logger.error(str(e))
        raise

def run_discover_ai50_links():
    logger = logging.getLogger(__name__)
    base_dir = '/opt/airflow/workspace'
    script_path = os.path.join(base_dir, 'src', 'discover', 'discover_links.py')
    try:
        if not os.path.exists(script_path):
            logger.warning(f"Script not found: {script_path}. Skipping discover links.")
            return "Discover AI50 links skipped (script not found)"
        
        os.chdir(base_dir)
        logger.info(f"Starting discover_links script: {script_path}")
        result = subprocess.run(['python', script_path], capture_output=True, text=True, timeout=1800)
        logger.info(result.stdout)
        if result.returncode != 0:
            logger.error(result.stderr)
            raise Exception(f"Discover AI50 links failed: {result.stderr}")
        return "Discover AI50 Links Success"
    except subprocess.TimeoutExpired as e:
        logger.error(f"Discover AI50 links timed out after 1800 seconds: {str(e)}")
        raise Exception(f"Discover AI50 links timeout: {str(e)}")
    except Exception as e:
        logger.error(str(e))
        raise

default_args = {
    'owner': 'data-engineering-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 10, 31),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'discover_ai50_dag',
    default_args=default_args,
    description='Discover Forbes AI50 companies and key page links',
    schedule_interval=None,
    catchup=False,
    tags=['ai50', 'discover'],
)

discover_task = PythonOperator(
    task_id='fetch_ai50_companies',
    python_callable=run_discover_ai50,
    execution_timeout=timedelta(minutes=30),
    dag=dag,
)

discover_links_task = PythonOperator(
    task_id='discover_ai50_links',
    python_callable=run_discover_ai50_links,
    execution_timeout=timedelta(minutes=60),
    dag=dag,
)

discover_task >> discover_links_task
