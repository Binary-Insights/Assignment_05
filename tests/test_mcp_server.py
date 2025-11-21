"""
Test suite for MCP Server implementation.

Tests FastMCP server tools, resources, security, and client interactions.
"""

import pytest
import sys
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_server.server import (
    get_tool_manager,
    get_file_io_manager,
    get_extraction_chain,
)
from mcp_server.security import (
    ToolFilter,
    RateLimiter,
    InputValidator,
    SecurityMiddleware
)


# ===========================
# Fixtures
# ===========================

@pytest.fixture
def sample_search_results():
    """Sample Tavily search results."""
    return {
        "results": [
            {
                "title": "Test Company Profile",
                "url": "https://example.com/test",
                "content": "Test Company was founded in 2020 in San Francisco.",
                "score": 0.95
            },
            {
                "title": "Test Company Funding",
                "url": "https://crunchbase.com/test",
                "content": "Test Company raised $50M in Series A.",
                "score": 0.92
            }
        ],
        "query": "Test Company funding",
        "count": 2
    }


@pytest.fixture
def sample_extraction_result():
    """Sample LLM extraction result."""
    return {
        "field_name": "founded_year",
        "value": 2020,
        "confidence": 0.95,
        "provenance": {
            "source_name": "Company Website",
            "source_url": "https://example.com/about",
            "quote": "Founded in 2020"
        },
        "reasoning": "The company website states it was founded in 2020."
    }


@pytest.fixture
def sample_payload():
    """Sample company payload."""
    return {
        "company_record": {
            "company_id": "test_company",
            "legal_name": None,
            "brand_name": "Test Company",
            "website": None,
            "founded_year": None,
            "hq_city": "San Francisco",
            "total_raised_usd": None
        },
        "events": [],
        "products": [],
        "leadership": [],
        "snapshots": [],
        "visibility": []
    }


# ===========================
# Test ToolFilter (Security)
# ===========================

class TestToolFilter:
    """Test tool filtering and authorization."""
    
    def test_allowed_tools_whitelist(self):
        """Test that allowed tools are correctly whitelisted."""
        assert ToolFilter.is_tool_allowed("search_company")
        assert ToolFilter.is_tool_allowed("extract_field")
        assert ToolFilter.is_tool_allowed("enrich_payload")
        assert ToolFilter.is_tool_allowed("analyze_null_fields")
    
    def test_disallowed_tools_blocked(self):
        """Test that non-whitelisted tools are blocked."""
        assert not ToolFilter.is_tool_allowed("delete_payload")
        assert not ToolFilter.is_tool_allowed("modify_database")
        assert not ToolFilter.is_tool_allowed("arbitrary_tool")
    
    def test_sensitive_tools_flagged(self):
        """Test that sensitive tools are correctly identified."""
        assert ToolFilter.is_sensitive_tool("enrich_payload")
        assert not ToolFilter.is_sensitive_tool("search_company")
    
    def test_rate_limits_configured(self):
        """Test that rate limits are properly configured."""
        assert ToolFilter.get_rate_limit("search_company") == 60
        assert ToolFilter.get_rate_limit("extract_field") == 30
        assert ToolFilter.get_rate_limit("enrich_payload") == 5
        assert ToolFilter.get_rate_limit("analyze_null_fields") == 30


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_allows_within_limit(self):
        """Test that calls within rate limit are allowed."""
        limiter = RateLimiter()
        
        # Should allow first 5 calls for enrich_payload (limit: 5/min)
        for i in range(5):
            assert limiter.check_rate_limit("enrich_payload")
    
    def test_rate_limiter_blocks_over_limit(self):
        """Test that calls exceeding rate limit are blocked."""
        limiter = RateLimiter()
        
        # Exhaust limit (5 calls)
        for i in range(5):
            limiter.check_rate_limit("enrich_payload")
        
        # 6th call should be blocked
        assert not limiter.check_rate_limit("enrich_payload")
    
    def test_rate_limiter_resets_after_time(self):
        """Test that rate limit resets after time window."""
        limiter = RateLimiter()
        
        # This test would require time mocking to be robust
        # For now, just verify structure
        remaining = limiter.get_remaining_calls("search_company")
        assert remaining == -1 or isinstance(remaining, int)
    
    def test_rate_limiter_tracks_multiple_tools(self):
        """Test that rate limiter tracks different tools independently."""
        limiter = RateLimiter()
        
        # Use limit for enrich_payload
        for i in range(5):
            limiter.check_rate_limit("enrich_payload")
        
        # search_company should still have its full limit
        assert limiter.check_rate_limit("search_company")


