"""Payload Validation and Update Tool.

TWO @tool functions for LangGraph agent:
1. validate_payload: Check structure and identify null fields
2. update_payload: Fill nulls from Pinecone + save as {company_id}.json (with versioned backup)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.tools import tool
from rag.rag_models import Payload

logger = logging.getLogger(__name__)
PAYLOADS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "payloads"


@tool
def validate_payload(company_id: str) -> Dict[str, Any]:
    """Validate payload structure and identify null fields."""
    try:
        from payload_agent.tools import get_latest_structured_payload
        payload = get_latest_structured_payload.invoke({"company_id": company_id})
        
        issues = []
        if not payload.company_record:
            issues.append("Missing company_record")
        else:
            if not payload.company_record.legal_name:
                issues.append("Missing legal_name")
            if not payload.company_record.company_id:
                issues.append("Missing company_id")
        
        null_fields = _identify_all_null_fields(payload)
        total_nulls = sum(len(fields) for fields in null_fields.values())
        
        logger.info(f"Validation: {company_id} issues={len(issues)} nulls={total_nulls}")
        
        return {
            "status": "valid" if not issues else "invalid",
            "issues": issues,
            "null_fields": null_fields,
            "total_nulls": total_nulls,
            "company_id": company_id,
        }
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {"status": "error", "issues": [str(e)], "company_id": company_id}


@tool
def update_payload(company_id: str, rag_search_tool: Optional[Any] = None, llm: Optional[Any] = None) -> Dict[str, Any]:
    """Fill null fields from Pinecone and save as {company_id}.json (creates versioned backup first)."""
    try:
        from payload_agent.tools import get_latest_structured_payload
        payload = get_latest_structured_payload.invoke({"company_id": company_id})
        
        if not rag_search_tool or not llm:
            return {"status": "error", "error": "Missing RAG/LLM", "company_id": company_id}
        
        null_fields = _identify_all_null_fields(payload)
        total_nulls = sum(len(fields) for fields in null_fields.values())
        
        if total_nulls == 0:
            return {"status": "success", "message": "No nulls", "company_id": company_id}
        
        filled_fields = {}
        filled_count = 0
        company_name = payload.company_record.legal_name if payload.company_record else None
        
        for section, fields in null_fields.items():
            filled_fields[section] = []
            for field_name in fields:
                snippets = _search_pinecone(company_id, field_name, section, rag_search_tool, company_name)
                if snippets:
                    value = _extract_with_llm(field_name, snippets, llm)
                    if value and _update_field(payload, section, field_name, value):
                        filled_fields[section].append(field_name)
                        filled_count += 1
        
        output_file = _save_payload(payload, company_id)
        return {
            "status": "success",
            "filled_count": filled_count,
            "output_file": str(output_file),
            "company_id": company_id,
        }
    except Exception as e:
        logger.error(f"Update error: {e}")
        return {"status": "error", "error": str(e), "company_id": company_id}


def _identify_all_null_fields(payload: Payload) -> Dict[str, list]:
    """Dynamically find all null fields."""
    null_fields = {}
    if payload.company_record:
        nulls = []
        cr = payload.company_record
        fields = cr.model_fields.keys() if hasattr(cr, 'model_fields') else [k for k in dir(cr) if not k.startswith('_')]
        for f in fields:
            try:
                v = getattr(cr, f, None)
                if v is None or (isinstance(v, str) and not v.strip()):
                    nulls.append(f)
            except:
                pass
        if nulls:
            null_fields["company_record"] = nulls
    return null_fields


def _search_pinecone(company_id, field_name, section, rag_tool, company_name):
    """Search Pinecone for field context."""
    queries = _build_queries(field_name, company_name)
    slug = company_id.lower().replace(" ", "_")
    for q in queries:
        try:
            results = rag_tool(slug, q, 50)
            if results:
                return results
        except:
            pass
    return []


def _build_queries(field_name, company_name):
    """Build semantic queries for field."""
    fl = field_name.lower()
    if "city" in fl:
        base = "What city is the headquarters in?"
    elif "country" in fl:
        base = "What country is the company based in?"
    elif "founded" in fl:
        base = "When was the company founded?"
    elif "github" in fl:
        base = "What is the GitHub URL?"
    elif "website" in fl:
        base = "What is the company website?"
    else:
        base = f"Information about {field_name.replace('_', ' ')}"
    
    queries = [base]
    if company_name:
        queries.append(f"{company_name} {base}")
    return queries


def _extract_with_llm(field_name, snippets, llm):
    """Extract field value using LLM."""
    text = "\n\n".join([s.get("snippet", s.get("text", ""))[:500] for s in snippets[:10]])
    prompt = f"""Extract the value for "{field_name.replace('_', ' ').title()}" from this text.
Return ONLY the value, or "null" if not found.

Text:
{text}

Value:"""
    try:
        response = llm.invoke(prompt)
        value = getattr(response, "content", "").strip()
        if value.lower() in ["null", "none", "n/a", ""]:
            return None
        return value
    except:
        return None


def _update_field(payload, section, field_name, value):
    """Update payload field."""
    try:
        if section == "company_record":
            setattr(payload.company_record, field_name, value)
            return True
        return False
    except:
        return False


def _backup_payload(company_id):
    """
    Create a versioned backup of the current payload.
    Saves current version as {company_id}_v1.json, {company_id}_v2.json, etc.
    
    Args:
        company_id: Company identifier
        
    Returns:
        Path to backup file or None if backup not needed/failed
    """
    original_path = PAYLOADS_DIR / f"{company_id}.json"
    
    if not original_path.exists():
        logger.debug(f"No existing payload to backup for {company_id}")
        return None
    
    try:
        # Find next version number
        version = 1
        while (PAYLOADS_DIR / f"{company_id}_v{version}.json").exists():
            version += 1
        
        backup_path = PAYLOADS_DIR / f"{company_id}_v{version}.json"
        
        # Read the original file and write to backup
        logger.info(f"Creating backup v{version} from: {original_path}")
        with open(original_path, 'r', encoding='utf-8') as src:
            content = src.read()
        
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(content)
        
        # Verify backup was created
        if backup_path.exists():
            logger.info(f"✓ Created backup: {backup_path}")
            return backup_path
        else:
            logger.error(f"Backup file was not created: {backup_path}")
            return None
            
    except PermissionError as e:
        logger.warning(f"⚠ Backup skipped (permission denied): {e}")
        logger.warning(f"  Continuing without backup (non-critical)")
        return None
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None


def _save_payload(payload, company_id):
    """
    Save updated payload as {company_id}.json (overwrites existing).
    Creates versioned backup before overwriting.
    
    Args:
        payload: Payload object to save
        company_id: Company identifier
        
    Returns:
        Path to saved file
    """
    # Create backup of existing file if it exists
    backup_path = _backup_payload(company_id)
    if backup_path:
        logger.info(f"Backed up existing payload before updating")
    
    # Save updated payload as main file
    output = PAYLOADS_DIR / f"{company_id}.json"
    PAYLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    data = payload.model_dump() if hasattr(payload, 'model_dump') else payload.__dict__
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    logger.info(f"✓ Saved updated payload to: {output}")
    return output
