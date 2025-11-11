#!/usr/bin/env python3
"""Test script for structured extraction with example data.

Validates that the structured extraction pipeline works correctly
without requiring large amounts of LLM API calls.

Usage:
  python src/rag/test_structured_extraction.py
"""

import json
import sys
from pathlib import Path
from datetime import date

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rag_models import (
    Company, Event, Snapshot, Product, Leadership, Visibility, 
    Payload, Provenance
)


def create_example_company() -> Company:
    """Create an example Company record for testing."""
    return Company(
        company_id="world-labs",
        legal_name="World Labs",
        brand_name="World Labs",
        website="https://worldlabs.ai",
        hq_city="San Francisco",
        hq_state="CA",
        hq_country="USA",
        founded_year=2023,
        categories=["AI", "Computer Vision", "3D Generation"],
        related_companies=["OpenAI", "Stability AI"],
        total_raised_usd=5000000.0,
        last_disclosed_valuation_usd=50000000.0,
        last_round_name="Series A",
        last_round_date=date(2024, 6, 15),
        provenance=[
            Provenance(
                source_url="https://worldlabs.ai/about",
                crawled_at="2025-11-05T12:00:00Z",
                snippet="World Labs is building..."
            )
        ]
    )


def create_example_events() -> list:
    """Create example Event records for testing."""
    return [
        Event(
            event_id="worldlabs-seed-2023",
            company_id="world-labs",
            occurred_on=date(2023, 9, 15),
            event_type="funding",
            title="Seed Round Funding",
            description="Initial seed funding round led by major VCs",
            amount_usd=500000.0,
            investors=["Khosla Ventures", "Founder Collective"],
            tags=["Seed"],
            provenance=[
                Provenance(
                    source_url="https://worldlabs.ai/about",
                    crawled_at="2025-11-05T12:00:00Z"
                )
            ]
        ),
        Event(
            event_id="worldlabs-seriesA-2024",
            company_id="world-labs",
            occurred_on=date(2024, 6, 15),
            event_type="funding",
            title="Series A Funding",
            description="Series A round to scale product and engineering",
            amount_usd=5000000.0,
            investors=["OpenAI Ventures", "Khosla Ventures", "Google Ventures"],
            tags=["Series A"],
            provenance=[
                Provenance(
                    source_url="https://worldlabs.ai/blog",
                    crawled_at="2025-11-05T12:00:00Z"
                )
            ]
        )
    ]


def create_example_snapshots() -> list:
    """Create example Snapshot records for testing."""
    return [
        Snapshot(
            company_id="world-labs",
            as_of=date(2025, 11, 5),
            headcount_total=45,
            headcount_growth_pct=200.0,
            job_openings_count=12,
            engineering_openings=8,
            sales_openings=2,
            hiring_focus=["ML Engineers", "3D Graphics", "DevOps"],
            active_products=["OpenWorld"],
            geo_presence=["USA (HQ)", "Canada", "UK"],
            confidence=0.85,
            provenance=[
                Provenance(
                    source_url="https://worldlabs.ai/careers",
                    crawled_at="2025-11-05T12:00:00Z"
                )
            ]
        )
    ]


def create_example_products() -> list:
    """Create example Product records for testing."""
    return [
        Product(
            product_id="worldlabs-openworld",
            company_id="world-labs",
            name="OpenWorld",
            description="AI-powered 3D world generation platform",
            pricing_model="seat",
            pricing_tiers_public=["Pro", "Enterprise"],
            ga_date=date(2024, 3, 1),
            integration_partners=["Unity", "Unreal Engine", "Blender"],
            github_repo="https://github.com/worldlabs/openworld",
            license_type="Proprietary",
            reference_customers=["Game Studio XYZ", "VFX Company ABC"],
            provenance=[
                Provenance(
                    source_url="https://worldlabs.ai/product",
                    crawled_at="2025-11-05T12:00:00Z"
                )
            ]
        )
    ]


