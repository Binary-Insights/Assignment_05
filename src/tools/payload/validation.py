"""
Payload Validation and Update Tool — Validate structure and fill nulls from vectors.

This module provides:
- validate_payload: Check structure and required fields (no modifications)
- update_payload: Validate + attempt to fill null fields from Pinecone vectors

Tools are decorated with @tool for LangGraph agent discovery.
"""

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool
from rag.rag_models import Payload
from .vectors import (
    search_vectors_for_field,
    extract_value_from_snippet,
    aggregate_candidates,
    fill_all_nulls,
)
from .persistence import persist_payload_and_metadata

logger = logging.getLogger(__name__)

def _validate_payload_internal(payload: Payload) -> Dict[str, Any]:
    """Internal helper function to validate payload (not decorated with @tool)."""
    issues = []
    
    try:
        # Check required top-level sections exist
        if not payload.company_record:
            issues.append("Missing company_record section")
        else:
            if not payload.company_record.legal_name:
                issues.append("company_record missing legal_name")
            if not payload.company_record.company_id:
                issues.append("company_record missing company_id")
        
        if "events" not in dir(payload) or payload.events is None:
            issues.append("Missing events array")
        
        if "leadership" not in dir(payload) or payload.leadership is None:
            issues.append("Missing leadership array")
        
        if "products" not in dir(payload) or payload.products is None:
            issues.append("Missing products array")
        
        logger.info(f"Validation complete. Issues: {len(issues)}")
        
        return {
            "status": "valid" if not issues else "invalid",
            "issues": issues,
            "total_issues": len(issues),
        }
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {
            "status": "error",
            "issues": [str(e)],
            "total_issues": 1,
        }


def validate_payload(payload: Payload) -> Dict[str, Any]:
    """Validate a payload structure and check for required fields.
    
    Use this tool to check if a company payload has all required sections and fields.
    
    Args:
        payload: Pydantic Payload object
        
    Returns:
        Dict with:
            - status: "valid" | "invalid" | "error"
            - issues: list of issue strings
            - total_issues: int
    """
    return _validate_payload_internal(payload)


