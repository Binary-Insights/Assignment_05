"""
Payload Tools Package — Consolidated payload retrieval, validation, persistence, and vector fill utilities.

This package provides:
- retrieval: Load and cache structured payloads
- validation: Validate payload structure and coordinate updates
- persistence: Write updated payloads and extraction metadata
- vectors: Vector search and field extraction utilities
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

from .persistence import (
    write_updated_payload,
    write_extraction_metadata,
    persist_payload_and_metadata,
)

from .vectors import (
    search_vectors_for_field,
    extract_value_from_snippet,
    aggregate_candidates,
    create_provenance_record,
    fill_all_nulls,
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
    # Persistence
    "write_updated_payload",
    "write_extraction_metadata",
    "persist_payload_and_metadata",
    # Vectors
    "search_vectors_for_field",
    "extract_value_from_snippet",
    "extract_field_llm_assisted",
    "aggregate_candidates",
    "create_provenance_record",
    "fill_all_nulls",
    # RAG Adapter
    "RagSearchAdapter",
    "create_pinecone_adapter",
]
