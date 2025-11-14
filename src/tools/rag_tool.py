from typing import List, Dict

async def rag_search_company(company_id: str, query: str) -> List[Dict]:
    """
    Tool: rag_search_company

    Perform retrieval-augmented search for the specified company and query.
    This should hit your existing vector DB (e.g., Chroma, FAISS, Qdrant)
    created in Assignment 2.

    Args:
        company_id: The canonical company identifier.
        query: Natural language query string (e.g., "layoffs", "funding").

    Returns:
        A list of chunks with metadata:
        [
          {"text": "<retrieved passage>",
           "source_url": "https://example.com/...",
           "score": 0.87},
          ...
        ]

    NOTE: This is a stub. Connect it to your real RAG index.
    """
    # TODO: implement real retrieval
    return [
        {
            "text": f"Stub context for company {company_id} answering query '{query}'.",
            "source_url": "https://example.com/stub",
            "score": 1.0,
        }
    ]