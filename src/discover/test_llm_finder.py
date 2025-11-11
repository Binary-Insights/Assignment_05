#!/usr/bin/env python3
"""
Test script for LLM page finder.

This script tests the llm_page_finder.py module with sample company URLs
from the company_pages_discovered.json file.

Usage:
  python src/discover/test_llm_finder.py
  python src/discover/test_llm_finder.py --sample-count 2
  python src/discover/test_llm_finder.py --website "https://www.anthropic.com/" --page-type "careers"
"""

import json
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import llm_page_finder
sys.path.insert(0, str(Path(__file__).parent))

from llm_page_finder import discover_page_with_llm, setup_logger


def load_sample_companies(json_path: str = "data/company_pages_discovered.json", limit: int = 3):
    """Load sample companies from discovered data."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Filter out companies without websites
    companies = [c for c in data if c.get("website")]
    return companies[:limit]


def test_single_company(website: str, page_type: str):
    """Test discovery for a single website and page type."""
    logger = setup_logger()
    logger.info(f"Testing: {website} -> {page_type}")
    
    result = discover_page_with_llm(website, page_type)
    
    print("\n" + "="*80)
    print(f"Discovery Result for {page_type.upper()} at {website}")
    print("="*80)
    print(json.dumps(result.model_dump(), indent=2))
    print("="*80 + "\n")
    
    return result


def test_batch(sample_count: int = 3, page_types: list = None):
    """Test discovery for multiple companies."""
    if page_types is None:
        page_types = ["product", "careers"]
    
    logger = setup_logger()
    logger.info(f"Loading {sample_count} sample companies...")
    
    companies = load_sample_companies(limit=sample_count)
    
    if not companies:
        logger.error("No companies loaded from data/company_pages_discovered.json")
        return []
    
    logger.info(f"Loaded {len(companies)} companies")
    
    results = []
    
    for company in companies:
        website = company.get("website")
        company_name = company.get("company_name", "Unknown")
        
        logger.info(f"\n--- Processing {company_name} ({website}) ---")
        
        for page_type in page_types:
            logger.info(f"  Discovering {page_type} page...")
            try:
                result = discover_page_with_llm(website, page_type)
                results.append({
                    "company": company_name,
                    "website": website,
                    "result": result.model_dump()
                })
                print(f"\n✓ {company_name} - {page_type}:")
                print(f"    URL: {result.result.discovered_url}")
                print(f"    Confidence: {result.result.confidence:.2f}")
            except Exception as e:
                logger.error(f"  Error discovering {page_type}: {e}")
                print(f"\n✗ {company_name} - {page_type}: ERROR - {e}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test the LLM page finder"
    )
    parser.add_argument(
        "--website",
        type=str,
        default=None,
        help="Test a specific website (e.g., https://www.anthropic.com/)"
    )
    parser.add_argument(
        "--page-type",
        type=str,
        choices=["product", "careers", "about", "blog"],
        default="product",
        help="Page type to discover"
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=3,
        help="Number of sample companies to test (default: 3)"
    )
    parser.add_argument(
        "--page-types",
        type=str,
        nargs="+",
        choices=["product", "careers", "about", "blog"],
        default=["product", "careers"],
        help="Page types to test in batch mode"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch test on sample companies"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    logger = setup_logger()
    logger.info("Starting LLM Page Finder Test")
    
    results = []
    
    if args.website:
        # Test specific website
        logger.info(f"Testing specific website: {args.website}")
        result = test_single_company(args.website, args.page_type)
        results = [{"website": args.website, "result": result.model_dump()}]
    else:
        # Batch test
        logger.info(f"Running batch test with {args.sample_count} companies")
        results = test_batch(args.sample_count, args.page_types)
    
    # Save results if requested
    if args.output and results:
        logger.info(f"Saving results to {args.output}")
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to {args.output}")
    
    logger.info("Test complete")
    return 0


if __name__ == "__main__":
    exit(main())
