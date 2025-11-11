# ✅ FastAPI & Streamlit .env Integration Complete

## 🎉 Latest Update Summary

Your FastAPI and Streamlit services now **automatically load the `.env` file** and access all environment variables!

---

## 📝 What Changed

### docker-compose.yml Updates

#### FastAPI Service (Lines 313-337)
```yaml
fastapi:
  env_file:
    - ../.env              # ✅ Loads .env automatically
  environment:
    <<: *airflow-common-env  # ✅ All AWS, DB vars available
    PYTHONUNBUFFERED: "1"
    ENVIRONMENT: docker
  healthcheck:             # ✅ Added health check
    test: ["CMD", "curl", "--fail", "http://localhost:8000/docs"]
  restart: on-failure      # ✅ Auto-restart
```

#### Streamlit Service (Lines 339-368)
```yaml
streamlit:
  env_file:
    - ../.env              # ✅ Loads .env automatically
  environment:
    <<: *airflow-common-env  # ✅ All AWS, DB vars available
    PYTHONUNBUFFERED: "1"
    ENVIRONMENT: docker
    STREAMLIT_SERVER_PORT: "8501"
    STREAMLIT_SERVER_ADDRESS: "0.0.0.0"
    STREAMLIT_SERVER_HEADLESS: "true"
  healthcheck:             # ✅ Added health check
    test: ["CMD", "curl", "--fail", "http://localhost:8501/_stcore/health"]
  restart: on-failure      # ✅ Auto-restart
```

---

## 🔧 How It Works

### .env File Location
```
Project Root/
├── .env                  ← Your environment variables
├── docker/
│   └── docker-compose.yml ← References ../env_file
└── src/
    ├── backend/
    │   └── rag_search_api.py ← Uses os.getenv() to access vars
    └── frontend/
        └── streamlit_app.py ← Uses os.getenv() to access vars
```

### Variable Loading Flow

```
.env File
├── AWS_ACCESS_KEY_ID=...
├── AWS_SECRET_ACCESS_KEY=...
├── S3_BUCKET_NAME=...
└── ... other variables ...
        ↓
docker-compose.yml loads via "env_file: - ../.env"
        ↓
FastAPI Container | Streamlit Container
        ↓
os.getenv("AWS_ACCESS_KEY_ID")
os.getenv("S3_BUCKET_NAME")
... etc ...
```

### Available Variables in FastAPI & Streamlit

#### From .env File (Your Configuration)
```python
import os

# In your FastAPI or Streamlit code:
aws_key = os.getenv("AWS_ACCESS_KEY_ID")
s3_bucket = os.getenv("S3_BUCKET_NAME")
api_key = os.getenv("OPENAI_API_KEY")
db_url = os.getenv("DATABASE_URL")
```

#### From Common Environment
```python
# Automatically available to both services:
db_host = os.getenv("DB_HOST")                    # "postgres"
db_user = os.getenv("DB_USER")                    # "airflow"
broker_url = os.getenv("AIRFLOW__CELERY__BROKER_URL")
# "redis://:@redis:6379/0"
```

#### Service-Specific (Streamlit)
```python
# In Streamlit only:
streamlit_port = os.getenv("STREAMLIT_SERVER_PORT")      # "8501"
streamlit_headless = os.getenv("STREAMLIT_SERVER_HEADLESS")  # "true"
```

---

## 📋 Create .env File

### Step 1: Create File in Project Root

```bash
# Create .env file in project root (NOT in docker/ folder)
cat > .env << 'EOF'
# AWS Configuration
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=my-bucket

# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=airflow
DB_PASSWORD=airflow
DATABASE_URL=postgresql://airflow:airflow@postgres:5432/airflow

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PINECONE_API_KEY=...

# Application
ENVIRONMENT=docker
EOF
```

### Step 2: Verify File
```bash
# Check file was created
ls -la .env

# Check format
head .env

# Do NOT commit to git!
echo ".env" >> .gitignore
```

