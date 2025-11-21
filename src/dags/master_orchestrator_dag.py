"""
Master Orchestrator DAG - Coordinates execution of all processing pipelines in sequence.

This DAG orchestrates the complete AI50 company data processing pipeline:
1. process_pages_dag - Discover and process company pages
2. ingest_dag - Ingest processed pages into vector store
3. extraction_dag - Extract structured information from pages
4. master_agent_dag - Enrich company data using master orchestrator (Tavily + Payload agents)
5. eval_runner_dag - Evaluate RAG and structured extraction results

Schedule: Manual trigger (no automatic schedule)
Dependencies: Requires all five pipelines to be defined as separate DAGs
"""

import logging
from datetime import datetime
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

logger = logging.getLogger(__name__)

# DAG configuration
PIPELINE_DAGS = [
    {
        "dag_id": "process_pages_dag",
        "description": "Discover and process company pages",
        "order": 1
    },
    {
        "dag_id": "ingest_dag",
        "description": "Ingest processed pages into vector store",
        "order": 2
    },
    {
        "dag_id": "extraction_payload_dag",
        "description": "Extract structured information from pages",
        "order": 3
    },
    {
        "dag_id": "master_agent_dag",
        "description": "Enrich company data using master orchestrator (Tavily + Payload agents)",
        "order": 4
    },
    {
        "dag_id": "eval_runner_dag",
        "description": "Evaluate RAG and structured extraction results",
        "order": 5
    }
]

# Default arguments for all tasks
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'email_on_failure': False,
    'email_on_retry': False,
}

# Define the master orchestrator DAG
with DAG(
    dag_id="master_orchestrator_dag",
    description="Master orchestrator for AI50 company data processing pipeline",
    schedule_interval="0 0 * * *",  # Daily run at midnight UTC
    start_date=datetime(2025, 11, 1),
    catchup=False,
    tags=["ai50", "orchestration", "master"],
    max_active_runs=1,  # Only allow one active run
    default_args=default_args,
) as dag:
    
    # Create task group for pipeline execution
    with TaskGroup(group_id="pipeline_execution") as pipeline_group:
        
        # Create trigger tasks for each DAG in sequence
        trigger_tasks = {}
        
        for pipeline in sorted(PIPELINE_DAGS, key=lambda x: x['order']):
            dag_id = pipeline['dag_id']
            order = pipeline['order']
            description = pipeline['description']
            
            task_id = f"trigger_{dag_id}"
            
            trigger_task = TriggerDagRunOperator(
                task_id=task_id,
                trigger_dag_id=dag_id,
                wait_for_completion=True,  # Wait for triggered DAG to complete
                allowed_states=['success'],  # Only proceed if triggered DAG succeeds
                failed_states=['failed'],  # Fail if triggered DAG fails
                poke_interval=30,  # Check status every 30 seconds
                execution_timeout=None,  # No timeout - let triggered DAG decide
            )
            
            trigger_tasks[order] = trigger_task
        
        # Create sequential dependencies between triggers
        # This ensures each DAG runs only after the previous one completes
        sorted_tasks = [trigger_tasks[i] for i in sorted(trigger_tasks.keys())]
        for i in range(len(sorted_tasks) - 1):
            sorted_tasks[i] >> sorted_tasks[i + 1]
    
    # Optional: Add summary task at the end
    def log_pipeline_completion(**context):
        """Log successful completion of entire pipeline."""
        execution_date = context['execution_date']
        run_id = context['run_id']
        
        logger.info("=" * 80)
        logger.info("🎉 MASTER ORCHESTRATOR PIPELINE COMPLETED SUCCESSFULLY 🎉")
        logger.info("=" * 80)
        logger.info(f"Execution Date: {execution_date}")
        logger.info(f"Run ID: {run_id}")
        logger.info("\nPipeline Execution Order:")
        for i, pipeline in enumerate(sorted(PIPELINE_DAGS, key=lambda x: x['order']), 1):
            logger.info(f"  {i}. {pipeline['dag_id']:30} - {pipeline['description']}")
        logger.info("=" * 80)
        logger.info("All processing stages completed successfully!")
        logger.info("=" * 80)
        
        return {
            "status": "success",
            "execution_date": str(execution_date),
            "run_id": run_id,
            "pipelines_executed": len(PIPELINE_DAGS)
        }
    
    summary_task = PythonOperator(
        task_id="pipeline_summary",
        python_callable=log_pipeline_completion,
        provide_context=True
    )
    
    # Set dependencies
    pipeline_group >> summary_task
