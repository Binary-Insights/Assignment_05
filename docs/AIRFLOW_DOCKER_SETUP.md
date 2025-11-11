# ✅ Docker Airflow Setup - Complete

## 🎯 What Was Updated

Your Docker setup now **fully supports Apache Airflow** alongside FastAPI and Streamlit!

## 📦 Files Updated

### 1. **Dockerfile** - Enhanced with Airflow
✅ Added Airflow 2.8.1 installation  
✅ Added Airflow providers (PostgreSQL, HTTP, Kafka, AWS)  
✅ Created Airflow directories (`/app/dags`, `/app/logs`, `/app/plugins`)  
✅ Set `AIRFLOW_HOME` environment variable  
✅ Auto-initialize Airflow database on build  

### 2. **docker-compose.yml** - Complete Orchestration
✅ Added PostgreSQL 15 service (Airflow metadata DB)  
✅ Added Airflow Webserver (http://localhost:8080)  
✅ Added Airflow Scheduler (background orchestrator)  
✅ Connected FastAPI and Streamlit to network  
✅ Added named volumes for persistence  
✅ Added health checks  
✅ Created `dashboard-network` for communication  

## 🚀 Quick Start (Windows)

```powershell
cd docker
docker-compose up -d
```

Wait 30 seconds for all services to start, then access:

| Service | URL | Login |
|---------|-----|-------|
| **Airflow UI** | http://localhost:8080 | admin / admin |
| **FastAPI Docs** | http://localhost:8000/docs | N/A |
| **Streamlit** | http://localhost:8501 | N/A |
| **PostgreSQL** | localhost:5432 | airflow / airflow |

## 📊 Service Architecture

```
┌─────────────────────────────────────────────────────┐
│         Docker Network: dashboard-network           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────┐                              │
│  │   PostgreSQL 15  │ ← Airflow Metadata DB        │
│  │   Port: 5432     │                              │
│  └──────────────────┘                              │
│         ↑        ↑                                  │
│         │        │                                  │
│  ┌──────────────┐  ┌──────────────────────┐       │
│  │ Airflow Web  │  │ Airflow Scheduler    │       │
│  │ Port: 8080   │  │ (Background Service) │       │
│  └──────────────┘  └──────────────────────┘       │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐               │
│  │   FastAPI    │  │  Streamlit   │               │
│  │ Port: 8000   │  │ Port: 8501   │               │
│  └──────────────┘  └──────────────┘               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 🎯 What You Can Do Now

### 1. View Your Existing DAGs
Your DAGs in `dags/` folder will appear automatically:
- ✅ `ai50_daily_refresh_dag.py`
- ✅ `ai50_full_ingest_dag.py`

### 2. Manage Workflows
- Create DAGs in `dags/` folder
- Scheduler auto-detects within 1 minute
- Trigger manually from web UI
- Monitor execution in real-time

### 3. Integrate with FastAPI
- Call FastAPI from Airflow DAGs
- Process data through your pipeline
- Store results in shared `/app/data` volume

### 4. Schedule Automatic Execution
- Set schedules in DAG definitions
- Scheduler executes automatically
- View execution history and logs

## 📝 Common Commands

### Check All Services
```powershell
docker-compose ps
```

### View Logs
```powershell
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-webserver
```

### List DAGs
```powershell
docker exec pe-dashboard-airflow-scheduler airflow dags list
```

### Trigger a DAG
```powershell
docker exec pe-dashboard-airflow-webserver airflow dags trigger ai50_daily_refresh_dag
```

### Stop All Services
```powershell
docker-compose down
```

### Clean Everything (Remove Data)
```powershell
docker-compose down -v
```

## 🔧 Configuration

### Environment Variables (.env file)

Edit `.env` in the `docker/` directory to customize:

```bash
# Executor type
AIRFLOW__CORE__EXECUTOR=LocalExecutor

# Database connection
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow

# PostgreSQL credentials
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# Scheduler behavior
AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT=false

# Web UI
AIRFLOW__WEBSERVER__AUTHENTICATE=false
```

## ✨ Key Features

### Airflow Services
- **Web UI**: Manage DAGs visually
- **Scheduler**: Automated task execution
- **REST API**: Programmatic access
- **Logging**: Built-in task log viewer
- **Monitoring**: Execution history

### Integration
- **FastAPI**: Accessible from DAGs
- **PostgreSQL**: Persistent metadata
- **Streamlit**: Dashboard visualization
- **Shared Volume**: Data persistence
- **Network**: Internal communication

## 🔄 Workflow Example

1. **Create a DAG** in `dags/my_dag.py`:
```python
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

def my_task():
    print("Hello from Airflow!")

with DAG(
    dag_id='my_first_dag',
    start_date=datetime(2025, 11, 7),
    schedule='0 0 * * *'  # Daily at midnight
) as dag:
    task = PythonOperator(
        task_id='hello_task',
        python_callable=my_task
    )
```

2. **Restart Scheduler** (auto-detects DAGs):
```powershell
docker-compose restart airflow-scheduler
```

3. **View in Airflow UI**: http://localhost:8080

4. **Trigger or Wait**: Manual trigger or automatic schedule

5. **Monitor Execution**: Check logs in UI

## 📊 File Structure

```
docker/
├── Dockerfile                    ← Updated with Airflow
├── docker-compose.yml            ← Updated with 5 services
└── .env                         ← Configuration

dags/
├── ai50_daily_refresh_dag.py    ← Your existing DAG
├── ai50_full_ingest_dag.py      ← Your existing DAG
└── (create new DAGs here)

data/
├── (shared volume for all services)
└── (persistent data storage)
```

## 🐛 Troubleshooting

### DAGs Don't Appear in UI
**Solution**: Restart scheduler - it auto-detects DAGs
```powershell
docker-compose restart airflow-scheduler
```

### Port Already in Use
**Solution**: Edit `docker-compose.yml` and change port:
```yaml
ports:
  - "8081:8080"  # Use 8081 instead of 8080
```

### Database Connection Error
**Solution**: Clean restart
```powershell
docker-compose down -v
docker-compose up -d
```

### Services Won't Start
**Solution**: Check logs
```powershell
docker-compose logs
```

## 🚀 Next Steps

### Immediate (Now)
1. Run `docker-compose up -d`
2. Open http://localhost:8080
3. View your existing DAGs
4. Explore the Airflow UI

### Short Term (Today)
1. Trigger a DAG manually
2. Monitor execution
3. Check task logs
4. View execution history

### Medium Term (This Week)
1. Create a new DAG
2. Set a schedule
3. Integrate with FastAPI
4. Store results

### Long Term (Production)
1. Configure production settings
2. Use external PostgreSQL
3. Set up monitoring
4. Configure backups

## 📞 Useful Links

- **Airflow Documentation**: https://airflow.apache.org/docs/
- **Docker Compose Reference**: https://docs.docker.com/compose/
- **PostgreSQL Docker**: https://hub.docker.com/_/postgres

## ✅ Verification

After running `docker-compose up -d`, verify:

```powershell
# All services running
docker-compose ps

# Airflow UI loads
curl http://localhost:8080

# FastAPI accessible
curl http://localhost:8000/docs

# DAGs detected
docker exec pe-dashboard-airflow-scheduler airflow dags list
```

## 🎉 You're Ready!

Your Docker environment now supports Apache Airflow with:

✅ **Web UI** for DAG management (port 8080)  
✅ **Scheduler** for automated execution  
✅ **PostgreSQL** for metadata storage  
✅ **FastAPI** backend integration  
✅ **Streamlit** frontend integration  
✅ **Persistent storage** for data and logs  

### Start Now:
```powershell
cd docker
docker-compose up -d
```

Then visit: **http://localhost:8080** 🚀

---

## 📖 Additional Resources

For more detailed information, see:
- `docker/README.md` - Complete Docker guide (if exists)
- `docker/QUICK_REFERENCE.md` - Command cheatsheet (if exists)
- `docker-compose.yml` - Service configuration
- `Dockerfile` - Image definition

## 🎊 Congratulations!

Your Airflow Docker setup is complete and ready to use!
