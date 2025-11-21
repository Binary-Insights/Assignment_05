# ⚡ Quick Reference - Airflow Login

## 🔓 LOGIN CREDENTIALS

```
USERNAME: airflow
PASSWORD: airflow
```

## 🌐 ACCESS URLS

```
Airflow UI:   http://localhost:8080
API:          http://localhost:8000
Dashboard:    http://localhost:8501
```

## 📝 Steps to Login

1. Open: **http://localhost:8080**
2. Enter username: **airflow**
3. Enter password: **airflow**
4. Click **Login** ✅

## ✅ What You Should See

- **DAGs Tab** → 3 DAGs listed
  - `eval_runner_dag` (your main DAG)
  - `ai50_daily_refresh_dag`
  - `ai50_full_ingest_dag`

- **Graph View** → Shows 8 tasks
  - Task dependencies
  - Execution status
  - Real-time updates

## 🆘 If Login Fails

### Wait 30 seconds and refresh
Database initializing...

### Check user exists
```bash
docker-compose exec airflow-scheduler airflow users list
```

### Create user manually
```bash
docker-compose exec airflow-scheduler airflow users create \
  --username airflow --password airflow \
  --firstname Airflow --lastname Admin \
  --role Admin --email admin@example.com
```

### Restart webserver
```bash
docker-compose restart airflow-webserver
```

## 🎮 After Login - First Actions

1. Click on `eval_runner_dag`
2. Click "Trigger DAG" button
3. Watch tasks execute in "Graph View"
4. Check logs in "Log" tab

## 📊 Useful Links in UI

- **Home** - Dashboard overview
- **DAGs** - All DAG list
- **Admin** - Users, connections, config
- **Logs** - Task execution logs
- **Security** - Authentication settings

---

**Username**: airflow | **Password**: airflow | **URL**: http://localhost:8080
