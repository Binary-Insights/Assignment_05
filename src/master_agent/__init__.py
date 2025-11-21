"""
Master Agent Module - Orchestrates Tavily and Payload Agents
=============================================================

This module provides the master orchestrator that combines:
- Tavily Agent: External web search for company_record fields
- Payload Agent: Pinecone vector search for entity extraction

Usage:
    from master_agent import MasterOrchestrator
    
    orchestrator = MasterOrchestrator()
    result = await orchestrator.enrich_company("abridge")
"""

from master_agent.master import MasterOrchestrator

__all__ = ["MasterOrchestrator"]
