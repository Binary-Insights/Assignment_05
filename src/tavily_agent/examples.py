"""
Example usage and testing script for Agentic RAG system.
Demonstrates various workflows and configurations.
"""

import asyncio
import json
import sys
from pathlib import Path

from . import (
    enrich_single_company,
    enrich_multiple_companies,
    enrich_all_companies,
    AgenticRAGOrchestrator,
    PayloadAnalyzer,
    FileIOManager,
    validate_config
)


async def example_single_company():
    """Example: Enrich a single company."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Enrich Single Company")
    print("="*60)
    
    company_name = "abridge"
    result = await enrich_single_company(company_name)
    
    print(f"\nResult for {company_name}:")
    print(json.dumps(result, indent=2, default=str))


async def example_multiple_companies():
    """Example: Enrich multiple companies."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Enrich Multiple Companies")
    print("="*60)
    
    companies = ["abridge"]  # Add more as needed
    summary = await enrich_multiple_companies(companies)
    
    print("\nBatch Summary:")
    print(json.dumps(summary, indent=2, default=str))


async def example_analyze_payload():
    """Example: Analyze payload without enrichment."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Analyze Payload Structure")
    print("="*60)
    
    file_io = FileIOManager()
    payload = await file_io.read_payload("abridge")
    
    if payload:
        analyzer = PayloadAnalyzer()
        null_fields = analyzer.get_null_fields_summary(payload)
        
        print(f"\nNull Fields Summary for abridge:")
        for entity_type, fields in null_fields.items():
            print(f"  {entity_type}: {', '.join(fields)}")
        
        is_valid, errors = analyzer.validate_payload_structure(payload)
        print(f"\nPayload Valid: {is_valid}")
        if errors:
            print("Errors:")
            for error in errors:
                print(f"  - {error}")


async def example_orchestrator_custom():
    """Example: Use orchestrator with custom configuration."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Custom Orchestrator Configuration")
    print("="*60)
    
    orchestrator = AgenticRAGOrchestrator()
    await orchestrator.initialize()
    
    # Process specific companies
    companies = ["abridge"]
    summary = await orchestrator.process_batch(companies)
    
    orchestrator.print_summary()
    summary_path = orchestrator.save_execution_summary()
    
    print(f"\nExecution summary saved to: {summary_path}")


async def example_list_available_companies():
    """Example: List all available companies."""
    print("\n" + "="*60)
    print("EXAMPLE 5: List Available Companies")
    print("="*60)
    
    file_io = FileIOManager()
    companies = await file_io.list_company_payloads()
    
    print(f"\nAvailable companies ({len(companies)}):")
    for i, company in enumerate(companies, 1):
        print(f"  {i}. {company}")


async def example_validate_setup():
    """Example: Validate system setup."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Validate System Setup")
    print("="*60)
    
    is_valid = validate_config()
    
    if is_valid:
        print("\n✓ All required API keys configured")
        print("✓ System is ready for use")
    else:
        print("\n✗ Configuration incomplete")
        print("Please ensure all required API keys are set in .env:")
        print("  - OPENAI_API_KEY")
        print("  - TAVILY_API_KEY")
        print("  - PINECONE_API_KEY")


async def main():
    """Run all examples or specific one."""
    examples = {
        "1": ("Single Company", example_single_company),
        "2": ("Multiple Companies", example_multiple_companies),
        "3": ("Analyze Payload", example_analyze_payload),
        "4": ("Custom Orchestrator", example_orchestrator_custom),
        "5": ("List Companies", example_list_available_companies),
        "6": ("Validate Setup", example_validate_setup),
    }
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        if choice in examples:
            print(f"\nRunning: {examples[choice][0]}")
            await examples[choice][1]()
        else:
            print(f"Unknown example: {choice}")
            print("\nAvailable examples:")
            for key, (name, _) in examples.items():
                print(f"  {key}: {name}")
    else:
        # Run all examples
        for key, (name, func) in examples.items():
            try:
                await func()
            except Exception as e:
                print(f"\nError in {name}: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
