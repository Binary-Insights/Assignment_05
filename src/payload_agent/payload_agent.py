"""
LangGraph-Based Payload Agent for Assignment 5 with ReAct Tool Calling.

This agent:
- Uses LangChain's ReAct pattern with tool calling
- Tools are decorated with @tool for agent discovery
- LLM decides which tools to call based on reasoning
- Provides explicit Thought/Action/Observation logging

Usage:
    agent = PayloadAgent()
    result = agent.retrieve_and_validate("abridge")
    result = agent.retrieve_and_update("abridge")
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from payload_agent.tools import (
    get_latest_structured_payload,
    validate_payload,
    update_payload,
)
 
from payload_agent.tools.rag_adapter import create_pinecone_adapter

# LangGraph and LangChain imports for tool calling
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent  # Deprecation warning but works
except ImportError as e:
    import logging
    logging.warning(f"LangGraph/LangChain imports failed: {e}")
    ChatOpenAI = None
    tool = None
    create_react_agent = None

# Setup
load_dotenv()
logger = logging.getLogger(__name__)

def _configure_logging():
    """Configure logging once (idempotent). Uses structured key=value style.

    If the root logger has no handlers (fresh process), install a basic handler.
    Format includes timestamp, level, module, and message. For deeper future
    analysis you can swap to JSON (e.g. `%(message)s` expecting preformatted JSON).
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured (avoid duplicate handlers)
        return

    level = os.getenv("PAYLOAD_AGENT_LOG_LEVEL", "INFO")
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(level=level, format=log_format)

    # File logging setup
    try:
        log_dir = Path(__file__).parent.parent.parent / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = os.getenv("PAYLOAD_AGENT_LOG_FILE", str(log_dir / "payload_agent.log"))
        file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=2)
        file_handler.setFormatter(logging.Formatter(log_format))
        file_handler.setLevel(level)
        root.addHandler(file_handler)
        root.debug(f"File logging initialized at {log_file}")
    except Exception as e:
        root.warning(f"Failed to initialize file logging: {e}")

_configure_logging()


