# ✅ .env Configuration for FastAPI & Streamlit

## Update Complete

Both **FastAPI** and **Streamlit** services have been updated to properly load and use the `.env` file.

## What Changed

### FastAPI Service (Lines 313-337)

```yaml
fastapi:
  <<: *airflow-common
  container_name: assignment04-api
  ports:
    - "8000:8000"
  networks:
    - assignment-network
  
  env_file:                         # ✅ NEW: Load .env file
    - ../.env
  
  environment:
    <<: *airflow-common-env          # ✅ Include common env vars
    PYTHONUNBUFFERED: "1"            # ✅ Python output buffering
    ENVIRONMENT: docker              # ✅ App environment
  
  command: uvicorn src.backend.rag_search_api:app --host 0.0.0.0 --port 8000 --reload
  profiles:
    - with-api
  
  healthcheck:                       # ✅ NEW: Health check
    test: ["CMD", "curl", "--fail", "http://localhost:8000/docs"]
  restart: on-failure
```

### Streamlit Service (Lines 339-368)

```yaml
streamlit:
  <<: *airflow-common
  container_name: assignment04-ui
  ports:
    - "8501:8501"
  networks:
    - assignment-network
  
  env_file:                         # ✅ NEW: Load .env file
    - ../.env
  
  environment:
    <<: *airflow-common-env          # ✅ Include common env vars
    PYTHONUNBUFFERED: "1"            # ✅ Python output buffering
    ENVIRONMENT: docker              # ✅ App environment
    STREAMLIT_SERVER_PORT: "8501"    # ✅ Streamlit config
    STREAMLIT_SERVER_ADDRESS: "0.0.0.0"  # ✅ Listen on all IPs
    STREAMLIT_SERVER_HEADLESS: "true"    # ✅ Headless mode
  
  command: streamlit run src/frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
  profiles:
    - with-ui
  
  healthcheck:                       # ✅ NEW: Health check
    test: ["CMD", "curl", "--fail", "http://localhost:8501/_stcore/health"]
  restart: on-failure
```

## Key Updates

### ✅ .env File Loading
Both services now explicitly load the `.env` file:
```yaml
env_file:
  - ../.env  # Loaded from project root
```

### ✅ Environment Variable Merging
Both services now merge common environment variables with service-specific ones:
```yaml
environment:
  <<: *airflow-common-env  # Common vars (AWS, DB, etc.)
  PYTHONUNBUFFERED: "1"    # Service-specific vars
```

### ✅ Streamlit Configuration
Added Streamlit-specific environment variables:
```yaml
STREAMLIT_SERVER_PORT: "8501"
STREAMLIT_SERVER_ADDRESS: "0.0.0.0"
STREAMLIT_SERVER_HEADLESS: "true"
```

### ✅ Health Checks
Added health checks for both services:
- **FastAPI**: Tests `/docs` endpoint (Swagger UI)
- **Streamlit**: Tests `/_stcore/health` endpoint

### ✅ Auto-restart
Both services now auto-restart on failure:
```yaml
restart: on-failure
```

## Available Environment Variables

### From .env File
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`
- `S3_BUCKET_NAME`
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `PINECONE_API_KEY`
- ... and any other custom variables

### FastAPI-Specific
- `API_HOST` (from .env or 0.0.0.0)
- `API_PORT` (from .env or 8000)
- `ENVIRONMENT` (docker)
- `PYTHONUNBUFFERED` (1)

### Streamlit-Specific
- `STREAMLIT_SERVER_PORT` (8501)
- `STREAMLIT_SERVER_ADDRESS` (0.0.0.0)
- `STREAMLIT_SERVER_HEADLESS` (true)

## Starting Services with .env

### FastAPI Only
```bash
docker-compose --profile with-api up -d
```

### Streamlit Only
```bash
docker-compose --profile with-ui up -d
```

### Both FastAPI & Streamlit
```bash
docker-compose --profile with-api --profile with-ui up -d
```

### All Services (Including Airflow, Flower, etc.)
```bash
docker-compose --profile flower --profile with-api --profile with-ui up -d
```

## Verifying .env Loading

### Check FastAPI Environment
```bash
docker-compose exec fastapi env | grep AWS_
docker-compose exec fastapi env | grep S3_
```

### Check Streamlit Environment
```bash
docker-compose exec streamlit env | grep STREAMLIT_
docker-compose exec streamlit env | grep AWS_
```

### View All Environment Variables
```bash
# FastAPI
docker-compose exec fastapi env | sort

