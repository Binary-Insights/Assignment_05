"""
Payload Tools Package — Consolidated payload retrieval and validation utilities.

This package provides:
- retrieval: Load and cache structured payloads
- validation: Validate payload structure and fill null fields from vectors
- rag_adapter: RAG search interface protocol
"""

from .retrieval import (
    get_latest_structured_payload,
    clear_payload_cache,
    retrieve_payload_summary,
)

from .validation import (
    validate_payload,
    update_payload,
)

from .rag_adapter import (
    RagSearchAdapter,
    create_pinecone_adapter,
)

__all__ = [
    # Retrieval
    "get_latest_structured_payload",
    "clear_payload_cache",
    "retrieve_payload_summary",
    # Validation
    "validate_payload",
    "update_payload",
    # RAG Adapter
    "RagSearchAdapter",
    "create_pinecone_adapter",
]