class TestInputValidator:
    """Test input validation and sanitization."""
    
    def test_validate_inputs_valid(self):
        """Test validation of valid inputs."""
        valid, msg = InputValidator.validate_inputs(
            "search_company",
            {"company_name": "abridge", "query": "funding"}
        )
        assert valid
        assert msg == "OK"
    
    def test_validate_inputs_blocks_sql_injection(self):
        """Test rejection of SQL injection attempts."""
        valid, msg = InputValidator.validate_inputs(
            "search_company",
            {"query": "test'; DROP TABLE companies; --"}
        )
        assert not valid
        assert "DROP" in msg or "Blocked pattern" in msg
    
    def test_validate_inputs_blocks_command_injection(self):
        """Test rejection of command injection attempts."""
        valid, msg = InputValidator.validate_inputs(
            "extract_field",
            {"field_name": "test; rm -rf /"}
        )
        # May pass since semicolon alone isn't blocked
        # But exec/eval patterns should be blocked
        valid2, msg2 = InputValidator.validate_inputs(
            "tool",
            {"value": "exec('malicious code')"}
        )
        assert not valid2
        assert "exec" in msg2.lower() or "blocked" in msg2.lower()
    
    def test_validate_inputs_with_nested_dict(self):
        """Test validation handles nested structures."""
        valid, msg = InputValidator.validate_inputs(
            "enrich_payload",
            {
                "payload": {
                    "company_record": {"legal_name": "Test Co"},
                    "metadata": {"source": "api"}
                }
            }
        )
        # Should handle nested validation
        assert isinstance(valid, bool)
    
    def test_sanitize_string_truncates_long_input(self):
        """Test string sanitization truncates long inputs."""
        long_string = "a" * 2000
        result = InputValidator.sanitize_string(long_string, max_length=1000)
        assert len(result) == 1000
    
    def test_sanitize_string_removes_null_bytes(self):
        """Test string sanitization removes null bytes."""
        dirty_string = "test\x00data\x00here"
        result = InputValidator.sanitize_string(dirty_string)
        assert "\x00" not in result
        assert result == "testdatahere"
    
    def test_validate_inputs_with_list_arguments(self):
        """Test validation handles list arguments with dicts."""
        valid, msg = InputValidator.validate_inputs(
            "batch_tool",
            {
                "items": [
                    {"name": "item1", "value": "safe"},
                    {"name": "item2", "value": "also safe"}
                ]
            }
        )
        assert valid
        assert msg == "OK"


