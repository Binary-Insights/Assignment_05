"""
Payload Retrieval Tool — Modular payload loading and initial summary.

This module handles:
- Loading structured payloads from data/payloads/{company_id}.json
- Returning a summary (counts, status, metadata)
- Caching for performance

Tools are decorated with @tool for LangGraph agent discovery.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import re
from datetime import date, datetime

from langchain_core.tools import tool
from rag.rag_models import Payload

logger = logging.getLogger(__name__)

# Cache for performance
_payload_cache: Dict[str, Payload] = {}
# Path calculation: retrieval.py -> payload/ -> tools/ -> src/ -> project_root/ -> data/
PAYLOADS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "payloads"


@tool
def get_latest_structured_payload(company_id: str) -> Payload:
    """Load and return the latest structured payload for a company.
    
    Use this tool to retrieve payload data for any company by their company_id.
    Uses lenient normalization to handle legacy JSON with dirty data (strings instead of lists, etc).
    
    Args:
        company_id: Company identifier (e.g., "abridge")
        
    Returns:
        Payload: Validated Pydantic Payload object
        
    Raises:
        FileNotFoundError: If payload JSON not found
        ValueError: If payload fails validation
    """
    # Return cached if available
    if company_id in _payload_cache:
        logger.debug(f"Returning cached payload for {company_id}")
        return _payload_cache[company_id]
    
    payload_file = PAYLOADS_DIR / f"{company_id}.json"
    
    if not payload_file.exists():
        raise FileNotFoundError(
            f"Payload not found for company '{company_id}'. "
            f"Expected file: {payload_file}"
        )
    
    try:
        with open(payload_file, "r", encoding="utf-8") as f:
            payload_dict = json.load(f)
        
        # Attempt strict Pydantic validation first
        try:
            payload = Payload.model_validate(payload_dict)
            _payload_cache[company_id] = payload
            logger.info(f"Loaded and cached payload for {company_id}")
            return payload
        except Exception as strict_err:
            # Try to normalize common legacy issues
            logger.warning(f"Strict validation failed for {company_id}, attempting normalization: {strict_err}")
            normalized = _normalize_payload_dict(payload_dict)
            
            try:
                payload = Payload.model_validate(normalized)
                _payload_cache[company_id] = payload
                logger.info(f"Loaded and cached payload after normalization for {company_id}")
                return payload
            except Exception as norm_err:
                # Last resort: construct without validation
                logger.warning(f"Normalized validation failed for {company_id}: {norm_err}. Using model_construct.")
                payload = Payload.model_construct(**normalized)
                _payload_cache[company_id] = payload
                return payload
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in payload file {payload_file}: {e}")
    except Exception as e:
        raise ValueError(f"Payload retrieval failed for {company_id}: {e}")





def clear_payload_cache():
    """Clear the payload cache (useful for testing and refreshes)."""
    global _payload_cache
    _payload_cache.clear()
    logger.debug("Payload cache cleared")


def _ensure_list(val):
    """Convert a value to a list if needed; helpful for legacy payloads."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    # If a dict, wrap it; if a string, try to split on commas
    if isinstance(val, dict):
        return [val]
    if isinstance(val, str):
        # Empty string -> empty list
        if not val.strip():
            return []
        # If comma separated, split
        if ',' in val:
            return [v.strip() for v in val.split(',') if v.strip()]
        return [val]
    # Fallback: put in a list
    return [val]


def _parse_int(val):
    try:
        if val is None:
            return None
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        if isinstance(val, str):
            s = val.strip()
            s = re.sub(r"[^0-9]", "", s)
            if not s:
                return None
            return int(s)
    except Exception:
        return None


def _parse_float(val):
    try:
        if val is None:
            return None
        if isinstance(val, (float, int)):
            return float(val)
        if isinstance(val, str):
            s = val.strip().replace(',', '')
            # Handle shorthand like 50M or $50M
            m = re.match(r"^\$?([0-9,.]+)\s*([MB])?$", s, flags=re.IGNORECASE)
            if m:
                number = float(m.group(1))
                suffix = (m.group(2) or "").upper()
                if suffix == 'M':
                    number *= 1_000_000
                elif suffix == 'B':
                    number *= 1_000_000_000
                return number
            # General numeric extraction
            s = re.sub(r"[^0-9\.\-]", "", s)
            if not s:
                return None
            return float(s)
    except Exception:
        return None


def _parse_date(val):
    try:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, int):
            # Year only
            return date(val, 1, 1)
        if isinstance(val, str):
            s = val.strip()
            # Try isoformat
            try:
                return date.fromisoformat(s)
            except Exception:
                pass
            # Try YYYY
            m = re.match(r"^(\d{4})$", s)
            if m:
                return date(int(m.group(1)), 1, 1)
            # Try other common formats
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(s, fmt).date()
                except Exception:
                    continue
    except Exception:
        return None
    return None


def _normalize_payload_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw payload dict to ease Pydantic validation.

    This function attempts common cleanup:
    - Ensure top-level list fields are lists
    - Parse string numbers for dates and floats
    - Normalize company fields like categories -> list
    - Ensure provenance is list
    """
    normalized = dict(d) if isinstance(d, dict) else {}

    # Ensure lists
    for list_key in ["events", "snapshots", "products", "leadership", "visibility"]:
        normalized[list_key] = _ensure_list(normalized.get(list_key))

    # Company record normalization
    comp = normalized.get("company_record") or {}
    if isinstance(comp, dict):
        # lists inside company_record
        for maybe_list in ["categories", "related_companies"]:
            if maybe_list in comp:
                comp[maybe_list] = _ensure_list(comp[maybe_list])

        # Numeric transforms
        comp["founded_year"] = _parse_int(comp.get("founded_year"))
        comp["total_raised_usd"] = _parse_float(comp.get("total_raised_usd"))
        comp["last_disclosed_valuation_usd"] = _parse_float(comp.get("last_disclosed_valuation_usd"))

        # Dates
        comp["last_round_date"] = _parse_date(comp.get("last_round_date"))
        comp["as_of"] = _parse_date(comp.get("as_of"))

        # provenance
        prov = comp.get("provenance")
        if prov is None:
            comp["provenance"] = []
        else:
            if isinstance(prov, list):
                comp["provenance"] = prov
            elif isinstance(prov, dict):
                comp["provenance"] = [prov]
            elif isinstance(prov, str):
                comp["provenance"] = [{"source_url": prov, "crawled_at": ""}]

        normalized["company_record"] = comp

    return normalized


def retrieve_payload_summary(company_id: str) -> Dict[str, Any]:
    """
    Return a concise summary of the stored payload.

    This is a lightweight helper used by tests and by tooling that wants
    counts and basic status without loading or serializing the entire object.
    """
    payload_file = PAYLOADS_DIR / f"{company_id}.json"
    if not payload_file.exists():
        return {"company_id": company_id, "status": "not_found"}

    # Keep it simple and pythonic for agent use; structured_extraction handles
    # comprehensive validation. Return not_found early and otherwise return
    # counts via reading the raw file for lightweight checks.
    try:
        with open(payload_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        counts = {
            "events": len(data.get("events", [])),
            "products": len(data.get("products", [])),
            "leadership": len(data.get("leadership", [])),
        }
        return {"company_id": company_id, "status": "success", "counts": counts}
    except Exception as e:
        logger.error(f"Failed to load payload summary for {company_id}: {e}")
        return {"company_id": company_id, "status": "error", "error": str(e)}
