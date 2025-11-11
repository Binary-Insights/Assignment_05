#!/usr/bin/env python3
"""
Quick timing test: Check how long structured extraction takes for one company.

This helps us understand the actual runtime so we can set proper timeouts.
"""

import subprocess
import sys
import time
from pathlib import Path

def time_single_company(company_slug: str = "world_labs") -> float:
    """Time how long it takes to extract one company."""
    
    cmd = [
        sys.executable,
        "src/rag/structured_extraction.py",
        "--company-slug", company_slug,
        "--verbose"
    ]
    
    print(f"🔍 Timing structured extraction for: {company_slug}")
    print(f"Command: {' '.join(cmd)}\n")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, check=False, timeout=3600)  # 1 hour max
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n✅ SUCCESS in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
            return elapsed
        else:
            print(f"\n❌ FAILED with exit code {result.returncode} after {elapsed:.1f} seconds")
            return -1
    
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"\n⏱️  TIMEOUT after {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        return -1
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ERROR after {elapsed:.1f} seconds: {e}")
        return -1


def main():
    """Run timing test."""
    print("="*80)
    print("STRUCTURED EXTRACTION TIMING TEST")
    print("="*80)
    print("\nThis will help determine appropriate timeout values.\n")
    
    elapsed = time_single_company("world_labs")
    
    if elapsed > 0:
        print(f"\n📊 TIMING RESULTS:")
        print(f"   Single company: {elapsed/60:.1f} minutes")
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   - Per-company timeout: {int(elapsed * 1.5 / 60) + 1} minutes (with 50% buffer)")
        print(f"   - All 50 companies: {int(elapsed * 1.5 * 50 / 60)} minutes sequentially")
        print(f"\nTo update timeout in run_all_structured.py:")
        print(f"   timeout={int(elapsed * 1.5)}")  # seconds with 50% buffer
    else:
        print("\n❌ Could not determine timing")


if __name__ == "__main__":
    main()
