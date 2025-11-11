"""
Evaluation Runner for LLM-generated dashboards.

Runs evaluations on dashboard outputs and caches results.

Supports two scoring modes:
- PROGRAMMATIC: Auto-calculate metrics from content and ground truth
- MANUAL: Use hardcoded/pre-defined scores

Usage:
    # Evaluate single company (programmatic)
    python src/evals/eval_runner.py --company world-labs --pipeline structured --mode programmatic
    
    # Batch evaluate all companies (manual)
    python src/evals/eval_runner.py --batch --mode manual
    
    # Generate comparison report
    python src/evals/eval_runner.py --batch --report --mode programmatic
    
    # Load cached results
    python src/evals/eval_runner.py --view world-labs
"""

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict
import argparse
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.eval_metrics import (
    EvaluationMetrics, ComparisonResult, calculate_mrr,
    calculate_factual_accuracy, calculate_schema_compliance,
    calculate_provenance_quality, calculate_hallucination_detection,
    calculate_readability
)

# Configure logging with both console and file output
def setup_logging():
    """Configure logging to output to both console and file."""
    # Get project root and logs directory
    project_root = Path(__file__).resolve().parents[2]
    logs_dir = project_root / "data" / "logs"
    
    # Try to create logs directory and file handler
    file_handler = None
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "eval_runner.log"
        
        # Verify we can write to the directory
        # Try to write a test file first
        test_file = logs_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()  # Remove test file
        
        # File handler (DEBUG level - captures everything, append mode)
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
    except (PermissionError, OSError) as e:
        print(f"⚠️  Warning: Cannot write to {logs_dir}: {e}")
        print("   Logging to console only. Results will not be persisted to file.")
        file_handler = None
    
    # Configure root logger
    logger = logging.getLogger("eval_runner")
    logger.setLevel(logging.DEBUG)
    
    # Console handler (INFO level - user-friendly output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to root logger
    if not logger.handlers:
        if file_handler:
            logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    # Also configure eval_metrics logger
    metrics_logger = logging.getLogger("eval_metrics")
    metrics_logger.setLevel(logging.DEBUG)
    if not metrics_logger.handlers:
        if file_handler:
            metrics_logger.addHandler(file_handler)
        metrics_logger.addHandler(console_handler)
    
    # Return logger and log file path (or None if couldn't create file)
    log_file = logs_dir / "eval_runner.log" if file_handler else None
    return logger, log_file

# Initialize logging
logger, log_file = setup_logging()
if log_file:
    logger.info(f"Logs stored at: {log_file}")
else:
    logger.info("Logs are being output to console only")

# Scoring mode: "programmatic" or "manual"
SCORING_MODE = "programmatic"  # ← CONTROL VARIABLE: Change to "manual" for hardcoded scores


