"""
MCP Server for Agentic RAG System
Exposes tools, resources, and prompts for payload enrichment via Model Context Protocol
"""

__version__ = "1.0.0"
__author__ = "Agentic RAG"

from .server import main

__all__ = ["main"]
