"""
Pydantic models for LLM-based page discovery.

This module defines all data models used in the page discovery system:
- DiscoveryRequest: Structured input for page discovery
- DiscoveredPage: Structured output for discovered page
- DiscoveryResult: Final result combining request and discovered page
- URLValidationInput: Input model for URL validation tool
- URLValidationResult: Result model for URL validation tool
"""

from typing import Optional
from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    """Structured input for page discovery."""
    website_url: str = Field(..., description="Base website URL (e.g., https://example.com/)")
    page_type: str = Field(..., description="Type of page to discover (e.g., 'product', 'careers', 'about', 'blog')")
    page_content_snippet: str = Field(..., description="Snippet of HTML/text content from the website homepage")


class DiscoveredPage(BaseModel):
    """Structured output for a discovered page."""
    page_type: str = Field(..., description="The type of page (e.g., 'product')")
    discovered_url: Optional[str] = Field(
        None, 
        description="The full URL of the discovered page, or None if not found"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")
    reasoning: str = Field(..., description="Explanation of why this URL was chosen or not found")
    alternative_urls: list[str] = Field(default_factory=list, description="Alternative candidate URLs if found")


class DiscoveryResult(BaseModel):
    """Final structured output combining request and result."""
    request: DiscoveryRequest
    result: DiscoveredPage


class URLValidationInput(BaseModel):
    """Input model for URL validation tool."""
    url: str = Field(..., description="The URL to validate")
    timeout: int = Field(default=5, description="Timeout in seconds")


class URLValidationResult(BaseModel):
    """Result model for URL validation tool."""
    url: str = Field(..., description="The validated URL")
    exists: bool = Field(..., description="Whether the URL is accessible (200-299 status)")
    status_code: int = Field(..., description="HTTP status code")
    is_redirect: bool = Field(..., description="Whether the URL redirects")
    final_url: str = Field(..., description="Final URL after redirects")
    reason: str = Field(..., description="Validation reason/message")
    validation_score: float = Field(..., description="Score adjustment for confidence (0.0-1.0)")
