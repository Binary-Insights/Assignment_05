"""
Test suite for Tavily Agent workflow and enrichment logic.

Tests the LangGraph workflow state machine, Tavily search integration,
LLM extraction, and payload enrichment flow.
"""

import pytest
import sys
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tavily_agent.main import AgenticRAGOrchestrator
from tavily_agent.graph import PayloadEnrichmentState, build_enrichment_graph
from tavily_agent.tools import ToolManager
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.llm_extraction import LLMExtractionChain
from langgraph.graph import END


# ===========================
# Fixtures
# ===========================

@pytest.fixture
def sample_payload():
    """Sample payload with null fields for testing."""
    return {
        "company_record": {
            "company_id": "test_company",
            "legal_name": None,  # Null field
            "brand_name": "Test Company",
            "website": None,  # Null field
            "hq_city": "San Francisco",
            "hq_state": None,  # Null field
            "founded_year": 2020,
            "total_raised_usd": None,  # Null field
            "categories": ["AI", "Healthcare"]
        },
        "events": [],
        "products": [],
        "leadership": [],
        "snapshots": [],
        "visibility": []
    }


@pytest.fixture
def sample_enriched_payload(sample_payload):
    """Sample enriched payload with filled fields."""
    enriched = sample_payload.copy()
    enriched["company_record"]["legal_name"] = "Test Company Inc."
    enriched["company_record"]["website"] = "https://testcompany.ai"
    enriched["company_record"]["hq_state"] = "CA"
    enriched["company_record"]["total_raised_usd"] = 50000000
    return enriched


@pytest.fixture
def mock_tavily_response():
    """Mock Tavily API search response."""
    return {
        "results": [
            {
                "title": "Test Company - About Us",
                "url": "https://testcompany.ai/about",
                "content": "Test Company Inc. was founded in 2020 in San Francisco, CA. We've raised $50M in funding.",
                "score": 0.95
            },
            {
                "title": "Test Company Funding",
                "url": "https://crunchbase.com/test-company",
                "content": "Test Company secured $50 million in Series A funding led by Sequoia Capital.",
                "score": 0.92
            }
        ],
        "query": "Test Company legal name headquarters funding"
    }


@pytest.fixture
def mock_llm_extraction_result():
    """Mock LLM extraction result."""
    return {
        "legal_name": {
            "value": "Test Company Inc.",
            "confidence": 0.95,
            "provenance": {
                "source_name": "Company Website",
                "source_url": "https://testcompany.ai/about",
                "quote": "Test Company Inc. was founded in 2020"
            }
        },
        "website": {
            "value": "https://testcompany.ai",
            "confidence": 0.98,
            "provenance": {
                "source_name": "Company Website",
                "source_url": "https://testcompany.ai",
                "quote": "Visit us at https://testcompany.ai"
            }
        }
    }


# ===========================
# Test ToolManager (Tavily Search)
# ===========================

class TestToolManager:
    """Test Tavily search tool integration."""
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_search_tavily_success(self, mock_post, mock_tavily_response):
        """Test successful Tavily search via HTTP API."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tavily_response
        mock_response.raise_for_status = Mock()
        
        # Create async context manager mock
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        tool_manager = ToolManager()
        
        # Act
        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tool_manager.search_tavily(
                query="Test Company funding",
                company_name="test_company",
                topic="funding"
            )
        
        # Assert - match actual return format
        assert result["success"] == True
        assert result["tool"] == "tavily"
        assert "results" in result
        assert len(result["results"]) == 2
        assert "raw_content" in result
        assert result["count"] == 2
    
    @pytest.mark.asyncio
    async def test_search_tavily_api_error(self):
        """Test Tavily API error handling."""
        # Arrange
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=Exception("API Error"))
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        tool_manager = ToolManager()
        
        # Act
        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tool_manager.search_tavily(
                query="test query",
                company_name="test_company"
            )
        
        # Assert - match actual error return format
        assert result["success"] == False
        assert "error" in result
        assert result["count"] == 0
    
    @pytest.mark.asyncio
    async def test_search_tavily_timeout(self):
        """Test Tavily search timeout handling."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(side_effect=asyncio.TimeoutError("Request timeout"))
        
        tool_manager = ToolManager()
        
        # Act
        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await tool_manager.search_tavily(
                query="test query",
                company_name="test_company"
            )
        
        # Assert - match actual timeout return format
        assert result["success"] == False
        assert result["error"] == "Search timeout"
        assert result["count"] == 0


