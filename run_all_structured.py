#!/usr/bin/env python3
"""
Batch runner for structured_extraction.py

Runs structured extraction for all 50 Forbes AI companies.

Usage:
    python run_all_structured.py
    python run_all_structured.py --verbose
    python run_all_structured.py --limit 10
    python run_all_structured.py --start-index 5 --limit 20
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import List

def load_company_slugs(seed_file: str = "data/forbes_ai50_seed.json") -> List[str]:
    """Load all company names/slugs from the seed file."""
    seed_path = Path(seed_file)
    
    if not seed_path.exists():
        print(f"❌ Error: Seed file not found: {seed_path}")
        sys.exit(1)
    
    with open(seed_path) as f:
        companies = json.load(f)
    
    # Convert company names to slugs (lowercase, replace spaces with underscores)
    slugs = [
        c["company_name"].lower().replace(" ", "_").replace("-", "_")
        for c in companies
    ]
    
    return slugs


def run_for_company(company_slug: str, extra_args: List[str] = None) -> bool:
    """
    Run structured_extraction.py for a single company.
    
    Args:
        company_slug: Company slug (e.g., "world_labs")
        extra_args: Additional command-line arguments to pass through
    
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        sys.executable,
        "src/rag/structured_extraction.py",
        "--company-slug", company_slug
    ]
    
    if extra_args:
        cmd.extend(extra_args)
    
    print(f"\n{'='*80}")
    print(f"🔄 Processing: {company_slug}")
    print(f"{'='*80}")
    print(f"Command: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=False, timeout=3600)  # 60 minute timeout per company
        if result.returncode == 0:
            print(f"✅ {company_slug}: SUCCESS")
            return True
        else:
            print(f"❌ {company_slug}: FAILED (exit code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️  {company_slug}: TIMEOUT (exceeded 60 minutes)")
        return False
    except Exception as e:
        print(f"❌ {company_slug}: ERROR - {e}")
        return False


def main():
    """Main batch processing loop."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Batch run structured_extraction.py for all 50 companies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_structured.py
  python run_all_structured.py --verbose
  python run_all_structured.py --limit 10       # Process only first 10
  python run_all_structured.py --start-index 5  # Start from 6th company
  python run_all_structured.py --start-index 5 --limit 20  # Companies 6-25
        """
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start from this company index (0-based, default: 0)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to this many companies (default: all)"
    )
    
    args = parser.parse_args()
    
    # Load company slugs
    print("📋 Loading company list...")
    slugs = load_company_slugs()
    print(f"✅ Loaded {len(slugs)} companies\n")
    
    # Apply start-index and limit
    if args.start_index > 0:
        print(f"⏭️  Starting from index {args.start_index}")
        slugs = slugs[args.start_index:]
    
    if args.limit:
        print(f"⏱️  Limiting to {args.limit} companies")
        slugs = slugs[:args.limit]
    
    print(f"🎯 Will process {len(slugs)} companies\n")
    
    # Build extra arguments
    extra_args = []
    
    if args.verbose:
        extra_args.append("--verbose")
    
    # Run for each company
    results = {}
    successful = 0
    failed = 0
    
    for i, company_slug in enumerate(slugs, 1):
        success = run_for_company(company_slug, extra_args)
        results[company_slug] = success
        
        if success:
            successful += 1
        else:
            failed += 1
        
        print(f"\n📊 Progress: {i}/{len(slugs)} ({successful} successful, {failed} failed)")
    
    # Print summary
    print("\n" + "="*80)
    print("BATCH PROCESSING SUMMARY")
    print("="*80)
    print(f"✅ Successful: {successful}/{len(slugs)}")
    print(f"❌ Failed: {failed}/{len(slugs)}")
    
    if failed > 0:
        print("\n❌ Failed companies:")
        for company, success in results.items():
            if not success:
                print(f"  - {company}")
    
    print(f"\n📂 Structured payloads saved to: data/structured/")
    print(f"\n✨ All companies processed!")
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