class EvaluationRunner:
    """Runner for evaluation pipeline."""
    
    def __init__(self):
        """Initialize evaluation runner."""
        # Get project root (2 levels up from src/evals/)
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_dir = self.project_root / "data"
        self.eval_dir = self.data_dir / "eval"
        self.payloads_dir = self.data_dir / "payloads"
        
        # Create eval directory if it doesn't exist
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        
        self.ground_truth_path = self.eval_dir / "ground_truth.json"
        self.results_path = self.eval_dir / "results.json"
        
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Eval directory: {self.eval_dir}")
        logger.info(f"Ground truth path: {self.ground_truth_path}")
        logger.info(f"Results path: {self.results_path}")
        
        self.ground_truth = self._load_ground_truth()
        self.results = self._load_results()
    
    def _load_ground_truth(self) -> Dict[str, Any]:
        """Load ground truth data."""
        if not self.ground_truth_path.exists():
            logger.warning(f"Ground truth file not found: {self.ground_truth_path}")
            return {}
        
        try:
            with open(self.ground_truth_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading ground truth: {e}")
            return {}
    
    def _load_results(self) -> Dict[str, Any]:
        """Load cached results."""
        if not self.results_path.exists():
            return {}
        
        try:
            with open(self.results_path) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            return {}
    
    def _save_results(self):
        """Save results to cache."""
        try:
            with open(self.results_path, "w") as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Saved results to {self.results_path}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def _load_dashboard_markdown(self, company_slug: str, pipeline: str) -> Optional[str]:
        """
        Load generated dashboard markdown from cached files.
        
        Tries multiple locations based on pipeline type:
        - Structured: data/payloads/{company_slug}.json → extract markdown
        - RAG: data/rag_results/{company_slug}_rag.md or similar
        
        Args:
            company_slug: Company slug (e.g., "world-labs")
            pipeline: "structured" or "rag"
        
        Returns:
            Dashboard markdown string or None if not found
        """
        logger.info(f"Loading {pipeline} dashboard for {company_slug}")
        
        # Try structured pipeline dashboards
        if pipeline == "structured":
            # Check for structured payload JSON
            payload_path = self.payloads_dir / f"{company_slug}.json"
            if payload_path.exists():
                try:
                    with open(payload_path) as f:
                        payload = json.load(f)
                    
                    # Extract dashboard markdown from payload if available
                    if isinstance(payload, dict):
                        # Try to extract markdown from the payload
                        markdown = payload.get("dashboard_markdown")
                        if markdown:
                            logger.info(f"✓ Loaded structured dashboard from {payload_path}")
                            return markdown
                        
                        # If no explicit markdown field, generate from available data
                        logger.debug(f"No dashboard_markdown field in {payload_path}, creating summary")
                        markdown = self._generate_dashboard_from_payload(payload, company_slug)
                        return markdown
                        
                except Exception as e:
                    logger.warning(f"Error loading structured payload: {e}")
        
        # Try RAG pipeline dashboards
        elif pipeline == "rag":
            # Check for RAG-specific result files
            rag_results_dir = self.data_dir / "rag_results"
            
            possible_paths = [
                rag_results_dir / f"{company_slug}_rag.md",
                rag_results_dir / f"{company_slug}_rag_dashboard.md",
                self.data_dir / "dashboards" / f"{company_slug}_rag.md",
                self.eval_dir / f"{company_slug}_rag.md",
            ]
            
            for path in possible_paths:
                if path.exists():
                    try:
                        markdown = path.read_text()
                        logger.info(f"✓ Loaded RAG dashboard from {path}")
                        return markdown
                    except Exception as e:
                        logger.warning(f"Error loading RAG dashboard from {path}: {e}")
        
        # If no file found, log what we looked for
        logger.warning(
            f"Could not find {pipeline} dashboard for {company_slug}. "
            f"Looked in: {self.payloads_dir}, {rag_results_dir if pipeline == 'rag' else 'N/A'}"
        )
        return None
    
    def _generate_dashboard_from_payload(self, payload: Dict[str, Any], company_slug: str) -> str:
        """
        Generate a simple dashboard summary from structured payload.
        
        This creates a markdown representation of the payload data.
        
        Args:
            payload: Structured payload dictionary
            company_slug: Company slug
        
        Returns:
            Markdown dashboard
        """
        lines = []
        company_name = payload.get("company_name", company_slug)
        
        lines.append(f"# {company_name} - Structured Dashboard\n")
        
        # Add sections from payload
        for key, value in payload.items():
            if key == "company_name":
                continue
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"## {key.replace('_', ' ').title()}\n")
                lines.append(f"{value}\n")
            elif isinstance(value, list) and value:
                lines.append(f"## {key.replace('_', ' ').title()}\n")
                for item in value[:5]:  # Limit to 5 items
                    lines.append(f"- {item}\n")
            elif isinstance(value, dict) and value:
                lines.append(f"## {key.replace('_', ' ').title()}\n")
                for k, v in value.items():
                    lines.append(f"- **{k}**: {v}\n")
        
        return "\n".join(lines)
    
    def _extract_facts_from_markdown(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Extract key facts from dashboard markdown for evaluation.
        
        This is a simplified placeholder. In practice, you'd use NLP to extract
        named entities, numbers, dates, etc.
        
        Args:
            markdown: Dashboard markdown content
        
        Returns:
            List of extracted facts with relevance scores
        """
        # Simplified extraction - in production, use more sophisticated NLP
        facts = []
        
        lines = markdown.split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith("#"):
                # Very basic fact extraction
                fact = {
                    "rank": i,
                    "text": line.strip()[:100],  # First 100 chars
                    "relevance_score": 0.7 + (0.3 * (10 - i) / 10),  # Decay by position
                }
                facts.append(fact)
        
        return facts[:20]  # Return top 20 facts
    
    def evaluate_company_pipeline(
        self,
        company_slug: str,
        pipeline: str = "structured",
        force: bool = False,
        scoring_mode: str = None
    ) -> Optional[EvaluationMetrics]:
        """
        Evaluate a specific company/pipeline combination.
        
        Args:
            company_slug: Company slug (e.g., "world-labs")
            pipeline: Pipeline type ("structured" or "rag")
            force: Force re-evaluation even if cached
            scoring_mode: "programmatic" (auto-calculate) or "manual" (hardcoded)
                         If None, uses module-level SCORING_MODE
        
        Returns:
            EvaluationMetrics or None if evaluation failed
        """
        if scoring_mode is None:
            scoring_mode = SCORING_MODE
        
        logger.info(f"Evaluating {company_slug}/{pipeline} (mode: {scoring_mode})")
        
        # Check cache
        if not force and company_slug in self.results:
            company_results = self.results[company_slug]
            if pipeline in company_results:
                logger.info(f"Using cached result for {company_slug}/{pipeline}")
                cached_metrics = company_results[pipeline]
                return EvaluationMetrics.from_dict(cached_metrics)
        
        # Load ground truth
        if company_slug not in self.ground_truth:
            logger.error(f"No ground truth for {company_slug}")
            return None
        
        gt = self.ground_truth[company_slug]
        
        # Load dashboard markdown
        dashboard_markdown = self._load_dashboard_markdown(company_slug, pipeline)
        
        if not dashboard_markdown:
            logger.warning(f"Could not load dashboard for {company_slug}/{pipeline}")
            # Create placeholder evaluation
            dashboard_markdown = f"# {gt['company_name']} - {pipeline.title()} Dashboard\n\nNo content available."
        
        # Extract facts for MRR calculation
        facts = self._extract_facts_from_markdown(dashboard_markdown)
        mrr = calculate_mrr(facts, relevant_threshold=0.7)
        
        # Calculate metrics based on scoring mode
        if scoring_mode.lower() == "programmatic":
            logger.info(f"Using PROGRAMMATIC scoring for {company_slug}/{pipeline}")
            factual_accuracy = calculate_factual_accuracy(dashboard_markdown, gt)
            schema_compliance = calculate_schema_compliance(dashboard_markdown, gt)
            provenance_quality = calculate_provenance_quality(dashboard_markdown, gt)
            hallucination_detection = calculate_hallucination_detection(dashboard_markdown, gt)
            readability = calculate_readability(dashboard_markdown, gt)
            notes = f"Auto-calculated metrics using {pipeline} pipeline (programmatic)"
        else:
            logger.info(f"Using MANUAL scoring for {company_slug}/{pipeline}")
            # Hardcoded placeholder scores
            factual_accuracy = 2
            schema_compliance = 2
            provenance_quality = 1
            hallucination_detection = 1
            readability = 1
            notes = f"Manual evaluation for {pipeline} pipeline (placeholder)"
        
        # Create evaluation metrics
        metrics = EvaluationMetrics(
            company_name=gt["company_name"],
            company_slug=company_slug,
            pipeline_type=pipeline,
            factual_accuracy=factual_accuracy,
            schema_compliance=schema_compliance,
            provenance_quality=provenance_quality,
            hallucination_detection=hallucination_detection,
            readability=readability,
            mrr_score=mrr,
            notes=notes
        )
        
        # Cache result
        if company_slug not in self.results:
            self.results[company_slug] = {}
        
        self.results[company_slug][pipeline] = metrics.to_dict()
        self._save_results()
        
        logger.info(f"✓ Evaluated {company_slug}/{pipeline}: total={metrics.get_total_score():.1f}/14")
        
        return metrics
    
    def batch_evaluate(self, force: bool = False, scoring_mode: str = None) -> Dict[str, Dict[str, EvaluationMetrics]]:
        """
        Evaluate all companies for both pipelines.
        
        Args:
            force: Force re-evaluation of all
            scoring_mode: "programmatic" or "manual" (uses SCORING_MODE if None)
        
        Returns:
            Dictionary mapping company_slug -> {pipeline -> EvaluationMetrics}
        """
        if scoring_mode is None:
            scoring_mode = SCORING_MODE
        
        logger.info(f"Starting batch evaluation (mode: {scoring_mode})...")
        
        results = {}
        
        for company_slug in self.ground_truth.keys():
            logger.info(f"\n=== Evaluating {company_slug} ===")
            
            results[company_slug] = {}
            
            for pipeline in ["structured", "rag"]:
                metrics = self.evaluate_company_pipeline(
                    company_slug,
                    pipeline,
                    force=force,
                    scoring_mode=scoring_mode
                )
                if metrics:
                    results[company_slug][pipeline] = metrics
        
        logger.info(f"\n✓ Batch evaluation complete")
        
        return results
    
    def generate_report(self) -> str:
        """Generate comparison report."""
        logger.info("Generating comparison report...")
        
        report_lines = [
            "# Evaluation Report: Structured vs RAG Pipelines\n",
            f"Generated: {datetime.utcnow().isoformat()}Z\n",
            "## Summary\n",
        ]
        
        # Aggregate scores
        structured_total = 0
        rag_total = 0
        structured_count = 0
        rag_count = 0
        
        # Table header
        report_lines.append(
            "| Company | Method | Factual (0-3) | Schema (0-2) | Provenance (0-2) | Hallucination (0-2) | Readability (0-1) | MRR | Total (0-14) |\n"
        )
        report_lines.append("|---------|--------|--------------|--------------|-------------------|----------------------|-------------------|-----|--------|\n")
        
        # Results rows
        for company_slug in sorted(self.results.keys()):
            company_results = self.results[company_slug]
            
            for pipeline in ["structured", "rag"]:
                if pipeline not in company_results:
                    continue
                
                metrics = company_results[pipeline]
                company_name = self.ground_truth[company_slug]["company_name"]
                
                row = (
                    f"| {company_name} | {pipeline.title()} | "
                    f"{metrics.get('factual_accuracy', '-')} | "
                    f"{metrics.get('schema_compliance', '-')} | "
                    f"{metrics.get('provenance_quality', '-')} | "
                    f"{metrics.get('hallucination_detection', '-')} | "
                    f"{metrics.get('readability', '-')} | "
                    f"{metrics.get('mrr_score', '-'):.2f} | "
                    f"{metrics.get('total_score', '-'):.1f} |\n"
                )
                report_lines.append(row)
                
                if pipeline == "structured":
                    structured_total += metrics.get('total_score', 0)
                    structured_count += 1
                else:
                    rag_total += metrics.get('total_score', 0)
                    rag_count += 1
        
        # Summary statistics
        report_lines.append("\n## Summary Statistics\n")
        
        if structured_count > 0:
            struct_avg = structured_total / structured_count
            report_lines.append(f"**Structured Pipeline**: Average Score = {struct_avg:.2f}/14\n")
        
        if rag_count > 0:
            rag_avg = rag_total / rag_count
            report_lines.append(f"**RAG Pipeline**: Average Score = {rag_avg:.2f}/14\n")
        
        # MRR Analysis
        report_lines.append("\n## Mean Reciprocal Ranking (MRR) Analysis\n")
        
        struct_mrr_scores = []
        rag_mrr_scores = []
        
        for company_slug in self.results:
            company_results = self.results[company_slug]
            if "structured" in company_results:
                struct_mrr_scores.append(company_results["structured"].get("mrr_score", 0))
            if "rag" in company_results:
                rag_mrr_scores.append(company_results["rag"].get("mrr_score", 0))
        
        if struct_mrr_scores:
            struct_avg_mrr = sum(struct_mrr_scores) / len(struct_mrr_scores)
            report_lines.append(f"**Structured Pipeline** Average MRR: {struct_avg_mrr:.3f}\n")
        
        if rag_mrr_scores:
            rag_avg_mrr = sum(rag_mrr_scores) / len(rag_mrr_scores)
            report_lines.append(f"**RAG Pipeline** Average MRR: {rag_avg_mrr:.3f}\n")
        
        report_lines.append(
            "\n> MRR measures how well important facts are ranked (higher is better, 1.0 is perfect)\n"
        )
        
        report = "".join(report_lines)
        
        # Save report
        report_path = self.eval_dir / "report.md"
        with open(report_path, "w") as f:
            f.write(report)
        
        logger.info(f"✓ Report saved to {report_path}")
        
        return report
    
    def view_results(self, company_slug: str) -> Optional[Dict[str, Any]]:
        """View cached results for a company."""
        if company_slug not in self.results:
            logger.warning(f"No results for {company_slug}")
            return None
        
        company_results = self.results[company_slug]
        
        print(f"\n=== Evaluation Results: {self.ground_truth[company_slug]['company_name']} ===\n")
        
        for pipeline in ["structured", "rag"]:
            if pipeline not in company_results:
                continue
            
            metrics = company_results[pipeline]
            print(f"{pipeline.upper()} Pipeline:")
            print(f"  Factual Accuracy: {metrics.get('factual_accuracy')}/3")
            print(f"  Schema Compliance: {metrics.get('schema_compliance')}/2")
            print(f"  Provenance Quality: {metrics.get('provenance_quality')}/2")
            print(f"  Hallucination Detection: {metrics.get('hallucination_detection')}/2")
            print(f"  Readability: {metrics.get('readability')}/1")
            print(f"  MRR Score: {metrics.get('mrr_score'):.3f}")
            print(f"  Total Score: {metrics.get('total_score'):.1f}/14")
            print(f"  Notes: {metrics.get('notes')}")
            print()
        
        return company_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluation runner for LLM dashboard outputs"
    )
    parser.add_argument(
        "--company",
        help="Evaluate specific company"
    )
    parser.add_argument(
        "--pipeline",
        choices=["structured", "rag"],
        default="structured",
        help="Pipeline type to evaluate"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch evaluation for all companies"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate comparison report"
    )
    parser.add_argument(
        "--view",
        help="View results for a company"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-evaluation (ignore cache)"
    )
    parser.add_argument(
        "--mode",
        choices=["programmatic", "manual"],
        default=None,
        help="Scoring mode: 'programmatic' (auto-calculate) or 'manual' (hardcoded)"
    )
    
    args = parser.parse_args()
    
    runner = EvaluationRunner()
    
    if args.view:
        runner.view_results(args.view)
    
    elif args.batch:
        runner.batch_evaluate(force=args.force, scoring_mode=args.mode)
        
        if args.report:
            report = runner.generate_report()
            print("\n" + report)
    
    elif args.company:
        metrics = runner.evaluate_company_pipeline(
            args.company,
            args.pipeline,
            force=args.force,
            scoring_mode=args.mode
        )
        
        if metrics:
            print(f"\n✓ Evaluation successful")
            print(f"  Company: {metrics.company_name}")
            print(f"  Pipeline: {metrics.pipeline_type}")
            print(f"  Scoring Mode: {args.mode or SCORING_MODE}")
            print(f"  Factual Accuracy: {metrics.factual_accuracy}/3")
            print(f"  Schema Compliance: {metrics.schema_compliance}/2")
            print(f"  Provenance Quality: {metrics.provenance_quality}/2")
            print(f"  Hallucination Detection: {metrics.hallucination_detection}/2")
            print(f"  Readability: {metrics.readability}/1")
            print(f"  MRR: {metrics.mrr_score:.3f}")
            print(f"  Total Score: {metrics.get_total_score():.1f}/14")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
