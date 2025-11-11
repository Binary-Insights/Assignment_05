"""
Evaluation Metrics Calculator for LLM-generated dashboards.

Calculates metrics for comparing Structured vs RAG pipeline outputs:
- Factual Accuracy (0-3)
- Schema Compliance (0-2)
- Provenance Quality (0-2)
- Hallucination Detection (0-2)
- Readability (0-1)
- Mean Reciprocal Ranking (MRR)

Usage:
    from eval_metrics import EvaluationMetrics, calculate_mrr, calculate_factual_accuracy
    
    # Manual scoring
    metrics = EvaluationMetrics(
        company_name="World Labs",
        pipeline_type="structured",
        factual_accuracy=3,
        schema_compliance=2
    )
    
    # Programmatic scoring from content
    generated_text = "# Dashboard content..."
    ground_truth = {"key_facts": [...], "expected_fields": [...]}
    
    factual_score = calculate_factual_accuracy(generated_text, ground_truth)
    schema_score = calculate_schema_compliance(generated_text, ground_truth)
    # ... etc
"""

import json
import logging
import re
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MetricRange(Enum):
    """Metric range constraints."""
    FACTUAL_ACCURACY = (0, 3)
    SCHEMA_COMPLIANCE = (0, 2)
    PROVENANCE_QUALITY = (0, 2)
    HALLUCINATION_DETECTION = (0, 2)
    READABILITY = (0, 1)
    MRR = (0.0, 1.0)


# ==================== PROGRAMMATIC SCORING FUNCTIONS ====================

def calculate_factual_accuracy(
    generated_text: str,
    ground_truth_data: Dict[str, Any]
) -> int:
    """
    Calculate Factual Accuracy (0-3) based on key facts presence and coverage.
    
    Scoring logic:
    - 0: No relevant facts or severe inaccuracies (< 40% coverage)
    - 1: Only basic facts present, missing important details (40-70% coverage)
    - 2: Most key facts present with minor gaps (70-90% coverage)
    - 3: All key facts accurately represented (>= 90% coverage)
    
    Args:
        generated_text: Dashboard markdown content
        ground_truth_data: Dict with 'key_facts' list
    
    Returns:
        Score 0-3
    """
    logger.info("=" * 80)
    logger.info("CALCULATING: Factual Accuracy (0-3)")
    logger.info("=" * 80)
    
    if not generated_text or not ground_truth_data:
        logger.warning("FACTUAL_ACCURACY: Missing generated_text or ground_truth_data")
        logger.info("Result: Score = 0 (missing data)")
        return 0
    
    key_facts = ground_truth_data.get("key_facts", [])
    if not key_facts:
        logger.warning("FACTUAL_ACCURACY: No key facts provided in ground truth")
        logger.info("Result: Score = 2 (default middle score, no facts to compare)")
        return 2  # Default middle score
    
    logger.info(f"FACTUAL_ACCURACY: Processing {len(key_facts)} key facts from ground truth")
    
    # Normalize text for comparison
    text_lower = generated_text.lower()
    text_length = len(generated_text)
    logger.info(f"FACTUAL_ACCURACY: Generated text length: {text_length} characters")
    
    # Count how many key facts are mentioned
    facts_found = 0
    facts_matched = []
    facts_missing = []
    
    for i, fact in enumerate(key_facts, 1):
        if isinstance(fact, dict):
            fact_text = fact.get("text", str(fact)).lower()
        else:
            fact_text = str(fact).lower()
        
        # Simple substring matching (can be enhanced with fuzzy matching)
        found = fact_text in text_lower or any(
            word in text_lower for word in fact_text.split() if len(word) > 3
        )
        
        if found:
            facts_found += 1
            facts_matched.append(fact_text[:50])  # First 50 chars for logging
            logger.debug(f"  ✓ Fact {i} FOUND: {fact_text[:60]}...")
        else:
            facts_missing.append(fact_text[:50])
            logger.debug(f"  ✗ Fact {i} MISSING: {fact_text[:60]}...")
    
    coverage = facts_found / len(key_facts) if key_facts else 0
    
    logger.info(f"FACTUAL_ACCURACY: Coverage Analysis")
    logger.info(f"  - Facts Found: {facts_found}/{len(key_facts)}")
    logger.info(f"  - Coverage Percentage: {coverage*100:.1f}%")
    logger.info(f"  - Matched Facts: {facts_matched}")
    logger.info(f"  - Missing Facts: {facts_missing}")
    
    # Score based on coverage
    if coverage >= 0.9:
        score = 3
        reason = "Excellent coverage (>= 90%) - All key facts accurately represented"
    elif coverage >= 0.7:
        score = 2
        reason = "Good coverage (70-90%) - Most key facts present with minor gaps"
    elif coverage >= 0.4:
        score = 1
        reason = "Poor coverage (40-70%) - Only basic facts present, missing important details"
    else:
        score = 0
        reason = "Very poor coverage (< 40%) - No relevant facts or severe inaccuracies"
    
    logger.info(f"FACTUAL_ACCURACY: Scoring Decision")
    logger.info(f"  - Threshold Check: {coverage*100:.1f}% coverage")
    logger.info(f"  - Condition Met: {reason}")
    logger.info(f"  - FINAL SCORE: {score}/3")
    logger.info("")
    
    return score


