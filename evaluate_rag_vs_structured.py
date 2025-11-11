#!/usr/bin/env python3
"""
Lab 9: Evaluation & Comparison - RAG vs Structured Extraction

This script compares RAG and Structured extraction methods for Forbes AI 50 companies.

Usage:
    python evaluate_rag_vs_structured.py

The script will:
1. Generate both RAG and Structured dashboards for 5+ companies
2. Display results side-by-side for comparison
3. Provide prompts to score each aspect
4. Generate evaluation summary
"""

import json
import requests
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Configuration
API_BASE = "http://localhost:8000"
SEED_FILE = Path("data/forbes_ai50_seed.json")

# Rubric criteria
RUBRIC = {
    "factual_correctness": (0, 3, "Are the facts accurate and verifiable?"),
    "schema_adherence": (0, 2, "Does the output follow the expected schema?"),
    "provenance_use": (0, 2, "Are sources cited/used appropriately?"),
    "hallucination_control": (0, 2, "Are there any unsupported claims (hallucinations)?"),
    "readability": (0, 1, "Is the output useful for investor decision-making?"),
}

def load_companies(count: int = 5) -> List[str]:
    """Load company names from seed file."""
    if not SEED_FILE.exists():
        print(f"❌ Seed file not found: {SEED_FILE}")
        sys.exit(1)
    
    with open(SEED_FILE) as f:
        companies = json.load(f)
    
    return [c["company_name"] for c in companies[:count]]


def fetch_rag_dashboard(company_name: str) -> Dict[str, Any]:
    """Fetch RAG dashboard from API."""
    try:
        resp = requests.post(
            f"{API_BASE}/dashboard/rag",
            params={"company_name": company_name},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"HTTP {resp.status_code}", "message": resp.text}
    except Exception as e:
        return {"error": str(e)}


def fetch_structured_dashboard(company_name: str) -> Dict[str, Any]:
    """Fetch Structured dashboard from API."""
    try:
        resp = requests.post(
            f"{API_BASE}/dashboard/structured",
            params={"company_name": company_name},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"HTTP {resp.status_code}", "message": resp.text}
    except Exception as e:
        return {"error": str(e)}


def display_comparison(company: str, rag_result: Dict, structured_result: Dict):
    """Display side-by-side comparison of RAG vs Structured."""
    print("\n" + "=" * 100)
    print(f"COMPANY: {company.upper()}")
    print("=" * 100)
    
    # RAG Output
    print("\n📊 RAG EXTRACTION")
    print("-" * 100)
    if "error" in rag_result:
        print(f"❌ Error: {rag_result['error']}")
        if "message" in rag_result:
            print(f"Details: {rag_result['message'][:200]}...")
    else:
        if "markdown" in rag_result:
            print(rag_result["markdown"][:1000])
            print("\n... [truncated]" if len(rag_result.get("markdown", "")) > 1000 else "")
        
        if "context_results" in rag_result:
            print(f"\n📌 Retrieved {len(rag_result['context_results'])} context chunks")
            for i, ctx in enumerate(rag_result["context_results"][:2], 1):
                score = ctx.get("similarity_score", 0)
                print(f"   [{i}] Score: {score:.4f} | {ctx.get('text', '')[:100]}...")
    
    # Structured Output
    print("\n" + "-" * 100)
    print("🏗️  STRUCTURED EXTRACTION")
    print("-" * 100)
    if "error" in structured_result:
        print(f"❌ Error: {structured_result['error']}")
        if "message" in structured_result:
            print(f"Details: {structured_result['message'][:200]}...")
    else:
        if "markdown" in structured_result:
            print(structured_result["markdown"][:1000])
            print("\n... [truncated]" if len(structured_result.get("markdown", "")) > 1000 else "")
        
        if "company_slug" in structured_result:
            payload_path = Path("data/payloads") / f"{structured_result['company_slug']}.json"
            if payload_path.exists():
                print(f"\n✅ Payload file available: {payload_path}")


def prompt_for_score(criterion: str, min_val: int, max_val: int, description: str) -> int:
    """Prompt user for a score on a criterion."""
    while True:
        print(f"\n{criterion.upper()}: {description}")
        print(f"Range: {min_val}-{max_val}")
        try:
            score = int(input(f"Enter score ({min_val}-{max_val}): ").strip())
            if min_val <= score <= max_val:
                return score
            print(f"⚠️  Score must be between {min_val} and {max_val}")
        except ValueError:
            print("⚠️  Invalid input, please enter a number")


def evaluate_method(company: str, method: str) -> Dict[str, int]:
    """Evaluate one method (RAG or Structured) across all rubric criteria."""
    scores = {}
    print(f"\n{'=' * 60}")
    print(f"EVALUATING: {company} - {method.upper()}")
    print(f"{'=' * 60}")
    
    for criterion, (min_val, max_val, description) in RUBRIC.items():
        score = prompt_for_score(criterion, min_val, max_val, description)
        scores[criterion] = score
    
    return scores