class PayloadAgent:
    """
    PayloadAgent with LangGraph ReAct Agent and Tool Calling.
    
    Uses LangGraph's create_react_agent:
    - Tools decorated with @tool for agent discovery
    - LLM-powered agent decides which tools to call
    - Automatic ReAct reasoning (Thought/Action/Observation)
    - Built on LangGraph state machine
    """
    
    def __init__(self, model_name: str = "gpt-4o", use_agent: bool = True):
        """
        Initialize PayloadAgent with LangGraph ReAct agent and tool calling.
        
        Args:
            model_name: OpenAI model (defaults to gpt-4o for cost efficiency)
            use_agent: Whether to initialize LangGraph agent (default: True)
        """
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not set; LLM features will not be available")
        
        self.model_name = model_name
        self.use_agent = use_agent
        
        # Initialize LLM for both extraction and agent reasoning
        if ChatOpenAI is None:
            logger.warning("langchain_openai not installed; LLM features will not be available")
            self.llm = None
        elif not os.getenv("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not set; LLM features will not be available")
            self.llm = None
        else:
            try:
                self.llm = ChatOpenAI(
                    model_name=model_name,
                    temperature=0.0,  # Deterministic
                    api_key=os.getenv("OPENAI_API_KEY"),
                    request_timeout=60,
                )
                logger.info(f"LLM initialized for extraction and agent: {model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
                self.llm = None
        
        # Initialize Pinecone search adapter for vector fills
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        pinecone_env = os.getenv("PINECONE_ENVIRONMENT")
        pinecone_index = os.getenv("PINECONE_INDEX_NAME")
        
        if pinecone_api_key and pinecone_env and pinecone_index:
            try:
                self.rag_search_tool = create_pinecone_adapter(
                    index_name=pinecone_index,
                    api_key=pinecone_api_key,
                    environment=pinecone_env,
                )
                logger.info(f"Pinecone adapter initialized: index={pinecone_index}")
            except Exception as e:
                logger.warning(f"Failed to initialize Pinecone adapter: {e}")
                self.rag_search_tool = None
        else:
            logger.warning("Pinecone credentials not configured in .env")
            self.rag_search_tool = None
        
        # Initialize LangGraph agent with tools
        self.agent_executor = None
        if self.use_agent and self.llm and create_react_agent and tool:
            self.agent_executor = self._create_langgraph_agent()
        
        logger.info(f"Initialized PayloadAgent with model={model_name}, agent_enabled={use_agent}")
    
    def _create_langgraph_agent(self):
        """
        Create LangGraph ReAct agent with tool calling.
        
        Returns:
            LangGraph agent with tools for payload operations
        """
        # Import the @tool decorated functions directly
        # These are already tool-decorated and agent-discoverable
        from payload_agent.tools.retrieval import get_latest_structured_payload
        from payload_agent.tools.validation import validate_payload, update_payload
        from langchain_core.tools import tool
        
        # Create agent wrapper tools that call the actual tools with proper parameters
        @tool
        def retrieve_payload_tool(company_id: str) -> dict:
            """Retrieve and load a company payload from storage.
            
            Args:
                company_id: Company identifier (e.g., 'abridge')
                
            Returns:
                Dict with company_id, status, and payload data
            """
            logger.info(f"AGENT TOOL CALL: retrieve_payload company_id={company_id}")
            payload = get_latest_structured_payload.invoke({"company_id": company_id})
            return {
                "company_id": company_id,
                "status": "success",
                "payload": payload.model_dump() if hasattr(payload, 'model_dump') else str(payload)
            }
        
        @tool
        def validate_payload_tool(company_id: str) -> dict:
            """Validate a company payload structure and check for required fields.
            
            Args:
                company_id: Company identifier (e.g., 'abridge')
                
            Returns:
                Dict with status, issues list, null_fields dict, and total_nulls count
            """
            logger.info(f"AGENT TOOL CALL: validate_payload company_id={company_id}")
            result = validate_payload.invoke({"company_id": company_id})
            return result
        
        @tool  
        def update_payload_tool(company_id: str) -> dict:
            """Update a company payload by filling null fields from Pinecone vector search.
            
            Saves updated payload as {company_id}_v2.json in data/payloads/ directory.
            
            Args:
                company_id: Company identifier (e.g., 'abridge')
                
            Returns:
                Dict with status, filled_count, output_file, filled_fields, unfilled_fields
            """
            logger.info(f"AGENT TOOL CALL: update_payload company_id={company_id}")
            
            # Call the new validation.update_payload tool with required parameters
            result = update_payload.invoke({
                "company_id": company_id,
                "rag_search_tool": self.rag_search_tool,
                "llm": self.llm,
            })
            
            return result
        
        # Create tools list
        tools = [retrieve_payload_tool, validate_payload_tool, update_payload_tool]
        
        # Create LangGraph ReAct agent
        agent_executor = create_react_agent(
            model=self.llm,
            tools=tools,
        )
        
        logger.info("LangGraph ReAct agent with tool calling initialized")
        return agent_executor
    
    # ========================================================================
    # ReAct Reasoning Methods (Thought/Action/Observation)
    # ========================================================================
    
    def think(self, task: str, company_id: str) -> str:
        """
        ReAct THOUGHT: Agent reasons about what to do before taking action.
        
        Args:
            task: Task to reason about (e.g., "validate", "update", "process")
            company_id: Company being processed
            
        Returns:
            Thought/reasoning string explaining the action plan
        """
        thoughts = {
            "validate": f"""
Thought: I need to validate the payload for {company_id}
- Step 1: Retrieve the latest structured payload
- Step 2: Check if all required fields are present
- Step 3: Identify any null/missing fields that could be filled
- Step 4: Report validation status and issues
Expected outcome: Valid payload structure with issue list
            """,
            "update": f"""
Thought: I need to update the payload for {company_id} with vector fills
- Step 1: Retrieve the payload
- Step 2: Search Pinecone for data about missing fields
- Step 3: Use LLM to extract values from found snippets
- Step 4: Fill null fields with high-confidence extracted values
- Step 5: Track provenance for each filled field
Expected outcome: Enriched payload with metadata about fills
            """,
            "process": f"""
Thought: I need to fully process the payload for {company_id}
- Step 1: Retrieve payload from storage
- Step 2: Validate the structure and identify issues
- Step 3: Attempt to fill null fields from Pinecone vectors
- Step 4: Verify improved data quality
- Step 5: Return final enriched payload
Expected outcome: Complete, validated, and enriched payload
            """
        }
        
        thought = thoughts.get(task, f"Processing {company_id} with task: {task}")
        logger.info(f"Agent THOUGHT: {thought}")
        return thought
    
    def act(self, action: str, company_id: str, **kwargs) -> Dict[str, Any]:
        """
        ReAct ACTION: Agent executes the planned action using available tools.
        
        Args:
            action: Action to take (retrieve, validate, update)
            company_id: Company identifier
            **kwargs: Additional parameters for the action
            
        Returns:
            Action result as dict
        """
        logger.info(f"Agent ACTION: Executing '{action}' for {company_id}")
        
        if action == "retrieve":
            return self.retrieve_payload(company_id)
        elif action == "validate":
            return self.validate_payload_workflow(company_id)
        elif action == "update":
            return self.update_payload_workflow(company_id, **kwargs)
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    
    def observe(self, action_result: Dict[str, Any], action: str) -> str:
        """
        ReAct OBSERVATION: Agent interprets the results of its action.
        
        Args:
            action_result: Result from the executed action
            action: The action that was executed
            
        Returns:
            Observation/interpretation string
        """
        observation = f"""
Observation from '{action}' action:
- Status: {action_result.get('status', 'unknown')}
- Details: """
        
        if action == "retrieve":
            payload = action_result.get('payload')
            if payload:
                observation += f"Retrieved payload with {len(payload.products)} products, {len(payload.leadership)} leadership entries"
        elif action == "validate":
            issues = action_result.get('issues', [])
            observation += f"Found {len(issues)} validation issues"
            if issues:
                observation += f": {'; '.join(issues[:2])}"
        elif action == "update":
            filled = len(action_result.get('filled_fields', []))
            unfilled = len(action_result.get('unfilled_nulls', []))
            observation += f"Filled {filled} fields, {unfilled} still null"
        
        logger.info(f"Agent OBSERVATION: {observation}")
        return observation
    
    def reason(self, task: str, company_id: str, verbose: bool = True) -> Dict[str, Any]:
        """
        Full ReAct reasoning cycle: Thought → Action → Observation
        
        Args:
            task: Task to perform (validate, update, process)
            company_id: Company identifier
            verbose: Whether to log detailed reasoning
            
        Returns:
            Combined result with reasoning steps
        """
        logger.info(f"=== ReAct Reasoning Cycle for {company_id} (task: {task}) ===")
        
        # THOUGHT
        thought = self.think(task, company_id)
        
        # ACTION - pass rag_search_tool for update tasks
        if task == "update":
            action_result = self.act(task, company_id, rag_search_tool=self.rag_search_tool)
        else:
            action_result = self.act(task, company_id)
        
        # OBSERVATION
        observation = self.observe(action_result, task)
        
        # Return combined result with all reasoning steps
        result = {
            "company_id": company_id,
            "task": task,
            "thought": thought,
            "action": task,
            "observation": observation,
            "action_result": action_result,
            "reasoning_complete": True,
        }
        
        if verbose:
            logger.info(f"Reasoning cycle complete. Result status: {action_result.get('status')}")
        
        return result
    
    def execute_with_agent(self, query: str) -> Dict[str, Any]:
        """
        Execute a task using the LangGraph ReAct agent with tool calling.
        
        The agent will:
        1. THINK about what to do (reasoning)
        2. Choose appropriate tools to call
        3. OBSERVE the results
        4. Continue until task is complete
        
        Args:
            query: Natural language query describing the task
                   e.g., "Validate the payload for company abridge"
                        "Update the payload for anthropic and fill null fields"
            
        Returns:
            Dict with agent execution result including reasoning trace
        """
        if not self.agent_executor:
            logger.error("LangGraph agent not initialized. Set use_agent=True")
            return {
                "status": "error",
                "message": "LangGraph agent not available. Initialize with use_agent=True"
            }
        
        logger.info(f"Executing with LangGraph agent: {query}")
        
        try:
            # LangGraph agent will automatically:
            # - Think about what to do (ReAct pattern)
            # - Choose tools to call (get_latest_structured_payload, validate_payload, etc.)
            # - Observe results
            # - Repeat until done
            result = self.agent_executor.invoke({"messages": [("user", query)]})
            
            logger.info("Agent execution complete")
            return {
                "status": "success",
                "query": query,
                "result": result,
                "messages": result.get("messages", [])
            }
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                "status": "error",
                "query": query,
                "error": str(e)
            }
    
    # ========================================================================
    # Retrieval Workflow
    # ========================================================================
    
    def retrieve_payload(self, company_id: str) -> Dict[str, Any]:
        """
        Retrieve complete payload for a company (no modifications).
        
        Args:
            company_id: Company identifier
            
        Returns:
            Dict with status and complete payload
        """
        logger.info(f"action=retrieve stage=start company_id={company_id}")
        
        # Call the tool using .invoke() since it's decorated with @tool
        payload = get_latest_structured_payload.invoke({"company_id": company_id})
        
        logger.info(f"action=retrieve stage=complete company_id={company_id}")
        
        return {
            "action": "retrieve",
            "company_id": company_id,
            "status": "success",
            "payload": payload.model_dump() if hasattr(payload, 'model_dump') else str(payload),
        }
    
    # ========================================================================
    # Validation Workflow
    # ========================================================================
    
    def validate_payload_workflow(self, company_id: str) -> Dict[str, Any]:
        """
        Retrieve and validate payload (deterministic checks only, no modifications).
        
        Args:
            company_id: Company identifier
            
        Returns:
            Dict with retrieval summary + validation result
        """
        logger.info(f"action=validate stage=start company_id={company_id}")
        
        try:
            # Validate using @tool function - returns dict with status, issues, null_fields
            validation_result = validate_payload.invoke({"company_id": company_id})
            logger.info(f"action=validate stage=complete company_id={company_id} validation_status={validation_result['status']}")
            
            # Get payload for counts (optional)
            payload = get_latest_structured_payload.invoke({"company_id": company_id})
            
            return {
                "action": "validate",
                "company_id": company_id,
                "status": validation_result["status"],
                "validation_result": validation_result,
                "payload_counts": {
                    "events": len(payload.events) if payload.events else 0,
                    "products": len(payload.products) if payload.products else 0,
                    "leadership": len(payload.leadership) if payload.leadership else 0,
                },
            }
        
        except Exception as e:
            logger.error(f"action=validate stage=error company_id={company_id} error={e}")
            return {
                "action": "validate",
                "company_id": company_id,
                "status": "error",
                "error": str(e),
            }
    
    # ========================================================================
    # Update Workflow (Validation + Vector Fills)
    # ========================================================================
    
    def update_payload_workflow(
        self,
        company_id: str,
        rag_search_tool: Any = None,
    ) -> Dict[str, Any]:
        """
        Retrieve payload and attempt to fill null fields from Pinecone vectors.
        
        Args:
            company_id: Company identifier
            rag_search_tool: Optional RAG search tool for vector fills
            
        Returns:
            Dict with update results, filled fields, and provenance
        """
        logger.info(f"action=update stage=start company_id={company_id}")
        
        try:
            # Use rag_search_tool from self if not provided
            if not rag_search_tool:
                rag_search_tool = self.rag_search_tool
            
            # Update using @tool function - returns dict with status, filled_count, output_file
            result = update_payload.invoke({
                "company_id": company_id,
                "rag_search_tool": rag_search_tool,
                "llm": self.llm,
            })
            
            # Extract results from new format
            filled_count = result.get("filled_count", 0)
            total_attempted = result.get("total_attempted", 0)
            filled_fields = result.get("filled_fields", {})
            unfilled_fields = result.get("unfilled_fields", {})
            
            logger.info(
                f"action=update stage=complete company_id={company_id} "
                f"filled_fields={filled_count}/{total_attempted}"
            )
            
            # Get payload for counts
            payload = get_latest_structured_payload.invoke({"company_id": company_id})
            
            return {
                "action": "update",
                "company_id": company_id,
                "status": result.get("status", "success"),
                "filled_fields": filled_fields,
                "unfilled_nulls": unfilled_fields,
                "total_filled": filled_count,
                "total_attempted": total_attempted,
                "output_file": result.get("output_file"),
                "payload_counts": {
                    "events": len(payload.events) if payload.events else 0,
                    "products": len(payload.products) if payload.products else 0,
                    "leadership": len(payload.leadership) if payload.leadership else 0,
                },
            }
        
        except Exception as e:
            logger.error(f"action=update stage=error company_id={company_id} error={repr(e)}")
            return {
                "action": "update",
                "company_id": company_id,
                "status": "error",
                "error": str(e),
            }
    
    # ========================================================================
    # Synchronous Interface (simple wrappers with ReAct)
    # ========================================================================
    
    def retrieve_and_validate(self, company_id: str, use_agent: bool = True, use_react: bool = False) -> Dict[str, Any]:
        """
        Synchronous: Retrieve and validate payload.
        
        Args:
            company_id: Company identifier
            use_agent: Use LangGraph autonomous agent (default: True - LLM decides tool sequence)
            use_react: Use manual ReAct pattern (default: False - predefined workflow)
            
        Returns:
            Combined result dict with agent trace if use_agent=True, or manual ReAct if use_react=True
        """
        if use_agent and self.agent_executor:
            # LangGraph agent autonomously decides which tools to call
            query = f"Validate the payload for company {company_id}. Check structure and identify any null or missing fields."
            return self.execute_with_agent(query)
        elif use_react:
            # Manual ReAct cycle with predefined workflow
            return self.reason(task="validate", company_id=company_id)
        else:
            # Direct execution without reasoning
            return self.validate_payload_workflow(company_id)
    
    def retrieve_and_update(self, company_id: str, rag_search_tool: Any = None, use_agent: bool = True, use_react: bool = False) -> Dict[str, Any]:
        """
        Synchronous: Retrieve and update (fill nulls from vectors).
        
        Args:
            company_id: Company identifier
            rag_search_tool: Optional RAG search tool for vector fills
            use_agent: Use LangGraph autonomous agent (default: True - LLM decides tool sequence)
            use_react: Use manual ReAct pattern (default: False - predefined workflow)
            
        Returns:
            Combined result dict with agent trace if use_agent=True, or manual ReAct if use_react=True
        """
        if use_agent and self.agent_executor:
            # LangGraph agent autonomously decides which tools to call
            query = f"Update the payload for company {company_id}. Fill null fields using Pinecone vector search and LLM extraction. Save the updated payload as {{company_id}}_v2.json."
            return self.execute_with_agent(query)
        elif use_react:
            # Manual ReAct cycle with predefined workflow
            return self.reason(task="update", company_id=company_id)
        else:
            # Direct execution without reasoning
            return self.update_payload_workflow(company_id, rag_search_tool)