---

## 🚀 Start Services

### All Services
```bash
docker-compose up -d
```

### With FastAPI Only
```bash
docker-compose --profile with-api up -d
```

### With Streamlit Only
```bash
docker-compose --profile with-ui up -d
```

### With Both FastAPI & Streamlit
```bash
docker-compose --profile with-api --profile with-ui up -d
```

### With Everything (Including Monitoring)
```bash
docker-compose --profile with-api --profile with-ui --profile flower up -d
```

---

## ✅ Verify .env Loading

### Check FastAPI

```bash
# 1. Verify service is running
docker-compose ps | grep fastapi

# 2. Check if .env variables are loaded
docker-compose exec fastapi env | grep AWS_

# 3. Test specific variable
docker-compose exec fastapi python -c "
import os
print(f'S3 Bucket: {os.getenv(\"S3_BUCKET_NAME\")}')
print(f'AWS Region: {os.getenv(\"AWS_DEFAULT_REGION\")}')
"

# 4. Access API
curl http://localhost:8000/docs
```

### Check Streamlit

```bash
# 1. Verify service is running
docker-compose ps | grep streamlit

# 2. Check if .env variables are loaded
docker-compose exec streamlit env | grep STREAMLIT_

# 3. Test specific variable
docker-compose exec streamlit python -c "
import os
print(f'S3 Bucket: {os.getenv(\"S3_BUCKET_NAME\")}')
print(f'Streamlit Port: {os.getenv(\"STREAMLIT_SERVER_PORT\")}')
"

# 4. Access UI
curl http://localhost:8501
```

---

## 📊 Service Comparison

### Before This Update
```yaml
fastapi:
  container_name: assignment04-api
  ports:
    - "8000:8000"
  command: uvicorn src.backend.rag_search_api:app ...
  # ❌ No explicit .env loading
  # ❌ No health check
  # ❌ No auto-restart
```

### After This Update
```yaml
fastapi:
  container_name: assignment04-api
  ports:
    - "8000:8000"
  env_file:              # ✅ NEW
    - ../.env
  environment:           # ✅ ENHANCED
    <<: *airflow-common-env
    PYTHONUNBUFFERED: "1"
  healthcheck:           # ✅ NEW
    test: ["CMD", "curl", "--fail", "http://localhost:8000/docs"]
  restart: on-failure    # ✅ NEW
  command: uvicorn src/backend/rag_search_api:app ...
```

---

## 🎯 Key Features Added

| Feature | FastAPI | Streamlit | Purpose |
|---------|---------|-----------|---------|
| **.env Loading** | ✅ | ✅ | Access environment variables |
| **Environment Merging** | ✅ | ✅ | Common + service-specific vars |
| **Health Checks** | ✅ | ✅ | Verify service is healthy |
| **Auto-Restart** | ✅ | ✅ | Resilience on failure |
| **Streamlit Config** | - | ✅ | Port, address, headless mode |

---

## 🔍 Use Cases

### FastAPI Using .env Variables

```python
# FastAPI code (src/backend/rag_search_api.py)
import os
from fastapi import FastAPI

app = FastAPI()

# Access .env variables
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION")
API_KEY = os.getenv("OPENAI_API_KEY")

@app.get("/search")
async def search(query: str):
    # Use S3_BUCKET and API_KEY from .env
    # Connect to S3: boto3.client('s3', region_name=AWS_REGION)
    # Call LLM: openai.ChatCompletion.create(api_key=API_KEY)
    return {"results": [...]}
```

### Streamlit Using .env Variables

```python
# Streamlit code (src/frontend/streamlit_app.py)
import os
import streamlit as st

# Access .env variables
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="RAG Search",
    page_icon="🔍"
)

# Use variables
st.write(f"Connecting to S3 bucket: {S3_BUCKET}")
response = requests.get(f"{API_URL}/search?query=...")
```

---

## 🛠️ Troubleshooting