# ===========================
# Test LLMExtractionChain
# ===========================

class TestLLMExtractionChain:
    """Test LLM-based extraction from search results."""
    
    @pytest.mark.asyncio
    async def test_llm_extraction_success(self, mock_tavily_response):
        """Test successful LLM extraction from search results."""
        # Arrange
        mock_question = Mock()
        mock_question.question = "What is the legal name of Test Company?"
        
        mock_extracted = Mock()
        mock_extracted.extracted_value = "Test Company Inc."
        mock_extracted.confidence = 0.95
        mock_extracted.reasoning = "Found in company website"
        mock_extracted.sources = ["https://testcompany.ai/about"]
        
        extractor = LLMExtractionChain()
        
        # Mock the chain steps
        with patch.object(extractor, 'generate_extraction_question', return_value=mock_question):
            with patch.object(extractor, 'extract_value_from_context', return_value=mock_extracted):
                with patch.object(extractor, 'validate_and_refine', return_value=mock_extracted):
                    # Act
                    result = await extractor.run_extraction_chain(
                        field_name="legal_name",
                        entity_type="company_record",
                        company_name="Test Company",
                        importance="high",
                        search_results=mock_tavily_response["results"]
                    )
                    
                    # Assert
                    assert result.field_name == "legal_name"
                    assert result.final_value == "Test Company Inc."
                    assert result.confidence >= 0.9
    
    @pytest.mark.asyncio
    async def test_llm_extraction_low_confidence(self, mock_tavily_response):
        """Test LLM extraction with low confidence values."""
        # Arrange
        mock_question = Mock()
        mock_question.question = "What is the legal name of Test Company?"
        
        mock_extracted = Mock()
        mock_extracted.extracted_value = "Test Company"
        mock_extracted.confidence = 0.3  # Low confidence
        mock_extracted.reasoning = "Limited information available"
        mock_extracted.sources = []
        
        extractor = LLMExtractionChain()
        
        # Mock the chain steps
        with patch.object(extractor, 'generate_extraction_question', return_value=mock_question):
            with patch.object(extractor, 'extract_value_from_context', return_value=mock_extracted):
                with patch.object(extractor, 'validate_and_refine', return_value=mock_extracted):
                    # Act
                    result = await extractor.run_extraction_chain(
                        field_name="legal_name",
                        entity_type="company_record",
                        company_name="Test Company",
                        importance="high",
                        search_results=mock_tavily_response["results"]
                    )
                    
                    # Assert - final_value should be None for low confidence
                    assert result.confidence < 0.5
                    assert result.final_value is None


# ===========================
# Test PayloadEnrichmentState
# ===========================

class TestPayloadEnrichmentState:
    """Test workflow state management."""
    
    def test_state_initialization(self, sample_payload):
        """Test state initialization with payload."""
        # Act
        state = PayloadEnrichmentState(
            company_name="test_company",
            company_id="test_company",
            current_payload=sample_payload,
            original_payload=sample_payload.copy()
        )
        
        # Assert
        assert state.company_name == "test_company"
        assert state.iteration == 0
        assert state.status == "initialized"
        assert len(state.null_fields) == 0  # Gets populated in analyze_payload node
        assert len(state.messages) == 0
    
    def test_state_tracks_null_fields(self, sample_payload):
        """Test state correctly identifies null fields."""
        # Arrange
        state = PayloadEnrichmentState(
            company_name="test_company",
            company_id="test_company",
            current_payload=sample_payload,
            original_payload=sample_payload.copy()
        )
        
        # Manually populate null_fields (normally done by analyze_payload node)
        company_record = sample_payload["company_record"]
        null_fields = [
            {"path": f"company_record.{key}", "value": None}
            for key, value in company_record.items()
            if value is None
        ]
        state.null_fields = null_fields
        
        # Assert
        assert len(state.null_fields) == 4  # legal_name, website, hq_state, total_raised_usd
        field_paths = [f["path"] for f in state.null_fields]
        assert "company_record.legal_name" in field_paths
        assert "company_record.website" in field_paths


