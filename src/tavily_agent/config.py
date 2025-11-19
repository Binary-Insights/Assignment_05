"""
Configuration module for Agentic RAG system.
Manages API keys, LLM settings, vector database configuration, and file paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, List

# Load environment variables
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ===========================
# API Keys and Credentials
# ===========================
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws")

# ===========================
# LangSmith Configuration
# ===========================
LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_ENABLED", "true").lower() == "true"
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "agentic-rag-enrichment")
LANGSMITH_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "true").lower() == "true"

# ===========================
# LLM Configuration
# ===========================
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")  # Default to gpt-4o if not set
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# ===========================
# Pinecone Configuration
# ===========================
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "agentic-rag-payloads")
PINECONE_NAMESPACE: str = os.getenv("PINECONE_NAMESPACE", "default")
PINECONE_DIMENSION: int = int(os.getenv("PINECONE_DIMENSION", "3072"))
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ===========================
# File Paths
# ===========================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PAYLOADS_DIR = DATA_DIR / "payloads"
RAW_DATA_DIR = DATA_DIR / "raw"
LOGS_DIR = DATA_DIR / "logs"
VECTORS_DIR = DATA_DIR / "vectors"

# Create directories if they don't exist
for directory in [PAYLOADS_DIR, RAW_DATA_DIR, LOGS_DIR, VECTORS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ===========================
# Agent Configuration
# ===========================
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "5"))  # Increased to allow entity extraction (5 company fields + 5 entities + buffer)
TOOL_TIMEOUT: int = int(os.getenv("TOOL_TIMEOUT", "30"))
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "3"))  # For concurrent processing

# ===========================
# Human-in-the-Loop Configuration
# ===========================

# HITL settings file path
HITL_SETTINGS_FILE = DATA_DIR / "hitl_settings.json"

def load_hitl_settings() -> dict:
    """
    Load HITL settings from persistent JSON file.
    Falls back to environment variables if file doesn't exist.
    
    Returns:
        Dictionary with HITL configuration
    """
    if HITL_SETTINGS_FILE.exists():
        try:
            import json
            with open(HITL_SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                print(f"✅ [CONFIG] Loaded HITL settings from {HITL_SETTINGS_FILE}")
                return settings
        except Exception as e:
            print(f"⚠️  [CONFIG] Error loading HITL settings: {e}. Using defaults.")
    
    # Fallback to environment variables
    return {
        "enabled": os.getenv("HITL_ENABLED", "false").lower() == "true",
        "high_risk_fields": os.getenv("HITL_HIGH_RISK_FIELDS", "true").lower() == "true",
        "low_confidence": os.getenv("HITL_LOW_CONFIDENCE", "true").lower() == "true",
        "conflicting_info": os.getenv("HITL_CONFLICTING_INFO", "false").lower() == "true",
        "entity_batch": os.getenv("HITL_ENTITY_BATCH", "false").lower() == "true",
        "pre_save": os.getenv("HITL_PRE_SAVE", "false").lower() == "true",
        "confidence_threshold": float(os.getenv("HITL_CONFIDENCE_THRESHOLD", "0.7"))
    }

# Load settings from file or environment
_hitl_settings = load_hitl_settings()

HITL_ENABLED: bool = _hitl_settings["enabled"]
HITL_HIGH_RISK_FIELDS: bool = _hitl_settings["high_risk_fields"]
HITL_LOW_CONFIDENCE: bool = _hitl_settings["low_confidence"]
HITL_CONFLICTING_INFO: bool = _hitl_settings["conflicting_info"]
HITL_ENTITY_BATCH: bool = _hitl_settings["entity_batch"]
HITL_PRE_SAVE: bool = _hitl_settings["pre_save"]
HITL_CONFIDENCE_THRESHOLD: float = _hitl_settings["confidence_threshold"]

# High-risk fields that require approval
HIGH_RISK_FIELDS: List[str] = [
    "total_raised_usd"
]

# ===========================
# Deduplication Settings
# ===========================
DEDUP_HASH_ALGORITHM: str = os.getenv("DEDUP_HASH_ALGORITHM", "md5")
DEDUP_CHECK_ENABLED: bool = os.getenv("DEDUP_CHECK_ENABLED", "true").lower() == "true"

# ===========================
# Logging Configuration
# ===========================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = os.getenv(
    "LOG_FORMAT",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ===========================
# Validation
# ===========================
def validate_config() -> bool:
    """Validate critical configuration values."""
    missing_keys = []
    
    if not OPENAI_API_KEY:
        missing_keys.append("OPENAI_API_KEY")
    if not TAVILY_API_KEY:
        missing_keys.append("TAVILY_API_KEY")
    if not PINECONE_API_KEY:
        missing_keys.append("PINECONE_API_KEY")
    
    if LANGSMITH_ENABLED and not LANGSMITH_API_KEY:
        print("⚠️  LangSmith enabled but LANGSMITH_API_KEY not set. Disabling LangSmith.")
    
    if missing_keys:
        print(f"⚠️  Missing API keys: {', '.join(missing_keys)}")
        return False
    
    return True


def setup_langsmith():
    """Configure LangSmith for tracing and monitoring."""
    import os
    
    print(f"\n🔍 [LANGSMITH DEBUG] Configuration Status:")
    print(f"   LANGSMITH_ENABLED: {LANGSMITH_ENABLED}")
    print(f"   LANGSMITH_API_KEY set: {'Yes' if LANGSMITH_API_KEY else 'No'}")
    
    if LANGSMITH_ENABLED and LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY  # Correct env var name
        os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
        
        print(f"   ✅ LangSmith ENV VARS SET:\")\n   LANGCHAIN_TRACING_V2: {os.environ.get('LANGCHAIN_TRACING_V2')}")
        print(f"   LANGSMITH_API_KEY: {os.environ.get('LANGSMITH_API_KEY')[:20]}...")
        print(f"   LANGCHAIN_PROJECT: {os.environ.get('LANGCHAIN_PROJECT')}")
        return True
    else:
        print(f"   ❌ LangSmith disabled or missing API key")
    return False
