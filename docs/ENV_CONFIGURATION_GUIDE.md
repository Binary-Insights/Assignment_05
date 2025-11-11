# .env Configuration Guide

## Overview

The `.env` file is loaded by all services in docker-compose including **FastAPI** and **Streamlit**. This guide explains how to configure your environment variables for proper service operation.

## Services Using .env

All services now explicitly load the `.env` file:
- ✅ Airflow Webserver
- ✅ Airflow Scheduler
- ✅ Celery Worker
- ✅ Airflow Triggerer
- ✅ PostgreSQL (via connection strings)
- ✅ FastAPI Backend **[NEW]**
- ✅ Streamlit Frontend **[NEW]**
- ✅ Flower (if enabled)

## .env File Location

```
Project Root/
├── docker/
│   └── docker-compose.yml
├── .env                    ◄─── Load from here
├── src/
├── dags/
└── data/
```

**Path in docker-compose.yml:**
```yaml
env_file:
  - ../.env  # Relative to docker/ directory
```

## Required Environment Variables

### AWS Credentials (For S3 integration)

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=your-bucket-name
```

### Airflow Configuration

```bash
# Airflow Admin User
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=admin
```

### Application Settings

```bash
# Environment Type
ENVIRONMENT=docker

# Python Settings
PYTHONUNBUFFERED=1

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
```

## Optional Environment Variables

### FastAPI Configuration

```bash
# FastAPI Settings
FASTAPI_DEBUG=false
FASTAPI_RELOAD=true
API_TITLE=RAG Search API
API_DESCRIPTION=Search API for AI50 dashboard
API_VERSION=1.0.0
```

### Streamlit Configuration

```bash
# Streamlit Settings
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_LOGGER_LEVEL=info
STREAMLIT_CLIENT_TOOLBAR_MODE=minimal
```

### LLM & Model Settings

```bash
# HuggingFace
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers

# DeepSearch
DEEPSEARCH_GLM_CACHE_DIR=/app/.cache/deepsearch_glm

# OpenAI/Anthropic (if using)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Database Configuration

```bash
# PostgreSQL Connection
DB_HOST=postgres
DB_PORT=5432
DB_NAME=airflow
DB_USER=airflow
DB_PASSWORD=airflow

# Connection String (for some apps)
DATABASE_URL=postgresql://airflow:airflow@postgres:5432/airflow
```

### Pinecone Configuration (if using)

```bash
# Pinecone Vector DB
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=your_index_name
```

### Logging Configuration

```bash
# Logging Level
LOG_LEVEL=INFO
AIRFLOW__LOGGING__LOGGING_LEVEL=INFO

# Log Format
LOG_FORMAT=%(asctime)s [%(levelname)s] %(name)s - %(message)s
```

## Example .env File

Create a `.env` file in your project root:

```bash
# ===== AWS Configuration =====
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=my-ai50-data

# ===== Airflow Configuration =====
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=airflow123

# ===== Database Configuration =====
DB_HOST=postgres
DB_PORT=5432
DB_NAME=airflow
DB_USER=airflow
DB_PASSWORD=airflow
DATABASE_URL=postgresql://airflow:airflow@postgres:5432/airflow

# ===== Application Settings =====
ENVIRONMENT=docker
PYTHONUNBUFFERED=1

# ===== API Configuration =====
API_HOST=0.0.0.0
API_PORT=8000
FASTAPI_DEBUG=false
FASTAPI_RELOAD=true
API_TITLE=RAG Search API
API_VERSION=1.0.0

# ===== Streamlit Configuration =====
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_LOGGER_LEVEL=info

# ===== LLM & Model Caching =====
HF_HOME=/app/.cache/huggingface
TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers
DEEPSEARCH_GLM_CACHE_DIR=/app/.cache/deepsearch_glm

# ===== Pinecone Configuration (Optional) =====
PINECONE_API_KEY=your_key_here
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=ai50-index

# ===== LLM Keys (Optional) =====
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# ===== Logging Configuration =====
LOG_LEVEL=INFO
AIRFLOW__LOGGING__LOGGING_LEVEL=INFO
```

## Environment Variable Precedence

### Precedence Order (Highest to Lowest)

