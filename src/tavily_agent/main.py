"""
Main orchestrator for Agentic RAG payload enrichment.
Handles workflow execution, batch processing, and result management.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from logging.handlers import RotatingFileHandler

try:
    from langsmith import traceable
except ImportError:
    # Fallback if langsmith not installed
    def traceable(func):
        return func

# Add src directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tavily_agent.config import (
    LOG_LEVEL, LOG_FORMAT, LOGS_DIR, BATCH_SIZE, validate_config, setup_langsmith
)
from tavily_agent.file_io_manager import FileIOManager
from tavily_agent.vector_db_manager import VectorDBManager, get_vector_db_manager
from tavily_agent.graph import build_enrichment_graph, save_graph_visualization, PayloadEnrichmentState


# ===========================
# Logging Configuration
# ===========================

def setup_logging() -> logging.Logger:
    """Configure logging for the agent system."""
    
    logger = logging.getLogger("agentic_rag")
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # File handler
    log_file = LOGS_DIR / f"agentic_rag_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    
    # Formatter
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logging()


# ===========================
# LangSmith Setup
# ===========================

# Initialize LangSmith tracing if enabled
logger.info("\n" + "="*70)
logger.info("🔧 [LANGSMITH SETUP] Configuring LangSmith tracing...")
logger.info("="*70)

if setup_langsmith():
    logger.info("✅ [LANGSMITH] LangSmith tracing ENABLED")
    logger.info(f"   Project: {os.getenv('LANGCHAIN_PROJECT', 'N/A')}")
    logger.info(f"   Tracing V2: {os.getenv('LANGCHAIN_TRACING_V2', 'N/A')}")
    logger.info(f"   API Key: {os.getenv('LANGSMITH_API_KEY', 'Not set')[:20]}...")
else:
    logger.warning("⚠️  [LANGSMITH] LangSmith tracing DISABLED - check configuration")


# ===========================
# Main Orchestrator
# ===========================

class AgenticRAGOrchestrator:
    """Orchestrates the agentic RAG enrichment process."""
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.file_io = FileIOManager()
        self.graph = None
        self.execution_summary = {
            "total_companies": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None,
            "results": []
        }
    
    async def initialize(self):
        """Initialize the orchestrator and build the graph."""
        logger.info("\n" + "="*70)
        logger.info("🔧 [INIT] Initializing Agentic RAG Orchestrator")
        logger.info("="*70)
        
        # Validate configuration
        logger.info("🔍 [CONFIG] Validating configuration...")
        if not validate_config():
            logger.error("❌ [CONFIG] Configuration validation failed!")
            raise RuntimeError("Configuration validation failed. Check .env file.")
        logger.info("✅ [CONFIG] Configuration valid")
        
        # Build the enrichment graph
        logger.info("💬 [GRAPH] Building LangGraph workflow...")
        self.graph = build_enrichment_graph()
        logger.info("✅ [GRAPH] LangGraph workflow built successfully")
        
        # Save graph visualization (optional, don't block on errors)
        try:
            graph_viz_path = LOGS_DIR / "graph_structure"
            graph_viz_path.mkdir(parents=True, exist_ok=True)
            save_graph_visualization(self.graph, str(graph_viz_path / "graph_visualization.png"))
            logger.info("📊 [GRAPH] Graph visualization saved")
        except Exception as e:
            logger.warning(f"⚠️  [GRAPH] Could not save visualization: {e}")
        
        logger.info("🌟 [INIT] Orchestrator ready!\n")
    
    async def process_single_company(self, company_name: str) -> Dict[str, Any]:
        """
        Process enrichment for a single company.
        NOTE: No @traceable decorator - execution is part of parent async context
        
        Args:
            company_name: Company identifier
        
        Returns:
            Result dictionary with status and metadata
        """
        logger.info(f"\n" + "="*70)
        logger.info(f"📄 [ENRICH] Processing {company_name}")
        logger.info("="*70)
        
        result = {
            "company_name": company_name,
            "status": "started",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "null_fields_found": 0,
            "null_fields_filled": 0,
            "errors": []
        }
        
        try:
            # 1. Read payload
            logger.info(f"📥 [FILE] Reading payload for {company_name}...")
            payload = await self.file_io.read_payload(company_name)
            
            if not payload:
                logger.error(f"❌ [FILE] Could not read payload file")
                result["status"] = "failed"
                result["errors"].append("Could not read payload file")
                return result
            logger.info(f"✅ [FILE] Payload loaded successfully")
            
            # 2. Backup original payload
            logger.info(f"📋 [BACKUP] Backing up original payload...")
            await self.file_io.backup_payload(company_name)
            logger.info(f"✅ [BACKUP] Backup complete")
            
            # 3. Create initial state
            logger.info(f"🔰 [STATE] Creating enrichment state...")
            state = PayloadEnrichmentState(
                company_name=company_name,
                company_id=payload.get("company_record", {}).get("company_id", company_name),
                current_payload=json.loads(json.dumps(payload, default=str)),
                original_payload=json.loads(json.dumps(payload, default=str))
            )
            
            result["null_fields_found"] = len(state.null_fields)
            logger.info(f"✅ [STATE] State created with {len(state.null_fields)} null fields")
            
            # 4. Execute workflow
            logger.info(f"\n🚀 [WORKFLOW] Starting enrichment workflow...")
            final_state = await self._execute_workflow(state)
            
            # 5. Calculate metrics - count actual field updates, not just keys in extracted_values
            # extracted_values contains meta info like "search_queries", so we need to be smarter
            actual_fields_updated = {k: v for k, v in final_state.extracted_values.items() 
                                    if k not in ["search_queries"]}
            result["null_fields_filled"] = len(actual_fields_updated)
            result["errors"] = final_state.errors
            result["extracted_fields"] = actual_fields_updated
            logger.info(f"\n📊 [METRICS] Updated {len(actual_fields_updated)} fields")
            for field, value in actual_fields_updated.items():
                logger.info(f"   ✅ {field}: {repr(value)}")
            
            # 6. Save updated payload
            logger.info(f"📝 [FILE] Saving updated payload...")
            await self.file_io.save_payload(
                company_name=company_name,
                payload=final_state.current_payload
            )
            logger.info(f"✅ [FILE] Payload saved successfully")
            
            result["status"] = "completed"
            result["iteration"] = final_state.iteration
            
            logger.info(f"🎉 [ENRICH COMPLETE] {company_name}: {result['null_fields_filled']} fields updated")
            logger.info("="*70 + "\n")
            
        except Exception as e:
            logger.error(f"❌ [ERROR] Error processing {company_name}: {type(e).__name__}: {e}", exc_info=True)
            result["status"] = "failed"
            result["errors"].append(str(e))
            logger.info("="*70 + "\n")
        
        return result
    
    async def _execute_workflow(self, state: PayloadEnrichmentState) -> PayloadEnrichmentState:
        """
        Execute the LangGraph workflow asynchronously.
        Uses ainvoke to support async nodes (LLM extraction chain).
        NOTE: No @traceable decorator - this is part of the parent process_single_company trace
        
        Args:
            state: Initial enrichment state
        
        Returns:
            Final state after workflow execution
        """
        try:
            # Use a high default recursion limit to avoid errors
            # Most workflows will complete in far fewer iterations
            recursion_limit = 100
            
            logger.info(f"🔬 [INVOKE] Invoking LangGraph with high recursion limit: {recursion_limit}")
            config = {"recursion_limit": recursion_limit}
            
            # Use ainvoke for async support (required for LLM extraction chain)
            final_state = await self.graph.ainvoke(state.dict(), config=config)
            
            logger.info(f"✅ [INVOKE] LangGraph execution completed")
            # Convert back to PayloadEnrichmentState
            return PayloadEnrichmentState(**final_state)
            
        except Exception as e:
            logger.error(f"❌ [INVOKE] Workflow execution error: {type(e).__name__}: {e}", exc_info=True)
            raise
    
    async def process_batch(self, company_names: List[str]) -> Dict[str, Any]:
        """
        Process multiple companies concurrently.
        
        Args:
            company_names: List of company identifiers
        
        Returns:
            Batch processing summary
        """
        logger.info(f"\n📦 [BATCH] Processing batch of {len(company_names)} companies")
        logger.info(f"Companies: {', '.join(company_names)}")
        
        self.execution_summary["start_time"] = datetime.now(timezone.utc).isoformat()
        self.execution_summary["total_companies"] = len(company_names)
        
        # Process sequentially to avoid overwhelming system
        all_results = []
        for i, company_name in enumerate(company_names, 1):
            logger.info(f"\n🔄 [BATCH] Processing {i}/{len(company_names)}: {company_name}")
            result = await self.process_single_company(company_name)
            all_results.append(result)
        
        self.execution_summary["end_time"] = datetime.now(timezone.utc).isoformat()
        self.execution_summary["results"] = all_results
        
        # Calculate summary statistics
        for result in all_results:
            if result["status"] == "completed":
                self.execution_summary["successful"] += 1
            elif result["status"] == "failed":
                self.execution_summary["failed"] += 1
            else:
                self.execution_summary["skipped"] += 1
        
        logger.info(f"\n✅ [BATCH COMPLETE] Success: {self.execution_summary['successful']}, Failed: {self.execution_summary['failed']}")
        return self.execution_summary
    
    async def process_all_available(self) -> Dict[str, Any]:
        """
        Process all available company payloads.
        
        Returns:
            Batch processing summary
        """
        logger.info("\n🔎 [DISCOVER] Loading all available company payloads...")
        companies = await self.file_io.list_company_payloads()
        
        if not companies:
            logger.warning("⚠️  [DISCOVER] No company payloads found")
            return self.execution_summary
        
        logger.info(f"📋 [DISCOVER] Found {len(companies)} companies to process")
        
        return await self.process_batch(companies)
    
    def save_execution_summary(self) -> Path:
        """
        Save execution summary to file.
        
        Returns:
            Path to summary file
        """
        summary_path = LOGS_DIR / f"execution_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(summary_path, "w") as f:
                json.dump(self.execution_summary, f, indent=2, default=str)
            logger.info(f"Saved execution summary to {summary_path}")
            return summary_path
        except Exception as e:
            logger.error(f"Error saving summary: {e}")
            return None
    
    def print_summary(self):
        """Print execution summary to console."""
        print("\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"Total Companies: {self.execution_summary['total_companies']}")
        print(f"Successful: {self.execution_summary['successful']}")
        print(f"Failed: {self.execution_summary['failed']}")
        print(f"Skipped: {self.execution_summary['skipped']}")
        print(f"Start Time: {self.execution_summary['start_time']}")
        print(f"End Time: {self.execution_summary['end_time']}")
        print("\nDetailed Results:")
        for result in self.execution_summary['results']:
            status_icon = "✓" if result['status'] == 'completed' else "✗"
            print(f"  {status_icon} {result['company_name']}: {result['status']} "
                  f"({result['null_fields_filled']}/{result['null_fields_found']} fields)")
            if result['errors']:
                for error in result['errors']:
                    print(f"      - {error}")
        print("="*60 + "\n")


# ===========================
# Entry Points
# ===========================

@traceable
async def enrich_single_company(company_name: str) -> Dict[str, Any]:
    """
    Enrich a single company payload.
    This is the single @traceable entry point that creates ONE unified trace.
    
    Args:
        company_name: Company identifier
    
    Returns:
        Processing result
    """
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    return await orchestrator.process_single_company(company_name)


async def enrich_multiple_companies(company_names: List[str]) -> Dict[str, Any]:
    """
    Enrich multiple company payloads.
    
    Args:
        company_names: List of company identifiers
    
    Returns:
        Batch processing summary
    """
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    summary = await orchestrator.process_batch(company_names)
    orchestrator.print_summary()
    orchestrator.save_execution_summary()
    return summary


async def enrich_all_companies() -> Dict[str, Any]:
    """
    Enrich all available company payloads.
    
    Returns:
        Batch processing summary
    """
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    summary = await orchestrator.process_all_available()
    orchestrator.print_summary()
    orchestrator.save_execution_summary()
    return summary


# ===========================
# CLI Interface
# ===========================

async def main():
    """Main entry point for CLI usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py single <company_name> [--test-mode] [--test-dir <path>]   - Enrich single company")
        print("  python main.py multiple <company1> <company2> ... [--test-mode]           - Enrich multiple companies")
        print("  python main.py all [--test-mode] [--test-dir <path>]                     - Enrich all companies")
        print("")
        print("Options:")
        print("  --test-mode              Save outputs to /tmp/agentic_rag_test instead of data/payloads")
        print("  --test-dir <path>        Custom output directory for test mode (implies --test-mode)")
        sys.exit(1)
    
    # Parse flags
    test_mode = False
    test_dir = None
    
    # Find and remove test flags from argv
    cleaned_argv = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == "--test-mode":
            test_mode = True
            i += 1
        elif sys.argv[i] == "--test-dir" and i + 1 < len(sys.argv):
            test_dir = sys.argv[i + 1]
            test_mode = True
            i += 2
        else:
            cleaned_argv.append(sys.argv[i])
            i += 1
    
    # Enable test mode if requested
    if test_mode:
        logger.info(f"\n🧪 [TEST MODE] Enabled - outputs saved to {test_dir or '/tmp/agentic_rag_test'}")
        FileIOManager.set_test_mode(enable=True, output_dir=test_dir)
    
    command = cleaned_argv[1] if len(cleaned_argv) > 1 else None
    
    try:
        if command == "single" and len(cleaned_argv) > 2:
            company_name = cleaned_argv[2]
            logger.info(f"\n📍 [CLI] Enriching single company: {company_name}")
            if test_mode:
                logger.info(f"🧪 [TEST MODE] Outputs will be saved to {FileIOManager.TEST_OUTPUT_DIR}")
            result = await enrich_single_company(company_name)
            print(json.dumps(result, indent=2, default=str))
        
        elif command == "multiple" and len(cleaned_argv) > 2:
            companies = cleaned_argv[2:]
            logger.info(f"\n📍 [CLI] Enriching {len(companies)} companies: {', '.join(companies)}")
            if test_mode:
                logger.info(f"🧪 [TEST MODE] Outputs will be saved to {FileIOManager.TEST_OUTPUT_DIR}")
            summary = await enrich_multiple_companies(companies)
            print(json.dumps(summary, indent=2, default=str))
        
        elif command == "all":
            logger.info("\n📍 [CLI] Enriching all available companies")
            if test_mode:
                logger.info(f"🧪 [TEST MODE] Outputs will be saved to {FileIOManager.TEST_OUTPUT_DIR}")
            summary = await enrich_all_companies()
            print(json.dumps(summary, indent=2, default=str))
        
        else:
            logger.error(f"❌ [CLI] Invalid command: {command}")
            print(f"Invalid command: {command}")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ [FATAL] Fatal error: {type(e).__name__}: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