### Issue: Variables Not Accessible

**Symptom:** `os.getenv("MY_VAR")` returns `None`

**Solution:**
```bash
# 1. Verify .env file exists
ls -la .env

# 2. Check path in docker-compose.yml
grep "env_file" docker/docker-compose.yml

# 3. Rebuild without cache
docker-compose build --no-cache

# 4. Restart services
docker-compose down -v
docker-compose up -d
```

### Issue: Variables Show in env But Not in App

**Symptom:** `docker-compose exec fastapi env | grep MY_VAR` works, but app can't access

**Solution:**
```bash
# 1. Verify app is reading from os.getenv()
docker-compose exec fastapi python -c "
import sys
print(sys.path)
import os
print(os.getenv('MY_VAR'))
"

# 2. Check for typos in variable name
# 3. Verify .env file format (no spaces around =)
```

### Issue: Special Characters in .env

**Symptom:** Values with `!`, `$`, etc. break

**Solution:**
```bash
# Use quotes for special characters
MY_VAR="value!with$special"

# Or escape them
MY_VAR=value\!\with\$special
```

---

## 📚 Additional Resources

### For Complete .env Configuration
→ Read: **ENV_CONFIGURATION_GUIDE.md**

### For All .env Changes
→ Read: **ENV_FASTAPI_STREAMLIT_UPDATE.md**

### For Getting Started
→ Read: **CELERY_QUICK_START.md**

### For Complete Documentation Index
→ Read: **DOCUMENTATION_INDEX.md**

---

## ✅ Checklist

Before starting services:
- [ ] `.env` file created in project root
- [ ] `.env` has AWS credentials (if using S3)
- [ ] `.env` has database credentials
- [ ] `.env` has any API keys needed
- [ ] `.env` is in `.gitignore`
- [ ] File permissions are readable
- [ ] No syntax errors in `.env`

To verify setup:
- [ ] Run `docker-compose ps`
- [ ] All services show "Up"
- [ ] Run `docker-compose exec fastapi env | grep AWS_`
- [ ] Variables appear correctly
- [ ] Access http://localhost:8000/docs (FastAPI)
- [ ] Access http://localhost:8501 (Streamlit)

---

## 🚀 Quick Start Command

```bash
# 1. Create .env (if not exists)
cat > .env << 'EOF'
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=your-bucket
EOF

# 2. Build images
cd docker
docker-compose build --no-cache

# 3. Start with FastAPI & Streamlit
cd ..
docker-compose --profile with-api --profile with-ui up -d

# 4. Verify
docker-compose ps
docker-compose exec fastapi env | grep AWS_

# 5. Access
# Airflow: http://localhost:8080
# FastAPI: http://localhost:8000/docs
# Streamlit: http://localhost:8501
```

---

## 📊 Service Health

After startup, verify health:

```bash
# Check all services
docker-compose ps

# Check specific services
docker-compose exec fastapi curl -f http://localhost:8000/docs
docker-compose exec streamlit curl -f http://localhost:8501/_stcore/health

# View logs if issues
docker-compose logs fastapi
docker-compose logs streamlit
```

---

## 🎓 Environment Variable Hierarchy

When a service needs a variable, it checks in this order:

1. **docker-compose.yml environment section**
   ```yaml
   environment:
     MY_VAR: priority_1
   ```

2. **.env file** (via env_file)
   ```bash
   # in .env
   MY_VAR=priority_2
   ```

3. **Host system environment**
   ```bash
   export MY_VAR=priority_3
   ```

4. **Not found** → `os.getenv("MY_VAR")` returns `None`

---

## 🎉 You're All Set!

Your FastAPI and Streamlit services are now fully configured to:
- ✅ Load .env automatically
- ✅ Access environment variables
- ✅ Health checks enabled
- ✅ Auto-restart on failure
- ✅ Ready for production

**Next Step:** Create `.env` and start services!

```bash
docker-compose --profile with-api --profile with-ui up -d
```
