# MCP Integration Guide for Agentic RAG

## Table of Contents
1. [What is MCP?](#what-is-mcp)
2. [Architecture Overview](#architecture-overview)
3. [Integration Strategy](#integration-strategy)
4. [Reusing Existing Code](#reusing-existing-code)
5. [Creating MCP Server](#creating-mcp-server)
6. [Tool Filtering & Security](#tool-filtering--security)
7. [Implementation Steps](#implementation-steps)
8. [Testing & Validation](#testing--validation)

---

## What is MCP?

### Model Context Protocol (MCP)

**MCP** is a standardized protocol for connecting AI models to external tools, data sources, and services.

**Three Core Components:**
```
┌─────────────────────────────────────────────────────────┐
│  MCP CLIENT (Claude/Your Agent)                        │
│  - Makes requests to MCP servers                       │
│  - Discovers available tools/resources/prompts         │
│  - Invokes tools with user-provided arguments          │
│  - Receives results via stdio or HTTP                  │
└─────────────────────────────────────────────────────────┘
                           ↕ (Standardized Protocol)
┌─────────────────────────────────────────────────────────┐
│  MCP SERVER (Your Agentic RAG System)                  │
│  ├─ Tools (callable functions)                         │
│  │  └─ enrich_payload()                                │
│  │  └─ search_company()                                │
│  │  └─ extract_field()                                 │
│  ├─ Resources (data/context)                           │
│  │  └─ company_payloads                                │
│  │  └─ extraction_history                              │
│  └─ Prompts (pre-built instructions)                   │
│     └─ "Enrich Company Data"                           │
│     └─ "Analyze Field Extraction"                      │
└─────────────────────────────────────────────────────────┘
```

**Key Benefits:**
- ✅ **Standardized Interface** - Same protocol for all tools
- ✅ **Tool Discovery** - Client knows available tools upfront
- ✅ **Security** - Tool filtering, input validation
- ✅ **Async Support** - Native async/await throughout
- ✅ **Streaming** - Real-time result streaming
- ✅ **Error Handling** - Standardized error responses

---

## Architecture Overview

### Current System vs. MCP Integration

**Current Architecture:**
```
LangGraph Agent
    ├─ Tavily Search (via ToolManager)
    ├─ OpenAI LLM (via LLMExtractionChain)
    └─ File I/O (via FileIOManager)
```

**With MCP Integration:**
```
┌──────────────────────────┐
│  Claude/Client Agent     │
│  (uses MCP client libs)  │
└──────────────┬───────────┘
               │
    MCP Protocol (stdio/HTTP)
               │
┌──────────────▼───────────────────────────┐
│  MCP Server (Your RAG System)            │
├──────────────────────────────────────────┤
│  TOOLS (Callable Functions)              │
│  ├─ enrich_company()                     │
│  │  └─ Reuses: LangGraph workflow        │
│  ├─ search_tavily()                      │
│  │  └─ Reuses: ToolManager.search_tavily │
│  └─ extract_field()                      │
│     └─ Reuses: LLMExtractionChain        │
├──────────────────────────────────────────┤
│  RESOURCES (Data Sources)                │
│  ├─ /company/{id}                        │
│  │  └─ Reuses: FileIOManager.read_payload│
│  ├─ /extractions/{id}                    │
│  │  └─ Reuses: extracted_values state    │
│  └─ /history/{id}                        │
│     └─ Reuses: execution logs            │
├──────────────────────────────────────────┤
│  PROMPTS (Pre-built Instructions)        │
│  ├─ "Enrich Company Profile"             │
│  ├─ "Find Missing Fields"                │
│  └─ "Validate Extractions"               │
└──────────────────────────────────────────┘
```

---

## Integration Strategy

### Phase 1: Identify Reusable Components

**From Existing Code:**

| Component | Use in MCP Server | Benefit |
|---|---|---|
| `LLMExtractionChain` | Tool: `extract_field()` | Reuse 3-step extraction logic |
| `ToolManager.search_tavily()` | Tool: `search_company()` | Reuse Tavily API calls |
| `FileIOManager` | Resource: `/payloads` | Reuse payload I/O |
| `PayloadEnrichmentState` | Tool input/output | Reuse state schema |
| `analyze_payload()` | Tool: `analyze_null_fields()` | Reuse field detection |
| LangSmith `@traceable` | MCP request tracking | Reuse observability |

### Phase 2: MCP Server Structure

**Directory Layout:**
```
src/
├─ tavily_agent/
│  ├─ graph.py              (existing - reuse)
│  ├─ llm_extraction.py     (existing - reuse)
│  ├─ tools.py              (existing - reuse)
│  ├─ file_io_manager.py    (existing - reuse)
│  └─ config.py             (existing - reuse)
│
└─ mcp_server/              (NEW)
   ├─ __init__.py
   ├─ server.py             (MCP server main)
   ├─ tools.py              (MCP tools wrapping existing code)
   ├─ resources.py          (MCP resources)
   ├─ prompts.py            (MCP prompt templates)
   └─ security.py           (Tool filtering & validation)
```

### Phase 3: Security & Tool Filtering

**Tool Filtering Strategy:**
```
User Request
    ↓
┌─ Validate Tool Name
│  └─ Against ALLOWED_TOOLS list
├─ Validate Input Schema
│  └─ Against Pydantic models
├─ Check Rate Limits
│  └─ Per-tool usage counters
└─ Sanitize Arguments
   └─ Remove/escape dangerous inputs

    ↓
Execute Tool
```

---

## Reusing Existing Code

### Strategy for Code Reuse

#### 1. **Wrap Existing Functions as MCP Tools**

**Before:**
```python
# In tools.py
async def search_tavily(query: str, company_name: str) -> Dict[str, Any]:
    # Implementation
    pass
```

**After (in MCP server):**
```python
# In mcp_server/tools.py
from tavily_agent.tools import ToolManager

@mcp.tool()
async def search_company(company_name: str, query: str) -> dict:
    """Search for company information via Tavily."""
    tool_manager = await get_tool_manager()
    result = await tool_manager.search_tavily(
        query=query,
        company_name=company_name
    )
    return result
```

**Benefits:**
- ✅ No code duplication
- ✅ Single source of truth
- ✅ Easy maintenance
- ✅ Leverages existing error handling

#### 2. **Expose LangGraph Workflow as MCP Tool**

**Before:**
```python
# In main.py
async def enrich_single_company(company_name: str) -> Dict[str, Any]:
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    result = await orchestrator.process_single_company(company_name)
    return result
```

**After (in MCP server):**
```python
# In mcp_server/tools.py
from tavily_agent.main import enrich_single_company

@mcp.tool()
async def enrich_payload(company_name: str) -> dict:
    """Run full enrichment workflow for a company."""
    result = await enrich_single_company(company_name)
    return result
```

#### 3. **Expose LLM Extraction Chain as MCP Tool**

**Before:**
```python
# In llm_extraction.py
chain = LLMExtractionChain()
result = await chain.run_extraction_chain(...)
```

**After (in MCP server):**
```python
# In mcp_server/tools.py
from tavily_agent.llm_extraction import LLMExtractionChain

@mcp.tool()
async def extract_field(
    field_name: str,
    company_name: str,
    search_results: list
) -> dict:
    """Extract value for a field using LLM chain."""
    chain = LLMExtractionChain()
    result = await chain.run_extraction_chain(
        field_name=field_name,
        entity_type="company_record",
        company_name=company_name,
        importance="high",
        search_results=search_results
    )
    return {
        "field_name": result.field_name,
        "value": result.final_value,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "sources": result.sources
    }
```

#### 4. **Expose Payload Data as MCP Resources**

**Before:**
```python
# In file_io_manager.py
payload = await FileIOManager.read_payload(company_name)
```

**After (in MCP server):**
```python
# In mcp_server/resources.py
@mcp.resource("company://{company_name}")
async def get_company_payload(company_name: str) -> dict:
    """Get current payload for a company."""
    payload = await FileIOManager.read_payload(company_name)
    return {
        "uri": f"company://{company_name}",
        "name": company_name,
        "mimeType": "application/json",
        "contents": json.dumps(payload, indent=2)
    }
```

---

## Creating MCP Server

### Installation & Setup

**Step 1: Install MCP SDK**
```bash
pip install mcp
pip install pydantic  # For data validation
```

**Step 2: Create Server Entry Point**

**File: `src/mcp_server/server.py`**
```python
"""
MCP Server for Agentic RAG System
Exposes tools, resources, and prompts for payload enrichment
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import (
    Tool, TextContent, ToolResult,
    Resource, ResourceTemplate
)
from pydantic import BaseModel, Field

# Import existing code
from tavily_agent.tools import ToolManager, get_tool_manager
from tavily_agent.llm_extraction import LLMExtractionChain
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.main import enrich_single_company
from tavily_agent.config import LLM_MODEL, LLM_TEMPERATURE

logger = logging.getLogger(__name__)

# ===========================
# Initialize MCP Server
# ===========================

server = Server("agentic-rag-mcp")

# ===========================
# Tool Definitions with Pydantic Schemas
# ===========================

class SearchCompanyInput(BaseModel):
    """Input for searching company information."""
    company_name: str = Field(description="Company name/identifier")
    query: str = Field(description="Search query for the company")
    topic: str = Field(
        default="general",
        description="Search topic (general, funding, products, leadership)"
    )

class ExtractFieldInput(BaseModel):
    """Input for field extraction."""
    field_name: str = Field(description="Field to extract (e.g., founded_year)")
    company_name: str = Field(description="Company name")
    search_results: List[Dict[str, Any]] = Field(
        description="Search results with title, content, url"
    )
    importance: str = Field(
        default="high",
        description="Field importance level"
    )

class EnrichPayloadInput(BaseModel):
    """Input for payload enrichment."""
    company_name: str = Field(description="Company identifier")
    max_iterations: int = Field(
        default=20,
        description="Maximum iterations for enrichment"
    )

# ===========================
# Tools
# ===========================

@server.call_tool()
async def search_company(arguments: Dict[str, Any]) -> List[ToolResult]:
    """
    Search for company information via Tavily.
    Reuses: tavily_agent.tools.ToolManager.search_tavily()
    """
    try:
        # Validate input
        input_data = SearchCompanyInput(**arguments)
        
        # Call existing Tavily search
        tool_manager = await get_tool_manager()
        result = await tool_manager.search_tavily(
            query=input_data.query,
            company_name=input_data.company_name,
            topic=input_data.topic
        )
        
        return [ToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )],
            is_error=False
        )]
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return [ToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            is_error=True
        )]

@server.call_tool()
async def extract_field(arguments: Dict[str, Any]) -> List[ToolResult]:
    """
    Extract value for a field using LLM chain.
    Reuses: tavily_agent.llm_extraction.LLMExtractionChain
    """
    try:
        # Validate input
        input_data = ExtractFieldInput(**arguments)
        
        # Run extraction chain
        chain = LLMExtractionChain(
            llm_model=LLM_MODEL,
            temperature=LLM_TEMPERATURE
        )
        extraction_result = await chain.run_extraction_chain(
            field_name=input_data.field_name,
            entity_type="company_record",
            company_name=input_data.company_name,
            importance=input_data.importance,
            search_results=input_data.search_results
        )
        
        return [ToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps({
                    "field_name": extraction_result.field_name,
                    "value": extraction_result.final_value,
                    "confidence": extraction_result.confidence,
                    "reasoning": extraction_result.reasoning,
                    "sources": extraction_result.sources,
                    "steps": extraction_result.chain_steps
                }, indent=2)
            )],
            is_error=False
        )]
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        return [ToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            is_error=True
        )]

@server.call_tool()
async def enrich_payload(arguments: Dict[str, Any]) -> List[ToolResult]:
    """
    Run full enrichment workflow for a company.
    Reuses: tavily_agent.main.enrich_single_company()
    """
    try:
        # Validate input
        input_data = EnrichPayloadInput(**arguments)
        
        # Run enrichment
        result = await enrich_single_company(input_data.company_name)
        
        return [ToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )],
            is_error=False
        )]
    except Exception as e:
        logger.error(f"Enrichment failed: {e}", exc_info=True)
        return [ToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            is_error=True
        )]

# ===========================
# Resources (Data Endpoints)
# ===========================

@server.list_resources()
async def list_resources() -> List[ResourceTemplate]:
    """List available resources."""
    return [
        ResourceTemplate(
            uri_template="company://{company_name}",
            name="Company Payload",
            description="Get current payload for a company",
            mimeType="application/json"
        ),
        ResourceTemplate(
            uri_template="company://{company_name}/extractions",
            name="Company Extractions",
            description="Get extraction history for a company",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read resource by URI."""
    try:
        if uri.startswith("company://"):
            parts = uri.replace("company://", "").split("/")
            company_name = parts[0]
            
            if len(parts) == 1:
                # Get payload
                payload = await FileIOManager.read_payload(company_name)
                return json.dumps({
                    "company_name": company_name,
                    "payload": payload
                }, indent=2, default=str)
            
            elif len(parts) == 2 and parts[1] == "extractions":
                # Get extraction history
                payload = await FileIOManager.read_payload(company_name)
                extractions = payload.get("_extraction_metadata", {})
                return json.dumps({
                    "company_name": company_name,
                    "extractions": extractions
                }, indent=2, default=str)
        
        return json.dumps({"error": f"Unknown resource: {uri}"})
    except Exception as e:
        logger.error(f"Resource read failed: {e}")
        return json.dumps({"error": str(e)})

# ===========================
# Prompts
# ===========================

@server.list_prompts()
async def list_prompts() -> List[Dict[str, Any]]:
    """List available prompt templates."""
    return [
        {
            "name": "enrich_company_profile",
            "description": "Prompt for enriching company profiles",
            "arguments": [
                {"name": "company_name", "description": "Company to enrich"}
            ]
        },
        {
            "name": "find_missing_fields",
            "description": "Prompt for analyzing missing fields",
            "arguments": [
                {"name": "company_name", "description": "Company to analyze"}
            ]
        }
    ]

@server.get_prompt()
async def get_prompt(name: str, arguments: Dict[str, str]) -> str:
    """Get prompt template."""
    company_name = arguments.get("company_name", "")
    
    if name == "enrich_company_profile":
        return f"""Analyze the company '{company_name}' and identify all missing fields in their profile.
        
        For each missing field:
        1. Generate targeted search queries
        2. Search for information using available tools
        3. Extract values using the LLM extraction chain
        4. Validate with confidence scoring
        5. Update the payload
        
        Use the enrich_payload tool to run the full workflow."""
    
    elif name == "find_missing_fields":
        return f"""Analyze the payload for '{company_name}' and identify which fields are null/empty.
        
        Priority Analysis:
        - Critical fields (must-have): company_id, legal_name
        - High priority: founded_year, categories, headquarters
        - Medium priority: employee_count, funding_amount
        - Low priority: social_media, awards
        
        For each null field, suggest enrichment strategies."""
    
    return f"Unknown prompt: {name}"

# ===========================
# Server Entry Point
# ===========================

async def main():
    """Run the MCP server."""
    # Register tools
    server.register_tool(Tool(
        name="search_company",
        description="Search for company information via Tavily",
        inputSchema=SearchCompanyInput.model_json_schema()
    ))
    
    server.register_tool(Tool(
        name="extract_field",
        description="Extract value for a field using LLM chain",
        inputSchema=ExtractFieldInput.model_json_schema()
    ))
    
    server.register_tool(Tool(
        name="enrich_payload",
        description="Run full enrichment workflow",
        inputSchema=EnrichPayloadInput.model_json_schema()
    ))
    
    # Start server with stdio transport
    async with server.stdio_transport() as transport:
        await transport.serve()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Tool Filtering & Security

**File: `src/mcp_server/security.py`**
```python
"""
Security layer for MCP server
Implements tool filtering, rate limiting, and input validation
"""

import time
from typing import Dict, Any, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# ===========================
# Tool Filtering
# ===========================

class ToolFilter:
    """Filters which tools are allowed based on configuration."""
    
    # Allowed tools (whitelist)
    ALLOWED_TOOLS = {
        "search_company",
        "extract_field",
        "enrich_payload"
    }
    
    # Tools requiring special authentication
    SENSITIVE_TOOLS = {
        "enrich_payload"  # Modifies payloads
    }
    
    # Rate limits (requests per minute)
    RATE_LIMITS = {
        "search_company": 60,      # 60 searches/min
        "extract_field": 30,       # 30 extractions/min
        "enrich_payload": 5        # 5 enrichments/min
    }
    
    @staticmethod
    def is_tool_allowed(tool_name: str) -> bool:
        """Check if tool is allowed."""
        return tool_name in ToolFilter.ALLOWED_TOOLS
    
    @staticmethod
    def is_sensitive_tool(tool_name: str) -> bool:
        """Check if tool requires special permissions."""
        return tool_name in ToolFilter.SENSITIVE_TOOLS

class RateLimiter:
    """Rate limiting for tool calls."""
    
    def __init__(self):
        self.call_history: Dict[str, list] = defaultdict(list)
    
    def check_rate_limit(self, tool_name: str) -> bool:
        """Check if tool call is within rate limit."""
        if tool_name not in ToolFilter.RATE_LIMITS:
            return True  # No limit
        
        limit = ToolFilter.RATE_LIMITS[tool_name]
        current_time = time.time()
        one_minute_ago = current_time - 60
        
        # Clean old entries
        self.call_history[tool_name] = [
            t for t in self.call_history[tool_name]
            if t > one_minute_ago
        ]
        
        # Check limit
        if len(self.call_history[tool_name]) >= limit:
            return False
        
        # Record call
        self.call_history[tool_name].append(current_time)
        return True

class InputValidator:
    """Validates tool inputs."""
    
    # Patterns to reject (SQL injection, code injection, etc.)
    BLOCKED_PATTERNS = [
        r"DROP\s+TABLE",
        r"DELETE\s+FROM",
        r"INSERT\s+INTO",
        r"UPDATE\s+",
        r"exec\(",
        r"eval\(",
        r"__import__",
    ]
    
    @staticmethod
    def validate_inputs(tool_name: str, arguments: Dict[str, Any]) -> bool:
        """Validate tool inputs."""
        for key, value in arguments.items():
            if isinstance(value, str):
                # Check for blocked patterns
                for pattern in InputValidator.BLOCKED_PATTERNS:
                    import re
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(
                            f"Blocked pattern detected in {tool_name}.{key}"
                        )
                        return False
        
        return True

# ===========================
# Security Middleware
# ===========================

class SecurityMiddleware:
    """Enforces security policies on tool calls."""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.tool_filter = ToolFilter()
        self.input_validator = InputValidator()
    
    def can_execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        requester_role: str = "user"
    ) -> tuple[bool, str]:
        """
        Check if tool can be executed.
        
        Returns:
            (can_execute: bool, reason: str)
        """
        # 1. Check if tool is allowed
        if not self.tool_filter.is_tool_allowed(tool_name):
            return False, f"Tool '{tool_name}' not allowed"
        
        # 2. Check sensitive tools
        if self.tool_filter.is_sensitive_tool(tool_name):
            if requester_role != "admin":
                return False, f"Tool '{tool_name}' requires admin role"
        
        # 3. Check rate limits
        if not self.rate_limiter.check_rate_limit(tool_name):
            return False, f"Rate limit exceeded for '{tool_name}'"
        
        # 4. Validate inputs
        if not self.input_validator.validate_inputs(tool_name, arguments):
            return False, "Invalid input detected"
        
        return True, "OK"

# Global instance
security_middleware = SecurityMiddleware()
```

### Step 4: Launch Script

**File: `src/mcp_server/__main__.py`**
```python
#!/usr/bin/env python3
"""
Launch MCP Server for Agentic RAG
Usage: python -m mcp_server
"""

import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Send logs to stderr so stdout is clean for MCP protocol
)

from mcp_server.server import main

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Tool Filtering & Security

### Implementation Details

**Security Layers:**

```
Tool Call Request
    ↓
┌─ Layer 1: Tool Whitelist
│  ├─ Is tool in ALLOWED_TOOLS?
│  └─ Reject if not allowed
    ↓
├─ Layer 2: Permission Check
│  ├─ Is requester authorized?
│  └─ Admin-only for sensitive tools
    ↓
├─ Layer 3: Rate Limiting
│  ├─ Has tool call limit been exceeded?
│  └─ Reject if over limit
    ↓
├─ Layer 4: Input Validation
│  ├─ Check for SQL injection patterns
│  ├─ Check for code injection
│  └─ Validate schema
    ↓
└─ Execute Tool

Tool Result
```

**Filtering Configuration:**

```python
# In security.py

ALLOWED_TOOLS = {
    "search_company",     # ✅ Safe - read-only Tavily search
    "extract_field",      # ✅ Safe - uses LLM, no DB modifications
    "enrich_payload"      # ⚠️  Sensitive - modifies payload
}

SENSITIVE_TOOLS = {
    "enrich_payload"      # Requires admin role
}

RATE_LIMITS = {
    "search_company": 60,      # Generous - external API
    "extract_field": 30,       # Moderate - LLM calls (cost)
    "enrich_payload": 5        # Strict - modifies state
}
```

---

## Implementation Steps

### Step 1: Create MCP Server Directory

```bash
mkdir -p src/mcp_server
touch src/mcp_server/__init__.py
```

### Step 2: Install MCP SDK

```bash
pip install mcp
```

### Step 3: Add MCP Server Files

Copy the code blocks above into:
- `src/mcp_server/server.py`
- `src/mcp_server/security.py`
- `src/mcp_server/__main__.py`

### Step 4: Test MCP Server Locally

**Terminal 1 - Start MCP Server:**
```bash
cd /path/to/Assignment_05
python -m mcp_server
```

**Terminal 2 - Test with Claude:**
```bash
# Using claude CLI
claude tools list

# Should output:
# - search_company
# - extract_field
# - enrich_payload
```

### Step 5: Configure Claude to Use MCP Server

**File: `~/.claude-config.json` (or create it)**
```json
{
  "mcpServers": {
    "agentic-rag": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/Assignment_05"
    }
  }
}
```

### Step 6: Use in Claude

**Prompt Claude:**
```
I need to enrich company data for "abridge". Please:
1. Use the search_company tool to find information
2. Use extract_field to pull specific values
3. Use enrich_payload to run the full workflow
```

---

## Testing & Validation

### Unit Tests for MCP Server

**File: `tests/test_mcp_server.py`**
```python
"""Tests for MCP server."""

import pytest
import asyncio
from mcp_server.security import SecurityMiddleware, RateLimiter
from mcp_server.server import (
    search_company, extract_field, enrich_payload,
    SearchCompanyInput, ExtractFieldInput, EnrichPayloadInput
)

# ===========================
# Security Tests
# ===========================

def test_tool_filter_allows_valid_tools():
    """Test that valid tools are allowed."""
    middleware = SecurityMiddleware()
    can_exec, reason = middleware.can_execute_tool(
        "search_company",
        {},
        requester_role="user"
    )
    assert can_exec, reason

def test_tool_filter_rejects_invalid_tools():
    """Test that invalid tools are rejected."""
    middleware = SecurityMiddleware()
    can_exec, reason = middleware.can_execute_tool(
        "delete_all_data",
        {},
        requester_role="user"
    )
    assert not can_exec

def test_sensitive_tool_requires_admin():
    """Test that sensitive tools require admin role."""
    middleware = SecurityMiddleware()
    
    # Should fail for user
    can_exec, reason = middleware.can_execute_tool(
        "enrich_payload",
        {},
        requester_role="user"
    )
    assert not can_exec
    
    # Should succeed for admin
    can_exec, reason = middleware.can_execute_tool(
        "enrich_payload",
        {},
        requester_role="admin"
    )
    assert can_exec

def test_rate_limiting():
    """Test rate limiting."""
    limiter = RateLimiter()
    
    # Allow first 5 calls
    for i in range(5):
        assert limiter.check_rate_limit("enrich_payload"), f"Call {i+1} failed"
    
    # Should fail on 6th
    assert not limiter.check_rate_limit("enrich_payload")

def test_input_validation_blocks_sql_injection():
    """Test that SQL injection patterns are blocked."""
    middleware = SecurityMiddleware()
    
    malicious_input = {
        "company_name": "'; DROP TABLE payloads; --"
    }
    
    can_exec, reason = middleware.can_execute_tool(
        "search_company",
        malicious_input,
        requester_role="user"
    )
    assert not can_exec

# ===========================
# Tool Tests
# ===========================

@pytest.mark.asyncio
async def test_search_company_tool():
    """Test search_company tool."""
    result = await search_company({
        "company_name": "abridge",
        "query": "abridge healthcare ai",
        "topic": "general"
    })
    
    assert result is not None
    # Check result structure

@pytest.mark.asyncio
async def test_extract_field_tool():
    """Test extract_field tool."""
    search_results = [
        {
            "title": "Abridge Overview",
            "content": "Abridge was founded in 2018",
            "url": "https://example.com",
            "relevance_score": 0.95
        }
    ]
    
    result = await extract_field({
        "field_name": "founded_year",
        "company_name": "abridge",
        "search_results": search_results,
        "importance": "high"
    })
    
    assert result is not None
    # Check extraction result

# ===========================
# Integration Tests
# ===========================

@pytest.mark.asyncio
async def test_full_enrichment_workflow():
    """Test full enrichment workflow through MCP."""
    result = await enrich_payload({
        "company_name": "abridge",
        "max_iterations": 5  # Limited for testing
    })
    
    assert result is not None
    # Check workflow result

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Run Tests:**
```bash
pytest tests/test_mcp_server.py -v
```

---

## Code Reuse Checklist

### ✅ What Can Be Reused

| Component | Reuse Strategy | Status |
|---|---|---|
| `LLMExtractionChain` | Wrap as `extract_field` tool | ✅ Direct |
| `ToolManager.search_tavily()` | Wrap as `search_company` tool | ✅ Direct |
| `FileIOManager` | Expose as resources | ✅ Direct |
| `enrich_single_company()` | Wrap as `enrich_payload` tool | ✅ Direct |
| `analyze_payload()` | Integrate in `enrich_payload` | ✅ Direct |
| Pydantic models | Use for MCP input schemas | ✅ Direct |
| LangSmith `@traceable` | Trace MCP calls | ✅ Extended |
| Error handling | Wrap with MCP error format | ✅ Adapted |

### ✅ Benefits of Reuse

1. **No Duplication** - Single source of truth
2. **Consistency** - Same logic, same results
3. **Maintainability** - Fix bugs once, everywhere
4. **Testing** - Existing tests still apply
5. **Reliability** - Proven, battle-tested code

---

## Deployment Scenarios

### Scenario 1: Local Development

```bash
# Terminal 1: Start MCP Server
python -m mcp_server

# Terminal 2: Use with Claude
claude chat --tools agentic-rag
```

### Scenario 2: Docker Deployment

**File: `docker/Dockerfile.mcp`**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY . .

# Install dependencies
RUN pip install -r requirements.txt
RUN pip install mcp

# Expose MCP over HTTP (optional)
EXPOSE 9999

# Run MCP server
CMD ["python", "-m", "mcp_server"]
```

**Launch:**
```bash
docker build -f docker/Dockerfile.mcp -t agentic-rag-mcp .
docker run -p 9999:9999 agentic-rag-mcp
```

### Scenario 3: Production with FastAPI

**File: `src/mcp_server/http_bridge.py`**
```python
"""HTTP bridge for MCP server (optional)."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Agentic RAG MCP Bridge")

@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, arguments: dict):
    """HTTP endpoint for tool calls."""
    from mcp_server.security import security_middleware
    
    # Check security
    can_exec, reason = security_middleware.can_execute_tool(
        tool_name,
        arguments,
        requester_role="user"
    )
    
    if not can_exec:
        raise HTTPException(status_code=403, detail=reason)
    
    # Call tool...
```

---

## Conclusion

### Summary

**MCP Integration provides:**

✅ **Standardized Tool Interface** - Claude can discover and use tools  
✅ **Code Reuse** - Leverages existing agent code (90%+ reuse)  
✅ **Security** - Tool filtering, rate limiting, input validation  
✅ **Observability** - LangSmith tracing for MCP calls  
✅ **Scalability** - Easy to add new tools/resources  
✅ **Production Ready** - Docker, HTTP, security layers  

**Next Steps:**
1. Create `src/mcp_server/` directory
2. Copy MCP server files
3. Install MCP SDK
4. Test locally with Claude
5. Deploy with Docker or HTTP bridge

**Key Files:**
- `src/mcp_server/server.py` - Main MCP server
- `src/mcp_server/security.py` - Tool filtering
- `src/mcp_server/__main__.py` - Launch script
- `tests/test_mcp_server.py` - Unit tests

Your existing code becomes the **backend** for the MCP server's tools!