def calculate_schema_compliance(
    generated_text: str,
    ground_truth_data: Dict[str, Any]
) -> int:
    """
    Calculate Schema Compliance (0-2) based on required fields and structure.
    
    Scoring logic:
    - 0: Missing required sections or major structure violations
        (< 50% section coverage OR no proper structure)
    - 1: Most sections present but inconsistent formatting
        (50-80% section coverage OR basic structure)
    - 2: All required sections present with consistent structure
        (>= 80% section coverage AND proper formatting)
    
    Args:
        generated_text: Dashboard markdown content
        ground_truth_data: Dict with 'required_fields' or 'expected_sections' list
    
    Returns:
        Score 0-2
    """
    logger.info("=" * 80)
    logger.info("CALCULATING: Schema Compliance (0-2)")
    logger.info("=" * 80)
    
    if not generated_text:
        logger.warning("SCHEMA_COMPLIANCE: Missing generated_text")
        logger.info("Result: Score = 0 (missing content)")
        return 0
    
    # Define expected schema patterns
    required_sections = ground_truth_data.get("required_fields", [])
    if not required_sections:
        required_sections = ground_truth_data.get("expected_sections", [
            "overview", "mission", "products", "team", "funding", "technology"
        ])
    
    logger.info(f"SCHEMA_COMPLIANCE: Checking {len(required_sections)} required sections")
    logger.info(f"  - Expected sections: {required_sections}")
    
    text_lower = generated_text.lower()
    
    # Count headers (markdown sections)
    header_count = len(re.findall(r'^#{1,3}\s+', generated_text, re.MULTILINE))
    logger.info(f"SCHEMA_COMPLIANCE: Structure Analysis")
    logger.info(f"  - Headers found: {header_count}")
    
    # Check for required sections
    sections_found = 0
    sections_matched = []
    sections_missing = []
    
    for section in required_sections:
        if section.lower() in text_lower:
            sections_found += 1
            sections_matched.append(section)
            logger.debug(f"  ✓ Section FOUND: {section}")
        else:
            sections_missing.append(section)
            logger.debug(f"  ✗ Section MISSING: {section}")
    
    section_coverage = sections_found / len(required_sections) if required_sections else 0
    
    # Check for structure consistency (bullet points, lists, etc.)
    list_items = len(re.findall(r'^[\s]*[-*•]\s+', generated_text, re.MULTILINE))
    has_structure = header_count > 0 or list_items > 0
    
    logger.info(f"SCHEMA_COMPLIANCE: Section Coverage Analysis")
    logger.info(f"  - Sections Found: {sections_found}/{len(required_sections)}")
    logger.info(f"  - Coverage Percentage: {section_coverage*100:.1f}%")
    logger.info(f"  - Matched Sections: {sections_matched}")
    logger.info(f"  - Missing Sections: {sections_missing}")
    logger.info(f"  - List Items Found: {list_items}")
    logger.info(f"  - Has Proper Structure: {has_structure}")
    
    # Score based on section coverage and structure
    if section_coverage >= 0.8 and has_structure:
        score = 2
        reason = (f"Excellent compliance (>= 80% sections AND structure): "
                 f"{section_coverage*100:.0f}% sections, {header_count} headers, {list_items} lists")
    elif section_coverage >= 0.5 or has_structure:
        score = 1
        reason = (f"Moderate compliance (50-80% sections OR basic structure): "
                 f"{section_coverage*100:.0f}% sections, structure={has_structure}")
    else:
        score = 0
        reason = (f"Poor compliance (< 50% sections AND no structure): "
                 f"{section_coverage*100:.0f}% sections, {header_count} headers")
    
    logger.info(f"SCHEMA_COMPLIANCE: Scoring Decision")
    logger.info(f"  - Coverage: {section_coverage*100:.1f}%, Structure: {has_structure}")
    logger.info(f"  - Condition Met: {reason}")
    logger.info(f"  - FINAL SCORE: {score}/2")
    logger.info("")
    
    return score


