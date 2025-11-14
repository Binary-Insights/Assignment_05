"""
Supervisor Agent stub for Assignment 5.

This should create a Due Diligence Supervisor Agent using your chosen agent framework.
For now, we demonstrate a fake ReAct-style sequence that calls the tools directly.
"""

import asyncio
from datetime import date
import sys
from pathlib import Path

# Add parent directory to path to allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.payload_tool import get_latest_structured_payload
from tools.rag_tool import rag_search_company
from tools.risk_logger import report_layoff_signal, LayoffSignal

# TODO: import and configure your real agent framework here.

async def demo_supervisor_run(company_id: str):
    print("Thought: I should get the latest structured payload.")
    payload = await get_latest_structured_payload(company_id)
    print("Observation (payload):", payload)

    print("Thought: I should search for layoffs.")
    chunks = await rag_search_company(company_id, "layoffs OR workforce reduction")
    print("Observation (rag):", chunks)

    if any("layoff" in c["text"].lower() for c in chunks):
        print("Thought: I should log a layoff risk signal.")
        signal = LayoffSignal(
            company_id=company_id,
            occurred_on=date.today(),
            description="Potential layoff signal detected in RAG results.",
            source_url=chunks[0]["source_url"],
        )
        await report_layoff_signal(signal)
    else:
        print("Thought: No layoff signals detected.")

if __name__ == "__main__":
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else "00000000-0000-0000-0000-000000000000"
    asyncio.run(demo_supervisor_run(cid))