# ===========================
# Test AgenticRAGOrchestrator
# ===========================

class TestAgenticRAGOrchestrator:
    """Test main orchestrator workflow."""
    
    @pytest.mark.asyncio
    @patch('tavily_agent.main.build_enrichment_graph')
    @patch('tavily_agent.main.validate_config')
    async def test_orchestrator_initialization(self, mock_validate, mock_build_graph):
        """Test orchestrator initialization."""
        # Arrange
        mock_validate.return_value = True
        mock_build_graph.return_value = Mock()
        
        orchestrator = AgenticRAGOrchestrator()
        
        # Act
        await orchestrator.initialize()
        
        # Assert
        assert orchestrator.graph is not None
        mock_validate.assert_called_once()
        mock_build_graph.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('tavily_agent.file_io_manager.FileIOManager.read_payload')
    @patch('tavily_agent.file_io_manager.FileIOManager.backup_payload')
    @patch('tavily_agent.file_io_manager.FileIOManager.save_payload')
    async def test_process_single_company_success(
        self, 
        mock_save, 
        mock_backup, 
        mock_read,
        sample_payload,
        sample_enriched_payload
    ):
        """Test successful single company processing."""
        # Arrange
        mock_read.return_value = sample_payload
        mock_backup.return_value = True
        mock_save.return_value = True
        
        orchestrator = AgenticRAGOrchestrator()
        
        # Mock the workflow execution
        mock_final_state = PayloadEnrichmentState(
            company_name="test_company",
            company_id="test_company",
            current_payload=sample_enriched_payload,
            original_payload=sample_payload,
            extracted_values={
                "legal_name": "Test Company Inc.",
                "website": "https://testcompany.ai",
                "hq_state": "CA",
                "total_raised_usd": 50000000
            },
            iteration=1,
            status="completed"
        )
        
        with patch.object(orchestrator, '_execute_workflow', return_value=mock_final_state):
            # Act
            result = await orchestrator.process_single_company("test_company")
            
            # Assert
            assert result["status"] == "completed"
            assert result["company_name"] == "test_company"
            assert result["null_fields_filled"] == 4
            assert len(result["errors"]) == 0
            mock_read.assert_called_once_with("test_company")
            mock_backup.assert_called_once()
            mock_save.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('tavily_agent.file_io_manager.FileIOManager.read_payload')
    async def test_process_single_company_read_failure(self, mock_read):
        """Test handling of payload read failure."""
        # Arrange
        mock_read.return_value = None  # Simulate read failure
        
        orchestrator = AgenticRAGOrchestrator()
        
        # Act
        result = await orchestrator.process_single_company("test_company")
        
        # Assert
        assert result["status"] == "failed"
        assert "Could not read payload file" in result["errors"]
    
    @pytest.mark.asyncio
    @patch('tavily_agent.file_io_manager.FileIOManager.read_payload')
    @patch('tavily_agent.file_io_manager.FileIOManager.backup_payload')
    async def test_process_single_company_exception_handling(self, mock_backup, mock_read, sample_payload):
        """Test exception handling during processing."""
        # Arrange
        mock_read.return_value = sample_payload
        mock_backup.side_effect = Exception("Backup failed")
        
        orchestrator = AgenticRAGOrchestrator()
        
        # Act
        result = await orchestrator.process_single_company("test_company")
        
        # Assert
        assert result["status"] == "failed"
        assert len(result["errors"]) > 0
        assert "Backup failed" in result["errors"][0]


# ===========================
# Test Workflow Graph Nodes
# ===========================

class TestWorkflowNodes:
    """Test individual workflow node functions."""
    
    def test_search_node_basic_structure(self):
        """Test search node basic structure and state handling."""
        # Arrange
        from tavily_agent.graph import execute_searches
        
        # Just verify the function exists and is callable
        # Full testing requires actual tool integration
        assert callable(execute_searches)
        
        # Test that it expects correct state type
        state = PayloadEnrichmentState(
            company_name="test_company",
            company_id="test_company",
            current_payload={"company_record": {}},
            original_payload={"company_record": {}},
            messages=[]
        )
        
        # Verify state is valid
        assert state.company_name == "test_company"
    
    # NOTE: update_payload is not a standalone function in graph.py
    # Payload updates happen in extract_and_update_payload node


