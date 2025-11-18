"""
Agentic RAG package initialization.
Exposes main API and entry points.
"""

__version__ = "1.0.0"
__author__ = "Agentic RAG Team"

from .main import (
    enrich_single_company,
    enrich_multiple_companies,
    enrich_all_companies,
    AgenticRAGOrchestrator
)

from .file_io_manager import FileIOManager, get_file_io_manager
from .vector_db_manager import VectorDBManager, get_vector_db_manager
from .tools import get_tool_manager
from .graph import build_enrichment_graph, save_graph_visualization
from .utils import (
    PayloadAnalyzer,
    FieldExtractor,
    ProvenanceManager,
    FileComparator
)
from .config import (
    PAYLOADS_DIR,
    RAW_DATA_DIR,
    LOGS_DIR,
    validate_config
)

__all__ = [
    # Main functions
    "enrich_single_company",
    "enrich_multiple_companies",
    "enrich_all_companies",
    "AgenticRAGOrchestrator",
    
    # Managers
    "FileIOManager",
    "get_file_io_manager",
    "VectorDBManager",
    "get_vector_db_manager",
    "get_tool_manager",
    
    # Utilities
    "PayloadAnalyzer",
    "FieldExtractor",
    "ProvenanceManager",
    "FileComparator",
    
    # Config
    "PAYLOADS_DIR",
    "RAW_DATA_DIR",
    "LOGS_DIR",
    "validate_config"
]
