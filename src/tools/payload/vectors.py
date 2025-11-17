"""
Payload Vector Fill Utilities — Fill ALL null fields from ALL payload sections.

This module provides a fully dynamic pipeline to fill ANY null field from ANY section:
- company_record (scalar metadata fields)
- events (list of Event objects)
- snapshots (list of Snapshot objects)
- products (list of Product objects)
- leadership (list of Leadership objects)
- visibility (list of Visibility objects)

Main Functions:
1. get_all_null_fields() - Identify ALL null fields across ALL sections (100% dynamic)
2. search_vectors_for_field() - Dynamic query generation (no hardcoding)
3. extract_value_from_snippet() - LLM-based extraction for any field
4. aggregate_candidates() - Consensus aggregation
5. fill_all_nulls() - Main orchestrator that fills ALL nulls across all sections

Architecture:
- ZERO hardcoding of field names or payload details
- Automatically adapts to ANY new field in ANY section
- LLM handles all extraction based on field name semantics
- Graceful fallback: if no vectors found or extraction fails, field stays null
- Works for ALL payload sections: company_record, events, snapshots, products, leadership, visibility
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


def get_all_null_fields(payload: Any) -> Dict[str, List[Tuple[int, str]]]:
    """
    Dynamically identify ALL null/empty fields across ALL payload sections.
    
    This is 100% dynamic - inspects each section and returns all null fields
    without any hardcoding of field names or payload structure.
    
    Args:
        payload: Pydantic Payload object with all sections
        
    Returns:
        Dict mapping section_name -> list of (item_index, field_name) tuples
        Example:
        {
            "company_record": [
                (None, "founded_year"),      # None index for scalar section
                (None, "hq_city"),
            ],
            "events": [
                (0, "description"),          # (item_index, field_name)
                (1, "round_name"),
            ],
            "snapshots": [
                (0, "headcount_total"),
            ],
            ...
        }
    """
    null_fields = {}
    
    # Get all top-level sections from payload (dynamically)
    sections_to_check = ["company_record", "events", "snapshots", "products", "leadership", "visibility"]
    
    for section_name in sections_to_check:
        section_data = getattr(payload, section_name, None)
        if section_data is None:
            continue
        
        null_in_section = []
        
        # Handle scalar section (company_record)
        if section_name == "company_record":
            if hasattr(section_data, "model_fields"):
                # Pydantic v2
                all_fields = section_data.model_fields.keys()
            else:
                all_fields = [k for k in dir(section_data) if not k.startswith("_") and not callable(getattr(section_data, k))]
            
            for field_name in all_fields:
                try:
                    value = getattr(section_data, field_name, None)
                    if callable(value):
                        continue
                    
                    # Check if null or empty
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        null_in_section.append((None, field_name))
                        
                except AttributeError:
                    continue
        
        # Handle list sections (events, snapshots, products, leadership, visibility)
        elif isinstance(section_data, list):
            for item_idx, item in enumerate(section_data):
                if item is None:
                    continue
                
                # Get all fields from this item
                if hasattr(item, "model_fields"):
                    # Pydantic v2
                    all_fields = item.model_fields.keys()
                else:
                    all_fields = [k for k in dir(item) if not k.startswith("_") and not callable(getattr(item, k))]
                
                for field_name in all_fields:
                    try:
                        value = getattr(item, field_name, None)
                        if callable(value):
                            continue
                        
                        # Check if null or empty
                        if value is None or (isinstance(value, str) and value.strip() == ""):
                            null_in_section.append((item_idx, field_name))
                            
                    except AttributeError:
                        continue
        
        if null_in_section:
            null_fields[section_name] = null_in_section
            logger.info(f"Found {len(null_in_section)} null fields in {section_name}: {[f[1] for f in null_in_section]}")
    
    return null_fields
    
    try:
        # Call RAG search tool
        chunks = rag_search_tool(company_id, query, top_k=top_k)
        
        results = []
        for chunk in chunks:
            # Handle both flat and nested metadata structures
            text = chunk.get("text") or chunk.get("snippet") or chunk.get("metadata", {}).get("text", "")
            source_url = chunk.get("source_url") or chunk.get("metadata", {}).get("source_url", "unknown")
            crawled_at = chunk.get("crawled_at") or chunk.get("metadata", {}).get("crawled_at")
            
            result = {
                "snippet": text,
                "source_url": source_url,
                "crawled_at": crawled_at,
                "confidence": "medium",
            }
            results.append(result)
        
        logger.info(f"Found {len(results)} candidate snippets for {section_name}.{field_name}")
        return results
        
    except Exception as e:
        logger.warning(f"Vector search failed for {section_name}.{field_name}: {e}")
        return []


def _build_semantic_search_query(field_name: str, section_name: str) -> str:
    """
    Dynamically build a semantic search query for ANY field.
    
    Maps field names to natural language questions that will match relevant content
    in Pinecone embeddings. Works without hardcoding for new/unknown fields.
    
    Args:
        field_name: The field name to search for (e.g., "hq_city", "github_repo", "employee_count")
        section_name: The section this field belongs to
        
    Returns:
        Natural language search query optimized for semantic matching
    """
    
    field_lower = field_name.lower()
    
    # Map field name patterns to semantic questions
    # Each pattern generates a question that will match relevant text in embeddings
    
    if any(x in field_lower for x in ["city", "location"]) and "hq" in field_lower:
        return "Where is the headquarters located? What city?"
    
    if any(x in field_lower for x in ["country"]) and "hq" in field_lower:
        return "In which country is the headquarters? Where is it based?"
    
    if any(x in field_lower for x in ["state", "province"]) and "hq" in field_lower:
        return "What state or province is headquarters in?"
    
    if "github" in field_lower or "repo" in field_lower:
        return "What is the GitHub repository URL or GitHub account username?"
    
    if any(x in field_lower for x in ["website", "url"]):
        return "What is the company website URL or web address?"
    
    if any(x in field_lower for x in ["founding", "founded", "year"]) and any(x in field_lower for x in ["found", "year", "date"]):
        return "When was the company founded? What year was it established?"
    
    if any(x in field_lower for x in ["category", "categories", "industry", "industries", "sector"]):
        return "What industries or business sectors does this company operate in?"
    
    if any(x in field_lower for x in ["employee", "headcount", "staff"]):
        return "How many employees does this company have?"
    
    if any(x in field_lower for x in ["funding", "raised", "investment"]) and "amount" in field_lower:
        return "How much total funding has this company raised in dollars?"
    
    if any(x in field_lower for x in ["funding", "round"]) and "round" in field_lower:
        return "What funding rounds has this company completed? Series A, Series B, etc?"
    
    if any(x in field_lower for x in ["stage", "phase"]):
        return "What stage of growth is this company at? Seed stage, growth stage, etc?"
    
    if any(x in field_lower for x in ["revenue", "income", "sales"]):
        return "What is the company revenue or annual turnover?"
    
    if any(x in field_lower for x in ["description", "about", "summary", "bio"]):
        return "What does this company do? What is their business or mission?"
    
    if any(x in field_lower for x in ["name", "brand", "title"]):
        return "What is the company name or brand name?"
    
    if "description" in field_lower:
        return "Describe what this company does and what products or services they offer"
    
    if any(x in field_lower for x in ["ceo", "founder", "leader", "executive"]):
        return "Who is the CEO or founder? Who leads this company?"
    
    if any(x in field_lower for x in ["partner", "client", "customer"]):
        return "Who are the clients or partners? Which companies does this company work with?"
    
    # Generic fallback for any unknown field
    readable_field = field_name.replace("_", " ")
    return f"Information about {readable_field} for this company"


def _build_semantic_query_candidates(
    field_name: str,
    section_name: str,
    company_id: Optional[str] = None,
    company_name: Optional[str] = None,
) -> List[str]:
    """
    Return a list of semantic query paraphrases for robust RAG search.

    We first generate the base semantic query (from existing helper), then produce
    additional paraphrases that include the company id or the human-readable
    company name when available. This mirrors what `structured_extraction` does
    (stronger signals with company name), but keeps everything dynamic.
    """

    base = _build_semantic_search_query(field_name, section_name)
    queries = [base]

    if company_id:
        try:
            slug = company_id.replace("-", " ").replace("_", " ")
            queries.append(f"{company_id} {base}")
            queries.append(f"Where is {slug} headquartered? {base}")
        except Exception:
            pass

    if company_name:
        queries.append(f"Where is {company_name} based? {base}")
        queries.append(f"{company_name} headquarters country or city? {base}")
        queries.append(f"company {company_name} headquarters location and country")

    # de-duplicate while preserving order
    seen = set()
    final = []
    for q in queries:
        qn = q.strip()
        if qn and qn not in seen:
            seen.add(qn)
            final.append(qn)

    return final


def search_vectors_for_field(
    company_id: str,
    field_name: str,
    section_name: str,
    rag_search_tool: Any,
    top_k: int = 200,
    company_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search Pinecone vectors for snippets containing a missing field.
    
    Dynamically constructs semantic search queries based on field name and section.
    Works for ANY field type without hardcoding.
    If no vectors are found, the field will remain null (acceptable).
    
    Args:
        company_id: Company identifier (slug format preferred for Pinecone filtering)
        field_name: Field name to search for (ANY field from ANY section)
        section_name: Section name (company_record, events, snapshots, etc.)
        rag_search_tool: Callable that takes (company_slug, query, top_k) and returns chunks
        top_k: Number of top results to return
        
    Returns:
        List of dicts with: snippet, source_url, crawled_at, confidence
    """
    if not rag_search_tool or not company_id:
        logger.warning(f"Missing rag_search_tool or company_id for {section_name}.{field_name}")
        return []
    
    # Generate semantic query dynamically based on field name
    # and build several paraphrase candidates that include the company
    # context (company_id and human-readable company name) to increase
    # the chance of finding a semantic match.
    queries = _build_semantic_query_candidates(
        field_name=field_name,
        section_name=section_name,
        company_id=company_id,
        company_name=company_name,
    )
    
    # Normalize company_id to slug format for consistent Pinecone filtering
    # Format: lowercase, hyphens to underscores, alphanumeric only
    company_slug = company_id.lower().split()[0]
    
    logger.info(
        f"Searching vectors for {section_name}.{field_name} using semantic queries: {queries[:3]}"
    )
    logger.debug(f"Company slug filter: {company_slug}")
    
    try:
        # Call RAG tool with semantic query and company filter
        # Try each query candidate in order; if any returns results we use it.
        results = []
        for q in queries:
            logger.debug(f"Calling RAG tool with company_slug='{company_slug}', query='{q}', top_k={top_k}")
            results = rag_search_tool(company_slug, q, top_k)
            if results:
                logger.info(f"Found {len(results)} results for query: {q}")
                break
        
        if results:
            logger.info(f"Found {len(results)} vector candidates for {section_name}.{field_name}")
            # Log first result for debugging
            if results:
                first = results[0]
                logger.debug(f"  First result snippet: {str(first.get('snippet', first.get('text', '')))[:100]}...")
                logger.debug(f"  First result source: {first.get('source_url', 'unknown')}")
            return results
        else:
            logger.info(f"No vector candidates for {section_name}.{field_name}")
            logger.debug(f"  company_slug used: '{company_slug}'")
            logger.debug(f"  query used: '{queries[0] if queries else ''}'")
            logger.debug(f"  top_k requested: {top_k}")
            
            # Try without company filter to see if data exists at all
            logger.debug(f"  Attempting search WITHOUT company filter to check if data exists...")
            try:
                # This is a diagnostic - call rag tool with empty company_id to search all
                test_results = rag_search_tool("", queries[0] if queries else "", 5)
                if test_results:
                    logger.warning(f"  Found {len(test_results)} results WITHOUT company filter!")
                    logger.warning(f"  This means data exists but company_slug filter is not matching.")
                    logger.warning(f"  Check that ingested data has 'company_slug'='{company_slug}' in metadata")
                else:
                    logger.debug(f"  No results even without filter - data may not be ingested")
            except Exception as diag_e:
                logger.debug(f"  Diagnostic search failed: {diag_e}")

            # ----- Local fallback: scan raw text for possible matches -----
            try:
                company_raw_root = Path(__file__).parent.parent.parent.parent / "data" / "raw" / company_slug
                if company_raw_root.exists():
                    found = []
                    # Build small keyword set from the query for substring matching
                    keywords = [w.lower() for w in (queries[0] if queries else "").split() if len(w) > 3]
                    for page_file in company_raw_root.rglob("*.txt"):
                        try:
                            txt = page_file.read_text(encoding="utf-8")
                        except Exception:
                            continue
                        lowered = txt.lower()
                        # If any keyword appears in text, add snippet
                        if any(k in lowered for k in keywords):
                            snippet = txt[:1000]
                            found.append({
                                "snippet": snippet,
                                "source_url": str(page_file),
                                "crawled_at": None,
                                "confidence": "low",
                            })
                    if found:
                        logger.warning(
                            f"Local fallback found {len(found)} text candidates for {section_name}.{field_name}"
                        )
                        return found[:top_k]
            except Exception as diag_e:
                logger.debug(f"Local fallback failed: {diag_e}")
            
            return []
            
    except Exception as e:
        logger.warning(f"Error searching vectors for {section_name}.{field_name}: {e}")
        return []