def main():
    """Main evaluation workflow."""
    print("\n" + "=" * 100)
    print("LAB 9: RAG vs STRUCTURED EVALUATION")
    print("=" * 100)
    
    # Step 1: Load companies
    print("\n📋 Loading companies...")
    companies = load_companies(5)
    print(f"✅ Loaded {len(companies)} companies: {', '.join(companies)}")
    
    # Step 2: Fetch dashboards for all companies
    print("\n⏳ Fetching dashboards from API...")
    print(f"API Base: {API_BASE}")
    
    evaluations = []
    
    for company in companies:
        print(f"\n🔄 Processing: {company}")
        
        # Fetch both methods
        print(f"   Fetching RAG dashboard...")
        rag_result = fetch_rag_dashboard(company)
        
        print(f"   Fetching Structured dashboard...")
        structured_result = fetch_structured_dashboard(company)
        
        # Display comparison
        display_comparison(company, rag_result, structured_result)
        
        # Prompt for evaluation
        print(f"\n{'*' * 60}")
        print("NOW EVALUATE THIS COMPANY")
        print(f"{'*' * 60}")
        
        rag_scores = evaluate_method(company, "RAG")
        structured_scores = evaluate_method(company, "Structured")
        
        # Calculate totals
        rag_total = sum(rag_scores.values())
        structured_total = sum(structured_scores.values())
        
        evaluations.append({
            "company": company,
            "rag": rag_scores,
            "structured": structured_scores,
            "rag_total": rag_total,
            "structured_total": structured_total,
        })
        
        print(f"\n✅ RAG Total: {rag_total}/10")
        print(f"✅ Structured Total: {structured_total}/10")
    
    # Step 3: Generate summary
    print("\n" + "=" * 100)
    print("EVALUATION SUMMARY")
    print("=" * 100)
    
    summary_rows = []
    for eval_data in evaluations:
        company = eval_data["company"]
        
        for method, scores, total in [
            ("RAG", eval_data["rag"], eval_data["rag_total"]),
            ("Structured", eval_data["structured"], eval_data["structured_total"]),
        ]:
            factual = scores.get("factual_correctness", 0)
            schema = scores.get("schema_adherence", 0)
            provenance = scores.get("provenance_use", 0)
            hallucination = scores.get("hallucination_control", 0)
            readability = scores.get("readability", 0)
            
            summary_rows.append({
                "company": company,
                "method": method,
                "factual": factual,
                "schema": schema,
                "provenance": provenance,
                "hallucination": hallucination,
                "readability": readability,
                "total": total,
            })
    
    # Print as table
    print("\n| company | method | factual (0–3) | schema (0–2) | provenance (0–2) | hallucination (0–2) | readability (0–1) | total |")
    print("|---------|--------|---------------|--------------|------------------|----------------------|-------------------|-------|")
    for row in summary_rows:
        print(
            f"| {row['company']:15} | {row['method']:9} | {row['factual']:13} | {row['schema']:12} | {row['provenance']:16} | {row['hallucination']:20} | {row['readability']:17} | {row['total']:5} |"
        )
    
    # Calculate averages
    rag_rows = [r for r in summary_rows if r["method"] == "RAG"]
    structured_rows = [r for r in summary_rows if r["method"] == "Structured"]
    
    rag_avg = sum(r["total"] for r in rag_rows) / len(rag_rows) if rag_rows else 0
    structured_avg = sum(r["total"] for r in structured_rows) / len(structured_rows) if structured_rows else 0
    
    print(f"\n🎯 AVERAGE SCORES:")
    print(f"   RAG: {rag_avg:.2f}/10")
    print(f"   Structured: {structured_avg:.2f}/10")
    
    winner = "RAG" if rag_avg > structured_avg else "Structured" if structured_avg > rag_avg else "TIE"
    print(f"\n🏆 WINNER: {winner}")
    
    # Step 4: Save to EVAL.md
    print(f"\n💾 Saving results to EVAL.md...")
    save_eval_md(summary_rows)
    print(f"✅ Saved to EVAL.md")
    
    print("\n" + "=" * 100)
    print("✨ Evaluation complete! Next step: Write 1-page reflection")
    print("=" * 100)


def save_eval_md(rows: List[Dict[str, Any]]):
    """Save evaluation results to EVAL.md."""
    eval_md_path = Path("EVAL.md")
    
    # Build markdown table
    lines = [
        "# RAG vs Structured Evaluation\n",
        "| company | method | factual (0–3) | schema (0–2) | provenance (0–2) | hallucination (0–2) | readability (0–1) | total |",
        "|---------|--------|---------------|--------------|------------------|----------------------|-------------------|-------|",
    ]
    
    for row in rows:
        line = (
            f"| {row['company']:<15} | {row['method']:<9} | {row['factual']:^13} | {row['schema']:^12} | {row['provenance']:^16} | {row['hallucination']:^20} | {row['readability']:^17} | {row['total']:^5} |"
        )
        lines.append(line)
    
    # Write to file
    with open(eval_md_path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