# ===========================
# Test Workflow Branch Logic
# ===========================

class TestWorkflowBranchLogic:
    """Test conditional workflow branches."""
    
    def test_check_completion_with_null_fields_remaining(self):
        """Test workflow continues when null fields remain."""
        from tavily_agent.graph import check_completion
        
        # Arrange - create valid state with null fields
        state = PayloadEnrichmentState(
            company_name="test",
            company_id="test",
            current_payload={"company_record": {"field1": None, "field2": None}},
            original_payload={"company_record": {"field1": None, "field2": None}},
            messages=[],
            iteration=1,
            max_iterations=10
        )
        # Manually add null_fields as dicts
        state.null_fields = [
            {"path": "company_record.field1", "importance": "high", "value": None},
            {"path": "company_record.field2", "importance": "low", "value": None}
        ]
        
        # Act
        result = check_completion(state)
        
        # Assert
        assert result == "continue"  # Should continue processing
    
    def test_check_completion_when_max_iterations_reached(self):
        """Test workflow stops at max iterations."""
        from tavily_agent.graph import check_completion
        
        # Arrange
        state = PayloadEnrichmentState(
            company_name="test",
            company_id="test",
            current_payload={},
            original_payload={},
            null_fields=[{"path": "field1", "importance": "high"}],
            iteration=100,  # At max
            max_iterations=100
        )
        
        # Act
        result = check_completion(state)
        
        # Assert
        assert result == END  # Should stop
    
    def test_check_completion_when_no_null_fields(self):
        """Test workflow stops when all fields filled."""
        from tavily_agent.graph import check_completion
        
        # Arrange
        state = PayloadEnrichmentState(
            company_name="test",
            company_id="test",
            current_payload={},
            original_payload={},
            null_fields=[],  # No null fields
            iteration=1,
            max_iterations=10
        )
        
        # Act
        result = check_completion(state)
        
        # Assert
        assert result == END  # Should stop


# ===========================
# Integration Tests
# ===========================

class TestEndToEndWorkflow:
    """Integration tests for complete workflow."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @patch('tavily_agent.tools.ToolManager.search_tavily')
    @patch('tavily_agent.llm_extraction.LLMExtractionChain.run_extraction_chain')
    @patch('tavily_agent.file_io_manager.FileIOManager.read_payload')
    @patch('tavily_agent.file_io_manager.FileIOManager.save_payload')
    @patch('tavily_agent.file_io_manager.FileIOManager.backup_payload')
    async def test_complete_enrichment_flow(
        self,
        mock_backup,
        mock_save,
        mock_read,
        mock_extract,
        mock_search,
        sample_payload,
        mock_tavily_response,
        mock_llm_extraction_result
    ):
        """Test complete enrichment flow from start to finish."""
        # Arrange
        mock_read.return_value = sample_payload
        mock_backup.return_value = True
        mock_save.return_value = True
        mock_search.return_value = {
            "success": True,
            "tool": "tavily",
            "results": mock_tavily_response["results"],
            "count": 2,
            "raw_content": "Test content"
        }
        
        # Mock ChainedExtractionResult as a proper Pydantic model
        from tavily_agent.llm_extraction import ChainedExtractionResult
        
        mock_result = ChainedExtractionResult(
            field_name="legal_name",
            final_value="Test Company Inc.",
            confidence=0.95,
            chain_steps=["step1", "step2"],
            reasoning="Found in search results",
            sources=["https://testcompany.ai"]
        )
        mock_extract.return_value = mock_result
        
        orchestrator = AgenticRAGOrchestrator()
        await orchestrator.initialize(with_checkpointing=False)
        
        # Act
        result = await orchestrator.process_single_company("test_company")
        
        # Assert
        assert result["status"] in ["completed", "started"]  # May vary based on mocks
        assert result["company_name"] == "test_company"
        assert "null_fields_found" in result
        assert "null_fields_filled" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