def calculate_provenance_quality(
    generated_text: str,
    ground_truth_data: Dict[str, Any]
) -> int:
    """
    Calculate Provenance Quality (0-2) based on citations and source attribution.
    
    Scoring logic:
    - 0: No citations or source references (< 2 citations AND < 1 unique source)
    - 1: Some citations present but incomplete/inconsistent
        (2-5 citations OR 1 unique source)
    - 2: Comprehensive citations with proper attribution
        (>= 5 citations AND >= 2 unique sources)
    
    Args:
        generated_text: Dashboard markdown content
        ground_truth_data: Dict with expected citation patterns
    
    Returns:
        Score 0-2
    """
    logger.info("=" * 80)
    logger.info("CALCULATING: Provenance Quality (0-2)")
    logger.info("=" * 80)
    
    if not generated_text:
        logger.warning("PROVENANCE_QUALITY: Missing generated_text")
        logger.info("Result: Score = 0 (no content to cite)")
        return 0
    
    logger.info("PROVENANCE_QUALITY: Scanning for citations and sources")
    
    # Patterns for citations and references
    citation_patterns = {
        "markdown_links": (r'\[.*?\]\(.*?\)', "Markdown links [text](url)"),
        "urls": (r'http[s]?://\S+', "Direct URLs"),
        "according_to": (r'According to.*?[:.]', '"According to" phrases'),
        "source_label": (r'Source:.*?[\n.]', "Source: labels"),
        "reference_label": (r'Reference:.*?[\n.]', "Reference: labels"),
        "parenthetical_source": (r'\(Source:.*?\)', "Parenthetical (Source: ...)"),
    }
    
    citations_by_pattern = {}
    total_citations = 0
    
    for pattern_name, (pattern, description) in citation_patterns.items():
        matches = len(re.findall(pattern, generated_text))
        citations_by_pattern[pattern_name] = matches
        total_citations += matches
        logger.debug(f"  {pattern_name}: {matches} ({description})")
    
    # Unique sources (URLs)
    unique_sources = len(set(re.findall(r'http[s]?://[^\s)"\n]+', generated_text)))
    logger.info(f"PROVENANCE_QUALITY: Citation Analysis")
    logger.info(f"  - Total Citation Patterns Found: {total_citations}")
    logger.info(f"  - Citations by Type: {citations_by_pattern}")
    logger.info(f"  - Unique URL Sources: {unique_sources}")
    
    # Score based on citation presence
    if total_citations >= 5 and unique_sources >= 2:
        score = 2
        reason = (f"Comprehensive citations: {total_citations} total citations "
                 f"from {unique_sources} unique sources")
    elif total_citations >= 2 or unique_sources >= 1:
        score = 1
        reason = (f"Some citations present: {total_citations} total citations "
                 f"from {unique_sources} source(s)")
    else:
        score = 0
        reason = f"No/minimal citations: {total_citations} total citations"
    
    logger.info(f"PROVENANCE_QUALITY: Scoring Decision")
    logger.info(f"  - Thresholds: >= 5 citations AND >= 2 sources for score 2")
    logger.info(f"  - Thresholds: >= 2 citations OR >= 1 source for score 1")
    logger.info(f"  - Condition Met: {reason}")
    logger.info(f"  - FINAL SCORE: {score}/2")
    logger.info("")
    
    return score