# Streamlit
docker-compose exec streamlit env | sort
```

### Test Variable Access in Python
```bash
# FastAPI
docker-compose exec fastapi python -c "
import os
print(f'S3 Bucket: {os.getenv(\"S3_BUCKET_NAME\")}')
print(f'AWS Region: {os.getenv(\"AWS_DEFAULT_REGION\")}')
"

# Streamlit
docker-compose exec streamlit python -c "
import os
print(f'S3 Bucket: {os.getenv(\"S3_BUCKET_NAME\")}')
print(f'DB Host: {os.getenv(\"DB_HOST\")}')
"
```

## Debugging .env Issues

### Issue: Variables Not Available

```bash
# 1. Verify .env file exists
ls -la .env

# 2. Check docker-compose.yml configuration
grep -A 5 "env_file:" docker/docker-compose.yml

# 3. View resolved configuration
docker-compose config | grep -A 20 "fastapi:"

# 4. Check container logs
docker-compose logs fastapi
docker-compose logs streamlit
```

### Issue: Special Characters

If your .env has special characters:
```bash
# ✅ DO: Use quotes for special characters
AWS_SECRET="my!secret$key"

# ❌ DON'T: Use unquoted special characters
AWS_SECRET=my!secret$key
```

### Issue: Changes Not Applied

```bash
# Rebuild without cache
docker-compose build --no-cache

# Stop and remove containers
docker-compose down -v

# Start fresh
docker-compose --profile with-api --profile with-ui up -d
```

## Example .env File

Create `.env` in project root:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=my-bucket

# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=airflow
DB_PASSWORD=airflow

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
PINECONE_API_KEY=...

# Application Settings
ENVIRONMENT=docker
PYTHONUNBUFFERED=1
```

## Environment Variable Precedence

Variables are loaded in this order (highest priority first):

1. **Runtime Override** (explicit export)
   ```bash
   export MY_VAR=value
   docker-compose up
   ```

2. **docker-compose.yml environment section**
   ```yaml
   environment:
     MY_VAR: overrides_env_file
   ```

3. **.env file** (via env_file)
   ```bash
   MY_VAR=from_env_file
   ```

4. **Host system environment** (inherited)

## Services Now Using .env

| Service | .env Loaded | Profile | Purpose |
|---------|----------|---------|---------|
| postgres | ✓ | (always) | Metadata |
| redis | ✓ | (always) | Message broker |
| airflow-webserver | ✓ | (always) | Airflow UI |
| airflow-scheduler | ✓ | (always) | Task scheduling |
| airflow-worker | ✓ | (always) | Task execution |
| airflow-triggerer | ✓ | (always) | Async events |
| **fastapi** | **✓** | **with-api** | Backend API |
| **streamlit** | **✓** | **with-ui** | Frontend UI |
| flower | ✓ | flower | Monitoring |

## Next Steps

1. **Create .env file** in project root with your configuration
2. **Start services**:
   ```bash
   docker-compose --profile with-api --profile with-ui up -d
   ```
3. **Verify** environment variables loaded:
   ```bash
   docker-compose exec fastapi env | grep AWS_
   docker-compose exec streamlit env | grep STREAMLIT_
   ```
4. **Access services**:
   - FastAPI: http://localhost:8000/docs
   - Streamlit: http://localhost:8501

## Documentation

- Read: **ENV_CONFIGURATION_GUIDE.md** for complete .env guide
- Read: **CELERY_QUICK_START.md** for service startup commands
- Read: **docker-compose.yml** lines 313-368 for FastAPI/Streamlit config

## Summary

✅ **FastAPI** can now access `.env` variables  
✅ **Streamlit** can now access `.env` variables  
✅ Both services inherit common environment variables  
✅ Health checks enabled for both  
✅ Auto-restart configured for both  
✅ Ready to start and test  

**Next command:**
```bash
docker-compose --profile with-api --profile with-ui up -d
```

Then verify:
```bash
docker-compose ps
curl http://localhost:8000/docs
curl http://localhost:8501
```