def update_payload(
    payload: Payload,
    rag_search_tool: Optional[Any] = None,
    attempt_vector_fills: bool = True,
    llm: Optional[Any] = None,
    write_back: bool = False,
    metadata_dir: Optional[Path] = None,
    persist_company_id: Optional[str] = None,
) -> Tuple[Payload, Dict[str, Any]]:
    """Update a payload by filling null fields from Pinecone vector search.
    
    Use this tool to enrich a company payload with missing data from vector database.
    
    Uses the new fill_all_nulls function which provides:
    - Dynamic vector search for ANY null field
    - LLM-driven extraction (no hardcoded patterns)
    - Safe fallback (if vectors don't have data, field stays null)
    
    Args:
        payload: Pydantic Payload object
        rag_search_tool: Callable (company_id, query, top_k) -> List[chunks] for vector search
        attempt_vector_fills: Whether to attempt fills (if False, just validate)
        llm: Optional LLM for extraction (ChatOpenAI compatible)
        write_back: Whether to persist updates to disk
        metadata_dir: Directory for metadata output
        
    Returns:
        Tuple of (updated_payload, metadata_dict) where metadata includes:
            - original_issues: issues found before filling
            - filled_fields: dict with section -> [field names]
            - ambiguous_fields: dict with section -> [field names]
            - unfilled_nulls: dict with section -> [field names]
            - total_filled, total_attempted: counts
            - provenance: dict with section -> field -> provenance records
    """
    
    # First, validate structure using internal helper
    validation_result = _validate_payload_internal(payload)
    
    metadata = {
        "original_issues": validation_result["issues"],
        "filled_fields": {},
        "ambiguous_fields": {},
        "unfilled_nulls": {},
        "provenance": {},
        "total_filled": 0,
        "total_attempted": 0,
    }
    
    # If validation failed badly, don't attempt fills
    if validation_result["status"] == "error":
        logger.warning(f"Payload has validation issues; skipping vector fills")
        return payload, metadata
    
    # If vector fills not enabled or no search tool, return as-is
    if not attempt_vector_fills or not rag_search_tool:
        logger.info("Vector fills disabled or no search tool provided")
        # Provide old-style metadata fields for backward compatibility with tests
        # "unfilled_nulls" previously returned as list - produce one here
        # We can flatten the null fields of the payload's company_record
        # to mimic the earlier behavior
        try:
            null_fields = _identify_null_fields(payload)
        except Exception:
            null_fields = []

        metadata["unfilled_nulls"] = null_fields
        metadata["extraction_runs"] = []
        metadata["field_confidence_map"] = {}
        return payload, metadata
    
    # Use new fill_all_nulls function for dynamic extraction
    logger.info("Starting dynamic vector-based null field filling...")
    try:
        # Wrap LLM if needed to match expected signature
        llm_extractor = None
        if llm is not None:
            llm_extractor = lambda f, s: _run_llm_extractor(llm, f, s)
        
        company_id = payload.company_record.company_id if payload.company_record else None
        if not company_id:
            logger.warning("Cannot fill - no company_id in payload")
            return payload, metadata
        
        payload, fill_metadata = fill_all_nulls(
            payload=payload,
            company_id=company_id,
            rag_search_tool=rag_search_tool,
            llm_extractor=llm_extractor,
            top_k=50,
            company_name=(payload.company_record.legal_name if payload.company_record and payload.company_record.legal_name else None),
        )
        
        # Merge fill_metadata into our metadata dict
        metadata.update(fill_metadata)
        # Backwards compatible keys for older tests and consumers
        # New format uses dicts keyed by section; provide flattened lists for legacy callers
        if isinstance(metadata.get("unfilled_nulls"), dict):
            flat_unfilled = []
            for val in metadata.get("unfilled_nulls", {}).values():
                if isinstance(val, list):
                    flat_unfilled.extend(val)
            metadata["unfilled_nulls"] = flat_unfilled

        # Provide extraction_runs and field_confidence_map defaults for compatibility
        metadata.setdefault("extraction_runs", [])
        metadata.setdefault("field_confidence_map", {})
        
        logger.info(
            f"Vector fills complete: "
            f"{fill_metadata.get('total_filled', 0)}/{fill_metadata.get('total_attempted', 0)} filled"
        )
        
    except Exception as e:
        logger.error(f"fill_all_nulls failed: {e}")
        # Don't propagate - just note the issue and return unchanged payload
        return payload, metadata
    
    # Persist if requested
    if write_back:
        _persist_via_external_module(payload, metadata, metadata_dir,persist_company_id=persist_company_id)
    
    return payload, metadata


def _identify_null_fields(payload: Payload) -> List[str]:
    """
    Dynamically identify ALL null or empty fields in company_record.
    
    This function inspects the company_record Pydantic model and returns
    all fields that have null, empty, or missing values. These are the fields
    that can potentially be filled from Pinecone vectors.
    
    ARCHITECTURE NOTE:
    Currently focused on company_record fields because:
    - company_record contains company metadata (founded_year, hq_city, etc.)
    - These are scalar fields that can be extracted from vectors
    - events, snapshots, products, leadership, visibility are LIST fields
    
    Future enhancement to fill list sections:
    - events: Could pull from timeline data or investor updates
    - snapshots: Could pull from historical records or archives
    - products: Could pull from product descriptions or feature lists
    - leadership: Could pull from team/management sections
    - visibility: Could pull from social media or PR mentions
    
    To extend: Create separate functions for each list section type,
    then call fill_all_nulls() for each section.
    
    Args:
        payload: Pydantic Payload object
        
    Returns:
        List of field names from company_record that are null/empty
    """
    null_fields = []
    
    cr = payload.company_record
    
    # Get all fields from the Pydantic model
    if hasattr(cr, 'model_fields'):
        # Pydantic v2
        all_fields = cr.model_fields.keys()
    else:
        # Fallback: get all public attributes
        all_fields = [k for k in dir(cr) if not k.startswith('_')]
    
    # Check each field for null/empty values
    for field_name in all_fields:
        try:
            value = getattr(cr, field_name, None)
            
            # Skip methods and private attributes
            if callable(value) or field_name.startswith('_'):
                continue
            
            # Check if field is null or empty
            if value is None:
                null_fields.append(field_name)
            elif isinstance(value, str) and value.strip() == "":
                null_fields.append(field_name)
            # Note: empty lists/dicts are expected, don't report as null
                
        except AttributeError:
            continue
    
    logger.info(f"Identified null fields in company_record: {null_fields}")
    return null_fields