def calculate_hallucination_detection(
    generated_text: str,
    ground_truth_data: Dict[str, Any]
) -> int:
    """
    Calculate Hallucination Detection (0-2) based on factual consistency.
    
    Scoring logic:
    - 0: Multiple factual errors or contradictions (>2 indicators)
    - 1: Some minor inconsistencies but mostly accurate (1-2 indicators)
    - 2: No detectable hallucinations or factual errors (0 indicators)
    
    Args:
        generated_text: Dashboard markdown content
        ground_truth_data: Dict with 'key_facts' to verify
    
    Returns:
        Score 0-2
    """
    logger.info("=" * 80)
    logger.info("CALCULATING: Hallucination Detection (0-2)")
    logger.info("=" * 80)
    
    # Input validation
    if not generated_text:
        logger.warning("INPUT: No generated text provided - returning neutral score")
        return 1
    if not ground_truth_data:
        logger.warning("INPUT: No ground truth data provided - returning neutral score")
        return 1
    
    key_facts = ground_truth_data.get("key_facts", [])
    if not key_facts:
        logger.warning("INPUT: No key facts in ground truth - returning neutral score")
        return 1
    
    logger.debug(f"INPUT VALIDATION: ✓ Generated text length: {len(generated_text)} chars")
    logger.debug(f"INPUT VALIDATION: ✓ Key facts count: {len(key_facts)}")
    
    text_lower = generated_text.lower()
    contradiction_indicators = []
    
    # Check for common hallucination markers
    logger.info("STEP 1: Detecting hallucination markers")
    logger.debug("-" * 60)
    
    hallucination_patterns = [
        (r'i (don\'t )?have access to', "Admission of access limitation"),
        (r'i (cannot|can\'t) (provide|give)', "Admission of capability limitation"),
        (r'unknown|not specified', "Vague uncertainty marker"),
        (r'approximately infinite|unlimited', "Unrealistic quantification"),
        (r'(very|extremely|incredibly) (large|small)', "Vague intensifiers"),
    ]
    
    for pattern, description in hallucination_patterns:
        match = re.search(pattern, text_lower)
        if match:
            contradiction_indicators.append(description)
            logger.debug(f"  [FOUND] {description}: '{match.group()}' at position {match.start()}")
        else:
            logger.debug(f"  [PASS] {description}: Not detected")
    
    logger.info(f"STEP 1 RESULT: Found {len(contradiction_indicators)} hallucination marker(s)")
    
    # Check for contradictions in facts
    logger.info("STEP 2: Checking fact consistency against key facts")
    logger.debug("-" * 60)
    
    facts_checked = 0
    contradictions_found = 0
    
    for idx, fact in enumerate(key_facts, 1):
        if isinstance(fact, dict):
            fact_text = fact.get("text", "").lower()
            contradictory = fact.get("contradictory_phrases", [])
        else:
            fact_text = str(fact).lower()
            contradictory = []
        
        logger.debug(f"  Fact #{idx}: '{fact_text[:60]}...' (checking {len(contradictory)} contradictions)")
        
        # Check if contradictory info exists
        for contra in contradictory:
            facts_checked += 1
            fact_in_text = fact_text in text_lower
            contra_in_text = contra.lower() in text_lower
            
            if contra_in_text and not fact_in_text:
                contradictions_found += 1
                logger.debug(f"    [CONTRADICTION] Contradictory phrase found: '{contra}' BUT fact '{fact_text[:40]}' missing")
            elif fact_in_text and not contra_in_text:
                logger.debug(f"    [CONSISTENT] Fact '{fact_text[:40]}' present, contradictory phrase absent")
            else:
                logger.debug(f"    [NEUTRAL] Both present or both absent")
    
    logger.info(f"STEP 2 RESULT: Found {contradictions_found} factual contradiction(s) in {facts_checked} checked")
    
    # Calculate final score based on hallucination indicators + contradictions
    total_indicators = len(contradiction_indicators) + contradictions_found
    logger.info("STEP 3: Scoring decision tree")
    logger.debug("-" * 60)
    logger.debug(f"  Hallucination markers: {len(contradiction_indicators)}")
    logger.debug(f"  Factual contradictions: {contradictions_found}")
    logger.debug(f"  Total indicators: {total_indicators}")
    
    if total_indicators == 0:
        logger.info("✓ THRESHOLD: 0 indicators → Score = 2 (Excellent: No hallucinations)")
        logger.info("=" * 80)
        return 2
    elif total_indicators <= 2:
        logger.info(f"◐ THRESHOLD: {total_indicators} indicator(s) (1-2 range) → Score = 1 (Acceptable: Minor inconsistencies)")
        logger.info("=" * 80)
        return 1
    else:
        logger.info(f"✗ THRESHOLD: {total_indicators} indicator(s) (>2) → Score = 0 (Poor: Multiple hallucinations)")
        logger.info("=" * 80)
        return 0


