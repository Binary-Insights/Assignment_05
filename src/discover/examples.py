#!/usr/bin/env python3
"""
Example: Using llm_page_finder programmatically (not just CLI).

This shows how to integrate the discovery function into your own scripts.
"""

import json
from llm_page_finder import discover_page_with_llm, setup_logger


def example_single_discovery():
    """Example 1: Discover a single page."""
    logger = setup_logger()
    logger.info("Example 1: Single Discovery")
    
    result = discover_page_with_llm(
        website_url="https://www.anthropic.com/",
        page_type="careers"
    )
    
    print("\n--- Result ---")
    print(f"URL Found: {result.result.discovered_url}")
    print(f"Confidence: {result.result.confidence:.2%}")
    print(f"Reasoning: {result.result.reasoning}")
    
    return result


def example_batch_discovery():
    """Example 2: Discover multiple page types for same website."""
    logger = setup_logger()
    logger.info("Example 2: Batch Discovery")
    
    companies = [
        "https://www.anthropic.com/",
        "https://www.abridge.com/",
        "https://cohere.com/"
    ]
    
    page_types = ["product", "careers"]
    
    results = {}
    
    for company_url in companies:
        results[company_url] = {}
        
        for page_type in page_types:
            logger.info(f"Discovering {page_type} for {company_url}")
            
            result = discover_page_with_llm(company_url, page_type)
            results[company_url][page_type] = {
                "url": result.result.discovered_url,
                "confidence": result.result.confidence,
                "reasoning": result.result.reasoning
            }
    
    # Pretty print results
    print("\n--- Batch Results ---")
    print(json.dumps(results, indent=2))
    
    return results


def example_error_handling():
    """Example 3: Handle errors gracefully."""
    logger = setup_logger()
    logger.info("Example 3: Error Handling")
    
    # Invalid URL
    result_1 = discover_page_with_llm(
        website_url="https://invalid-domain-that-does-not-exist-12345.com/",
        page_type="product"
    )
    
    print("\n--- Invalid URL Result ---")
    print(f"URL: {result_1.result.discovered_url}")
    print(f"Confidence: {result_1.result.confidence:.2%}")
    print(f"Reasoning: {result_1.result.reasoning}")
    
    # Check if discovery was successful
    if result_1.result.discovered_url:
        print("✓ Discovery succeeded")
    else:
        print("✗ Discovery failed (this is expected for invalid domains)")
    
    return result_1


def example_structured_output():
    """Example 4: Access structured output models directly."""
    logger = setup_logger()
    logger.info("Example 4: Structured Output Access")
    
    result = discover_page_with_llm(
        website_url="https://www.databricks.com/",
        page_type="about"
    )
    
    # Access via Pydantic model
    print("\n--- Structured Access ---")
    print(f"Request URL: {result.request.website_url}")
    print(f"Requested Page Type: {result.request.page_type}")
    print(f"Discovered URL: {result.result.discovered_url}")
    print(f"Confidence: {result.result.confidence}")
    print(f"Alternatives: {result.result.alternative_urls}")
    
    # Convert to dict for JSON serialization
    as_dict = result.model_dump()
    as_json = result.model_dump_json(indent=2)
    
    print("\n--- JSON Serialization ---")
    print(as_json)
    
    return result


def example_integration_with_discovery_pipeline():
    """Example 5: Integrate with existing discover_links.py pipeline."""
    import json
    from pathlib import Path
    
    logger = setup_logger()
    logger.info("Example 5: Pipeline Integration")
    
    # Load existing discovered pages
    discovered_path = Path("data/company_pages_discovered.json")
    
    if not discovered_path.exists():
        logger.warning(f"File not found: {discovered_path}")
        return None
    
    with open(discovered_path, "r") as f:
        discovered_data = json.load(f)
    
    # For each company with low-confidence discoveries, use LLM for refinement
    refined_results = []
    
    for company_entry in discovered_data[:2]:  # Limit to first 2 for demo
        company_name = company_entry.get("company_name")
        website = company_entry.get("website")
        discovered_pages = company_entry.get("discovered_pages", {})
        
        logger.info(f"Refining discoveries for {company_name}...")
        
        refined = {
            "company_name": company_name,
            "website": website,
            "heuristic_results": discovered_pages,
            "llm_refinements": {}
        }
        
        # For each page type with no/low confidence, use LLM
        for page_type in ["product", "careers", "about", "blog"]:
            candidates = discovered_pages.get(page_type, [])
            
            # If no candidates found, try LLM
            if not candidates:
                logger.info(f"  No {page_type} found via heuristics, trying LLM...")
                
                result = discover_page_with_llm(website, page_type)
                
                refined["llm_refinements"][page_type] = {
                    "url": result.result.discovered_url,
                    "confidence": result.result.confidence,
                    "reasoning": result.result.reasoning
                }
        
        refined_results.append(refined)
    
    # Save refined results
    output_path = "output/llm_refined_discoveries.json"
    Path(output_path).parent.mkdir(exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(refined_results, f, indent=2)
    
    logger.info(f"Saved refined results to {output_path}")
    
    print("\n--- Refined Results Summary ---")
    print(json.dumps(refined_results, indent=2))
    
    return refined_results


if __name__ == "__main__":
    import sys
    
    examples = {
        "1": ("Single Discovery", example_single_discovery),
        "2": ("Batch Discovery", example_batch_discovery),
        "3": ("Error Handling", example_error_handling),
        "4": ("Structured Output", example_structured_output),
        "5": ("Pipeline Integration", example_integration_with_discovery_pipeline),
    }
    
    print("LLM Page Finder - Examples")
    print("=" * 60)
    print("Choose an example to run:")
    print()
    
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    
    print(f"  0. Run all examples")
    print()
    
    choice = sys.argv[1] if len(sys.argv) > 1 else input("Enter choice (0-5): ").strip()
    
    if choice == "0":
        for key in sorted(examples.keys()):
            print(f"\n{'=' * 60}")
            print(f"Running Example {key}: {examples[key][0]}")
            print('=' * 60)
            try:
                examples[key][1]()
            except Exception as e:
                print(f"✗ Error in example {key}: {e}")
    elif choice in examples:
        print(f"\nRunning Example {choice}: {examples[choice][0]}")
        print("=" * 60)
        try:
            examples[choice][1]()
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid choice")
        sys.exit(1)
