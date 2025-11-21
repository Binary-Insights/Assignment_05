"""
MCP Server stub for Assignment 5.

This should expose your dashboard generation logic as MCP Tools, Resources, and Prompts.
For now, it just starts a FastAPI app with placeholder endpoints.

You may replace this with FastMCP or any MCP-compliant server implementation.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="PE Dashboard MCP Server (Stub)")

class CompanyIdList(BaseModel):
    company_ids: List[str]

@app.get("/resource/ai50/companies", response_model=CompanyIdList)
def get_companies():
    # TODO: load real company IDs from your AI50 seed JSON
    return CompanyIdList(company_ids=["00000000-0000-0000-0000-000000000000"])

@app.get("/prompt/pe-dashboard")
def get_pe_dashboard_prompt():
    # TODO: return your real 8-section dashboard prompt here
    return {
        "id": "pe-dashboard",
        "description": "PE 8-section dashboard prompt",
        "template": "## Company Overview\n..."
    }

class DashboardRequest(BaseModel):
    company_id: str

@app.post("/tool/generate_structured_dashboard")
def generate_structured_dashboard(req: DashboardRequest):
    # TODO: call your real structured dashboard logic (Assignment 2)
    return {"markdown": f"## Company Overview\nStub structured dashboard for {req.company_id}"}

@app.post("/tool/generate_rag_dashboard")
def generate_rag_dashboard(req: DashboardRequest):
    # TODO: call your real RAG dashboard logic (Assignment 2)
    return {"markdown": f"## Company Overview\nStub RAG dashboard for {req.company_id}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)