def calculate_readability(
    generated_text: str,
    ground_truth_data: Dict[str, Any] = None
) -> int:
    """
    Calculate Readability (0-1) based on formatting and clarity.
    
    Scoring logic:
    - 0: Poor formatting, lacks structure, or unreasonable line lengths
    - 1: Good formatting, clear structure (headers + lists), reasonable line lengths
    
    Args:
        generated_text: Dashboard markdown content
        ground_truth_data: Optional dict with readability preferences
    
    Returns:
        Score 0-1
    """
    logger.info("=" * 80)
    logger.info("CALCULATING: Readability (0-1)")
    logger.info("=" * 80)
    
    # Input validation
    if not generated_text:
        logger.warning("INPUT: No text provided - returning score 0 (not readable)")
        return 0
    
    lines = generated_text.split('\n')
    logger.debug(f"INPUT VALIDATION: ✓ Total lines: {len(lines)}")
    
    if len(lines) < 3:
        logger.warning(f"INPUT: Text too short ({len(lines)} lines) - returning score 0 (insufficient content)")
        return 0
    
    logger.info("STEP 1: Analyzing formatting elements")
    logger.debug("-" * 60)
    
    # Count formatting elements
    headers = len(re.findall(r'^#{1,6}\s+', generated_text, re.MULTILINE))
    bold_text = len(re.findall(r'\*\*[^*]+\*\*', generated_text))
    italic_text = len(re.findall(r'\*[^*]+\*', generated_text))
    lists = len(re.findall(r'^[\s]*[-*•]\s+', generated_text, re.MULTILINE))
    code_blocks = len(re.findall(r'```|`[^`]+`', generated_text))
    
    logger.debug(f"  Headers (# to ######): {headers}")
    logger.debug(f"  Bold text (**text**): {bold_text}")
    logger.debug(f"  Italic text (*text*): {italic_text}")
    logger.debug(f"  Lists (-, *, •): {lists}")
    logger.debug(f"  Code blocks (``` or `): {code_blocks}")
    
    total_formatting = headers + bold_text + italic_text + lists + code_blocks
    logger.info(f"STEP 1 RESULT: Total formatting elements = {total_formatting}")
    
    # Check for average line length (readability)
    logger.info("STEP 2: Analyzing line length (readability)")
    logger.debug("-" * 60)
    
    non_empty_lines = [l for l in lines if l.strip()]
    if non_empty_lines:
        avg_line_length = sum(len(l) for l in non_empty_lines) / len(non_empty_lines)
        min_line_length = min(len(l) for l in non_empty_lines)
        max_line_length = max(len(l) for l in non_empty_lines)
    else:
        avg_line_length = 0
        min_line_length = 0
        max_line_length = 0
    
    logger.debug(f"  Non-empty lines: {len(non_empty_lines)}")
    logger.debug(f"  Average line length: {avg_line_length:.1f} characters")
    logger.debug(f"  Min line length: {min_line_length} characters")
    logger.debug(f"  Max line length: {max_line_length} characters")
    logger.debug(f"  Ideal range: 30-120 characters (promotes scannability)")
    
    has_reasonable_lines = 30 < avg_line_length < 120
    if has_reasonable_lines:
        logger.info(f"✓ Line length: {avg_line_length:.1f} chars (in ideal 30-120 range)")
    else:
        logger.info(f"✗ Line length: {avg_line_length:.1f} chars (outside ideal 30-120 range)")
    
    # Check for structural elements
    logger.info("STEP 3: Checking structural requirements")
    logger.debug("-" * 60)
    
    has_good_structure = headers > 0 and lists > 0
    if headers > 0:
        logger.debug(f"  [✓] Structure: Has {headers} header(s) for organization")
    else:
        logger.debug(f"  [✗] Structure: Missing headers")
    
    if lists > 0:
        logger.debug(f"  [✓] Structure: Has {lists} list item(s) for clarity")
    else:
        logger.debug(f"  [✗] Structure: Missing lists")
    
    logger.info(f"STEP 3 RESULT: Good structure = {has_good_structure}")
    
    # Final scoring decision
    logger.info("STEP 4: Scoring decision tree")
    logger.debug("-" * 60)
    logger.debug(f"  Good structure (headers > 0 AND lists > 0): {has_good_structure}")
    logger.debug(f"  Reasonable line length (30-120 chars): {has_reasonable_lines}")
    
    if has_good_structure and has_reasonable_lines:
        logger.info("✓ THRESHOLD: Good structure AND reasonable line length → Score = 1 (Excellent)")
        logger.info("=" * 80)
        return 1
    else:
        if not has_good_structure:
            logger.info(f"✗ THRESHOLD: Missing required structure (headers: {headers}, lists: {lists})")
        if not has_reasonable_lines:
            logger.info(f"✗ THRESHOLD: Line length issue (avg: {avg_line_length:.1f} chars)")
        logger.info("✗ Overall: Poor formatting or structure → Score = 0 (Poor)")
        logger.info("=" * 80)
        return 0


