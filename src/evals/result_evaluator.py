"""
LLM-based Result Evaluator

Evaluates RAG and Structured pipeline responses against ground truth using OpenAI GPT-4o.
Uses Instructor with Pydantic models for structured output.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

# Configure logging
def setup_logging():
    """Configure logging to file and console."""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Use fixed log filename
    log_filename = log_dir / "evaluation.log"
    
    # Configure logging format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_filename}")
    return logger

logger = setup_logging()

# Import models
from eval_results_models import EvaluationResult, CompanyEvaluations


class EvaluationPromptData(BaseModel):
    """Data structure for evaluation prompt."""
    
    company_name: str
    company_slug: str
    ground_truth: Dict[str, Any]
    response: Dict[str, Any]
    pipeline_type: str  # "structured" or "rag"


def load_ground_truth(company_slug: str, ground_truth_path: str) -> Optional[Dict[str, Any]]:
    """Load ground truth for a specific company."""
    try:
        with open(ground_truth_path, 'r') as f:
            data = json.load(f)
            logger.info(f"✅ Loaded ground truth from {ground_truth_path}")
            return data.get(company_slug)
    except FileNotFoundError:
        logger.error(f"❌ Ground truth file not found: {ground_truth_path}")
        print(f"Ground truth file not found: {ground_truth_path}")
        return None


def load_llm_response(company_slug: str, pipeline_type: str, response_dir: str = "data/llm_response/json") -> Optional[Dict[str, Any]]:
    """Load LLM response for a specific company and pipeline.
    
    Args:
        company_slug: URL-friendly company identifier
        pipeline_type: "structured" or "rag"
        response_dir: Base directory where responses are stored (default: data/llm_response/json)
    
    Returns:
        LLM response data or None if not found
    """
    try:
        # Try both hyphen and underscore versions of company_slug
        # (e.g., "world-labs" and "world_labs")
        slugs_to_try = [
            company_slug,
            company_slug.replace('-', '_'),
            company_slug.replace('_', '-')
        ]
        
        for slug in slugs_to_try:
            response_path = os.path.join(response_dir, slug, "responses.json")
            
            if os.path.exists(response_path):
                with open(response_path, 'r') as f:
                    data = json.load(f)
                    # Extract the pipeline response from nested structure
                    return data.get(pipeline_type)
        
        return None
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def create_evaluation_prompt(
    ground_truth: Dict[str, Any],
    response: Dict[str, Any],
    pipeline_type: str,
    company_name: str
) -> str:
    """Create a detailed evaluation prompt for the LLM."""
    
    ground_truth_facts = ground_truth.get('reference_material', {}).get('key_facts', [])
    facts_text = "\n".join([
        f"- {fact['claim']}"
        for fact in ground_truth_facts
    ])
    
    hallucination_examples = ground_truth.get('reference_material', {}).get('hallucination_examples', [])
    hallucinations_text = "\n".join([f"- {ex}" for ex in hallucination_examples]) if hallucination_examples else "None provided"
    
    evaluation_notes = ground_truth.get('evaluation_notes', {})
    pipeline_notes = evaluation_notes.get(f"{pipeline_type}_pipeline_notes", "") if evaluation_notes else ""
    common_issues = evaluation_notes.get("common_issues", []) if evaluation_notes else []
    issues_text = "\n".join([f"- {issue}" for issue in common_issues]) if common_issues else "No specific issues noted"
    
    response_text = json.dumps(response, indent=2) if isinstance(response, dict) else str(response)
    
    prompt = f"""
You are an expert evaluator for AI company information extraction. Evaluate the following {pipeline_type.upper()} pipeline response against ground truth.

COMPANY: {company_name}

GROUND TRUTH FACTS:
{facts_text}

KNOWN HALLUCINATION EXAMPLES (DO NOT ACCEPT THESE):
{hallucinations_text}

EVALUATION FOCUS ({pipeline_type.upper()} PIPELINE):
{pipeline_notes}

COMMON ISSUES TO WATCH:
{issues_text}

RESPONSE TO EVALUATE:
{response_text}

SCORING GUIDELINES:

1. FACTUAL ACCURACY (0-3):
   - 3: All verifiable facts are accurate and match ground truth
   - 2: Most facts are accurate with minor discrepancies
   - 1: Some facts are accurate but notable errors exist
   - 0: Multiple factual errors or hallucinations detected

2. SCHEMA COMPLIANCE (0-2):
   - 2: Response perfectly follows expected structure/format
   - 1: Response mostly follows structure with minor deviations
   - 0: Response poorly structured or non-compliant

3. PROVENANCE QUALITY (0-2):
   - 2: All claims have proper citations/sources
   - 1: Most claims have sources but some missing
   - 0: Few or no proper source citations

