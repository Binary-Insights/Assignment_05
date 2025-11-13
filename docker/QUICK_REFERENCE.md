# 🚀 Docker Airflow Quick Reference

## Starting Up

```bash
cd docker

# Linux/Mac
chmod +x start.sh
./start.sh

# Windows
.\start.ps1

# Or manual
docker-compose up -d
```

## Access Services

| Service | URL | Login |
|---------|-----|-------|
| Airflow | http://localhost:8080 | admin/admin |
| FastAPI | http://localhost:8000/docs | N/A |
| Streamlit | http://localhost:8501 | N/A |
| PostgreSQL | localhost:5432 | airflow/airflow |

## View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f airflow-webserver
docker-compose logs -f airflow-scheduler
docker-compose logs -f fastapi
docker-compose logs -f streamlit
```

## DAG Management

```bash
# List all DAGs
docker exec pe-dashboard-airflow-scheduler airflow dags list

# List tasks in DAG
docker exec pe-dashboard-airflow-scheduler airflow tasks list ai50_daily_refresh_dag

# DAG info
docker exec pe-dashboard-airflow-scheduler airflow dags info ai50_daily_refresh_dag

# Next execution time
docker exec pe-dashboard-airflow-scheduler airflow dags next-execution ai50_daily_refresh_dag

# Trigger DAG
docker exec pe-dashboard-airflow-webserver airflow dags trigger ai50_daily_refresh_dag

# Backfill DAG (run past dates)
docker exec pe-dashboard-airflow-scheduler airflow dags backfill \
  ai50_daily_refresh_dag \
  -s 2025-10-31 \
  -e 2025-11-07
```

## Service Management

```bash
# Check status
docker-compose ps

# Stop all services
docker-compose down

# Stop and remove data
docker-compose down -v

# Restart specific service
docker-compose restart airflow-scheduler
docker-compose restart airflow-webserver

# Restart all
docker-compose down
docker-compose up -d

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

## Database Operations

```bash
# Connect to PostgreSQL
docker exec -it pe-dashboard-postgres psql -U airflow -d airflow

# Inside psql:
\dt                          # List tables
SELECT * FROM dag;           # View DAGs
SELECT * FROM dag_run;       # View runs
SELECT * FROM task_instance; # View tasks

# Export data
docker exec pe-dashboard-postgres pg_dump -U airflow airflow > backup.sql

# Restore data
docker exec -i pe-dashboard-postgres psql -U airflow airflow < backup.sql
```

## Debugging

```bash
# Check container health
docker-compose ps

# View resource usage
docker stats

# Execute commands in container
docker exec pe-dashboard-airflow-scheduler bash

# Inside container:
airflow config get-value core executor
airflow config get-value core dags_folder
ls -la /app/dags/

# View Python environment
docker exec pe-dashboard-airflow-scheduler python -c "import airflow; print(airflow.__version__)"
```

## Files Location

```bash
# Inside container
/app/dags/                  # DAG definitions
/app/data/                  # Shared data volume
/app/logs/                  # Task logs
/app/airflow_home/          # Airflow config

# On host
docker/
├── Dockerfile
├── docker-compose.yml
├── .env
├── start.sh
├── start.ps1
└── AIRFLOW_SETUP.md
```

## Environment Variables

Edit `.env` file to change:

```bash
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT=false
POSTGRES_PASSWORD=airflow
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Port 8080 in use | Change in docker-compose.yml: `8081:8080` |
| DAGs not showing | Check `/app/dags/` mounted and readable |
| PostgreSQL won't start | Check volume permissions: `docker-compose down -v` |
| Scheduler won't run | Check `airflow-webserver` is healthy first |
| Memory issues | Add limits in docker-compose.yml |

## Performance Tuning

```yaml
# In docker-compose.yml

# Increase resources
airflow-scheduler:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G

# Increase parallelism
environment:
  - AIRFLOW__CORE__PARALLELISM=32
  - AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=16
```

## Monitoring

```bash
# Task failures
docker exec pe-dashboard-airflow-scheduler airflow tasks failed-deps <dag_id>

# Airflow health
curl http://localhost:8080/health

# FastAPI health
curl http://localhost:8000/docs

# All metrics
docker stats
```

## DAG Development Workflow

1. **Create DAG** in `dags/` folder
2. **Restart scheduler** (auto-detects):
   ```bash
   docker-compose restart airflow-scheduler
   ```
3. **Check DAG UI** at http://localhost:8080
4. **Trigger manually** or wait for schedule
5. **Monitor logs** at http://localhost:8080/graph

## Integration Points

### From Airflow to FastAPI
```python
import requests
response = requests.get('http://fastapi:8000/api/endpoint')
```

### From Airflow to PostgreSQL
```python
import psycopg2
conn = psycopg2.connect("dbname=airflow user=airflow password=airflow host=postgres")
```

### From Streamlit to FastAPI
```python
import requests
response = requests.get('http://fastapi:8000/docs')
```

## Backup & Restore

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U airflow airflow > backup.sql

# Backup volumes
docker run --rm -v assignment-04_postgres_data:/data \
  -v $(pwd):/backup ubuntu tar czf /backup/backup.tar.gz /data

# Restore
docker run --rm -v assignment-04_postgres_data:/data \
  -v $(pwd):/backup ubuntu tar xzf /backup/backup.tar.gz -C /

# Backup data directory
tar -czf data_backup.tar.gz ../data/
```

## Scale to Production

```bash
# Use CeleryExecutor instead of LocalExecutor
# Add Redis or RabbitMQ for message broker
# Add multiple scheduler/worker instances
# Use managed PostgreSQL (RDS, CloudSQL, etc.)
# Set up monitoring (Prometheus, Grafana)
# Enable authentication and RBAC
# Configure SSL/TLS
```

## Useful Links

- [Airflow CLI Reference](https://airflow.apache.org/docs/apache-airflow/stable/cli-and-env-variables-ref.html)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [PostgreSQL Docker Docs](https://hub.docker.com/_/postgres)

## Quick Commands Copy-Paste

```bash
# Start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f airflow-scheduler

# List DAGs
docker exec pe-dashboard-airflow-scheduler airflow dags list

# Stop
docker-compose down
```

---
**Last Updated**: November 7, 2025  
**Airflow Version**: 2.8.1  
**Python Version**: 3.11