# ==================== END PROGRAMMATIC SCORING ====================

@dataclass
class EvaluationMetrics:
    """Container for evaluation metrics of a single output."""
    
    company_name: str
    company_slug: str
    pipeline_type: str  # "structured" or "rag"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    # Metrics (0-3 scale)
    factual_accuracy: Optional[int] = None
    
    # Metrics (0-2 scale)
    schema_compliance: Optional[int] = None
    provenance_quality: Optional[int] = None
    hallucination_detection: Optional[int] = None
    
    # Metrics (0-1 scale)
    readability: Optional[int] = None
    
    # Ranking metric
    mrr_score: Optional[float] = None
    
    # Notes and justification
    notes: str = ""
    
    def __post_init__(self):
        """Validate metrics on initialization."""
        self.validate()
    
    def validate(self) -> bool:
        """Validate all metrics are in valid ranges."""
        validators = {
            "factual_accuracy": (0, 3),
            "schema_compliance": (0, 2),
            "provenance_quality": (0, 2),
            "hallucination_detection": (0, 2),
            "readability": (0, 1),
            "mrr_score": (0.0, 1.0),
        }
        
        errors = []
        for field_name, (min_val, max_val) in validators.items():
            value = getattr(self, field_name)
            if value is not None:
                if not (min_val <= value <= max_val):
                    errors.append(
                        f"{field_name}={value} not in range [{min_val}, {max_val}]"
                    )
        
        if errors:
            logger.warning(f"Validation errors for {self.company_slug}/{self.pipeline_type}: {', '.join(errors)}")
            return False
        
        return True
    
    def get_total_score(self) -> Optional[float]:
        """
        Calculate total score out of 14 (max sum of all metrics).
        
        Max scores:
        - Factual Accuracy: 3
        - Schema Compliance: 2
        - Provenance Quality: 2
        - Hallucination Detection: 2
        - Readability: 1
        - MRR: 2 (scaled from 0-1 to 0-2 for comparison)
        
        Returns:
            Total score or None if any metric is missing
        """
        if any(m is None for m in [
            self.factual_accuracy,
            self.schema_compliance,
            self.provenance_quality,
            self.hallucination_detection,
            self.readability,
            self.mrr_score
        ]):
            return None
        
        # Scale MRR to 0-2 range for comparison
        mrr_scaled = self.mrr_score * 2
        
        total = (
            self.factual_accuracy +
            self.schema_compliance +
            self.provenance_quality +
            self.hallucination_detection +
            self.readability +
            mrr_scaled
        )
        
        return total
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["total_score"] = self.get_total_score()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationMetrics":
        """Create from dictionary."""
        # Remove total_score if present (it's calculated)
        data_copy = {k: v for k, v in data.items() if k != "total_score"}
        return cls(**data_copy)


