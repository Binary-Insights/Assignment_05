# 🐳 Docker Setup for Airflow + FastAPI + Streamlit

## Overview

This Docker setup provides a complete containerized environment for running:
- **Apache Airflow** with PostgreSQL backend
- **FastAPI** backend service
- **Streamlit** frontend dashboard
- All integrated and networked together

## 📁 Directory Structure

```
docker/
├── Dockerfile                    # Multi-stage Docker image
├── docker-compose.yml            # Container orchestration
├── .env.example                  # Environment template
├── start.sh                      # Linux/Mac launcher
├── start.ps1                     # Windows launcher
├── AIRFLOW_SETUP.md             # Detailed Airflow guide
└── README.md                     # This file
```

## 🚀 Quick Start

### On Linux/Mac
```bash
cd docker
chmod +x start.sh
./start.sh
```

### On Windows
```powershell
cd docker
.\start.ps1
```

### Manual (All Platforms)
```bash
cd docker
docker-compose up -d
```

## 📊 Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| **Airflow Webserver** | 8080 | DAG orchestration UI |
| **Airflow Scheduler** | - | Background scheduler |
| **FastAPI** | 8000 | Backend API |
| **Streamlit** | 8501 | Frontend dashboard |
| **PostgreSQL** | 5432 | Airflow metadata DB |

## 🔧 Configuration

### Environment Variables

Edit `.env` to customize:

```bash
# Airflow
AIRFLOW__CORE__EXECUTOR=LocalExecutor          # Change to CeleryExecutor for scale
AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT=false   # Don't catch up missed runs
AIRFLOW__WEBSERVER__AUTHENTICATE=false         # Set to true in production

# Database
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow
```

### Resource Limits

Edit `docker-compose.yml` to add resource constraints:

```yaml
services:
  airflow-webserver:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## 🎯 Common Tasks

### View Airflow DAGs
```bash
docker exec pe-dashboard-airflow-scheduler airflow dags list
```

### Trigger a DAG
```bash
docker exec pe-dashboard-airflow-webserver airflow dags trigger ai50_daily_refresh_dag
```

### View Task Logs
```bash
docker exec pe-dashboard-airflow-scheduler airflow tasks list ai50_daily_refresh_dag
```

### Access PostgreSQL
```bash
docker exec -it pe-dashboard-postgres psql -U airflow -d airflow
```

### Restart a Service
```bash
docker-compose restart airflow-scheduler
docker-compose restart airflow-webserver
docker-compose restart fastapi
docker-compose restart streamlit
```

## 📝 Files Explanation

### Dockerfile
- **Base stage**: Python 3.11 slim image
- **System dependencies**: Build tools, curl, git, postgresql-client
- **Python packages**: Requirements.txt + Airflow + providers
- **Volumes**: Airflow home, logs, plugins, dags, data
- **Environment**: AIRFLOW_HOME, PYTHONPATH set up

### docker-compose.yml
- **postgres**: PostgreSQL 15 for Airflow metadata
- **airflow-webserver**: Airflow UI on port 8080
- **airflow-scheduler**: Background DAG orchestrator
- **fastapi**: Backend API on port 8000
- **streamlit**: Frontend UI on port 8501
- **Named volumes**: Persistent storage
- **Network**: Internal communication bridge

### .env.example
Template with all configurable variables for easy setup

### start.sh / start.ps1
Automation scripts that:
1. Check Docker installation
2. Create .env from template
3. Build images
4. Start containers
5. Show access URLs

## 🔗 Service Communication

Services can reach each other using container names:

```python
# In your Python code inside Docker
import requests

# FastAPI from Airflow
response = requests.get('http://fastapi:8000/docs')

# PostgreSQL from any service
import psycopg2
conn = psycopg2.connect("dbname=airflow user=airflow password=airflow host=postgres")

# Streamlit to FastAPI
requests.get('http://fastapi:8000/api/endpoint')
```

## 🧹 Cleanup Commands

### Stop all services (keep data)
```bash
docker-compose down
```

### Stop and remove all data
```bash
docker-compose down -v
```

### Remove specific volume
```bash
docker volume rm assignment-04_postgres_data
```

### Remove all unused Docker resources
```bash
docker system prune -a --volumes
```

## 🐛 Troubleshooting

### Port Already in Use
**Error**: `Address already in use`

**Solution**: Change port in docker-compose.yml
```yaml
ports:
  - "8081:8080"  # Use 8081 instead of 8080
```

### Airflow Database Won't Initialize
**Error**: `Error: Database is not initialized`

**Solution**: 
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d    # Fresh start
```

### Services Won't Start
**Error**: `container exited with code 1`

**Solution**:
```bash
# Check logs
docker-compose logs airflow-webserver

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### PostgreSQL Connection Refused
**Error**: `Error connecting to PostgreSQL`

**Solution**:
```bash
# Wait for PostgreSQL to be ready
docker-compose logs postgres

# Restart services
docker-compose restart postgres
docker-compose restart airflow-webserver
```

## 📚 Learning Resources

- [Airflow Documentation](https://airflow.apache.org/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)

## 🔐 Production Checklist

Before deploying to production:

- [ ] Set `AIRFLOW__WEBSERVER__AUTHENTICATE=true`
- [ ] Use strong passwords (not 'airflow')
- [ ] Use external PostgreSQL (not Docker)
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy
- [ ] Set resource limits for all services
- [ ] Use CeleryExecutor for scaling
- [ ] Set up log aggregation (ELK, Datadog, etc.)
- [ ] Configure monitoring/alerting
- [ ] Document runbooks for operations

## 📞 Getting Help

Check the detailed guides:
- `AIRFLOW_SETUP.md` - Complete Airflow guide
- `docker-compose.yml` - Service configuration
- `Dockerfile` - Image definition

## ✅ Verification

After starting, verify with:

```bash
# All services running
docker-compose ps

# Test Airflow
curl http://localhost:8080/health

# Test FastAPI
curl http://localhost:8000/docs

# Test Streamlit
curl http://localhost:8501
```

## 🎉 You're Ready!

Your containerized environment is ready to use:
1. Open http://localhost:8080 for Airflow
2. Visit http://localhost:8000/docs for API
3. Check http://localhost:8501 for Streamlit
4. Define your DAGs in the `dags/` directory
5. Enjoy automated workflows!