def _update_payload_field(payload: Payload, section_name: str, item_idx: Optional[int], field_name: str, value: Any) -> None:
    """
    Update a specific field in the payload.
    
    Args:
        payload: Pydantic Payload object (mutable)
        section_name: Section name (company_record, events, etc.)
        item_idx: Item index (None for company_record, 0+ for list sections)
        field_name: Field to update
        value: New value
        
    Raises:
        ValueError: If field doesn't exist or update fails
    """
    try:
        section = getattr(payload, section_name)
        
        if section_name == "company_record":
            # Scalar section
            setattr(section, field_name, value)
        else:
            # List sections
            if not isinstance(section, list) or item_idx is None or item_idx >= len(section):
                raise ValueError(f"Invalid item index {item_idx} for {section_name}")
            setattr(section[item_idx], field_name, value)
        
        logger.debug(f"Updated {section_name}[{item_idx}].{field_name} = {value}")
        
    except Exception as e:
        logger.error(f"Failed to update {section_name}.{field_name}: {e}")
        raise


def _run_llm_extractor(llm, field_name: str, snippet: str) -> Dict[str, Any]:
    """Run a constrained LLM call to extract a field value from ANY field type.

    Uses semantic understanding of field names to guide extraction.
    Works dynamically for ANY field without hardcoding.
    """
    
    # Convert field name to human-readable format for LLM guidance
    # Examples: hq_city → "headquarters city", github_repo → "GitHub repository"
    readable_field = _humanize_field_name(field_name)
    
    # Build extraction instruction based on field type inference
    extraction_instruction = _build_extraction_instruction(field_name, readable_field)
    
    prompt = f"""You are a precise information extraction assistant.
Field to extract: {readable_field} (technical name: {field_name})
Extraction guideline: {extraction_instruction}

CRITICAL RULES:
1. Extract ONLY the explicit value for this field from the text
2. Do NOT invent or infer values not stated in the text
3. Return valid JSON with EXACT keys: {{"value": <null_or_extracted_value>, "confidence": <"high"|"medium"|"low">, "evidence": "<relevant_quote>"}}
4. If field cannot be found, set value to null and confidence to "low"
5. Confidence levels:
   - "high": value explicitly stated and unambiguous
   - "medium": value clearly implied from context
   - "low": value uncertain or weakly stated

Text to extract from:
{snippet}

Return ONLY the JSON response, nothing else:"""
    
    try:
        resp = llm.invoke(prompt)  # ChatOpenAI compatible
        text = getattr(resp, "content", "") or getattr(resp, "text", "")
        
        # Parse JSON response
        import json as _json
        start = text.find("{")
        end = text.rfind("}")
        
        if start == -1 or end == -1:
            logger.debug(f"No JSON found in LLM response for {field_name}")
            return {"value": None, "confidence": "low", "evidence": None}
        
        obj = _json.loads(text[start:end+1])
        
        # Validate response has required keys
        if "value" not in obj:
            obj["value"] = None
        if "confidence" not in obj:
            obj["confidence"] = "medium"
        if "evidence" not in obj:
            obj["evidence"] = None
        
        # Validate confidence value
        if obj["confidence"] not in ["high", "medium", "low"]:
            obj["confidence"] = "medium"
        
        # Clean up null strings (LLM sometimes returns "null" as string instead of null)
        if obj["value"] == "null" or obj["value"] == "":
            obj["value"] = None
        
        # Clean up string values (strip whitespace)
        if isinstance(obj["value"], str):
            obj["value"] = obj["value"].strip()
            if not obj["value"]:
                obj["value"] = None
        
        logger.debug(f"LLM extraction for {field_name}: value={obj['value']}, confidence={obj['confidence']}")
        return obj
        
    except Exception as e:
        logger.debug(f"LLM extractor error for {field_name}: {e}")
        return {"value": None, "confidence": "low", "evidence": None}


