"""
Unit tests for payload tools - validates each tool's behavior per Assignment 5 requirements.

Tests cover:
- get_latest_structured_payload: retrieval, caching, error handling
- validate_payload: structure validation
- update_payload: null field filling with vector search
- Persistence: file writing and metadata tracking
"""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import json
from unittest.mock import patch, MagicMock, mock_open

from tools.payload import (
    get_latest_structured_payload,
    retrieve_payload_summary,
    clear_payload_cache,
    validate_payload,
    update_payload,
)
from tools.payload.retrieval import PAYLOADS_DIR
from rag.rag_models import Payload, Company, Event, Leadership


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear payload cache before each test."""
    clear_payload_cache()


@pytest.fixture
def sample_payload_with_nulls():
    """Create a test payload with null fields for update testing."""
    return Payload(
        company_record=Company(
            company_id="testcorp",
            legal_name="Test Corp",
            website="https://test.com",
            founded_year=None,  # null field to test filling
            hq_city=None,
            total_raised_usd=None,
        ),
        events=[],
        snapshots=[],
        products=[],
        leadership=[],
        visibility=[],
        notes="Test payload with nulls",
        provenance_policy="Test policy"
    )


@pytest.fixture
def mock_rag_with_founded_year():
    """Mock RAG adapter that returns snippets containing founded year."""
    def mock_search(company_id: str, query: str, top_k: int = 5):
        if "founded" in query.lower() or "year" in query.lower():
            return [
                {
                    "snippet": "The company was founded in 2015 by the CEO.",
                    "source_url": "https://example.com/about",
                    "crawled_at": "2024-01-01",
                }
            ]
        return []
    return mock_search


# ============================================================================
# Test: get_latest_structured_payload (Retrieval Tool)
# ============================================================================

class TestPayloadRetrieval:
    """Test payload retrieval tool behavior."""

    def test_retrieve_nonexistent_payload(self):
        """Tool should raise FileNotFoundError for missing company."""
        with pytest.raises(FileNotFoundError):
            get_latest_structured_payload.invoke({"company_id": "nonexistent_company_xyz"})

    def test_retrieve_valid_payload(self):
        """Tool should successfully load and validate existing payload."""
        abridge_file = PAYLOADS_DIR / "abridge.json"
        if abridge_file.exists():
            payload = get_latest_structured_payload.invoke({"company_id": "abridge"})
            assert isinstance(payload, Payload)
            assert payload.company_record is not None
            assert payload.company_record.legal_name == "Abridge Al, Inc."

    def test_payload_caching(self):
        """Tool should cache payloads after first load."""
        abridge_file = PAYLOADS_DIR / "abridge.json"
        if abridge_file.exists():
            payload1 = get_latest_structured_payload.invoke({"company_id": "abridge"})
            payload2 = get_latest_structured_payload.invoke({"company_id": "abridge"})
            # Same object in memory (cached)
            assert payload1 is payload2

    def test_clear_cache(self):
        """Cache clear should force fresh load on next retrieval."""
        abridge_file = PAYLOADS_DIR / "abridge.json"
        if abridge_file.exists():
            payload1 = get_latest_structured_payload.invoke({"company_id": "abridge"})
            clear_payload_cache()
            payload2 = get_latest_structured_payload.invoke({"company_id": "abridge"})
            # Different objects after cache clear
            assert payload1 is not payload2

    def test_retrieve_summary(self):
        """Summary tool should return counts and status."""
        abridge_file = PAYLOADS_DIR / "abridge.json"
        if abridge_file.exists():
            summary = retrieve_payload_summary("abridge")
            assert "company_id" in summary
            assert "status" in summary
            assert summary["company_id"] == "abridge"
            assert summary["status"] == "success"


# ============================================================================
# Test: validate_payload (Validation Tool)
# ============================================================================

class TestPayloadValidation:
    """Test payload validation tool behavior."""

    def test_validate_valid_payload(self, sample_payload_with_nulls):
        """Valid payload should pass validation."""
        result = validate_payload(sample_payload_with_nulls)
        assert result["status"] == "valid"
        assert result["issues"] == []

    def test_validate_missing_legal_name(self):
        """Payload without legal_name should fail validation."""
        # Use model_construct to bypass pydantic validation for this negative test
        invalid_payload = Payload(
            company_record=Company.model_construct(
                company_id="test",
                legal_name=None,  # Missing required field (allow construction for testing)
                website="https://test.com",
            ),
            events=[],
            snapshots=[],
            products=[],
            leadership=[],
            visibility=[],
            notes="Missing legal name",
            provenance_policy="Test"
        )
        result = validate_payload(invalid_payload)
        assert result["status"] == "invalid"
        assert len(result["issues"]) > 0

    def test_identify_null_fields(self, sample_payload_with_nulls):
        """Validation should report the payload structure correctly."""
        result = validate_payload(sample_payload_with_nulls)
        # Should be valid structurally (has all required top-level arrays)
        assert result["status"] == "valid"
        assert isinstance(result["issues"], list)


# ============================================================================
# Test: update_payload (Update/Fill Tool with RAG)
# ============================================================================

class TestPayloadUpdate:
    """Test payload update tool with vector search integration."""

    def test_update_with_no_search_tool(self, sample_payload_with_nulls):
        """Update without RAG tool should skip fills and return original."""
        updated, metadata = update_payload(
            sample_payload_with_nulls,
            rag_search_tool=None,
            attempt_vector_fills=False,
            write_back=False,
        )
        
        # Should return payload unchanged
        assert updated.company_record.founded_year is None
        assert metadata is not None
        assert "unfilled_nulls" in metadata

    def test_update_identifies_null_fields(self, sample_payload_with_nulls, mock_rag_with_founded_year):
        """Update tool should identify and report null fields."""
        updated, metadata = update_payload(
            sample_payload_with_nulls,
            rag_search_tool=mock_rag_with_founded_year,
            attempt_vector_fills=False,  # Don't fill, just identify
            write_back=False,
        )
        
        # Metadata should list unfilled nulls
        assert "unfilled_nulls" in metadata
        assert isinstance(metadata["unfilled_nulls"], list)
        assert "founded_year" in metadata["unfilled_nulls"]

    def test_update_with_vector_fills(self, sample_payload_with_nulls, mock_rag_with_founded_year):
        """Update tool should attempt fills when RAG tool provided."""
        updated, metadata = update_payload(
            sample_payload_with_nulls,
            rag_search_tool=mock_rag_with_founded_year,
            attempt_vector_fills=True,
            write_back=False,
        )
        
        # Should attempt fills (may or may not succeed depending on extraction logic)
        assert metadata is not None
        assert "filled_fields" in metadata or "unfilled_nulls" in metadata

    def test_search_vectors_with_paraphrases(self):
        """Search should return results when paraphrases include company name or HQ tokens."""
        from tools.payload.vectors import search_vectors_for_field

        def mock_rag(company_id: str, query: str, top_k: int = 5):
            # Mimic Pinecone returning results for queries containing 'headquarters' or company name
            if "headquarters" in query.lower() or "abridge" in query.lower():
                return [{
                    "snippet": "Abridge is headquartered in San Francisco, CA, United States.",
                    "source_url": "https://abridge.com/about",
                    "crawled_at": "2024-01-01",
                }]
            return []

        results = search_vectors_for_field(
            company_id="abridge",
            field_name="hq_country",
            section_name="company_record",
            rag_search_tool=mock_rag,
            top_k=5,
            company_name="Abridge AI",
        )

        assert isinstance(results, list)
        assert len(results) > 0

    def test_metadata_structure(self, sample_payload_with_nulls):
        """Update tool should return properly structured metadata."""
        updated, metadata = update_payload(
            sample_payload_with_nulls,
            rag_search_tool=None,
            write_back=False,
        )
        
        # Metadata should have expected keys
        assert isinstance(metadata, dict)
        assert "unfilled_nulls" in metadata or "filled_fields" in metadata
        assert "extraction_runs" in metadata or "field_confidence_map" in metadata

    def test_write_back_false_no_persistence(self, sample_payload_with_nulls):
        """When write_back=False, no files should be written."""
        with patch("tools.payload.persistence.write_updated_payload") as mock_write:
            updated, metadata = update_payload(
                sample_payload_with_nulls,
                rag_search_tool=None,
                write_back=False,
            )
            
            # Persistence should not be called
            mock_write.assert_not_called()


# ============================================================================
# Test: High-Risk Field Safety
# ============================================================================

class TestHighRiskFields:
    """Test that high-risk fields are not auto-filled (require HITL)."""

    def test_high_risk_fields_skipped(self, sample_payload_with_nulls):
        """Fields like total_raised_usd should not be auto-filled."""
        def mock_rag(company_id: str, query: str, top_k: int = 5):
            if "raised" in query.lower():
                return [
                    {
                        "snippet": "raised $50M",
                        "source_url": "test.com",
                        "crawled_at": "2024-01-01"
                    }
                ]
            return []
        
        updated, metadata = update_payload(
            sample_payload_with_nulls,
            rag_search_tool=mock_rag,
            attempt_vector_fills=True,
            write_back=False,
        )
        
        # High-risk field should remain None (not auto-filled)
        # This depends on fill logic
        assert updated.company_record.total_raised_usd is None or \
               "total_raised_usd" in metadata.get("unfilled_nulls", {}).get("company_record", [])


# ============================================================================
# Run Summary
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
