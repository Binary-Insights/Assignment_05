def evaluate_dashboards(rag_md: str, structured_md: str):
    """
    Stub evaluator: always prefers structured dashboard.
    Replace with rubric-based logic or an LLM call.
    """
    return {
        "winner": "structured",
        "scores": {
            "rag": {"factual": 2, "schema": 2, "provenance": 1, "hallucination": 1, "readability": 1},
            "structured": {"factual": 3, "schema": 2, "provenance": 2, "hallucination": 2, "readability": 1},
        },
    }