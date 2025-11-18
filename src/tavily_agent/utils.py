"""
Utility functions for Agentic RAG system.
Provides helper functions for payload analysis, field extraction, and data processing.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime
from difflib import unified_diff
import sys
from pathlib import Path

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import PAYLOADS_DIR

logger = logging.getLogger(__name__)


class PayloadAnalyzer:
    """Analyzes payloads to identify changes and null fields."""
    
    @staticmethod
    def get_null_fields_summary(payload: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Get a summary of null fields by entity type.
        
        Args:
            payload: Payload dictionary
        
        Returns:
            Dictionary mapping entity types to lists of null field names
        """
        summary = {}
        
        # Analyze company_record
        if "company_record" in payload:
            company = payload["company_record"]
            null_fields = [k for k, v in company.items() if v is None and k != "provenance"]
            if null_fields:
                summary["company_record"] = null_fields
        
        # Analyze lists
        for entity_type in ["events", "snapshots", "products", "leadership", "visibility"]:
            if entity_type in payload and isinstance(payload[entity_type], list):
                all_null = set()
                for item in payload[entity_type]:
                    if isinstance(item, dict):
                        for field, value in item.items():
                            if value is None and field != "provenance":
                                all_null.add(field)
                if all_null:
                    summary[entity_type] = sorted(list(all_null))
        
        return summary
    
    @staticmethod
    def compare_payloads(original: Dict[str, Any], updated: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two payloads and identify changes.
        
        Args:
            original: Original payload
            updated: Updated payload
        
        Returns:
            Dictionary with change summary
        """
        changes = {
            "total_changes": 0,
            "entity_changes": {},
            "new_fields_filled": 0,
            "field_updates": []
        }
        
        # Compare company_record
        if "company_record" in original and "company_record" in updated:
            orig_company = original["company_record"]
            upd_company = updated["company_record"]
            
            for field in orig_company:
                if orig_company.get(field) is None and upd_company.get(field) is not None:
                    changes["new_fields_filled"] += 1
                    changes["field_updates"].append({
                        "entity": "company_record",
                        "field": field,
                        "old_value": None,
                        "new_value": upd_company.get(field)
                    })
                    changes["total_changes"] += 1
        
        return changes
    
    @staticmethod
    def validate_payload_structure(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that payload has correct structure.
        
        Args:
            payload: Payload to validate
        
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if "company_record" not in payload:
            errors.append("Missing 'company_record' section")
        
        required_sections = ["events", "snapshots", "products", "leadership", "visibility"]
        for section in required_sections:
            if section not in payload:
                errors.append(f"Missing '{section}' section")
            elif not isinstance(payload[section], list):
                errors.append(f"'{section}' should be a list")
        
        return len(errors) == 0, errors


class FieldExtractor:
    """Extracts and formats field information for LLM processing."""
    
    @staticmethod
    def format_field_for_llm(
        field_name: str,
        entity_type: str,
        company_name: str,
        context: Optional[str] = None
    ) -> str:
        """
        Format field information for LLM processing.
        
        Args:
            field_name: Name of the field
            entity_type: Type of entity
            company_name: Company name
            context: Additional context
        
        Returns:
            Formatted string for LLM
        """
        prompt = f"""Find information about the {field_name} for company {company_name}.
        
Entity Type: {entity_type}
Field: {field_name}
Company: {company_name}

"""
        if context:
            prompt += f"Context:\n{context}\n\n"
        
        prompt += "Extract the value if found. Return as JSON with fields: value, confidence, source, reasoning"
        
        return prompt
    
    @staticmethod
    def categorize_field_importance(field_name: str, entity_type: str) -> str:
        """
        Categorize field importance for prioritization.
        
        Args:
            field_name: Field name
            entity_type: Entity type
        
        Returns:
            Importance level: 'critical', 'high', 'medium', 'low'
        """
        # Define importance levels
        critical_fields = {
            "company_record": ["legal_name", "company_id", "website"],
            "events": ["event_id", "company_id", "occurred_on", "event_type"],
            "products": ["product_id", "company_id", "name"],
            "leadership": ["person_id", "company_id", "name", "role"]
        }
        
        high_importance = {
            "company_record": ["founded_year", "categories", "total_raised_usd"],
            "events": ["title", "description", "amount_usd"],
            "products": ["description", "pricing_model"],
            "snapshots": ["job_openings_count", "headcount_total"],
            "visibility": ["news_mentions_30d", "avg_sentiment"]
        }
        
        if entity_type in critical_fields:
            if field_name in critical_fields[entity_type]:
                return "critical"
        
        if entity_type in high_importance:
            if field_name in high_importance[entity_type]:
                return "high"
        
        return "medium" if "description" not in field_name else "low"


class ProvenanceManager:
    """Manages provenance tracking for payload updates."""
    
    @staticmethod
    def create_provenance_entry(
        source_tool: str,
        source_url: str,
        snippet: Optional[str] = None,
        chunk_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a provenance entry for a data source.
        
        Args:
            source_tool: Tool that retrieved the data
            source_url: URL or source identifier
            snippet: Optional excerpt from source
            chunk_ids: Optional list of chunk identifiers
        
        Returns:
            Provenance dictionary
        """
        return {
            "source_url": source_url,
            "crawled_at": datetime.utcnow().isoformat(),
            "snippet": snippet,
            "chunk_id": chunk_ids or []
        }
    
    @staticmethod
    def append_provenance(
        payload_section: Union[Dict[str, Any], List[Dict[str, Any]]],
        provenance: Dict[str, Any]
    ) -> None:
        """
        Append provenance to a payload section.
        
        Args:
            payload_section: Payload section (dict or list item)
            provenance: Provenance entry to add
        """
        if isinstance(payload_section, dict):
            if "provenance" not in payload_section:
                payload_section["provenance"] = []
            
            # Check for duplicates before adding
            existing_urls = {p.get("source_url") for p in payload_section["provenance"]}
            if provenance.get("source_url") not in existing_urls:
                payload_section["provenance"].append(provenance)


class FileComparator:
    """Compare payload files and generate diffs."""
    
    @staticmethod
    def generate_diff(
        original_path: str,
        updated_path: str
    ) -> str:
        """
        Generate a unified diff between two payload files.
        
        Args:
            original_path: Path to original file
            updated_path: Path to updated file
        
        Returns:
            Unified diff string
        """
        try:
            with open(original_path, "r") as f:
                original_lines = f.readlines()
            
            with open(updated_path, "r") as f:
                updated_lines = f.readlines()
            
            diff_lines = unified_diff(
                original_lines,
                updated_lines,
                fromfile="original",
                tofile="updated"
            )
            
            return "".join(diff_lines)
        
        except Exception as e:
            logger.error(f"Error generating diff: {e}")
            return ""


# Utility functions
def merge_payloads(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge updated payload into base payload.
    
    Args:
        base: Base payload
        updates: Updates to merge
    
    Returns:
        Merged payload
    """
    result = json.loads(json.dumps(base))
    
    for key, value in updates.items():
        if key == "company_record" and isinstance(value, dict):
            result["company_record"].update(value)
        elif isinstance(value, list):
            result[key] = value
    
    return result


def calculate_enrichment_percentage(
    original: Dict[str, Any],
    updated: Dict[str, Any]
) -> float:
    """
    Calculate enrichment percentage.
    
    Args:
        original: Original payload
        updated: Updated payload
    
    Returns:
        Enrichment percentage (0-100)
    """
    original_nulls = sum(
        1 for v in original.get("company_record", {}).values()
        if v is None
    )
    
    updated_nulls = sum(
        1 for v in updated.get("company_record", {}).values()
        if v is None
    )
    
    if original_nulls == 0:
        return 100.0 if updated_nulls == 0 else 0.0
    
    filled = original_nulls - updated_nulls
    return (filled / original_nulls) * 100
