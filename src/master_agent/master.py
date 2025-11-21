"""
Master Orchestrator Agent - Combines Tavily and Payload Agents
=================================================================

This master agent orchestrates both:
1. Tavily Agent - Uses Tavily API to fetch external data for company_record fields
2. Payload Agent - Uses Pinecone vector search to fill entity fields (events, products, etc.)

The master agent:
- Loads the initial payload
- Routes company_record fields to Tavily Agent
- Routes entity extraction to Payload Agent
- Merges results and saves final enriched payload
- Provides comprehensive logging and error handling

Usage:
    python src/master_agent/master.py abridge
    python src/master_agent/master.py abridge --verbose
    python src/master_agent/master.py abridge --tavily-only
    python src/master_agent/master.py abridge --payload-only
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Tavily Agent components
from tavily_agent.main import AgenticRAGOrchestrator, enrich_single_company
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.config import setup_langsmith

# Import Payload Agent components
from payload_agent.payload_workflow import run_payload_workflow
from payload_agent.tools.rag_adapter import create_pinecone_adapter
from payload_agent.tools import get_latest_structured_payload

# Import LangSmith tracing
try:
    from langsmith import traceable
except ImportError:
    def traceable(func):
        return func

load_dotenv()
logger = logging.getLogger(__name__)


# ===========================
# Logging Configuration
# ===========================

def setup_master_logging() -> logging.Logger:
    """Configure logging for the master orchestrator."""
    
    logger = logging.getLogger("master_orchestrator")
    logger.setLevel(logging.INFO)
    
    # Console handler with immediate flush for Airflow
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Force unbuffered output for Airflow
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    
    # File handler
    log_dir = Path(__file__).parent.parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"master_orchestrator_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Formatter - simplified for Airflow logs
    log_format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Ensure immediate output
    logger.propagate = False
    
    return logger


logger = setup_master_logging()


# ===========================
# Graph Visualization
# ===========================

def save_master_workflow_diagram(output_path: str = "data/graph/master_orchestrator_workflow.txt") -> Optional[str]:
    """
    Save master orchestrator workflow diagram as ASCII art.
    
    Args:
        output_path: Path to save the visualization (default: data/graph/master_orchestrator_workflow.txt)
    
    Returns:
        Path to saved file, or None if failed
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        workflow_diagram = """
================================================================================
MASTER ORCHESTRATOR WORKFLOW
================================================================================

                            ┌─────────────────────┐
                            │  START              │
                            │  Load Initial       │
                            │  Payload            │
                            └──────────┬──────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   Check Enabled Agents        │
                       └───────────────────────────────┘
                                       │
              ┌────────────────────────┴─────────────────────────┐
              │                                                   │
              ▼                                                   ▼
    ┌─────────────────────┐                           ┌─────────────────────┐
    │  PHASE 1            │                           │  PHASE 2            │
    │  Tavily Agent       │                           │  Payload Agent      │
    │  (if enabled)       │                           │  (if enabled)       │
    └─────────────────────┘                           └─────────────────────┘
              │                                                   │
              │  ┌───────────────────────────────┐              │
              └─▶│  Web Search via Tavily API    │              │
                 │  - company_record fields      │              │
                 │  - Provenance tracking        │              │
                 │  - Auto-save with versioning  │              │
                 └───────────────┬───────────────┘              │
                                 │                               │
                                 │  ┌───────────────────────────┴──────────┐
                                 └─▶│  Vector Search via Pinecone           │
                                    │  - Entity extraction (events, etc.)   │
                                    │  - LLM-powered field filling          │
                                    │  - Auto-save with versioning          │
                                    └───────────────┬───────────────────────┘
                                                    │
                                                    ▼
                                    ┌───────────────────────────────┐
                                    │  MERGE RESULTS                │
                                    │  - Load final payload         │
                                    │  - Count enriched fields      │
                                    │  - Count extracted entities   │
                                    │  - Generate statistics        │
                                    └───────────────┬───────────────┘
                                                    │
                                                    ▼
                                    ┌───────────────────────────────┐
                                    │  PRINT SUMMARY                │
                                    │  - Execution time             │
                                    │  - Fields filled              │
                                    │  - Entities added             │
                                    │  - Error details (if any)     │
                                    └───────────────┬───────────────┘
                                                    │
                                                    ▼
                                            ┌───────────────┐
                                            │  END          │
                                            │  Success/Fail │
                                            └───────────────┘

================================================================================
PHASE 1: TAVILY AGENT DETAILS
================================================================================

Tavily Agent enriches company_record fields using web search:

    Input: company_id
       ↓
    ┌──────────────────────────────────────┐
    │  LangGraph Workflow (Tavily)         │
    ├──────────────────────────────────────┤
    │  1. Analyze payload (find nulls)     │
    │  2. Generate search queries          │
    │  3. Execute Tavily searches          │
    │  4. Extract values with LLM          │
    │  5. Update payload fields            │
    │  6. Save with auto-versioning        │
    └──────────────────────────────────────┘
       ↓
    Output: Enriched company_record
    Files: {company_id}.json, {company_id}_v*.json (backups)

Fields enriched:
    - brand_name, hq_city, hq_state, hq_country
    - founded_year, categories
    - total_raised_usd, last_disclosed_valuation_usd
    - last_round_name, last_round_date

================================================================================
PHASE 2: PAYLOAD AGENT DETAILS
================================================================================

Payload Agent extracts entities using Pinecone vector search:

    Input: company_id
       ↓
    ┌──────────────────────────────────────┐
    │  LangGraph Workflow (Payload)        │
    ├──────────────────────────────────────┤
    │  1. Retrieve payload                 │
    │  2. Validate structure               │
    │  3. Search Pinecone vectors          │
    │  4. Extract entities with LLM        │
    │  5. Fill entity arrays               │
    │  6. Save with auto-versioning        │
    └──────────────────────────────────────┘
       ↓
    Output: Enriched entity arrays
    Files: {company_id}.json (updated), {company_id}_v*.json (backups)

Entities extracted:
    - events[] - funding, partnerships, product releases
    - products[] - product details, pricing
    - leadership[] - executives, founders
    - snapshots[] - headcount, job openings
    - visibility[] - news mentions, ratings

================================================================================
VERSIONING SYSTEM
================================================================================

Auto-versioning ensures no data loss:

    First save:  → company.json
    Second save: → company_v1.json (backup) + company.json (new)
    Third save:  → company_v2.json (backup) + company.json (new)

Both agents use the same versioning system, so all updates are tracked.

================================================================================
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(workflow_diagram)
        
        logger.info(f"✅ Master orchestrator workflow diagram saved to: {output_file}")
        return str(output_file)
        
    except Exception as e:
        logger.error(f"❌ Failed to save workflow diagram: {e}")
        return None


# ===========================
# Master Orchestrator Class
# ===========================

class MasterOrchestrator:
    """
    Master orchestrator that combines Tavily and Payload agents.
    
    Workflow:
    1. Load initial payload
    2. Phase 1: Tavily Agent enriches company_record fields
    3. Phase 2: Payload Agent extracts entities (events, products, leadership, etc.)
    4. Merge results and save final payload
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize master orchestrator.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.file_io = FileIOManager()
        self.execution_summary = {
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "company_id": None,
            "tavily_phase": {},
            "payload_phase": {},
            "total_fields_filled": 0,
            "total_entities_added": 0,
            "errors": []
        }
        
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    @traceable(name="master_orchestrator_agent_run", run_type="chain")
    async def enrich_company(
        self,
        company_id: str,
        enable_tavily: bool = True,
        enable_payload: bool = True
    ) -> Dict[str, Any]:
        """
        Main orchestration method - runs both agents in sequence.
        
        Args:
            company_id: Company identifier (e.g., 'abridge')
            enable_tavily: Run Tavily agent for company_record fields
            enable_payload: Run Payload agent for entity extraction
            
        Returns:
            Final enrichment summary with results from both agents
        """
        self.execution_summary["company_id"] = company_id
        
        logger.info("=" * 80)
        logger.info(f"🚀 MASTER ORCHESTRATOR - Starting enrichment for {company_id}")
        logger.info("=" * 80)
        logger.info(f"   Tavily Agent: {'✅ ENABLED' if enable_tavily else '❌ DISABLED'}")
        logger.info(f"   Payload Agent: {'✅ ENABLED' if enable_payload else '❌ DISABLED'}")
        logger.info("")
        
        try:
            # Phase 1: Tavily Agent - Enrich company_record fields
            tavily_result = None
            if enable_tavily:
                logger.info("=" * 80)
                logger.info("📡 PHASE 1: TAVILY AGENT - Enriching company_record fields")
                logger.info("=" * 80)
                tavily_result = await self._run_tavily_agent(company_id)
                self.execution_summary["tavily_phase"] = tavily_result
                logger.info(f"✅ Tavily phase complete: {tavily_result.get('status', 'unknown')}")
                logger.info("")
            
            # Phase 2: Payload Agent - Extract entities from Pinecone
            payload_result = None
            if enable_payload:
                logger.info("=" * 80)
                logger.info("🔍 PHASE 2: PAYLOAD AGENT - Extracting entities from Pinecone")
                logger.info("=" * 80)
                payload_result = await self._run_payload_agent(company_id)
                self.execution_summary["payload_phase"] = payload_result
                logger.info(f"✅ Payload phase complete: {payload_result.get('status', 'unknown')}")
                logger.info("")
            
            # Merge and finalize
            final_result = await self._merge_results(
                company_id,
                tavily_result,
                payload_result
            )
            
            self.execution_summary["end_time"] = datetime.now(timezone.utc).isoformat()
            self.execution_summary["total_fields_filled"] = final_result.get("total_fields_filled", 0)
            self.execution_summary["total_entities_added"] = final_result.get("total_entities_added", 0)
            
            # Print summary
            self._print_summary()
            
            return final_result
            
        except Exception as e:
            logger.error(f"❌ Master orchestrator failed: {e}", exc_info=True)
            self.execution_summary["errors"].append(str(e))
            self.execution_summary["end_time"] = datetime.now(timezone.utc).isoformat()
            raise
    
    async def _run_tavily_agent(self, company_id: str) -> Dict[str, Any]:
        """
        Run Tavily agent to enrich company_record fields.
        
        Args:
            company_id: Company identifier
            
        Returns:
            Tavily agent execution result
        """
        logger.info(f"🔧 Initializing Tavily Agent for {company_id}...")
        
        try:
            # Use the existing Tavily agent orchestrator
            result = await enrich_single_company(company_id)
            
            logger.info(f"📊 Tavily Agent Results:")
            logger.info(f"   Status: {result.get('status', 'unknown')}")
            logger.info(f"   Fields enriched: {result.get('fields_enriched', 0)}")
            
            return {
                "status": "success",
                "agent": "tavily",
                "company_id": company_id,
                "fields_enriched": result.get("fields_enriched", 0),
                "result": result
            }
            
        except Exception as e:
            logger.error(f"❌ Tavily agent failed: {e}")
            return {
                "status": "error",
                "agent": "tavily",
                "company_id": company_id,
                "error": str(e)
            }
    
    async def _run_payload_agent(self, company_id: str) -> Dict[str, Any]:
        """
        Run Payload agent to extract entities from Pinecone.
        
        Args:
            company_id: Company identifier
            
        Returns:
            Payload agent execution result
        """
        logger.info(f"🔧 Initializing Payload Agent for {company_id}...")
        
        try:
            # Initialize Pinecone adapter
            rag_search_tool = None
            try:
                logger.info("   Connecting to Pinecone...")
                rag_search_tool = create_pinecone_adapter()
                logger.info("   ✅ Pinecone connection established")
            except Exception as e:
                logger.warning(f"   ⚠️  Pinecone unavailable: {e}")
            
            # Initialize LLM
            llm = None
            try:
                from langchain_openai import ChatOpenAI
                logger.info("   Initializing LLM (gpt-4o)...")
                llm = ChatOpenAI(
                    model="gpt-4o",
                    temperature=0,
                    max_tokens=500,
                    api_key=os.getenv("OPENAI_API_KEY")
                )
                logger.info("   ✅ LLM initialized")
            except Exception as e:
                logger.warning(f"   ⚠️  LLM initialization failed: {e}")
            
            # Run payload workflow
            logger.info(f"   Running payload workflow...")
            final_state = run_payload_workflow(
                company_id=company_id,
                rag_search_tool=rag_search_tool,
                llm=llm
            )
            
            # Extract results
            update_result = final_state.get("update_result", {})
            filled_count = update_result.get("filled_count", 0)
            
            logger.info(f"📊 Payload Agent Results:")
            logger.info(f"   Status: {final_state.get('status', 'unknown')}")
            logger.info(f"   Fields filled: {filled_count}")
            logger.info(f"   Output: {update_result.get('output_file', 'N/A')}")
            
            return {
                "status": "success",
                "agent": "payload",
                "company_id": company_id,
                "fields_filled": filled_count,
                "output_file": update_result.get("output_file"),
                "result": final_state
            }
            
        except Exception as e:
            logger.error(f"❌ Payload agent failed: {e}")
            return {
                "status": "error",
                "agent": "payload",
                "company_id": company_id,
                "error": str(e)
            }
    
    async def _merge_results(
        self,
        company_id: str,
        tavily_result: Optional[Dict[str, Any]],
        payload_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge results from both agents and create final payload.
        
        Args:
            company_id: Company identifier
            tavily_result: Results from Tavily agent
            payload_result: Results from Payload agent
            
        Returns:
            Merged final result
        """
        logger.info("=" * 80)
        logger.info("🔄 MERGING RESULTS - Combining Tavily and Payload agent outputs")
        logger.info("=" * 80)
        
        try:
            # Load the final payload (should have both agents' updates)
            payload = await self.file_io.read_payload(company_id)
            
            if not payload:
                logger.error(f"❌ Could not load final payload for {company_id}")
                return {
                    "status": "error",
                    "company_id": company_id,
                    "error": "Payload not found after enrichment"
                }
            
            # Count enriched fields
            company_record = payload.get("company_record", {})
            filled_fields = sum(1 for v in company_record.values() if v is not None and v != "")
            
            # Count entities
            total_entities = (
                len(payload.get("events", [])) +
                len(payload.get("products", [])) +
                len(payload.get("leadership", [])) +
                len(payload.get("snapshots", [])) +
                len(payload.get("visibility", []))
            )
            
            logger.info(f"📊 Final Payload Statistics:")
            logger.info(f"   Company record fields filled: {filled_fields}")
            logger.info(f"   Total entities: {total_entities}")
            logger.info(f"      - Events: {len(payload.get('events', []))}")
            logger.info(f"      - Products: {len(payload.get('products', []))}")
            logger.info(f"      - Leadership: {len(payload.get('leadership', []))}")
            logger.info(f"      - Snapshots: {len(payload.get('snapshots', []))}")
            logger.info(f"      - Visibility: {len(payload.get('visibility', []))}")
            
            return {
                "status": "success",
                "company_id": company_id,
                "total_fields_filled": filled_fields,
                "total_entities_added": total_entities,
                "entity_breakdown": {
                    "events": len(payload.get("events", [])),
                    "products": len(payload.get("products", [])),
                    "leadership": len(payload.get("leadership", [])),
                    "snapshots": len(payload.get("snapshots", [])),
                    "visibility": len(payload.get("visibility", []))
                },
                "tavily_result": tavily_result,
                "payload_result": payload_result,
                "final_payload": payload
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to merge results: {e}")
            return {
                "status": "error",
                "company_id": company_id,
                "error": str(e)
            }
    
    def _print_summary(self):
        """Print execution summary."""
        logger.info("\n" + "=" * 80)
        logger.info("📈 MASTER ORCHESTRATOR - EXECUTION SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"\n🏢 Company: {self.execution_summary['company_id']}")
        
        # Tavily phase
        tavily = self.execution_summary.get("tavily_phase", {})
        if tavily:
            logger.info(f"\n📡 Tavily Agent:")
            logger.info(f"   Status: {tavily.get('status', 'N/A')}")
            logger.info(f"   Fields enriched: {tavily.get('fields_enriched', 0)}")
        
        # Payload phase
        payload = self.execution_summary.get("payload_phase", {})
        if payload:
            logger.info(f"\n🔍 Payload Agent:")
            logger.info(f"   Status: {payload.get('status', 'N/A')}")
            logger.info(f"   Fields filled: {payload.get('fields_filled', 0)}")
        
        # Overall
        logger.info(f"\n📊 Overall Results:")
        logger.info(f"   Total fields filled: {self.execution_summary['total_fields_filled']}")
        logger.info(f"   Total entities added: {self.execution_summary['total_entities_added']}")
        
        # Timing
        start = self.execution_summary["start_time"]
        end = self.execution_summary["end_time"]
        if start and end:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            duration = (end_dt - start_dt).total_seconds()
            logger.info(f"\n⏱️  Execution Time: {duration:.2f} seconds")
        
        # Errors
        errors = self.execution_summary.get("errors", [])
        if errors:
            logger.warning(f"\n⚠️  Errors: {len(errors)}")
            for error in errors:
                logger.warning(f"   - {error}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ MASTER ORCHESTRATOR COMPLETE")
        logger.info("=" * 80)


# ===========================
# CLI Interface
# ===========================

async def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Master Orchestrator - Combines Tavily and Payload agents for comprehensive enrichment"
    )
    parser.add_argument(
        "company_id",
        help="Company identifier (e.g., 'abridge', 'world_labs')"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--tavily-only",
        action="store_true",
        help="Run only Tavily agent (company_record fields)"
    )
    parser.add_argument(
        "--payload-only",
        action="store_true",
        help="Run only Payload agent (entity extraction)"
    )
    
    args = parser.parse_args()
    
    # Setup LangSmith
    if setup_langsmith():
        logger.info("✅ LangSmith tracing ENABLED")
    
    # Save workflow diagram
    try:
        diagram_path = save_master_workflow_diagram()
        if diagram_path:
            logger.info(f"📊 Workflow diagram: {diagram_path}")
    except Exception as e:
        logger.warning(f"⚠️  Could not save workflow diagram: {e}")
    
    # Determine which agents to run
    enable_tavily = not args.payload_only
    enable_payload = not args.tavily_only
    
    # Run master orchestrator
    orchestrator = MasterOrchestrator(verbose=args.verbose)
    
    try:
        result = await orchestrator.enrich_company(
            company_id=args.company_id,
            enable_tavily=enable_tavily,
            enable_payload=enable_payload
        )
        
        if result["status"] == "success":
            logger.info(f"\n✅ SUCCESS - {args.company_id} enriched successfully")
            sys.exit(0)
        else:
            logger.error(f"\n❌ FAILED - {args.company_id} enrichment failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n❌ FATAL ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
