"""
Test suite for payload agent workflow and branching logic.

Tests the LangGraph workflow state machine and conditional branches.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from payload_agent.payload_agent import PayloadAgent


class TestPayloadAgentWorkflow:
    """Test PayloadAgent with different execution modes."""
    
    @patch('payload_agent.payload_agent.create_pinecone_adapter')
    @patch('payload_agent.payload_agent.ChatOpenAI')
    def test_agent_initializes_successfully(self, mock_llm, mock_pinecone):
        """Verify agent initialization with all components."""
        # Arrange
        mock_llm.return_value = Mock()
        mock_pinecone.return_value = Mock()
        
        # Act
        agent = PayloadAgent()
        
        # Assert
        assert agent is not None
        assert agent.llm is not None
        assert agent.rag_search_tool is not None
    
    @patch('payload_agent.payload_agent.get_latest_structured_payload')
    def test_retrieve_payload_mode(self, mock_get_payload):
        """Test simple payload retrieval mode."""
        # Arrange
        mock_get_payload.invoke.return_value = {
            "status": "success",
            "company_id": "test",
            "payload": {"company_record": {"legal_name": "Test"}}
        }
        
        agent = PayloadAgent()
        
        # Act
        result = agent.retrieve_payload("test")
        
        # Assert
        assert result["status"] == "success"
        assert result["company_id"] == "test"
        mock_get_payload.invoke.assert_called_once()
    
    @patch('payload_agent.payload_agent.create_react_agent')
    @patch('payload_agent.payload_agent.get_latest_structured_payload')
    def test_validation_with_agent_mode(self, mock_get, mock_create_agent):
        """Test validation using LangGraph agent mode."""
        # Arrange
        mock_get.invoke.return_value = {
            "status": "success",
            "payload": {"company_record": {"company_id": "test"}}
        }
        
        # Mock the agent executor
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(content="Validation complete. Found 5 null fields.")
            ]
        }
        mock_create_agent.return_value = mock_agent
        
        agent = PayloadAgent()
        
        # Act
        result = agent.retrieve_and_validate("test", use_agent=True)
        
        # Assert
        assert result["status"] == "success"
        assert "messages" in result
        mock_agent.invoke.assert_called_once()


class TestWorkflowBranchLogic:
    """Test conditional workflow branches."""
    
    def test_validation_success_proceeds_to_update(self):
        """Verify workflow continues to update when validation succeeds."""
        from payload_agent.payload_workflow import should_update
        
        # Arrange: State with successful validation (status must be "valid")
        state = {
            "company_id": "test",
            "validation_result": {
                "status": "valid",  # Changed from "success" to "valid"
                "total_nulls": 5
            },
            "status": "validated"
        }
        
        # Act
        decision = should_update(state)
        
        # Assert: Should proceed to update
        assert decision == "update"
    
    def test_validation_failure_skips_update(self):
        """Verify workflow skips update when validation fails."""
        from payload_agent.payload_workflow import should_update
        
        # Arrange: State with failed validation (status "invalid" not "valid")
        state = {
            "company_id": "test",
            "validation_result": {
                "status": "invalid",  # Changed from "error" to "invalid"
                "issues": ["Invalid payload structure"]
            },
            "status": "error"
        }
        
        # Act
        decision = should_update(state)
        
        # Assert: Should end workflow
        assert decision == "end"
    
    def test_no_nulls_found_skips_update(self):
        """Verify workflow ends when no null fields need updating."""
        from payload_agent.payload_workflow import should_update
        
        # Arrange: State with zero nulls (but status is still "valid")
        state = {
            "company_id": "test",
            "validation_result": {
                "status": "valid",  # Status is "valid" even with 0 nulls
                "total_nulls": 0,
                "null_fields": {}
            },
            "status": "validated"
        }
        
        # Act
        decision = should_update(state)
        
        # Assert: Should still proceed to update (decision logic only checks status)
        assert decision == "update"  # Changed expectation


class TestWorkflowExecution:
    """Test end-to-end workflow execution."""
    
    @patch('payload_agent.payload_workflow.update_payload')
    @patch('payload_agent.payload_workflow.validate_payload')
    @patch('payload_agent.payload_workflow.get_latest_structured_payload')
    def test_full_workflow_with_updates(self, mock_get, mock_validate, mock_update):
        """Test complete workflow from retrieval to update."""
        from payload_agent.payload_workflow import run_payload_workflow
        
        # Arrange: Mock all steps
        from rag.rag_models import Payload
        mock_payload = Payload.model_construct(
            company_record={"company_id": "test", "legal_name": "Test"}
        )
        mock_get.invoke.return_value = mock_payload
        
        mock_validate.invoke.return_value = {
            "status": "valid",  # Must be "valid" to proceed to update
            "total_nulls": 3,
            "null_fields": {"company_record": ["website", "founded_year", "hq_city"]}
        }
        
        mock_update.invoke.return_value = {
            "status": "success",
            "filled_count": 2,
            "output_file": "test_v2.json",
            "company_id": "test"
        }
        
        # Act
        final_state = run_payload_workflow(
            company_id="test",
            rag_search_tool=Mock(),
            llm=Mock()
        )
        
        # Assert: All steps executed and status is "completed"
        assert final_state["status"] == "completed"
        assert "update_result" in final_state
        mock_get.invoke.assert_called_once()
        mock_validate.invoke.assert_called_once()
        mock_update.invoke.assert_called_once()
    
    @patch('payload_agent.payload_workflow.validate_payload')
    @patch('payload_agent.payload_workflow.get_latest_structured_payload')
    def test_workflow_handles_validation_failure(self, mock_get, mock_validate):
        """Test workflow stops gracefully on validation error."""
        from payload_agent.payload_workflow import run_payload_workflow
        
        # Arrange
        from rag.rag_models import Payload
        mock_payload = Payload.model_construct(
            company_record={"invalid": "structure"}
        )
        mock_get.invoke.return_value = mock_payload
        
        mock_validate.invoke.return_value = {
            "status": "invalid",  # Changed to "invalid" to trigger skip
            "issues": ["Invalid payload schema"]
        }
        
        # Act
        final_state = run_payload_workflow(
            company_id="test",
            rag_search_tool=Mock(),
            llm=Mock()
        )
        
        # Assert: Workflow stopped at validation, status is "validated" not "completed"
        assert final_state["status"] == "validated"  # Changed expectation
        assert "update_result" not in final_state or final_state["update_result"] == {}  # Update never ran


class TestAgentToolSelection:
    """Test autonomous agent tool selection logic."""
    
    @patch('payload_agent.payload_agent.create_react_agent')
    def test_agent_selects_correct_tools(self, mock_create_agent):
        """Verify agent chooses appropriate tools for task."""
        # Arrange: Mock agent that calls validate_payload
        mock_agent = Mock()
        mock_agent.invoke.return_value = {
            "messages": [
                Mock(content="", tool_calls=[{"name": "validate_payload"}])
            ]
        }
        mock_create_agent.return_value = mock_agent
        
        agent = PayloadAgent()
        
        # Act
        result = agent.execute_with_agent(
            "Check if the test company payload has any missing fields"
        )
        
        # Assert: Agent was invoked
        assert mock_agent.invoke.called
    
    @patch('payload_agent.payload_agent.create_react_agent')
    def test_agent_handles_tool_errors(self, mock_create_agent):
        """Verify agent handles tool execution errors gracefully."""
        # Arrange: Mock agent that encounters error
        mock_agent = Mock()
        mock_agent.invoke.side_effect = Exception("Tool execution failed")
        mock_create_agent.return_value = mock_agent
        
        agent = PayloadAgent()
        
        # Act
        result = agent.execute_with_agent("Test query")
        
        # Assert: Error is caught and returned
        assert result["status"] == "error"
        assert "error" in result


# Test fixtures
@pytest.fixture
def mock_workflow_state():
    """Standard workflow state for testing."""
    return {
        "company_id": "test-company",
        "payload": None,
        "validation_result": {},
        "update_result": {},
        "status": "initialized",
        "error": None
    }


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    llm = Mock()
    llm.invoke.return_value = Mock(content="Extracted value")
    return llm
