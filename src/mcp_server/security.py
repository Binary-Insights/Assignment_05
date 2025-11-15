"""
Security layer for MCP server
Implements tool filtering, rate limiting, and input validation
"""

import time
import re
import logging
from typing import Dict, Any, Set
from collections import defaultdict

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
        "enrich_payload",
        "analyze_null_fields"
    }
    
    # Tools requiring special authentication
    SENSITIVE_TOOLS = {
        "enrich_payload"  # Modifies payloads
    }
    
    # Rate limits (requests per minute)
    RATE_LIMITS = {
        "search_company": 60,      # 60 searches/min
        "extract_field": 30,       # 30 extractions/min
        "enrich_payload": 5,       # 5 enrichments/min
        "analyze_null_fields": 30  # 30 analyses/min
    }
    
    @staticmethod
    def is_tool_allowed(tool_name: str) -> bool:
        """Check if tool is allowed."""
        return tool_name in ToolFilter.ALLOWED_TOOLS
    
    @staticmethod
    def is_sensitive_tool(tool_name: str) -> bool:
        """Check if tool requires special permissions."""
        return tool_name in ToolFilter.SENSITIVE_TOOLS
    
    @staticmethod
    def get_rate_limit(tool_name: str) -> int:
        """Get rate limit for a tool."""
        return ToolFilter.RATE_LIMITS.get(tool_name, 60)


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
            logger.warning(
                f"Rate limit exceeded for {tool_name}: "
                f"{len(self.call_history[tool_name])}/{limit} calls in last minute"
            )
            return False
        
        # Record call
        self.call_history[tool_name].append(current_time)
        logger.debug(
            f"Rate limit check OK for {tool_name}: "
            f"{len(self.call_history[tool_name])}/{limit}"
        )
        return True
    
    def get_remaining_calls(self, tool_name: str) -> int:
        """Get remaining calls for a tool."""
        if tool_name not in ToolFilter.RATE_LIMITS:
            return -1  # Unlimited
        
        limit = ToolFilter.RATE_LIMITS[tool_name]
        current_time = time.time()
        one_minute_ago = current_time - 60
        
        recent_calls = len([
            t for t in self.call_history[tool_name]
            if t > one_minute_ago
        ])
        
        return max(0, limit - recent_calls)


class InputValidator:
    """Validates tool inputs."""
    
    # Patterns to reject (SQL injection, code injection, etc.)
    BLOCKED_PATTERNS = [
        r"DROP\s+TABLE",
        r"DELETE\s+FROM",
        r"INSERT\s+INTO",
        r"UPDATE\s+",
        r"SELECT\s+.*\s+FROM",
        r"exec\(",
        r"eval\(",
        r"__import__",
        r"os\.system",
        r"subprocess",
    ]
    
    @staticmethod
    def validate_inputs(tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate tool inputs.
        
        Returns:
            (is_valid: bool, message: str)
        """
        for key, value in arguments.items():
            if isinstance(value, str):
                # Check for blocked patterns
                for pattern in InputValidator.BLOCKED_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        msg = f"Blocked pattern detected in {tool_name}.{key}: {pattern}"
                        logger.warning(msg)
                        return False, msg
            
            elif isinstance(value, list):
                # Recursively validate list items
                for item in value:
                    if isinstance(item, dict):
                        valid, msg = InputValidator.validate_inputs(f"{tool_name}.{key}[]", item)
                        if not valid:
                            return False, msg
        
        return True, "OK"
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        # Truncate if too long
        if len(value) > max_length:
            value = value[:max_length]
        
        # Remove null bytes
        value = value.replace("\x00", "")
        
        return value


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
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            requester_role: Role of the requester (user, admin, system)
        
        Returns:
            (can_execute: bool, reason: str)
        """
        # 1. Check if tool is allowed
        if not self.tool_filter.is_tool_allowed(tool_name):
            return False, f"Tool '{tool_name}' not allowed"
        
        logger.info(f"✓ Tool '{tool_name}' is whitelisted")
        
        # 2. Check sensitive tools
        if self.tool_filter.is_sensitive_tool(tool_name):
            if requester_role not in ["admin", "system"]:
                return False, f"Tool '{tool_name}' requires admin/system role, got {requester_role}"
            logger.info(f"✓ Requester role {requester_role} authorized for sensitive tool")
        
        # 3. Check rate limits
        if not self.rate_limiter.check_rate_limit(tool_name):
            remaining = self.rate_limiter.get_remaining_calls(tool_name)
            return False, f"Rate limit exceeded for '{tool_name}'. Retry after 1 minute."
        
        logger.info(f"✓ Rate limit OK for '{tool_name}'")
        
        # 4. Validate inputs
        valid, msg = self.input_validator.validate_inputs(tool_name, arguments)
        if not valid:
            return False, msg
        
        logger.info(f"✓ Input validation passed for '{tool_name}'")
        
        return True, "OK"


# Global instance
security_middleware = SecurityMiddleware()
