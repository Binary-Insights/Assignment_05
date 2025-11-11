# Airflow Docker Setup Guide

## 📋 Overview

This Docker setup now includes:
- **PostgreSQL** (Airflow metadata database)
- **Airflow Webserver** (UI and REST API) on port 8080
- **Airflow Scheduler** (DAG orchestration)
- **FastAPI** (Backend API) on port 8000
- **Streamlit** (Frontend UI) on port 8501

## 🚀 Quick Start

### 1. Build and Start All Services

```bash
cd docker
docker-compose up -d
```

### 2. Wait for Services to Start

```bash
# Check status
docker-compose ps

# Check logs
docker-compose logs -f airflow-webserver
docker-compose logs -f airflow-scheduler
```

### 3. Access Services

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| Airflow UI | http://localhost:8080 | admin / admin |
| FastAPI Docs | http://localhost:8000/docs | N/A |
| Streamlit | http://localhost:8501 | N/A |
| PostgreSQL | localhost:5432 | airflow / airflow |

## 📁 Service Architecture

```
docker-compose.yml
├── postgres (PostgreSQL 15)
│   └── Stores Airflow metadata
├── airflow-webserver (Port 8080)
│   └── Airflow UI & REST API
├── airflow-scheduler
│   └── DAG orchestration & scheduling
├── fastapi (Port 8000)
│   └── Backend API
└── streamlit (Port 8501)
    └── Frontend Dashboard
```

## 🔧 Configuration Details

### Dockerfile Changes
- Added Airflow installation
- Added Airflow providers:
  - PostgreSQL provider
  - HTTP provider
  - Kafka provider
  - Amazon AWS provider
- Created Airflow directories and initialization

### docker-compose.yml Changes
- Added PostgreSQL service with health checks
- Added Airflow Webserver with auto-init
- Added Airflow Scheduler
- Created named volumes for persistence
- Added custom network for service communication
- Added health checks and dependencies

## 📝 Common Tasks

### Check Airflow Status

```bash
# View all containers
docker-compose ps

# Check specific service
docker-compose logs airflow-webserver
docker-compose logs airflow-scheduler
```

### Access Airflow UI

1. Open http://localhost:8080
2. Login with: admin / admin
3. You should see your DAGs in the list:
   - `ai50_daily_refresh_dag`
   - `ai50_full_ingest_dag`

### View DAG Logs

```bash
# Inside Docker container
docker exec pe-dashboard-airflow-scheduler airflow dags list

# View specific DAG
docker exec pe-dashboard-airflow-scheduler airflow dags info ai50_daily_refresh_dag

# View task logs
docker exec pe-dashboard-airflow-scheduler airflow tasks list ai50_daily_refresh_dag
```

### Manually Trigger a DAG

From Airflow UI:
1. Click DAG name
2. Click "Trigger DAG" button
3. Monitor execution in "Graph" view

Or via CLI:
```bash
docker exec pe-dashboard-airflow-webserver airflow dags trigger ai50_daily_refresh_dag
```

### View Scheduled Runs

```bash
# In Airflow UI: Calendar view shows scheduled runs
# Or via CLI:
docker exec pe-dashboard-airflow-scheduler airflow dags next-execution ai50_daily_refresh_dag
```

## 🔄 Restart Services

### Restart Airflow Webserver
```bash
docker-compose restart airflow-webserver
```

### Restart Scheduler
```bash
docker-compose restart airflow-scheduler
```

### Full Restart
```bash
docker-compose down
docker-compose up -d
```

## 🧹 Cleanup

### Stop All Services (keep volumes)
```bash
docker-compose down
```

### Complete Cleanup (delete volumes)
```bash
docker-compose down -v
```

### Remove Specific Service Data
```bash
# Remove PostgreSQL data
docker volume rm assignment-04_postgres_data
```

## 🐛 Troubleshooting

### Webserver Won't Start

**Problem**: `Error: Failed to init the database`

**Solution**:
```bash
# Manually reinitialize database
docker exec pe-dashboard-airflow-webserver airflow db reset
docker-compose restart airflow-webserver
```

### Scheduler Not Picking Up DAGs

**Problem**: DAGs don't appear in Airflow UI

**Solution**:
```bash
# Check DAG syntax
docker exec pe-dashboard-airflow-scheduler airflow dags list-import-errors

# Verify DAG folder mounted
docker exec pe-dashboard-airflow-scheduler ls -la /app/dags/

# Restart scheduler
docker-compose restart airflow-scheduler
```

### Database Connection Issues

**Problem**: `Cannot connect to PostgreSQL`

