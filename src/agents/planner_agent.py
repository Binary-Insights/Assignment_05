def plan_due_diligence(company_id: str):
    """Return a simple, static plan. Replace with LLM-based planner if desired."""
    return {
        "company_id": company_id,
        "steps": [
            "generate_structured_dashboard",
            "generate_rag_dashboard",
            "evaluate_dashboards",
            "check_for_risks",
        ],
    }