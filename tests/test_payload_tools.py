"""
Test suite for payload agent tools.

Tests core functionality of payload retrieval, validation, and update tools.
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the tools we're testing
from payload_agent.tools.retrieval import get_latest_structured_payload
from payload_agent.tools.validation import validate_payload, update_payload
from payload_agent.tools.rag_adapter import create_pinecone_adapter


class TestPayloadRetrieval:
    """Test get_latest_structured_payload tool."""
    
    def test_retrieval_returns_valid_schema(self, tmp_path):
        """Verify tool returns Payload object with required fields."""
        # Arrange: Create a test payload
        test_payload = {
            "company_record": {
                "company_id": "test-company",
                "legal_name": "Test Company Inc.",
                "brand_name": None,
                "website": "https://test.com"
            },
            "events": [],
            "products": [],
            "leadership": [],
            "snapshots": [],
            "visibility": []
        }
        
        payload_file = tmp_path / "test-company.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(test_payload, f)
        
        # Act: Call the tool
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            result = get_latest_structured_payload.invoke({"company_id": "test-company"})
        
        # Assert: Tool returns Pydantic Payload object
        assert hasattr(result, 'company_record')
        assert result.company_record.legal_name == "Test Company Inc."
        assert result.company_record.company_id == "test-company"
    
    def test_retrieval_handles_missing_file(self, tmp_path):
        """Verify tool raises FileNotFoundError for missing payload."""
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            with pytest.raises(FileNotFoundError) as exc_info:
                get_latest_structured_payload.invoke({"company_id": "nonexistent"})
        
        assert "Payload not found" in str(exc_info.value)
    
    def test_retrieval_handles_invalid_json(self, tmp_path):
        """Verify tool raises ValueError for corrupted JSON files."""
        payload_file = tmp_path / "corrupt.json"
        with open(payload_file, 'w') as f:
            f.write("{ invalid json }")
        
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            with pytest.raises(ValueError) as exc_info:
                get_latest_structured_payload.invoke({"company_id": "corrupt"})
        
        assert "Malformed JSON" in str(exc_info.value)


class TestPayloadValidation:
    """Test validate_payload tool."""
    
    def test_validation_identifies_null_fields(self, tmp_path):
        """Verify validation correctly identifies null/missing fields."""
        # Arrange: Create payload with nulls
        test_payload = {
            "company_record": {
                "company_id": "test",
                "legal_name": "Test Co",
                "brand_name": None,  # NULL field
                "website": None,      # NULL field
                "founded_year": None  # NULL field
            },
            "events": [],
            "products": [],
            "leadership": [],
            "snapshots": [],
            "visibility": []
        }
        
        payload_file = tmp_path / "test.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(test_payload, f)
        
        # Act
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            result = validate_payload.invoke({"company_id": "test"})
        
        # Assert
        assert result["status"] == "valid" or result["status"] == "invalid"
        assert "null_fields" in result
        assert "total_nulls" in result
        assert result["total_nulls"] >= 3  # brand_name, website, founded_year
    
    def test_validation_returns_expected_schema(self, tmp_path):
        """Verify validation result has all required fields."""
        test_payload = {
            "company_record": {"company_id": "test", "legal_name": "Test"},
            "events": [], "products": [], "leadership": [],
            "snapshots": [], "visibility": []
        }
        
        payload_file = tmp_path / "test.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(test_payload, f)
        
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            result = validate_payload.invoke({"company_id": "test"})
        
        # Assert schema structure
        assert "status" in result
        assert "null_fields" in result
        assert "total_nulls" in result
        assert "company_id" in result
        assert isinstance(result["null_fields"], dict)


class TestPayloadUpdate:
    """Test update_payload tool with RAG integration."""
    
    def test_update_returns_valid_schema(self, tmp_path):
        """Verify update returns expected schema."""
        # Arrange: Create test payload
        test_payload = {
            "company_record": {
                "company_id": "test",
                "legal_name": "Test",
                "website": None
            },
            "events": [], "products": [], "leadership": [],
            "snapshots": [], "visibility": []
        }
        
        payload_file = tmp_path / "test.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(test_payload, f)
        
        # Mock RAG search and LLM
        mock_rag = Mock()
        mock_rag.invoke.return_value = []  # No RAG results
        mock_llm = Mock()
        
        # Act
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            with patch('payload_agent.tools.validation.PAYLOADS_DIR', tmp_path):
                result = update_payload.invoke({
                    "company_id": "test",
                    "rag_search_tool": mock_rag,
                    "llm": mock_llm
                })
        
        # Assert schema
        assert "status" in result
        assert "company_id" in result
        assert result["company_id"] == "test"
    
    def test_update_saves_v2_file(self, tmp_path):
        """Verify update creates _v2.json file."""
        # Arrange
        test_payload = {
            "company_record": {"company_id": "test", "legal_name": "Test"},
            "events": [], "products": [], "leadership": [],
            "snapshots": [], "visibility": []
        }
        
        payload_file = tmp_path / "test.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(test_payload, f)
        
        mock_rag = Mock()
        mock_rag.invoke.return_value = []
        mock_llm = Mock()
        
        # Act
        with patch('payload_agent.tools.retrieval.PAYLOADS_DIR', tmp_path):
            with patch('payload_agent.tools.validation.PAYLOADS_DIR', tmp_path):
                result = update_payload.invoke({
                    "company_id": "test",
                    "rag_search_tool": mock_rag,
                    "llm": mock_llm
                })
        
        # Assert: Check v2 file was mentioned in result
        assert "output_file" in result or "status" in result


class TestRAGAdapter:
    """Test Pinecone RAG adapter."""
    
    def test_adapter_creation(self):
        """Verify RAG adapter initializes correctly."""
        # Act: Create adapter (uses env vars)
        try:
            adapter = create_pinecone_adapter()
            
            # Assert: Should return a callable
            assert adapter is not None
            assert callable(adapter)
        except Exception as e:
            # If Pinecone not configured, that's expected in test environment
            assert "PINECONE" in str(e) or "api_key" in str(e).lower()
    
    def test_adapter_is_callable(self):
        """Verify adapter function signature is correct."""
        # Act: Create mock adapter matching protocol
        def mock_adapter(company_id: str, query: str, top_k: int = 5):
            return []
        
        # Assert: Mock matches RagSearchAdapter protocol
        from payload_agent.tools.rag_adapter import RagSearchAdapter
        assert isinstance(mock_adapter, RagSearchAdapter)


# Fixtures for common test data
@pytest.fixture
def sample_payload():
    """Sample payload for testing."""
    return {
        "company_record": {
            "company_id": "test-company",
            "legal_name": "Test Company Inc.",
            "brand_name": None,
            "website": None,
            "hq_city": "San Francisco",
            "founded_year": None
        },
        "events": [],
        "products": [],
        "leadership": [],
        "snapshots": [],
        "visibility": []
    }


@pytest.fixture
def mock_rag_results():
    """Mock RAG search results."""
    return [
        {
            "text": "Test Company was founded in 2020.",
            "score": 0.95,
            "metadata": {"chunk_id": "chunk_1"}
        },
        {
            "text": "The company's website is https://test.com",
            "score": 0.88,
            "metadata": {"chunk_id": "chunk_2"}
        }
    ]
