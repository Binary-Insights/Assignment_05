# Running in Docker - Setup Guide

## Problem Solved

**Error:** `HTTPConnectionPool(host='localhost', port=8000): Failed to establish a new connection`

**Root Cause:** When Streamlit container tried to reach FastAPI on `localhost:8000`, it failed because:
- `localhost` inside a Docker container refers to the container itself
- FastAPI is running in a different container named `fastapi`
- Docker containers need to use service names to communicate, not `localhost`

**Solution:** Updated to use Docker service name `fastapi:8000` when running in Docker.

## Updated Configuration

### 1. `src/frontend/streamlit_app.py`

**What Changed:**
- Added environment detection (ENVIRONMENT=docker vs local)
- Uses `http://fastapi:8000` when running in Docker
- Uses `http://localhost:8000` when running locally

**Code:**
```python
ENVIRONMENT = os.getenv("ENVIRONMENT", "local").lower()

if ENVIRONMENT == "docker":
    # Running in Docker - use Docker service name
    API_BASE = os.getenv("FASTAPI_URL", "http://fastapi:8000")
else:
    # Running locally - use localhost
    API_BASE = os.getenv("FASTAPI_URL", "http://localhost:8000")
```

### 2. `docker/docker-compose.yml`

**What Changed:**
- Added `ENVIRONMENT=docker` environment variable to Streamlit service

**Code:**
```yaml
streamlit:
  # ...
  environment:
    - PYTHONUNBUFFERED=1
    - ENVIRONMENT=docker  # ← NEW
  # ...
```

## How It Works

### Docker Environment (in containers)

```
┌─────────────────────────────────────────┐
│     Docker Network: assignment-04       │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────────┐ │
│  │   Streamlit (pe-dashboard-ui)     │ │
│  │   :8501                           │ │
│  │   ENVIRONMENT=docker              │ │
│  │                                   │ │
│  │   API_BASE=http://fastapi:8000 ← │ │
│  │        ↓ (Docker DNS)             │ │
│  └───────────────────────────────────┘ │
│                 ↓                       │
│  ┌───────────────────────────────────┐ │
│  │   FastAPI (pe-dashboard-api)      │ │
│  │   :8000                           │ │
│  │   Pinecone + OpenAI               │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

### Local Environment (on host)

```
Host Machine
├─ FastAPI: http://localhost:8000
└─ Streamlit: http://localhost:8501
   └─ API_BASE=http://localhost:8000 ← Uses localhost