@dataclass
class ComparisonResult:
    """Comparison of metrics between two pipelines."""
    
    company_name: str
    company_slug: str
    structured: EvaluationMetrics
    rag: EvaluationMetrics
    
    def get_winner(self, metric_name: str) -> Optional[str]:
        """
        Get which pipeline wins for a specific metric.
        
        Args:
            metric_name: Name of metric (e.g., "factual_accuracy")
        
        Returns:
            "structured", "rag", or "tie"
        """
        struct_val = getattr(self.structured, metric_name, None)
        rag_val = getattr(self.rag, metric_name, None)
        
        if struct_val is None or rag_val is None:
            return None
        
        if struct_val > rag_val:
            return "structured"
        elif rag_val > struct_val:
            return "rag"
        else:
            return "tie"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "company_name": self.company_name,
            "company_slug": self.company_slug,
            "structured": self.structured.to_dict(),
            "rag": self.rag.to_dict(),
            "winners": {
                "factual_accuracy": self.get_winner("factual_accuracy"),
                "schema_compliance": self.get_winner("schema_compliance"),
                "provenance_quality": self.get_winner("provenance_quality"),
                "hallucination_detection": self.get_winner("hallucination_detection"),
                "readability": self.get_winner("readability"),
                "mrr_score": self.get_winner("mrr_score"),
            }
        }


def calculate_mrr(
    ranked_facts: List[Dict[str, Any]],
    relevant_threshold: float = 0.7
) -> float:
    """
    Calculate Mean Reciprocal Ranking (MRR) for a list of facts.
    
    MRR measures how well highly relevant information is ranked.
    Formula: MRR = 1/rank_of_first_relevant_item
    
    Args:
        ranked_facts: List of dicts with 'relevance_score' (0-1)
                     and optionally 'rank', 'text', 'source'
        relevant_threshold: Minimum relevance to consider "relevant" (default: 0.7)
    
    Returns:
        MRR score (0-1). Higher is better.
        
    Examples:
        # Perfect ranking (first fact most relevant)
        >>> calculate_mrr([{"relevance_score": 0.95}, {"relevance_score": 0.5}])
        1.0
        
        # Good ranking (second fact most relevant)
        >>> calculate_mrr([{"relevance_score": 0.5}, {"relevance_score": 0.95}])
        0.5
        
        # No relevant facts found
        >>> calculate_mrr([{"relevance_score": 0.3}, {"relevance_score": 0.4}])
        0.0
    """
    if not ranked_facts:
        return 0.0
    
    # Find first relevant fact
    for rank, fact in enumerate(ranked_facts, start=1):
        relevance = fact.get("relevance_score", 0.0)
        if relevance >= relevant_threshold:
            mrr = 1.0 / rank
            logger.debug(f"MRR: Found relevant fact at rank {rank}, MRR={mrr:.3f}")
            return min(mrr, 1.0)  # Cap at 1.0
    
    # No relevant facts found
    logger.debug("MRR: No relevant facts found above threshold")
    return 0.0


def calculate_aggregate_mrr(
    pipeline_results: List[Dict[str, Any]]
) -> float:
    """
    Calculate aggregate MRR across multiple evaluation results.
    
    Args:
        pipeline_results: List of results with 'mrr_score'
    
    Returns:
        Average MRR across all results
    """
    if not pipeline_results:
        return 0.0
    
    scores = [r.get("mrr_score", 0.0) for r in pipeline_results]
    avg_mrr = sum(scores) / len(scores)
    
    logger.info(f"Aggregate MRR: {avg_mrr:.3f} (n={len(scores)})")
    return avg_mrr


