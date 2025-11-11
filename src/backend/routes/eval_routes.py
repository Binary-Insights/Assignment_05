"""
Evaluation API Endpoints

FastAPI endpoints for running LLM-based evaluations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import os
from pathlib import Path
from datetime import datetime

from result_evaluator import (
    evaluate_company,
    evaluate_batch,
    get_evaluation_summary,
    load_ground_truth
)
from eval_results_models import CompanyEvaluations, EvaluationResult


router = APIRouter(prefix="/api/evals", tags=["evaluations"])


class EvaluationRequest(BaseModel):
    """Request to evaluate a company."""
    company_slug: str
    company_name: str
    ground_truth_path: Optional[str] = "data/eval/ground_truth.json"
    structured_response_path: Optional[str] = "data/llm_response/structured_responses.json"
    rag_response_path: Optional[str] = "data/llm_response/rag_responses.json"


class EvaluationResponse(BaseModel):
    """Response from evaluation."""
    status: str
    message: str
    company_slug: str
    company_name: str
    structured: Optional[Dict[str, Any]] = None
    rag: Optional[Dict[str, Any]] = None
    winners: Dict[str, str] = {}
    timestamp: str


class BatchEvaluationRequest(BaseModel):
    """Request to evaluate all companies."""
    ground_truth_path: Optional[str] = "data/eval/ground_truth.json"
    structured_response_path: Optional[str] = "data/llm_response/structured_responses.json"
    rag_response_path: Optional[str] = "data/llm_response/rag_responses.json"
    output_path: Optional[str] = "data/eval/results.json"


class BatchEvaluationResponse(BaseModel):
    """Response from batch evaluation."""
    status: str
    message: str
    total_companies: int
    results: Dict[str, EvaluationResponse]
    summary: Dict[str, Any]


def determine_winners(structured: EvaluationResult, rag: EvaluationResult) -> Dict[str, str]:
    """Determine which pipeline scored higher for each metric."""
    winners = {}
    
    if structured.factual_accuracy > rag.factual_accuracy:
        winners["factual_accuracy"] = "structured"
    elif rag.factual_accuracy > structured.factual_accuracy:
        winners["factual_accuracy"] = "rag"
    else:
        winners["factual_accuracy"] = "tie"
    
    if structured.schema_compliance > rag.schema_compliance:
        winners["schema_compliance"] = "structured"
    elif rag.schema_compliance > structured.schema_compliance:
        winners["schema_compliance"] = "rag"
    else:
        winners["schema_compliance"] = "tie"
    
    if structured.provenance_quality > rag.provenance_quality:
        winners["provenance_quality"] = "structured"
    elif rag.provenance_quality > structured.provenance_quality:
        winners["provenance_quality"] = "rag"
    else:
        winners["provenance_quality"] = "tie"
    
    if structured.hallucination_detection > rag.hallucination_detection:
        winners["hallucination_detection"] = "structured"
    elif rag.hallucination_detection > structured.hallucination_detection:
        winners["hallucination_detection"] = "rag"
    else:
        winners["hallucination_detection"] = "tie"
    
    if structured.readability > rag.readability:
        winners["readability"] = "structured"
    elif rag.readability > structured.readability:
        winners["readability"] = "rag"
    else:
        winners["readability"] = "tie"
    
    if structured.mrr_score > rag.mrr_score:
        winners["mrr_score"] = "structured"
    elif rag.mrr_score > structured.mrr_score:
        winners["mrr_score"] = "rag"
    else:
        winners["mrr_score"] = "tie"
    
    if structured.total_score > rag.total_score:
        winners["total_score"] = "structured"
    elif rag.total_score > structured.total_score:
        winners["total_score"] = "rag"
    else:
        winners["total_score"] = "tie"
    
    return winners


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_single_company(request: EvaluationRequest):
    """
    Evaluate a single company's structured and RAG responses.
    
    Uses Claude with Instructor to generate structured evaluation scores.
    """
    try:
        # Evaluate company
        evaluation = evaluate_company(
            request.company_slug,
            request.company_name,
            request.ground_truth_path,
            request.structured_response_path,
            request.rag_response_path
        )
        
        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail=f"Could not evaluate {request.company_slug}"
            )
        
        # Determine winners
        winners = determine_winners(evaluation.structured, evaluation.rag)
        
        # Convert to dict
        structured_dict = json.loads(evaluation.structured.json())
        rag_dict = json.loads(evaluation.rag.json())
        
        return EvaluationResponse(
            status="success",
            message=f"Successfully evaluated {request.company_name}",
            company_slug=request.company_slug,
            company_name=request.company_name,
            structured=structured_dict,
            rag=rag_dict,
            winners=winners,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate/batch")
async def evaluate_all_companies(request: BatchEvaluationRequest, background_tasks: BackgroundTasks):
    """
    Evaluate all companies in batch.
    
    Runs in background and saves results to output file.
    """
    try:
        # Load ground truth
        with open(request.ground_truth_path, 'r') as f:
            ground_truth_data = json.load(f)
        
        results = {}
        
        for company_slug, company_data in ground_truth_data.items():
            company_name = company_data.get("company_name", company_slug)
            
            try:
                evaluation = evaluate_company(
                    company_slug,
                    company_name,
                    request.ground_truth_path,
                    request.structured_response_path,
                    request.rag_response_path
                )
                
                if evaluation:
                    winners = determine_winners(evaluation.structured, evaluation.rag)
                    structured_dict = json.loads(evaluation.structured.json())
                    rag_dict = json.loads(evaluation.rag.json())
                    
                    results[company_slug] = EvaluationResponse(
                        status="success",
                        message=f"Successfully evaluated {company_name}",
                        company_slug=company_slug,
                        company_name=company_name,
                        structured=structured_dict,
                        rag=rag_dict,
                        winners=winners,
                        timestamp=datetime.now().isoformat()
                    )
            
            except Exception as e:
                results[company_slug] = {
                    "status": "error",
                    "message": str(e),
                    "company_slug": company_slug,
                    "company_name": company_name
                }
        
        # Save to file
        output_dict = {}
        for slug, result in results.items():
            if isinstance(result, EvaluationResponse):
                output_dict[slug] = {
                    "structured": result.structured,
                    "rag": result.rag
                }
        
        if output_dict and request.output_path:
            with open(request.output_path, 'w') as f:
                json.dump(output_dict, f, indent=2, default=str)
        
        summary = get_evaluation_summary({})
        
        return BatchEvaluationResponse(
            status="success",
            message=f"Evaluated {len(results)} companies",
            total_companies=len(results),
            results=results,
            summary=summary
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluate/{company_slug}", response_model=EvaluationResponse)
async def get_evaluation(
    company_slug: str,
    ground_truth_path: str = Query("data/eval/ground_truth.json"),
    structured_response_path: str = Query("data/llm_response/structured_responses.json"),
    rag_response_path: str = Query("data/llm_response/rag_responses.json")
):
    """
    Get evaluation for a specific company.
    
    Runs evaluation on-demand and returns results.
    """
    
    # Load ground truth
    ground_truth = load_ground_truth(company_slug, ground_truth_path)
    
    if not ground_truth:
        raise HTTPException(status_code=404, detail=f"Company not found: {company_slug}")
    
    company_name = ground_truth.get("company_name", company_slug)
    
    # Run evaluation
    try:
        evaluation = evaluate_company(
            company_slug,
            company_name,
            ground_truth_path,
            structured_response_path,
            rag_response_path
        )
        
        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail=f"Could not evaluate {company_slug}"
            )
        
        winners = determine_winners(evaluation.structured, evaluation.rag)
        structured_dict = json.loads(evaluation.structured.json())
        rag_dict = json.loads(evaluation.rag.json())
        
        return EvaluationResponse(
            status="success",
            message=f"Successfully evaluated {company_name}",
            company_slug=company_slug,
            company_name=company_name,
            structured=structured_dict,
            rag=rag_dict,
            winners=winners,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "evaluation-api"}