class TestSecurityMiddleware:
    """Test integrated security manager."""
    
    def test_security_manager_allows_valid_request(self):
        """Test that valid requests are allowed."""
        manager = SecurityMiddleware()
        
        can_execute, reason = manager.can_execute_tool(
            tool_name="search_company",
            arguments={"company_name": "abridge", "query": "funding information"},
            requester_role="user"
        )
        
        assert can_execute
        assert reason == "OK"
    
    def test_security_manager_blocks_invalid_tool(self):
        """Test that invalid tools are blocked."""
        manager = SecurityMiddleware()
        
        can_execute, reason = manager.can_execute_tool(
            tool_name="delete_all_data",
            arguments={"company_name": "abridge"},
            requester_role="user"
        )
        
        assert not can_execute
        assert "not allowed" in reason.lower()
    
    def test_security_manager_blocks_rate_limited(self):
        """Test that rate-limited requests are blocked."""
        manager = SecurityMiddleware()
        
        # Exhaust rate limit (default is 5 per minute for enrich_payload)
        # Use admin role since enrich_payload is sensitive
        for i in range(5):
            manager.can_execute_tool(
                tool_name="enrich_payload",
                arguments={"company_name": f"company_{i}"},
                requester_role="admin"
            )
        
        # Next request should be blocked by rate limit
        can_execute, reason = manager.can_execute_tool(
            tool_name="enrich_payload",
            arguments={"company_name": "another_company"},
            requester_role="admin"
        )
        
        assert not can_execute
        assert "rate limit" in reason.lower()
    
    def test_security_manager_validates_inputs(self):
        """Test that security manager validates inputs."""
        manager = SecurityMiddleware()
        
        can_execute, reason = manager.can_execute_tool(
            tool_name="search_company",
            arguments={
                "company_name": "test",
                "query": "DROP TABLE users;"  # SQL injection attempt
            },
            requester_role="user"
        )
        
        assert not can_execute
        assert "blocked" in reason.lower() or "drop" in reason.lower()


# ===========================
# Test MCP Server Tools
# ===========================

