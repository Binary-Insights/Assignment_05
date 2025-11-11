# 🚀 Airflow Docker - Quick Start (Windows)

## ⚡ 30 Second Start

```powershell
cd docker
docker-compose up -d
```

Then open: **http://localhost:8080**  
Login: **admin / admin**

## 🌐 Access Services

```
Airflow UI:     http://localhost:8080  (admin/admin)
FastAPI:        http://localhost:8000/docs
Streamlit:      http://localhost:8501
PostgreSQL:     localhost:5432  (airflow/airflow)
```

## 📝 Essential Commands

```powershell
# Check status
docker-compose ps

# View logs (real-time)
docker-compose logs -f

# View specific service logs
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-webserver

# List all DAGs
docker exec pe-dashboard-airflow-scheduler airflow dags list

# Trigger a DAG
docker exec pe-dashboard-airflow-webserver airflow dags trigger ai50_daily_refresh_dag

# Restart a service
docker-compose restart airflow-scheduler

# Stop all services
docker-compose down

# Stop and remove data
docker-compose down -v
```

## 🎯 What's Running

| Container | Port | Purpose |
|-----------|------|---------|
| postgres | 5432 | Metadata database |
| airflow-webserver | 8080 | Web UI |
| airflow-scheduler | - | Background scheduler |
| fastapi | 8000 | Backend API |
| streamlit | 8501 | Frontend |

## 📋 Your DAGs

Located in: `dags/` folder

Your existing DAGs:
- `ai50_daily_refresh_dag.py`
- `ai50_full_ingest_dag.py`

They'll appear in Airflow UI automatically!

## 🔧 First Time Setup

1. **Start services**:
   ```powershell
   cd docker
   docker-compose up -d
   ```

2. **Wait 30 seconds** for initialization

3. **Open Airflow**: http://localhost:8080

4. **See your DAGs** in the DAGs list

5. **Trigger one**:
   - Click on DAG name
   - Click "Trigger DAG" button
   - Monitor in "Graph" view

## ⚠️ Common Issues & Fixes

| Problem | Fix |
|---------|-----|
| Port 8080 in use | Change docker-compose.yml: `8081:8080` |
| DAGs not showing | Restart scheduler: `docker-compose restart airflow-scheduler` |
| Database error | Clean restart: `docker-compose down -v && docker-compose up -d` |
| Services won't start | Check logs: `docker-compose logs` |

## 💡 Pro Tips

### Monitor Real-Time Execution
1. Go to Airflow UI (http://localhost:8080)
2. Click on a DAG
3. Click "Graph" tab
4. Watch tasks change color as they run

### View Task Output
1. Click task in Graph view
2. Click "Logs" tab
3. See console output

### Check Resource Usage
```powershell
docker stats
```

### Access Database
```powershell
docker exec -it pe-dashboard-postgres psql -U airflow -d airflow
# Then inside: SELECT * FROM dag_run;
```

## 📚 Learn More

- **Complete setup**: See `AIRFLOW_DOCKER_SETUP.md`
- **Troubleshooting**: See `docker/AIRFLOW_SETUP.md` (if available)
- **Examples**: Check `dags/example_advanced_dags.py` (if available)

## 🎉 Ready to Go!

Everything is set up. Just run and explore! 🚀

---

**Quick Links**:
- Airflow: http://localhost:8080
- FastAPI: http://localhost:8000/docs
- Streamlit: http://localhost:8501