# ============================================================================
# Example Usage & Testing
# ============================================================================

def main():
    """Test the PayloadAgent with sample workflows."""
    import sys
    
    # Parse command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python payload_agent.py <company_slug>")
        print("Example: python payload_agent.py abridge")
        sys.exit(1)
    
    company_id = sys.argv[1]
    
    print("\n" + "="*70)
    print(f"LANGGRAPH PAYLOAD AGENT - TESTING ({company_id})")
    print("="*70)
    
    try:
        agent = PayloadAgent()
    except Exception as e:
        print(f"Error initializing agent: {e}")
        sys.exit(1)
    
    # Test 1: Simple retrieval
    print("\n[TEST 1] Retrieve complete payload")
    print("-" * 70)
    result = agent.retrieve_payload(company_id)
    print(f"Status: {result['status']}")
    if result['status'] == 'success':
        payload = result['payload']
        company_record = payload.get('company_record', {})
        print(f"\nCompany: {company_record.get('legal_name', 'N/A')}")
        print(f"Website: {company_record.get('website', 'N/A')}")
        print(f"\nPayload Structure:")
        print(f"  Events: {len(payload.get('events', []))}")
        print(f"  Products: {len(payload.get('products', []))}")
        print(f"  Leadership: {len(payload.get('leadership', []))}")
        print(f"  Snapshots: {len(payload.get('snapshots', []))}")
        print(f"  Visibility: {len(payload.get('visibility', []))}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    
    # Test 2: Validate payload with LangGraph agent
    print("\n[TEST 2] Validate payload using LangGraph autonomous agent")
    print("-" * 70)
    result = agent.retrieve_and_validate(company_id, use_agent=True)
    print(f"Status: {result.get('status', 'unknown')}")
    
    # Extract validation results from agent messages
    if result.get('status') == 'success':
        messages = result.get('messages', [])
        print(f"Agent executed {len(messages)} reasoning steps")
        
        # Try to find the validation result in agent output
        for msg in messages:
            if hasattr(msg, 'content') and 'valid' in str(msg.content).lower():
                print(f"Agent response: {msg.content[:200]}...")
                break
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    # Test 3: Update payload with LangGraph agent (autonomous tool selection)
    print("\n[TEST 3] Update payload using LangGraph autonomous agent")
    print("-" * 70)
    result = agent.retrieve_and_update(company_id, use_agent=True)
    print(f"Status: {result.get('status', 'unknown')}")
    
    if result.get('status') == 'success':
        messages = result.get('messages', [])
        print(f"Agent executed {len(messages)} reasoning steps")
        
        # Try to find the update result in agent output
        for msg in messages:
            if hasattr(msg, 'content'):
                content = str(msg.content)
                if 'filled' in content.lower() or 'v2.json' in content:
                    print(f"Agent response: {content[:300]}...")
                    break
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 70)
    print("Tests complete! Agent used LangGraph autonomous tool selection.")
    print("=" * 70)
    print(f"\n✅ Success - {company_id} processed by payload agent")
    sys.exit(0)


if __name__ == "__main__":
    main()
