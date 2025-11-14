"""
Graph-based workflow stub for Assignment 5.

You will implement a workflow using LangGraph or your agent framework's WorkflowBuilder.
For now, this prints a stub plan and simulates a conditional branch.
"""

from src.agents.planner_agent import plan_due_diligence
from src.agents.evaluation_agent import evaluate_dashboards

def run_workflow(company_id: str):
    plan = plan_due_diligence(company_id)
    print("PLAN:", plan)

    # TODO: replace with real MCP calls
    rag_dashboard = "# RAG Dashboard (stub)"
    structured_dashboard = "# Structured Dashboard (stub)"

    eval_result = evaluate_dashboards(rag_dashboard, structured_dashboard)
    print("EVAL RESULT:", eval_result)

    # Simulate risk detection
    contains_risk = "layoff" in structured_dashboard.lower()
    if contains_risk:
        print("Risk detected -> HITL branch!")
        # TODO: implement HITL interaction (pause until approval)
    else:
        print("No risk detected -> Auto-approve branch.")

if __name__ == "__main__":
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else "00000000-0000-0000-0000-000000000000"
    run_workflow(cid)