1. **Runtime Override** (command line, explicit export)
   ```bash
   export MY_VAR=value
   docker-compose up
   ```

2. **Environment Section in docker-compose.yml**
   ```yaml
   environment:
     MY_VAR: value
   ```

3. **.env File** (via `env_file`)
   ```bash
   # in .env
   MY_VAR=value
   ```

4. **Host Machine Environment**
   ```bash
   # System environment variables
   echo $MY_VAR
   ```

5. **Container Default** (if hardcoded in image)

**Example:**
```yaml
env_file:
  - ../.env  # Loaded first

environment:
  MY_VAR: overridden_value  # This takes precedence!
```

## How Services Access .env

### FastAPI Service

```yaml
fastapi:
  <<: *airflow-common
  env_file:
    - ../.env              # ✅ Loads .env
  environment:
    <<: *airflow-common-env  # ✅ Merges common env vars
    ENVIRONMENT: docker    # ✅ Can override
```

**In FastAPI code:**
```python
import os
from dotenv import load_dotenv

# Option 1: Access via os.environ
api_title = os.getenv("API_TITLE", "default")

# Option 2: Use python-dotenv
load_dotenv()
bucket_name = os.getenv("S3_BUCKET_NAME")
```

### Streamlit Service

```yaml
streamlit:
  <<: *airflow-common
  env_file:
    - ../.env              # ✅ Loads .env
  environment:
    <<: *airflow-common-env  # ✅ Merges common env vars
    STREAMLIT_SERVER_PORT: "8501"  # ✅ Streamlit-specific
```

**In Streamlit code:**
```python
import os
import streamlit as st

# Access environment variables
s3_bucket = os.getenv("S3_BUCKET_NAME")
api_host = os.getenv("API_HOST", "localhost")

# Use in Streamlit config
st.set_page_config(
    page_title=os.getenv("API_TITLE", "Dashboard"),
    layout="wide"
)
```

## Starting Services with .env

### Load Environment

```bash
# .env is automatically loaded by docker-compose
docker-compose up -d

# Or explicitly specify .env file
docker-compose --env-file ../.env up -d

# Override specific variable
AWS_ACCESS_KEY_ID=newkey docker-compose up -d
```

### Verify Environment Variables

```bash
# Check FastAPI service has env vars
docker-compose exec fastapi env | grep AWS_

# Check Streamlit service has env vars
docker-compose exec streamlit env | grep STREAMLIT_

# Inside container, read from Python
docker-compose exec fastapi python -c "import os; print(os.getenv('S3_BUCKET_NAME'))"
```

### Debug Environment Loading

```bash
# View all environment variables in a service
docker-compose exec fastapi env

# Check if .env file was loaded
docker-compose logs fastapi | grep "env_file"

# View docker-compose resolved configuration
docker-compose config | grep -A 20 "fastapi:"
```

## Common Issues & Solutions

### Issue 1: Environment Variables Not Available

**Problem:** Variables from .env not accessible in application

**Solution:**
```bash
# 1. Verify .env file exists
ls -la .env

# 2. Check file format (UTF-8, no BOM)
file .env

# 3. Verify path in docker-compose.yml
grep "env_file" docker-compose.yml

# 4. Rebuild and restart
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Issue 2: Special Characters in .env

**Problem:** Special characters (!, $, etc.) cause issues

**Solution:**
```bash
# Use quotes for special characters
AWS_SECRET=my!secret$key  # ❌ Wrong
AWS_SECRET="my!secret$key"  # ✅ Correct

# Or escape special characters
AWS_SECRET=my\!secret\$key  # ✅ Also correct
```

### Issue 3: Multiline Values

**Problem:** Multiline values (certificates, keys) break parsing

**Solution:**
```bash
# Use quotes for multiline
SSH_KEY="-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----"  # ✅ Correct

# Or use base64 encoding
SSH_KEY_B64=LS0tLS1CRUdJTi...  # ✅ Alternative
```

### Issue 4: Comments Not Working

**Problem:** Comments in .env file cause issues

**Solution:**
```bash
# Format for comments in .env
# This is a comment ✅
MY_VAR=value  # Inline comment ✗ Avoid