4. HALLUCINATION DETECTION (0-2):
   - 2: No hallucinations; all claims are verifiable
   - 1: Minor unverifiable claims but no major hallucinations
   - 0: Contains known false claims or significant hallucinations

5. READABILITY (0-1):
   - 1: Clear, well-organized, and easy to understand
   - 0: Confusing, poorly formatted, or hard to parse

6. MEAN RECIPROCAL RANKING (0-1):
   - 1.0: Most important facts appear first
   - 0.5: Most important facts appear second position
   - 0.0: Important facts missing or ranked poorly

EVALUATION INSTRUCTIONS:
1. Compare response facts against ground truth key facts
2. Check for any hallucinations from the known examples
3. Assess accuracy and confidence of extracted information
4. Score each metric independently
5. Calculate total_score as sum of all metrics
6. Provide detailed notes explaining the scores

Return your evaluation as structured data.
"""
    
    return prompt


def evaluate_response(
    company_slug: str,
    company_name: str,
    pipeline_type: str,
    ground_truth: Dict[str, Any],
    response: Dict[str, Any],
    api_key: Optional[str] = None
) -> EvaluationResult:
    """
    Evaluate an LLM response using GPT-4o with Instructor.
    
    Args:
        company_slug: URL-friendly company identifier
        company_name: Official company name
        pipeline_type: "structured" or "rag"
        ground_truth: Ground truth data for the company
        response: LLM response to evaluate
        api_key: OpenAI API key (uses env var if not provided)
    
    Returns:
        EvaluationResult: Structured evaluation with scores
    """
    
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    logger.info(f"Evaluating {pipeline_type} pipeline for {company_name} ({company_slug})")
    
    # Initialize OpenAI client with Instructor
    client = OpenAI(api_key=api_key)
    client = instructor.from_openai(client)
    
    # Create evaluation prompt
    prompt = create_evaluation_prompt(ground_truth, response, pipeline_type, company_name)
    
    # Call GPT-4o with structured output
    logger.debug(f"Calling GPT-4o for {company_slug} - {pipeline_type}")
    evaluation = client.messages.create(
        model="gpt-4o",
        max_tokens=1500,
        temperature=0.2,  # Low temperature for deterministic, consistent responses
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_model=EvaluationResult
    )
    
    # Set additional fields
    evaluation.company_name = company_name
    evaluation.company_slug = company_slug
    evaluation.pipeline_type = pipeline_type
    evaluation.timestamp = datetime.now()
    
    logger.info(f"✅ {pipeline_type.upper()} evaluation complete for {company_name}: Score {evaluation.total_score:.1f}/11")
    
    return evaluation


def evaluate_company(
    company_slug: str,
    company_name: str,
    ground_truth_path: str,
    response_dir: str = "data/llm_response/json",
    api_key: Optional[str] = None
) -> Optional[CompanyEvaluations]:
    """
    Evaluate both structured and RAG responses for a company.
    
    Args:
        company_slug: URL-friendly company identifier
        company_name: Official company name
        ground_truth_path: Path to ground_truth.json
        response_dir: Directory containing response JSON files (default: data/llm_response/json)
        api_key: OpenAI API key
    
    Returns:
        CompanyEvaluations: Evaluation results for both pipelines
    """
    
    print(f"\n🔍 Evaluating {company_name}...")
    logger.info(f"Evaluating company: {company_name} ({company_slug})")
    
    # Load ground truth
    ground_truth = load_ground_truth(company_slug, ground_truth_path)
    if not ground_truth:
        logger.error(f"Could not load ground truth for {company_slug}")
        print(f"❌ Could not load ground truth for {company_slug}")
        return None
    
    # Evaluate structured pipeline
    print(f"  📋 Evaluating Structured pipeline...")
    logger.info(f"  Starting Structured pipeline evaluation for {company_slug}")
    structured_response = load_llm_response(company_slug, "structured", response_dir)
    if structured_response:
        structured_eval = evaluate_response(
            company_slug,
            company_name,
            "structured",
            ground_truth,
            structured_response,
            api_key
        )
        print(f"    ✅ Structured Score: {structured_eval.total_score:.1f}/11")
        logger.info(f"  Structured Score: {structured_eval.total_score:.1f}/11")
    else:
        logger.warning(f"No structured response found at {os.path.join(response_dir, company_slug, 'responses.json')}")
        print(f"    ⚠️  No structured response found at {os.path.join(response_dir, company_slug, 'responses.json')}")
        structured_eval = None
    
    # Evaluate RAG pipeline
    print(f"  🔄 Evaluating RAG pipeline...")
    logger.info(f"  Starting RAG pipeline evaluation for {company_slug}")
    rag_response = load_llm_response(company_slug, "rag", response_dir)
    if rag_response:
        rag_eval = evaluate_response(
            company_slug,
            company_name,
            "rag",
            ground_truth,
            rag_response,
            api_key
        )
        print(f"    ✅ RAG Score: {rag_eval.total_score:.1f}/11")
        logger.info(f"  RAG Score: {rag_eval.total_score:.1f}/11")
    else:
        logger.warning(f"No RAG response found at {os.path.join(response_dir, company_slug, 'responses.json')}")
        print(f"    ⚠️  No RAG response found at {os.path.join(response_dir, company_slug, 'responses.json')}")
        rag_eval = None
    
    if structured_eval and rag_eval:
        logger.info(f"✅ Completed evaluation for {company_name}: Structured {structured_eval.total_score:.1f}/11, RAG {rag_eval.total_score:.1f}/11")
        return CompanyEvaluations(structured=structured_eval, rag=rag_eval)
    
    return None


def evaluate_batch(
    ground_truth_path: str = "data/eval/ground_truth.json",
    response_dir: str = "data/llm_response/json",
    output_path: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, CompanyEvaluations]:
    """
    Evaluate all companies in batch.
    
    Args:
        ground_truth_path: Path to ground_truth.json
        response_dir: Directory containing response JSON files
        output_path: Path to save results (optional)
        api_key: OpenAI API key
    
    Returns:
        Dictionary of company slug -> CompanyEvaluations
    """
    
    # Load ground truth to get list of companies
    try:
        with open(ground_truth_path, 'r') as f:
            ground_truth_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"Ground truth file not found: {ground_truth_path}")
        print(f"❌ Ground truth file not found: {ground_truth_path}")
        return {}
    
    logger.info(f"Starting batch evaluation of {len(ground_truth_data)} companies")
    logger.info(f"   Response directory: {response_dir}")
    logger.info(f"   Ground truth: {ground_truth_path}")
    logger.info(f"   Output path: {output_path}")
    
    print(f"\n📊 Starting batch evaluation of {len(ground_truth_data)} companies...")
    print(f"   📁 Response directory: {response_dir}")
    print(f"   📄 Ground truth: {ground_truth_path}")
    
    results = {}
    
    for company_slug, company_data in ground_truth_data.items():
        company_name = company_data.get("company_name", company_slug)
        
        try:
            logger.debug(f"Evaluating company: {company_name} ({company_slug})")
            evaluation = evaluate_company(
                company_slug,
                company_name,
                ground_truth_path,
                response_dir,
                api_key
            )
            
            if evaluation:
                results[company_slug] = evaluation
                logger.info(f"✅ Successfully evaluated: {company_name}")
            else:
                logger.warning(f"Skipped {company_name} (no evaluation results)")
                print(f"  ⏭️  Skipped {company_name} (no evaluation results)")
        except Exception as e:
            logger.error(f"Error evaluating {company_name}: {str(e)}", exc_info=True)
            print(f"  ❌ Error evaluating {company_name}: {str(e)}")
            continue
    
    # Save results if output path provided
    if output_path and results:
        # Create output directory if it doesn't exist
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data or start with empty dict
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r') as f:
                    existing_data = json.load(f)
                logger.info(f"Loaded existing results from {output_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load existing results: {e}. Starting with empty dict.")
                existing_data = {}
        else:
            existing_data = {}
        
        # Merge new results with existing data
        for slug, evaluation in results.items():
            existing_data[slug] = {
                "structured": json.loads(evaluation.structured.model_dump_json()),
                "rag": json.loads(evaluation.rag.model_dump_json())
            }
        
        # Save merged data
        with open(output_path, 'w') as f:
            json.dump(existing_data, f, indent=2, default=str)
        
        # Verify file was saved
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"✅ Results file saved successfully: {output_path}")
            logger.info(f"   File size: {file_size} bytes")
            logger.info(f"   Total companies in file: {len(existing_data)}")
            logger.info(f"   Companies added/updated: {len(results)}")
            print(f"\n✅ Results saved to {output_path}")
            print(f"   File size: {file_size} bytes")
            print(f"   Total companies in file: {len(existing_data)}")
        else:
            logger.error(f"❌ Failed to save results file: {output_path}")
            print(f"❌ Failed to save results file: {output_path}")
    
    logger.info(f"✅ Batch evaluation complete! Evaluated {len(results)}/{len(ground_truth_data)} companies")
    print(f"\n✅ Batch evaluation complete! Evaluated {len(results)}/{len(ground_truth_data)} companies")
    return results


def get_evaluation_summary(evaluations: Dict[str, CompanyEvaluations]) -> Dict[str, Any]:
    """Generate summary statistics from evaluations."""
    
    if not evaluations:
        return {}
    
    structured_scores = []
    rag_scores = []
    structured_mrr = []
    rag_mrr = []
    
    for slug, evals in evaluations.items():
        if evals.structured:
            structured_scores.append(evals.structured.total_score)
            structured_mrr.append(evals.structured.mrr_score)
        if evals.rag:
            rag_scores.append(evals.rag.total_score)
            rag_mrr.append(evals.rag.mrr_score)
    
    return {
        "total_companies": len(evaluations),
        "structured_avg_score": sum(structured_scores) / len(structured_scores) if structured_scores else 0,
        "rag_avg_score": sum(rag_scores) / len(rag_scores) if rag_scores else 0,
        "structured_avg_mrr": sum(structured_mrr) / len(structured_mrr) if structured_mrr else 0,
        "rag_avg_mrr": sum(rag_mrr) / len(rag_mrr) if rag_mrr else 0,
        "structured_better_count": sum(
            1 for slug, evals in evaluations.items()
            if evals.structured and evals.rag and evals.structured.total_score > evals.rag.total_score
        ),
        "rag_better_count": sum(
            1 for slug, evals in evaluations.items()
            if evals.structured and evals.rag and evals.rag.total_score > evals.structured.total_score
        )
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate LLM responses against ground truth")
    parser.add_argument(
        "--company",
        help="Evaluate specific company by slug"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Evaluate all companies"
    )
    parser.add_argument(
        "--ground-truth",
        default="data/eval/ground_truth.json",
        help="Path to ground truth file"
    )
    parser.add_argument(
        "--response-dir",
        default="data/llm_response/json",
        help="Directory containing response JSON files"
    )
    parser.add_argument(
        "--output",
        default="data/eval/results_llm_eval.json",
        help="Path to save evaluation results"
    )
    
    args = parser.parse_args()
    
    # Load ground truth to get company info
    try:
        with open(args.ground_truth, 'r') as f:
            ground_truth_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Ground truth file not found: {args.ground_truth}")
        exit(1)
    
    if args.company:
        # Evaluate specific company
        if args.company not in ground_truth_data:
            print(f"❌ Company not found: {args.company}")
            exit(1)
        
        company_data = ground_truth_data[args.company]
        evaluation = evaluate_company(
            args.company,
            company_data.get("company_name", args.company),
            args.ground_truth,
            args.response_dir
        )
        
        if evaluation:
            print(f"\n✅ Evaluation complete for {company_data.get('company_name')}")
            print(f"   Structured: {evaluation.structured.total_score:.1f}/11")
            print(f"   RAG: {evaluation.rag.total_score:.1f}/11")
            
            # Create output directory if it doesn't exist
            output_file = Path(args.output)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing data or start with empty dict
            if os.path.exists(args.output):
                try:
                    with open(args.output, 'r') as f:
                        existing_data = json.load(f)
                    logger.info(f"Loaded existing results from {args.output}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not load existing results: {e}. Starting with empty dict.")
                    existing_data = {}
            else:
                existing_data = {}
            
            # Add/update the evaluated company
            existing_data[args.company] = {
                "structured": json.loads(evaluation.structured.model_dump_json()),
                "rag": json.loads(evaluation.rag.model_dump_json())
            }
            
            # Save merged data
            with open(args.output, 'w') as f:
                json.dump(existing_data, f, indent=2, default=str)
            
            # Verify file was saved
            if os.path.exists(args.output):
                file_size = os.path.getsize(args.output)
                logger.info(f"✅ Results file saved successfully: {args.output}")
                logger.info(f"   File size: {file_size} bytes")
                logger.info(f"   Total companies in file: {len(existing_data)}")
                logger.info(f"   Companies added/updated: 1 ({args.company})")
                print(f"\n✅ Results saved to {args.output}")
                print(f"   File size: {file_size} bytes")
                print(f"   Total companies in file: {len(existing_data)}")
            else:
                logger.error(f"❌ Failed to save results file: {args.output}")
                print(f"❌ Failed to save results file: {args.output}")
    
    elif args.batch:
        # Evaluate all companies
        print("🔄 Starting batch evaluation...")
        results = evaluate_batch(
            args.ground_truth,
            args.response_dir,
            args.output
        )
        
        summary = get_evaluation_summary(results)
        print("\n📊 Evaluation Summary:")
        print(f"   Companies Evaluated: {summary.get('total_companies', 0)}")
        print(f"   Structured Avg Score: {summary.get('structured_avg_score', 0):.2f}/11")
        print(f"   RAG Avg Score: {summary.get('rag_avg_score', 0):.2f}/11")
        print(f"   Structured Avg MRR: {summary.get('structured_avg_mrr', 0):.3f}")
        print(f"   RAG Avg MRR: {summary.get('rag_avg_mrr', 0):.3f}")
        print(f"   Structured Better: {summary.get('structured_better_count', 0)} companies")
        print(f"   RAG Better: {summary.get('rag_better_count', 0)} companies")
    
    else:
        parser.print_help()