**Solution**:
```bash
# Check PostgreSQL health
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Port Already in Use

**Problem**: Port 8080 or 8501 already in use

**Solution**: Edit `docker-compose.yml` and change ports:
```yaml
airflow-webserver:
  ports:
    - "8081:8080"  # Changed from 8080 to 8081
```

## 📊 Environment Variables

Key Airflow environment variables in `docker-compose.yml`:

| Variable | Value | Purpose |
|----------|-------|---------|
| `AIRFLOW_HOME` | `/app/airflow_home` | Airflow configuration directory |
| `AIRFLOW__CORE__EXECUTOR` | `LocalExecutor` | Task execution strategy |
| `AIRFLOW__CORE__LOAD_EXAMPLES` | `false` | Don't load example DAGs |
| `AIRFLOW__CORE__DAGS_FOLDER` | `/app/dags` | DAG location |
| `AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT` | `false` | Don't catchup missed runs |
| `AIRFLOW__WEBSERVER__AUTHENTICATE` | `false` | Disable auth (enable for production) |

## 🔐 Production Considerations

For production deployment:

1. **Enable Authentication**
   ```yaml
   AIRFLOW__WEBSERVER__AUTHENTICATE: true
   AIRFLOW__WEBSERVER__AUTH_BACKEND: airflow.contrib.auth.backends.password_auth
   ```

2. **Use CeleryExecutor** (for distributed execution)
   ```yaml
   AIRFLOW__CORE__EXECUTOR: CeleryExecutor
   ```

3. **Use External Database** (not in Docker)
   - Replace PostgreSQL connection string

4. **Add SSL/TLS** for Webserver

5. **Set Resource Limits**
   ```yaml
   airflow-webserver:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
   ```

## 📚 Useful Commands

### Monitor DAG Execution

```bash
# SSH into scheduler
docker exec -it pe-dashboard-airflow-scheduler bash

# Inside container:
airflow dags list                    # List all DAGs
airflow tasks list <dag_id>          # List tasks in DAG
airflow dags info <dag_id>           # DAG details
airflow dags next-execution <dag_id> # Next scheduled run
```

### Execute DAG Programmatically

Inside a DAG or Python script:
```python
from datetime import datetime
from airflow.models import DagRun
from airflow.models import Variable

# Check if previous run succeeded
dag_runs = DagRun.find(
    dag_id='ai50_daily_refresh_dag',
    state='success'
)
if dag_runs:
    print(f"Last successful run: {dag_runs[0].execution_date}")
```

### View Database

```bash
# Connect to PostgreSQL
docker exec -it pe-dashboard-postgres psql -U airflow -d airflow

# Inside PostgreSQL:
\dt                          # List tables
SELECT * FROM dag;           # View DAGs
SELECT * FROM dag_run;       # View DAG runs
SELECT * FROM task_instance; # View task instances
```

## 🔗 Integration with Your Pipeline

### Trigger FastAPI from Airflow DAG

```python
from airflow.operators.http_operator import SimpleHttpOperator

trigger_api = SimpleHttpOperator(
    task_id='trigger_api',
    http_conn_id='fastapi',
    endpoint='/process/company/{company_id}',
    method='POST',
    dag=dag
)
```

### Store Results in Data Volume

```python
from airflow.operators.python import PythonOperator
import json

def save_results(**context):
    results = context['task_instance'].xcom_pull(task_ids='previous_task')
    with open('/app/data/results.json', 'w') as f:
        json.dump(results, f)

save_task = PythonOperator(
    task_id='save_results',
    python_callable=save_results,
    dag=dag
)
```

## 📖 Next Steps

1. View DAGs in Airflow UI (http://localhost:8080)
2. Trigger your first DAG manually
3. Monitor logs in the Scheduler view
4. Modify DAGs as needed in `/dags` directory
5. Changes are automatically picked up

## 🆘 Getting Help

- Airflow Documentation: https://airflow.apache.org/docs/
- DAG Writing Guide: https://airflow.apache.org/docs/apache-airflow/stable/tutorial/fundamentals.html
- Providers Documentation: https://airflow.apache.org/docs/apache-airflow-providers/

## ✅ Verification Checklist

After starting the stack:

- [ ] `docker-compose ps` shows all 5 services as "running"
- [ ] Airflow UI loads at http://localhost:8080
- [ ] FastAPI docs accessible at http://localhost:8000/docs
- [ ] Streamlit loads at http://localhost:8501
- [ ] DAGs appear in Airflow UI under "DAGs" section
- [ ] PostgreSQL connections established (check logs)
- [ ] No error messages in `airflow-scheduler` logs

## 🎉 You're Ready!

Your Airflow environment is now fully dockerized and integrated with your FastAPI and Streamlit services!
