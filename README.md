# 🚀 Project ORBIT (Part 2): Agentification and Secure Scaling of PE Intelligence
**DAMG 7245 – Fall 2025 – Assignment 5 – Binary Insights**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Airflow](https://img.shields.io/badge/Airflow-2.10.4-orange.svg)](https://airflow.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![LangChain](https://img.shields.io/badge/LangChain-1.0+-green.svg)](https://langchain.com)
[![MCP](https://img.shields.io/badge/MCP-Server-purple.svg)](https://modelcontextprotocol.io)

## 📋 Overview

**Project ORBIT Part 2** evolves the static PE intelligence platform from Assignment 4 into an **agentic, production-ready system** that orchestrates due-diligence workflows through supervisory LLM agents using the **Model Context Protocol (MCP)**.

The system features:
- 🤖 **Supervisory Agent Architecture** with specialized sub-agents (Planner, Evaluator, Risk Detector)
- 🔧 **Model Context Protocol (MCP)** server exposing Tools, Prompts, and Resources
- 🧠 **ReAct Pattern** implementation with structured Thought → Action → Observation logging
- 🔀 **LangGraph Workflow** with conditional branching and Human-in-the-Loop (HITL) approval
- 📊 **Dual Dashboard Generation** using RAG and Structured Extraction pipelines
- 🐳 **Full Docker Deployment** with Airflow orchestration
- ✅ **Comprehensive Testing** with pytest coverage

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph "Airflow Orchestration Layer"
        DAG1[Initial Load DAG<br/>Data Discovery & Setup]
        DAG2[Daily Update DAG<br/>Incremental Updates]
        DAG3[Agentic Dashboard DAG<br/>Agent Workflow Execution]
        DAG4[Master Orchestrator<br/>Pipeline Coordination]
    end
    
    subgraph "MCP Server Layer"
        MCP[MCP Server :9000<br/>Tools | Prompts | Resources]
        TOOL1[generate_structured_dashboard]
        TOOL2[generate_rag_dashboard]
        RES1[/resource/ai50/companies]
        PROMPT1[/prompt/pe-dashboard]
    end
    
    subgraph "Agent Layer"
        SUPER[Supervisor Agent<br/>ReAct Orchestration]
        PLANNER[Planner Agent<br/>Task Planning]
        EVAL[Evaluation Agent<br/>Quality Scoring]
        RISK[Risk Detector<br/>Signal Analysis]
    end
    
    subgraph "Workflow Layer"
        GRAPH[LangGraph Workflow]
        NODE1[Plan Generation]
        NODE2[Data Collection]
        NODE3[Dashboard Generation]
        NODE4[Quality Evaluation]
        NODE5{Risk Detection}
        HITL[Human Approval<br/>HITL Pause]
        AUTO[Auto-Approve]
    end
    
    subgraph "Data Layer"
        PINECONE[(Pinecone<br/>Vector DB)]
        S3[(AWS S3<br/>Cloud Storage)]
        PAYLOADS[(Local JSON<br/>Payloads)]
        LOGS[(Structured Logs<br/>ReAct Traces)]
    end
    
    subgraph "Interface Layer"
        FASTAPI[FastAPI :8000<br/>REST API]
        STREAMLIT[Streamlit :8501<br/>Dashboard UI]
    end
    
    DAG3 -->|HTTP/CLI| MCP
    DAG4 --> DAG1 & DAG2 & DAG3
    MCP --> TOOL1 & TOOL2 & RES1 & PROMPT1
    MCP --> SUPER
    SUPER --> PLANNER & EVAL & RISK
    SUPER --> GRAPH
    GRAPH --> NODE1 --> NODE2 --> NODE3 --> NODE4 --> NODE5
    NODE5 -->|Risk Found| HITL --> PAYLOADS
    NODE5 -->|No Risk| AUTO --> PAYLOADS
    TOOL1 & TOOL2 --> PINECONE & PAYLOADS
    PAYLOADS --> S3
    SUPER --> LOGS
    FASTAPI --> PINECONE & PAYLOADS
    STREAMLIT --> FASTAPI
    
    classDef airflowStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef mcpStyle fill:#bbf,stroke:#333,stroke-width:2px
    classDef agentStyle fill:#bfb,stroke:#333,stroke-width:2px
    classDef workflowStyle fill:#ffb,stroke:#333,stroke-width:2px
    classDef dataStyle fill:#fbb,stroke:#333,stroke-width:2px
    
    class DAG1,DAG2,DAG3,DAG4 airflowStyle
    class MCP,TOOL1,TOOL2,RES1,PROMPT1 mcpStyle
    class SUPER,PLANNER,EVAL,RISK agentStyle
    class GRAPH,NODE1,NODE2,NODE3,NODE4,NODE5,HITL,AUTO workflowStyle
    class PINECONE,S3,PAYLOADS,LOGS dataStyle
```

---

## 📦 Setup Instructions

### 1️⃣ Prerequisites

- Python 3.11+
- Docker 20.10+
- Docker Compose 2.0+
- Git (latest)
- OpenAI API key (required)
- Pinecone API key (required)
- Airflow 2.10+
- AWS credentials (S3,EC2)

---

### 2️⃣ Clone the Repository

```bash
git clone https://github.com/Binary-Insights/Assignment_05.git
cd Assignment_05
```

---

### 3️⃣ Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example configuration
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# ===== REQUIRED: OpenAI Configuration =====
OPENAI_API_KEY=sk-proj-...your-key-here...

# ===== REQUIRED: Pinecone Configuration =====
PINECONE_API_KEY=pcsk_...your-key-here...
PINECONE_INDEX_NAME=bigdata-assignment-05
PINECONE_NAMESPACE=default
PINECONE_EMBEDDING_DIMENSION=3072
PINECONE_EMBEDDING_MODEL=text-embedding-3-large

# ===== OPTIONAL: AWS S3 Configuration =====
AWS_ACCESS_KEY_ID=AKIA...your-key...
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=pe-dashboard-ai50

# ===== OPTIONAL: LangSmith Tracing =====
LANGSMITH_API_KEY=lsv2_pt_...your-key...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=orbit-assignment-05

# ===== Airflow Configuration =====
AIRFLOW_UID=50000
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true

# ===== Application Configuration =====
LOG_LEVEL=INFO
PROJECT_NAME=Assignment_05
```

---

### 4️⃣ Local Development Setup (Optional)

For local development without Docker:

```bash
# Create virtual environment
python -m venv .venv
# with uv in Linusx
uv venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
uv sync 

pip install -r requirements.txt
```

---

### 5️⃣ Start Services with Docker

```bash
# Build and start all services
cd docker
docker-compose build --no-cache
docker-compose up -d

# Wait 30-60 seconds for initialization
```

---

### 6️⃣ Access Web Interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow UI** | http://98.95.70.0:8080 | `airflow` / `airflow` |
| **MCP Server** | http://98.95.70.0:9000 | N/A (API) |
| **FastAPI Docs** | http://98.95.70.0:8000/docs | N/A |
| **Streamlit Dashboard** | http://98.95.70.0:8501 | N/A 


## 📂 Project Structure

```
Assignment_05/
├── 📁 src/                         
│   ├── 📁 mcp_server/                   
│   │   └── mcp_enrichment_client.py          
│   ├── 📁 dags/
│   │   ├── discover_dag.py                     
│   │   ├── process_pages_dag.py     
│   │   ├── ingest_dag.py            
│   │   ├── extraction_dag.py
│   │   ├── storing_dag.py
│   │   ├── dashboard_generation.py 
│   │   ├── eval_runner_dag.py
│   │   ├── master_orchestrator_dag.py        
│   │   ├── agentic_rag_dag.py      
│   │   ├── payload_agent_dag.py     
│   │   └── enrichment_dag.py
│   ├── 📁 rag/                      
│   │   ├── ingest_to_pinecone.py    
│   │   ├── rag_pipeline.py          
│   │   └── structured_extraction_search.py
│   │   └── rag_models.py                
│   ├── 📁 payload_agent/           
│   │   ├── payload_agent.py         
│   │   ├── payload_workflow.py
│   │   ├── tools/rag_adapter.py 
│   │   ├── tools/validation.py
│   │   └── tools/retrieval.py     
│   ├── 📁 tavily_agent/            
│   │   ├── main.py                  
│   │   └── file_io_manager.py       
│   ├── 📁 discover/                 
│   │   ├── discover.py         
│   │   └── process_discovered_pages.py       
│   ├── 📁 backend/                  
│   │   └── rag_search_api.py                   
│   ├── 📁 frontend/ 
│   │   ├── eval_dashboard.py                
│   │   └── streamlit_app.py         
│   ├── 📁 evals/                    
│   │   └── results_evaluator.py             
│   └── 📁 prompts/                 
│       ├── pe_dashboard.md           
├── 📁 docker/                      
│   ├── Dockerfile                   
│   ├── docker-compose.yml           
│   ├── .env.example                                
├── 📁 docs/                      
│   ├── 00_START_HERE.md           
│   ├── QUICKSTART.md                
│   ├── EVALUATION_GUIDE.md         
│   ├── REACT_QUICK_REFERENCE.md     
│   └── WORKFLOW_GRAPH.md           
├── 📁 tests/                       
│   ├── test_payload_tools.py       
│   └── test_payload_workflow.py     
├── .env.example                  
├── pyproject.toml                  
├── requirements.txt               
├── Assignment5.md                 
├── README.md                       


```

---

## Links

📚 [Full Technical Codelabs](https://codelabs-preview.appspot.com/?file_id=1hCRRMtxdtcyp1OVLlNYxGbYM1qvOBnoxT4442yt5ZXY#0) — Detailed walkthrough  
📋 [Assignment Requirements](./Assignment5.md) — Lab breakdown  
🎥 [Demo Video]() — Project walkthrough

---