def _humanize_field_name(field_name: str) -> str:
    """
    Convert technical field names to human-readable descriptions.
    
    Examples:
        hq_city → "Headquarters City"
        github_repo → "GitHub Repository"
        total_raised_usd → "Total Funding Raised (USD)"
        founding_year → "Year Founded"
    """
    # Map common field patterns
    patterns = {
        r"^hq_": "Headquarters ",
        r"^gh_": "GitHub ",
        r"_city$": " City",
        r"_country$": " Country",
        r"_state$": " State/Province",
        r"_repo$": " Repository",
        r"_url$": " URL",
        r"_link$": " Link",
        r"_usd$": " (USD)",
        r"_year$": " Year",
        r"^total_": "Total ",
        r"^annual_": "Annual ",
        r"^employee": "Employee ",
        r"_count$": " Count",
    }
    
    readable = field_name
    
    # Apply patterns
    for pattern, replacement in patterns.items():
        import re
        readable = re.sub(pattern, replacement, readable, flags=re.IGNORECASE)
    
    # Replace remaining underscores with spaces
    readable = readable.replace("_", " ")
    
    # Capitalize properly
    readable = " ".join(word.capitalize() for word in readable.split())
    
    return readable


def _build_extraction_instruction(field_name: str, readable_field: str) -> str:
    """
    Build extraction instruction dynamically based on field name semantics.
    
    Infers what kind of value should be extracted based on field naming patterns.
    """
    instructions = []
    
    field_lower = field_name.lower()
    
    # Infer field type from name patterns
    if any(x in field_lower for x in ["city", "country", "state", "location", "region"]):
        instructions.append("Extract geographic location names only (city, country, state names)")
    
    if any(x in field_lower for x in ["url", "link", "repo", "github", "website"]):
        instructions.append("Extract web URLs or identifiers in URL format")
    
    if any(x in field_lower for x in ["year", "date", "founded", "established"]):
        instructions.append("Extract dates or years as numbers (YYYY format preferred)")
    
    if any(x in field_lower for x in ["count", "number", "total", "amount", "raised"]):
        instructions.append("Extract numeric values only")
    
    if any(x in field_lower for x in ["name", "title"]):
        instructions.append("Extract proper names or titles as stated")
    
    if any(x in field_lower for x in ["category", "industry", "sector", "type"]):
        instructions.append("Extract category or classification names")
    
    if any(x in field_lower for x in ["description", "about", "summary", "bio"]):
        instructions.append("Extract a brief, concise description or summary (1-3 sentences)")
    
    # Default instruction if no pattern matched
    if not instructions:
        instructions.append(f"Extract the explicit value for '{readable_field}' exactly as stated in the text")
    
    return "; ".join(instructions)


def _persist_via_external_module(
    payload: Payload,
    metadata: Dict[str, Any],
    metadata_dir: Optional[Path],
    persist_company_id: Optional[str] = None,
) -> None:
    """Persist updated payload and extraction metadata using the dedicated persistence module."""
    try:
        company_id = persist_company_id
        if not company_id:
            company_id = payload.company_record.company_id if payload.company_record else None
        persist_payload_and_metadata(payload, metadata, company_id, metadata_dir)
    except Exception as e:
        logger.warning(f"Failed to persist via external module: {e}")