# Correct format
MY_VAR=value  # Store in variable
```

## Security Best Practices

### 1. Never Commit .env to Git

```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
echo ".env.*" >> .gitignore
```

### 2. Use .env.example Template

```bash
# Create template for team
cp .env .env.example

# Remove sensitive values
sed -i 's/=.*/=CHANGE_ME/g' .env.example

# Commit template, not actual .env
git add .env.example
git commit -m "Add .env template"
```

### 3. Use Strong Credentials

```bash
# Use generated credentials, not defaults
AWS_ACCESS_KEY_ID=AKIA...  # Use IAM keys, not root
DB_PASSWORD=generate_strong_password  # Not "password"
OPENAI_API_KEY=sk-...  # Use app-specific keys
```

### 4. Rotate Credentials Regularly

```bash
# Change sensitive values periodically
# Update AWS IAM keys monthly
# Rotate database passwords quarterly
# Regenerate API keys on team changes
```

### 5. Use Environment-Specific .env Files

```bash
# Local development
.env.local

# Staging environment
.env.staging

# Production environment
.env.production

# Load with:
docker-compose --env-file .env.production up -d
```

## Testing .env Configuration

### Test 1: Verify File Loading

```bash
docker-compose config | grep -A 30 "environment:"
```

### Test 2: Check Variables in Container

```bash
docker-compose up -d fastapi
docker-compose exec fastapi python -c "
import os
print(f'S3_BUCKET: {os.getenv(\"S3_BUCKET_NAME\")}')
print(f'AWS_KEY: {os.getenv(\"AWS_ACCESS_KEY_ID\")[:10]}...')
print(f'DB_HOST: {os.getenv(\"DB_HOST\")}')
"
```

### Test 3: Application Access to Variables

**FastAPI:**
```bash
docker-compose exec fastapi python -c "
from src.backend.rag_search_api import app
# Your app should have access to env vars
"
```

**Streamlit:**
```bash
docker-compose exec streamlit python -c "
import streamlit as st
import os
print(os.getenv('STREAMLIT_SERVER_PORT'))
"
```

## Complete Configuration Checklist

Before starting services, verify:

- [ ] `.env` file exists in project root
- [ ] `.env` has all required variables set
- [ ] AWS credentials are valid (if using S3)
- [ ] Database credentials match PostgreSQL setup
- [ ] API keys are present (OpenAI, Anthropic, etc.)
- [ ] `.env` is in `.gitignore`
- [ ] File permissions allow reading (not executable)
- [ ] No syntax errors in `.env` (test with `source .env`)
- [ ] Sensitive values are not committed to git
- [ ] Team members have their own `.env` (not shared)

## Usage Examples

### Starting All Services

```bash
# Start with .env loaded
docker-compose up -d

# Or with explicit .env file
docker-compose --env-file .env up -d

# With specific environment override
AWS_REGION=us-west-2 docker-compose up -d
```

### Starting Specific Services

```bash
# FastAPI only (with .env)
docker-compose --profile with-api up -d

# Streamlit only (with .env)
docker-compose --profile with-ui up -d

# Everything (with .env)
docker-compose --profile flower --profile with-api --profile with-ui up -d
```

### Viewing Loaded Variables

```bash
# In FastAPI container
docker-compose exec fastapi env | sort

# In Streamlit container
docker-compose exec streamlit env | sort

# Compare what was expected vs actual
docker-compose exec fastapi bash -c "
echo 'Expected: S3_BUCKET_NAME'
echo \"Actual: \$(echo \$S3_BUCKET_NAME)\"
"
```

## Support & Troubleshooting

If .env variables aren't loading:

1. **Verify file exists:**
   ```bash
   ls -la .env
   ```

2. **Check docker-compose.yml path:**
   ```bash
   grep "env_file" docker/docker-compose.yml
   ```

3. **Test with explicit path:**
   ```bash
   docker-compose --env-file /path/to/.env up -d
   ```

4. **Rebuild without cache:**
   ```bash
   docker-compose build --no-cache
   docker-compose down -v
   docker-compose up -d
   ```

5. **Check container logs:**
   ```bash
   docker-compose logs fastapi
   docker-compose logs streamlit
   ```

---

**Your FastAPI and Streamlit services now properly load and use the .env file!**