def score_from_ground_truth(
    generated_text: str,
    ground_truth_data: Dict[str, Any],
    company_slug: str
) -> EvaluationMetrics:
    """
    Score generated output against ground truth data.
    
    This is a template function - in practice, you would customize
    the scoring logic based on your specific evaluation criteria.
    
    Args:
        generated_text: The dashboard markdown generated by pipeline
        ground_truth_data: Ground truth facts and reference material
        company_slug: Slug of the company
    
    Returns:
        EvaluationMetrics with calculated scores
    """
    metrics = EvaluationMetrics(
        company_name=ground_truth_data.get("company_name", ""),
        company_slug=company_slug,
        pipeline_type="unknown"
    )
    
    # Placeholder scoring logic
    # In practice, this would involve:
    # 1. Named entity extraction from generated_text
    # 2. Comparison against ground_truth_data["key_facts"]
    # 3. Verification of citations/provenance
    # 4. Fact ordering analysis for MRR calculation
    
    logger.warning(
        "score_from_ground_truth is a placeholder. "
        "Implement custom scoring logic for your dataset."
    )
    
    return metrics


def compare_pipelines(
    company_slug: str,
    structured_metrics: EvaluationMetrics,
    rag_metrics: EvaluationMetrics
) -> ComparisonResult:
    """
    Create a comparison between structured and RAG pipeline metrics.
    
    Args:
        company_slug: Slug of the company
        structured_metrics: Metrics for structured pipeline
        rag_metrics: Metrics for RAG pipeline
    
    Returns:
        ComparisonResult with comparison and winners
    """
    if structured_metrics.validate() and rag_metrics.validate():
        comparison = ComparisonResult(
            company_name=structured_metrics.company_name,
            company_slug=company_slug,
            structured=structured_metrics,
            rag=rag_metrics
        )
        return comparison
    
    logger.error(f"Invalid metrics for {company_slug}")
    return None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example MRR calculation
    print("=== MRR Calculation Examples ===\n")
    
    # Perfect ranking
    facts_perfect = [
        {"relevance_score": 0.95, "text": "Founded in 2023"},
        {"relevance_score": 0.5, "text": "Based in San Francisco"},
    ]
    mrr_perfect = calculate_mrr(facts_perfect)
    print(f"Perfect ranking MRR: {mrr_perfect:.3f}")
    
    # Sub-optimal ranking
    facts_suboptimal = [
        {"relevance_score": 0.5, "text": "Based in San Francisco"},
        {"relevance_score": 0.95, "text": "Founded in 2023"},
    ]
    mrr_suboptimal = calculate_mrr(facts_suboptimal)
    print(f"Sub-optimal ranking MRR: {mrr_suboptimal:.3f}")
    
    # No relevant facts
    facts_none = [
        {"relevance_score": 0.3, "text": "Some fact"},
        {"relevance_score": 0.4, "text": "Another fact"},
    ]
    mrr_none = calculate_mrr(facts_none)
    print(f"No relevant facts MRR: {mrr_none:.3f}")
    
    # Example metrics comparison
    print("\n=== Metrics Comparison Example ===\n")
    
    struct_metrics = EvaluationMetrics(
        company_name="World Labs",
        company_slug="world-labs",
        pipeline_type="structured",
        factual_accuracy=3,
        schema_compliance=2,
        provenance_quality=2,
        hallucination_detection=2,
        readability=1,
        mrr_score=0.95,
        notes="Excellent structured output"
    )
    
    rag_metrics = EvaluationMetrics(
        company_name="World Labs",
        company_slug="world-labs",
        pipeline_type="rag",
        factual_accuracy=2,
        schema_compliance=2,
        provenance_quality=1,
        hallucination_detection=1,
        readability=1,
        mrr_score=0.75,
        notes="Good content but some hallucinations"
    )
    
    print(f"Structured Total: {struct_metrics.get_total_score():.1f}/14")
    print(f"RAG Total: {rag_metrics.get_total_score():.1f}/14")
    
    comparison = compare_pipelines("world-labs", struct_metrics, rag_metrics)
    if comparison:
        print(f"\nWinners by metric:")
        for metric in ["factual_accuracy", "schema_compliance", "provenance_quality", 
                      "hallucination_detection", "readability", "mrr_score"]:
            winner = comparison.get_winner(metric)
            print(f"  {metric}: {winner}")