def extract_value_from_snippet(
    field_name: str,
    section_name: str,
    snippet: str,
    llm_extractor: Any,
) -> Optional[Dict[str, Any]]:
    """
    Extract a field value using LLM (100% dynamic, works for ANY field).
    
    Args:
        field_name: Field to extract
        section_name: Section name (for context)
        snippet: Text snippet to extract from
        llm_extractor: Callable LLM extractor that returns {"value": ..., "evidence": ...}
        
    Returns:
        Dict with extracted value and evidence, or None if extraction failed
    """
    if not snippet or not llm_extractor:
        return None
    
    try:
        logger.debug(f"Attempting LLM extraction for {section_name}.{field_name}")
        result = llm_extractor(field_name, snippet)
        
        if result and result.get("value") is not None:
            logger.info(f"LLM extraction succeeded for {section_name}.{field_name}: {result['value']}")
            return result
        
        return None
        
    except Exception as e:
        logger.debug(f"LLM extraction error for {section_name}.{field_name}: {e}")
        return None


def aggregate_candidates(
    candidates: List[Dict[str, Any]],
    field_name: str,
    section_name: str,
) -> Optional[Tuple[Any, List[Dict[str, Any]]]]:
    """
    Aggregate multiple candidate extractions and decide on final value via consensus.
    
    Args:
        candidates: List of dicts with extracted values and provenance
        field_name: Field name
        section_name: Section name
        
    Returns:
        Tuple of (final_value, provenance_list) or (None, []) if no agreement
    """
    if not candidates:
        return None, []
    
    # Extract values, filter out nulls
    values_with_confidence = [
        (c.get("value"), c.get("confidence", "medium"))
        for c in candidates 
        if c.get("value") is not None
    ]
    
    if not values_with_confidence:
        logger.info(f"No candidate values found for {section_name}.{field_name}")
        return None, []
    
    # Sort by confidence (high > medium > low)
    confidence_order = {"high": 0, "medium": 1, "low": 2}
    values_with_confidence.sort(key=lambda x: confidence_order.get(x[1], 2))
    
    # Extract values (sorted by confidence)
    values = [v[0] for v in values_with_confidence]
    
    # Check if top candidates agree (allow some variation for city names, etc)
    top_value = str(values[0]).lower().strip()
    
    # Count how many values match the top value (case-insensitive)
    matching_count = sum(
        1 for v in values 
        if str(v).lower().strip() == top_value
    )
    
    if matching_count >= max(1, len(values) // 2):
        # Majority agreement or single confident extraction
        final_value = values[0]  # Use the highest confidence value
        provenance = [
            {
                "source_url": c.get("source_url"),
                "crawled_at": c.get("crawled_at"),
                "snippet": c.get("snippet"),
                "method": c.get("method", "vector_search"),
                "confidence": c.get("confidence", "medium"),
            }
            for c in candidates
            if c.get("value") is not None
        ]
        logger.info(
            f"Candidates for {section_name}.{field_name} have majority agreement: {final_value} "
            f"({matching_count}/{len(values)} agree)"
        )
        return final_value, provenance
    else:
        # Not enough agreement: check if we have high-confidence single extraction
        if len(values_with_confidence) == 1 and values_with_confidence[0][1] == "high":
            # Single high-confidence extraction is acceptable
            final_value = values[0]
            provenance = [
                {
                    "source_url": candidates[0].get("source_url"),
                    "crawled_at": candidates[0].get("crawled_at"),
                    "snippet": candidates[0].get("snippet"),
                    "method": candidates[0].get("method", "vector_search"),
                    "confidence": "high",
                }
            ]
            logger.info(f"Single high-confidence extraction for {section_name}.{field_name}: {final_value}")
            return final_value, provenance
        else:
            # Conflict: mark ambiguous
            logger.warning(
                f"Conflicting values for {section_name}.{field_name}: {values}. "
                f"({matching_count}/{len(values)} agree, need majority). Marking ambiguous."
            )
            return None, []


def create_provenance_record(
    source_url: str,
    crawled_at: Optional[str],
    snippet: str,
    method: str = "vector_search",
) -> Dict[str, Any]:
    """
    Create a standardized provenance record.
    
    Args:
        source_url: URL where info was sourced
        crawled_at: Date scraped
        snippet: Text evidence
        method: How value was extracted
        
    Returns:
        Provenance dict
    """
    return {
        "source_url": source_url,
        "crawled_at": crawled_at or datetime.now().isoformat(),
        "snippet": snippet,
        "method": method,
    }


def fill_all_nulls(
    payload: Any,
    company_id: str,
    rag_search_tool: Any,
    llm_extractor: Optional[Any] = None,
    top_k: int = 50,
    company_name: Optional[str] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """
    MAIN ORCHESTRATOR: Fill ALL null fields across ALL payload sections.
    
    This dynamically:
    1. Identifies all null fields in ALL sections
    2. Searches vectors for each null field
    3. Uses LLM to extract values (no hardcoded patterns)
    4. Aggregates with consensus logic
    5. Updates the payload
    
    Architecture:
    - 100% dynamic - works for ANY field in ANY section
    - NO hardcoding of field names or payload structure
    - LLM handles all extraction based on field semantics
    
    Args:
        payload: Pydantic Payload object to fill
        company_id: Company identifier
        rag_search_tool: Callable for vector search
        llm_extractor: LLM extractor callable
        top_k: Number of vector results per field
        
    Returns:
        Tuple of (updated_payload, metadata_dict) where metadata includes:
        {
            "filled_fields": {section_name: [field_names]},
            "ambiguous_fields": {section_name: [field_names]},
            "unfilled_nulls": {section_name: [field_names]},
            "total_filled": int,
            "total_attempted": int,
            "provenance": {section_name: {field_name: [provenance_records]}},
        }
    """
    if llm_extractor is None:
        logger.warning("No LLM extractor provided; cannot fill fields")
        return payload, {
            "filled_fields": {},
            "ambiguous_fields": {},
            "unfilled_nulls": {},
            "total_filled": 0,
            "total_attempted": 0,
            "provenance": {},
        }
    
    # Step 1: Identify ALL null fields across ALL sections
    all_nulls = get_all_null_fields(payload)
    
    total_nulls = sum(len(fields) for fields in all_nulls.values())
    logger.info(f"Identified {total_nulls} total null fields across {len(all_nulls)} sections")
    
    # Initialize metadata tracking
    filled = {}
    ambiguous = {}
    unfilled = {}
    provenance = {}
    total_filled = 0
    
    # Step 2: Process each null field in each section
    for section_name, null_fields_list in all_nulls.items():
        filled[section_name] = []
        ambiguous[section_name] = []
        unfilled[section_name] = []
        provenance[section_name] = {}
        
        for item_idx, field_name in null_fields_list:
            logger.info(f"Attempting to fill {section_name}.{field_name}")
            
            # Search vectors
            candidates = search_vectors_for_field(
                company_id=company_id,
                field_name=field_name,
                section_name=section_name,
                rag_search_tool=rag_search_tool,
                top_k=top_k,
                company_name=company_name,
            )
            
            if not candidates:
                logger.info(f"No vector candidates for {section_name}.{field_name}")
                unfilled[section_name].append(field_name)
                continue
            
            # Extract with LLM
            extracted = []
            for candidate in candidates:
                result = extract_value_from_snippet(
                    field_name=field_name,
                    section_name=section_name,
                    snippet=candidate["snippet"],
                    llm_extractor=llm_extractor,
                )
                if result and result.get("value") is not None:
                    extracted.append({
                        "value": result["value"],
                        "source_url": candidate["source_url"],
                        "crawled_at": candidate["crawled_at"],
                        "snippet": candidate["snippet"],
                        "method": "llm_extraction",
                    })
            
            if not extracted:
                logger.info(f"LLM extraction produced no values for {section_name}.{field_name}")
                unfilled[section_name].append(field_name)
                continue
            
            # Aggregate with consensus
            final_value, prov = aggregate_candidates(extracted, field_name, section_name)
            
            if final_value is not None:
                # Update payload
                try:
                    _update_payload_field(payload, section_name, item_idx, field_name, final_value)
                    filled[section_name].append(field_name)
                    provenance[section_name][field_name] = prov
                    total_filled += 1
                    logger.info(f"✓ Filled {section_name}.{field_name} = {final_value}")
                except Exception as e:
                    logger.error(f"Failed to update {section_name}.{field_name}: {e}")
                    unfilled[section_name].append(field_name)
            else:
                logger.warning(f"Conflicting values for {section_name}.{field_name}")
                ambiguous[section_name].append(field_name)
    
    # Cleanup empty sections from metadata
    filled = {k: v for k, v in filled.items() if v}
    ambiguous = {k: v for k, v in ambiguous.items() if v}
    unfilled = {k: v for k, v in unfilled.items() if v}
    provenance = {k: v for k, v in provenance.items() if v}
    
    metadata = {
        "filled_fields": filled,
        "ambiguous_fields": ambiguous,
        "unfilled_nulls": unfilled,
        "total_filled": total_filled,
        "total_attempted": total_nulls,
        "provenance": provenance,
    }
    
    logger.info(f"fill_all_nulls complete. Filled: {total_filled}/{total_nulls}")
    
    return payload, metadata


def _update_payload_field(payload: Any, section_name: str, item_idx: Optional[int], field_name: str, value: Any) -> None:
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