```

## Running in Docker

### Prerequisites

1. Install Docker and Docker Compose
2. Set environment variables in `.env`:
```bash
PINECONE_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
ENVIRONMENT=docker  # Optional, can be set in docker-compose.yml
```

3. Ensure raw data exists:
```bash
ls data/raw/world_labs/*/text.txt
```

### Start All Services

```bash
cd docker
docker-compose up -d
```

Expected output:
```
Creating assignment-04_fastapi_1 ... done
Creating assignment-04_streamlit_1 ... done
```

### Verify Services Are Running

```bash
docker-compose ps
```

Expected:
```
NAME                     STATUS      PORTS
pe-dashboard-api         Up 1 min    0.0.0.0:8000->8000/tcp
pe-dashboard-ui          Up 1 min    0.0.0.0:8501->8501/tcp
```

### Check Connection

```bash
# Test FastAPI health
curl http://localhost:8000/health

# Test companies endpoint
curl http://localhost:8000/companies

# Check Streamlit logs
docker-compose logs streamlit
```

### Access Applications

- **FastAPI**: http://localhost:8000
- **Streamlit**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs

## Troubleshooting

### Streamlit still can't reach FastAPI

**Symptoms:** Error in Streamlit logs about connection to localhost

**Solutions:**

1. **Verify services are both running:**
```bash
docker-compose ps
```

2. **Check service names:**
```bash
docker network ls
docker network inspect assignment-04
```

3. **Test from inside Streamlit container:**
```bash
docker-compose exec streamlit curl http://fastapi:8000/health
```

4. **Check environment variable in Streamlit:**
```bash
docker-compose exec streamlit python -c "import os; print(os.getenv('ENVIRONMENT'))"
```

5. **Check logs:**
```bash
docker-compose logs -f streamlit
docker-compose logs -f fastapi
```

---

### "Connection refused" error

**Cause:** FastAPI not ready when Streamlit connects

**Solution:** Wait a few seconds and refresh Streamlit page

```bash
# Wait for FastAPI to start
sleep 5

# Open browser
http://localhost:8501
```

---

### Docker compose command not found

**Cause:** Docker Compose not installed or old version

**Solution:**
```bash
# Install latest Docker Compose v2
docker --version  # Should show v20+

# Or use older syntax
docker-compose --version  # Should show v1.29+
```

---

### Permissions error

**Cause:** Running without sudo on Linux

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or:
newgrp docker
```

## Environment Variables

### Required

```bash
PINECONE_API_KEY=your-pinecone-key
OPENAI_API_KEY=your-openai-key
```

### Optional (with defaults)

```bash
PINECONE_INDEX_NAME=bigdata-assignment-04
PINECONE_NAMESPACE=default
FASTAPI_URL=http://fastapi:8000          # Docker only, set in docker-compose.yml
ENVIRONMENT=docker                        # Docker only, set in docker-compose.yml
```

### Local Development (not in Docker)

```bash
ENVIRONMENT=local                          # Optional, defaults to local
FASTAPI_URL=http://localhost:8000         # Optional
```

## Logs and Debugging

### View All Logs

```bash
docker-compose logs
```

### Follow Streamlit Logs in Real-time

```bash
docker-compose logs -f streamlit
```

### Follow FastAPI Logs in Real-time

```bash
docker-compose logs -f fastapi
```

### Check Specific Container

```bash
docker-compose logs streamlit --tail 50
docker-compose logs fastapi --tail 50
```

### Exec into Container for Debugging

```bash
# Streamlit container
docker-compose exec streamlit bash
python -c "import os; print(os.getenv('ENVIRONMENT'))"

# FastAPI container
docker-compose exec fastapi bash
python -c "from pinecone import Pinecone; print('Pinecone OK')"
```

## Stopping and Cleanup

### Stop Services (keep data)

```bash
docker-compose stop
```

### Stop and Remove Containers

```bash
docker-compose down
```

### Full Cleanup (remove volumes too)

```bash
docker-compose down -v
```

### Remove Images

```bash
docker-compose down --rmi all
```

## Rebuilding

### Rebuild All Images

```bash
docker-compose build
```

### Rebuild Specific Service

```bash
docker-compose build streamlit
docker-compose build fastapi
```

### Force Clean Rebuild

```bash
docker-compose build --no-cache
```

## Common Workflows

### First Run

```bash
cd docker

# Build and start all services
docker-compose up -d

# Wait 5 seconds for services to start
sleep 5

# Check health
docker-compose exec fastapi curl http://localhost:8000/health

# Open Streamlit
# http://localhost:8501
```

### Development (with hot reload)

```bash
# Start in foreground to see logs
docker-compose up

# In another terminal, edit files
# Changes auto-reload due to volumes

# Ctrl+C to stop
```

### Running Extraction Pipeline in Docker

```bash
# First ensure raw data exists locally
# Then run ingestion in container
docker-compose exec fastapi python src/rag/ingest_to_pinecone.py --company-slug world_labs

# Then run extraction
docker-compose exec fastapi python src/rag/structured_extraction_search.py --company-slug world_labs

# Then refresh Streamlit dashboard
```

### Checking Docker Network

```bash
# List networks
docker network ls

# Inspect assignment-04 network
docker network inspect assignment-04

# You should see both containers connected with their IPs
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│               Docker Compose (assignment-04)                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐              ┌──────────────────┐    │
│  │   Streamlit      │              │   FastAPI        │    │
│  │   :8501          │              │   :8000          │    │
│  │                  │              │                  │    │
│  │ ENVIRONMENT      │ Docker DNS   │ Endpoints:       │    │
│  │ =docker          ├─ http:// ──→ │ /health          │    │
│  │                  │  fastapi     │ /companies       │    │
│  │ API_BASE         │  :8000       │ /dashboard/*     │    │
│  │ http://fastapi   │              │ /rag/search      │    │
│  │ :8000            │              │                  │    │
│  └──────────────────┘              └──────────────────┘    │
│          ↑                                 ↑               │
│          │ volumes                        │ volumes        │
│          │ ../data                        │ ../data        │
│          │ ../.env                        │ ../.env        │
│          └────────────┬────────────────────┘               │
│                       ↓                                    │
│                  Shared Volumes                            │
│                                                            │
│                     External (Cloud)                       │
│                     ├─ Pinecone (vectors)                  │
│                     └─ OpenAI (LLM)                        │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Update `.env` file:**
   ```bash
   PINECONE_API_KEY=your-key
   OPENAI_API_KEY=your-key
   ```

2. **Start Docker:**
   ```bash
   cd docker
   docker-compose up -d
   ```

3. **Verify connection:**
   ```bash
   curl http://localhost:8000/health
   ```

4. **Open Streamlit:**
   ```
   http://localhost:8501
   ```

5. **Generate dashboard:**
   - Select company
   - Click "Generate (Structured)"
   - Wait for extraction pipeline to complete

That's it! Your Docker setup is now properly configured with Docker service names for inter-container communication.