def create_example_leadership() -> list:
    """Create example Leadership records for testing."""
    return [
        Leadership(
            person_id="alex-johnson",
            company_id="world-labs",
            name="Alex Johnson",
            role="CEO",
            is_founder=True,
            start_date=date(2023, 1, 1),
            previous_affiliation="OpenAI",
            education="Stanford University (BS Computer Science)",
            linkedin="https://linkedin.com/in/alexjohnson",
            provenance=[
                Provenance(
                    source_url="https://worldlabs.ai/about",
                    crawled_at="2025-11-05T12:00:00Z"
                )
            ]
        ),
        Leadership(
            person_id="sarah-chen",
            company_id="world-labs",
            name="Sarah Chen",
            role="CTO",
            is_founder=True,
            start_date=date(2023, 1, 15),
            previous_affiliation="Google Brain",
            education="MIT (PhD Machine Learning)",
            linkedin="https://linkedin.com/in/sarahchen",
            provenance=[
                Provenance(
                    source_url="https://worldlabs.ai/about",
                    crawled_at="2025-11-05T12:00:00Z"
                )
            ]
        )
    ]


def create_example_visibility() -> Visibility:
    """Create example Visibility record for testing."""
    return Visibility(
        company_id="world-labs",
        as_of=date(2025, 11, 5),
        news_mentions_30d=42,
        avg_sentiment=0.78,
        github_stars=5420,
        glassdoor_rating=4.6,
        provenance=[
            Provenance(
                source_url="https://worldlabs.ai/blog",
                crawled_at="2025-11-05T12:00:00Z"
            )
        ]
    )


def test_payload_creation():
    """Test creating a complete Payload with all data models."""
    print("=" * 60)
    print("Testing Structured Extraction Models")
    print("=" * 60)
    
    # Create example data
    company = create_example_company()
    events = create_example_events()
    snapshots = create_example_snapshots()
    products = create_example_products()
    leadership = create_example_leadership()
    visibility = create_example_visibility()
    
    # Create payload
    payload = Payload(
        company_record=company,
        events=events,
        snapshots=snapshots,
        products=products,
        leadership=leadership,
        visibility=[visibility],
        notes="Test extraction payload with example data"
    )
    
    print("\n✓ Successfully created Payload with:")
    print(f"  - Company: {company.legal_name}")
    print(f"  - Events: {len(events)}")
    print(f"  - Snapshots: {len(snapshots)}")
    print(f"  - Products: {len(products)}")
    print(f"  - Leadership: {len(leadership)}")
    print(f"  - Visibility: 1")
    
    # Serialize to JSON
    payload_dict = payload.model_dump(mode='json')
    payload_json = json.dumps(payload_dict, indent=2, default=str)
    
    print(f"\n✓ Successfully serialized to JSON: {len(payload_json)} chars")
    
    # Save to file
    output_dir = Path("data/structured")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "test_example.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(payload_json)
    
    print(f"✓ Saved test payload to: {output_file}")
    
    # Print sample of output
    print("\nSample JSON output (first 500 chars):")
    print("-" * 60)
    print(payload_json[:500] + "...")
    print("-" * 60)
    
    return payload


def validate_models():
    """Validate all Pydantic models can be instantiated."""
    print("\n" + "=" * 60)
    print("Validating Pydantic Models")
    print("=" * 60)
    
    models_to_test = [
        ("Company", create_example_company),
        ("Events", create_example_events),
        ("Snapshots", create_example_snapshots),
        ("Products", create_example_products),
        ("Leadership", create_example_leadership),
        ("Visibility", create_example_visibility),
    ]
    
    for model_name, create_func in models_to_test:
        try:
            result = create_func()
            if isinstance(result, list):
                print(f"✓ {model_name}: {len(result)} items")
            else:
                print(f"✓ {model_name}: valid")
        except Exception as e:
            print(f"✗ {model_name}: FAILED - {e}")
            return False
    
    return True


def main():
    print("\n")
    
    # Validate models
    if not validate_models():
        print("\n✗ Model validation failed!")
        return 1
    
    # Test payload creation
    try:
        payload = test_payload_creation()
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
