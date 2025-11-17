"""
Payload Persistence — Write updated payloads and extraction metadata to disk.

This module provides:
- write_updated_payload: Save modified Payload to data/metadata/{company}
- write_extraction_metadata: Save extraction runs, provenance, confidence to JSON
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from rag.rag_models import Payload

logger = logging.getLogger(__name__)


def _clear_payload_cache_for_company(company_id: str):
    """Clear cached payload for a specific company after writes."""
    try:
        # Import here to avoid circular dependency
        from .retrieval import _payload_cache
        if company_id in _payload_cache:
            del _payload_cache[company_id]
            logger.debug(f"Cleared cache for {company_id}")
    except Exception as e:
        logger.debug(f"Could not clear cache: {e}")

def write_updated_payload(
    payload: Payload,
    company_id: Optional[str] = None,
    base_dir: Optional[Path] = None,
    overwrite_original: bool = True,
) -> Path:
    """
    Write updated payload to disk.
    
    Args:
        payload: Updated Pydantic Payload object
        company_id: Company identifier (optional; extracted from payload if not provided)
        base_dir: Override base directory (default: data/payloads/ for overwrite, data/metadata/ otherwise)
        overwrite_original: If True, overwrites original payload in data/payloads/; if False, writes to metadata folder
        
    Returns:
        Path to written file
        
    Raises:
        ValueError: If company_id cannot be determined
    """
    if not company_id:
        if not payload.company_record or not payload.company_record.company_id:
            raise ValueError("Cannot determine company_id for persistence")
        company_id = payload.company_record.company_id
    
    if not base_dir:
        # Path: persistence.py -> payload/ -> tools/ -> src/ -> project_root/ -> data/
        project_root = Path(__file__).parent.parent.parent.parent
        if overwrite_original:
            base_dir = project_root / "data" / "payloads"
            payload_path = base_dir / f"{company_id}.json"
        else:
            base_dir = project_root / "data" / "metadata" / company_id
            base_dir.mkdir(parents=True, exist_ok=True)
            payload_path = base_dir / f"{company_id}.updated.json"
    else:
        payload_path = base_dir / f"{company_id}.json"
    
    try:
        with open(payload_path, "w", encoding="utf-8") as f:
            f.write(payload.model_dump_json(indent=2))
        
        # Clear cache so next read gets fresh data
        _clear_payload_cache_for_company(company_id)
        
        logger.info(f"Persisted updated payload for {company_id} to {payload_path}")
        return payload_path
        
    except Exception as e:
        logger.error(f"Failed to write updated payload for {company_id}: {e}")
        raise


def write_extraction_metadata(
    metadata: Dict[str, Any],
    company_id: str,
    base_dir: Optional[Path] = None,
) -> Path:
    """
    Write extraction metadata (filled fields, provenance, confidence, runs) to JSON.
    
    Handles both old and new metadata formats:
    - Old format: filled_fields/unfilled_nulls as lists
    - New format (fill_all_nulls): filled_fields/unfilled_nulls as dicts with section names
    
    Args:
        metadata: Metadata dict from update_payload or fill_all_nulls
        company_id: Company identifier
        base_dir: Override base directory (default: data/metadata/{company_id})
        
    Returns:
        Path to written metadata file
    """
    if not base_dir:
        # Path: persistence.py -> payload/ -> tools/ -> src/ -> project_root/ -> data/
        base_dir = Path(__file__).parent.parent.parent.parent / "data" / "metadata" / company_id
    
    base_dir.mkdir(parents=True, exist_ok=True)
    
    meta_path = base_dir / "extraction_search_metadata.json"
    
    # Support both old and new metadata formats
    filled_fields = metadata.get("filled_fields", [])
    if isinstance(filled_fields, dict):
        # New format: flatten dict to list or keep as dict
        filled_fields = filled_fields
    
    ambiguous_fields = metadata.get("ambiguous_fields", [])
    if isinstance(ambiguous_fields, dict):
        ambiguous_fields = ambiguous_fields
    
    unfilled_nulls = metadata.get("unfilled_nulls", [])
    if isinstance(unfilled_nulls, dict):
        unfilled_nulls = unfilled_nulls
    
    meta_doc = {
        "company_id": company_id,
        "generated_at": datetime.utcnow().isoformat(),
        "filled_fields": filled_fields,
        "ambiguous_fields": ambiguous_fields,
        "unfilled_nulls": unfilled_nulls,
        "field_confidence_map": metadata.get("field_confidence_map", {}),
        "extraction_runs": metadata.get("extraction_runs", []),
        "provenance": metadata.get("provenance", {}),  # New format uses 'provenance' not 'provenance_updates'
        "provenance_updates": metadata.get("provenance_updates", {}),  # Keep for backward compat
        "total_filled": metadata.get("total_filled", 0),
        "total_attempted": metadata.get("total_attempted", 0),
    }
    
    try:
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta_doc, mf, indent=2)
        
        logger.info(f"Persisted extraction metadata for {company_id} to {meta_path}")
        return meta_path
        
    except Exception as e:
        logger.error(f"Failed to write extraction metadata for {company_id}: {e}")
        raise


def persist_payload_and_metadata(
    payload: Payload,
    metadata: Dict[str, Any],
    company_id: Optional[str] = None,
    base_dir: Optional[Path] = None,
    overwrite_original: bool = True,
) -> Dict[str, Path]:
    """
    Convenience function to persist both payload and metadata in one call.
    
    Args:
        payload: Updated Pydantic Payload object
        metadata: Metadata dict from update_payload
        company_id: Company identifier (optional; extracted from payload if not provided)
        base_dir: Override base directory
        overwrite_original: If True, overwrites original payload in data/payloads/; metadata always goes to data/metadata/
        
    Returns:
        Dict with keys 'payload_path' and 'metadata_path'
    """
    if not company_id:
        if not payload.company_record or not payload.company_record.company_id:
            raise ValueError("Cannot determine company_id for persistence")
        company_id = payload.company_record.company_id
    
    payload_path = write_updated_payload(payload, company_id, base_dir, overwrite_original)
    
    # Metadata always goes to metadata folder (for diagnostics/audit trail)
    metadata_base = Path(__file__).parent.parent.parent.parent / "data" / "metadata" / company_id
    metadata_path = write_extraction_metadata(metadata, company_id, metadata_base)
    
    return {
        "payload_path": payload_path,
        "metadata_path": metadata_path,
    }