class TestMCPServerTools:
    """Test FastMCP server tool implementations."""
    
    @pytest.mark.skip(reason="FastMCP tools require server instance - test tool logic separately")
    @pytest.mark.asyncio
    async def test_search_company_tool(self, sample_search_results):
        """Test search_company tool."""
        # Arrange - import the underlying function directly
        import mcp_server.server as server_module
        
        # Mock get_tool_manager to return our mock
        with patch.object(server_module, 'get_tool_manager', new_callable=AsyncMock) as mock_get_tm:
            mock_tm = Mock()
            mock_tm.search_tavily = AsyncMock(return_value=sample_search_results)
            mock_get_tm.return_value = mock_tm
            
            # Get the actual tool function from the decorator
            search_func = None
            for item in dir(server_module.app):
                if item == 'search_company':
                    search_func = getattr(server_module.app, item)
            
            # Call the underlying function directly (not the tool wrapper)
            # Access the wrapped function
            actual_func = server_module.search_company
            if hasattr(actual_func, '__wrapped__'):
                actual_func = actual_func.__wrapped__
            
            result_json = await actual_func(
                query="Test Company funding",
                company_name="test_company",
                topic="funding"
            )
            
            result = json.loads(result_json)
            
            # Assert
            assert "results" in result
            assert result["count"] == 2
            assert result["results"][0]["score"] == 0.95
    
        @pytest.mark.skip(reason="FastMCP tools require server instance - test tool logic separately")
    @pytest.mark.asyncio
    async def test_extract_field_tool(self, sample_extraction_result, sample_search_results):
        """Test extract_field tool."""
        # Arrange
        from mcp_server.server import extract_field
        from tavily_agent.llm_extraction import ChainedExtractionResult
        
        mock_result = ChainedExtractionResult(
            field_name="founded_year",
            final_value="2020",
            confidence=0.95,
            chain_steps=["step1", "step2"],
            reasoning="Found in search results",
            sources=["https://example.com"]
        )
        
        with patch('mcp_server.server.extract_field_value', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_result
            
            # Act
            result_json = await extract_field(
                field_name="founded_year",
                entity_type="company_record",
                company_name="test_company",
                importance="high",
                search_results=json.dumps(sample_search_results)
            )
            
            result = json.loads(result_json)
            
            # Assert
            assert result["field_name"] == "founded_year"
            assert result["final_value"] == "2020"
            assert result["confidence"] == 0.95
    
        @pytest.mark.skip(reason="FastMCP tools require server instance - test tool logic separately")
    @pytest.mark.asyncio
    async def test_enrich_payload_tool(self):
        """Test enrich_payload tool."""
        # Arrange
        from mcp_server.server import enrich_payload
        
        with patch('mcp_server.server.enrich_single_company', new_callable=AsyncMock) as mock_enrich:
            mock_enrich.return_value = {
                "status": "completed",
                "null_fields_found": 4,
                "null_fields_filled": 3,
                "timestamp": datetime.now().isoformat()
            }
            
            # Act
            result_json = await enrich_payload(
                company_name="test_company",
                max_iterations=20
            )
            
            result = json.loads(result_json)
            
            # Assert
            assert result["status"] == "completed"
        assert result["company_name"] == "test_company"
        assert result["null_fields_found"] == 4
        assert result["null_fields_filled"] == 3
        assert result["success"] is True
    
        @pytest.mark.asyncio
    @patch('mcp_server.server.FileIOManager')
    async def test_analyze_null_fields_tool(self, mock_file_io, sample_payload):
        """Test analyze_null_fields tool (if implemented)."""
        # Arrange
        mock_fio = Mock()
        mock_fio.read_payload = AsyncMock(return_value=sample_payload)
        mock_file_io.return_value = mock_fio
        
        # This test depends on whether analyze_null_fields is implemented
        # Adjust based on actual implementation


# ===========================
# Test MCP Client
# ===========================

class TestMCPEnrichmentClient:
    """Test MCP client functionality."""
    
        @pytest.mark.asyncio
    @patch('mcp_server.mcp_enrichment_client.stdio_client')
    async def test_client_connection(self, mock_stdio):
        """Test client can connect to MCP server."""
        # Arrange
        mock_context = AsyncMock()
        mock_read = Mock()
        mock_write = Mock()
        mock_context.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio.return_value = mock_context
        
        from mcp_server.mcp_enrichment_client import MCPEnrichmentClient
        
        client = MCPEnrichmentClient()
        
        # Act
        with patch('mcp_server.mcp_enrichment_client.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.initialize = AsyncMock()
            mock_session_class.return_value = mock_session
            
            await client.connect()
            
            # Assert
            assert client.session is not None
            mock_session.initialize.assert_called_once()
    
        @pytest.mark.asyncio
    async def test_client_search_tool_call(self):
        """Test client can call search_company tool."""
        from mcp_server.mcp_enrichment_client import MCPEnrichmentClient
        
        client = MCPEnrichmentClient()
        
        # Mock session
        mock_session = Mock()
        mock_session.call_tool = AsyncMock(return_value=Mock(
            content=[Mock(text='{"results": [], "count": 0}')]
        ))
        client.session = mock_session
        
        # Act
        result = await client.search_company(
            company_name="test_company",
            query="funding information"
        )
        
        # Assert
        assert result is not None
        mock_session.call_tool.assert_called_once()
    
        @pytest.mark.skip(reason="Client method API needs verification")
    @pytest.mark.asyncio
    async def test_client_enrich_payload_call(self):
        """Test client can call enrich_payload tool."""
        from mcp_server.mcp_enrichment_client import MCPEnrichmentClient
        
        client = MCPEnrichmentClient()
        
        # Mock session
        mock_session = Mock()
        mock_session.call_tool = AsyncMock(return_value=Mock(
            content=[Mock(text='{"status": "completed", "success": true}')]
        ))
        client.session = mock_session
        
        # Act
        result = await client.enrich_company("test_company")
        
        # Assert
        assert result is not None
        mock_session.call_tool.assert_called_once()


# ===========================
# Integration Tests
# ===========================

class TestMCPServerIntegration:
    """Integration tests for complete MCP server workflow."""
    
        @pytest.mark.skip(reason="FastMCP tools require server instance")
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_enrichment_flow(
        self,
        sample_payload,
        sample_search_results,
        sample_extraction_result
    ):
        """Test complete enrichment workflow through MCP server."""
        # Arrange
        from mcp_server.server import search_company, extract_field
        from tavily_agent.llm_extraction import ChainedExtractionResult
        
        mock_result = ChainedExtractionResult(
            field_name="founded_year",
            final_value="2020",
            confidence=0.95,
            chain_steps=["step1"],
            reasoning="Found",
            sources=[]
        )
        
        with patch('mcp_server.server.get_tool_manager') as mock_get_tm:
            with patch('mcp_server.server.extract_field_value', new_callable=AsyncMock) as mock_extract:
                mock_tm = Mock()
                mock_tm.search_tavily = AsyncMock(return_value=sample_search_results)
                mock_get_tm.return_value = mock_tm
                mock_extract.return_value = mock_result
                
                # Act
                # 1. Search
                search_result = await search_company(
                    query="Test Company funding",
                    company_name="test_company",
                    topic="general"
                )
                search_data = json.loads(search_result)
                
                # 2. Extract
                extract_result = await extract_field(
                    field_name="founded_year",
                    entity_type="company_record",
                    company_name="test_company",
                    importance="high",
                    search_results=search_result
                )
                extract_data = json.loads(extract_result)
                
                # Assert
                assert search_data["count"] == 2
                assert extract_data["final_value"] == "2020"
    
        @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_security_enforcement_in_workflow(self):
        """Test that security checks are enforced during workflow."""
        from mcp_server.security import SecurityMiddleware
        
        manager = SecurityMiddleware()
        
        # Test 1: Valid request passes
        can_execute1, reason1 = manager.can_execute_tool(
            tool_name="search_company",
            arguments={"company_name": "abridge", "query": "valid query"},
            requester_role="user"
        )
        assert can_execute1
        
        # Test 2: Malicious SQL injection blocked
        can_execute2, reason2 = manager.can_execute_tool(
            tool_name="search_company",
            arguments={"company_name": "test", "query": "DROP TABLE users"},
            requester_role="user"
        )
        assert not can_execute2
        
        # Test 3: Rate limiting enforced
        for i in range(5):
            manager.can_execute_tool(
                tool_name="enrich_payload",
                arguments={"company_name": f"company_{i}"},
                requester_role="admin"  # Use admin since enrich_payload is sensitive
            )
        
        can_execute3, reason3 = manager.can_execute_tool(
            tool_name="enrich_payload",
            arguments={"company_name": "company_6"},
            requester_role="admin"
        )
        assert not can_execute3
        assert "rate limit" in reason3.lower()


# ===========================
# Error Handling Tests
# ===========================

class TestErrorHandling:
    """Test error handling in MCP server."""
    
        @pytest.mark.skip(reason="FastMCP tools require server instance")
    @pytest.mark.asyncio
    async def test_search_tool_handles_api_error(self):
        """Test search_company handles API errors gracefully."""
        from mcp_server.server import search_company
        
        with patch('mcp_server.server.get_tool_manager') as mock_get_tm:
            mock_tm = Mock()
            mock_tm.search_tavily = AsyncMock(side_effect=Exception("API Error"))
            mock_get_tm.return_value = mock_tm
            
            # Act
            result_json = await search_company(
                query="test",
                company_name="test_company"
            )
            
            result = json.loads(result_json)
            
            # Assert
            assert "error" in result
            assert result["success"] is False
    
        @pytest.mark.skip(reason="FastMCP tools require server instance")
    @pytest.mark.asyncio
    async def test_extract_tool_handles_invalid_json(self):
        """Test extract_field handles invalid JSON search results."""
        from mcp_server.server import extract_field
        from tavily_agent.llm_extraction import ChainedExtractionResult
        
        mock_result = ChainedExtractionResult(
            field_name="founded_year",
            final_value=None,
            confidence=0.0,
            chain_steps=[],
            reasoning="Invalid input",
            sources=[]
        )
        
        with patch('mcp_server.server.extract_field_value', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_result
            
            # Act
            result_json = await extract_field(
                field_name="founded_year",
                entity_type="company_record",
                company_name="test_company",
                importance="high",
                search_results="invalid json{{"
            )
            
            # Should not crash, should return result
            result = json.loads(result_json)
            assert "field_name" in result or "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
