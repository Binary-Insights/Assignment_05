from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Literal
from datetime import date

class Provenance(BaseModel):
    source_url: str  # Changed from HttpUrl to str to accept page type identifiers like "about", "product", etc.
    crawled_at: str
    snippet: Optional[str] = None
    chunk_id: Optional[str] = None

class Company(BaseModel):
    company_id: str
    legal_name: str
    brand_name: Optional[str] = None
    website: Optional[HttpUrl] = None
    hq_city: Optional[str] = None
    hq_state: Optional[str] = None
    hq_country: Optional[str] = None
    founded_year: Optional[int] = None
    categories: Optional[List[str]] = None
    related_companies: Optional[List[str]] = None
    total_raised_usd: Optional[float] = None
    last_disclosed_valuation_usd: Optional[float] = None
    last_round_name: Optional[str] = None
    last_round_date: Optional[date] = None
    schema_version: str = "2.0.0"
    as_of: Optional[date] = None
    provenance: List[Provenance] = []

class Event(BaseModel):
    event_id: str
    company_id: str
    occurred_on: date
    event_type: Literal[
        "funding","mna","product_release","integration","partnership",
        "customer_win","leadership_change","regulatory","security_incident",
        "pricing_change","layoff","hiring_spike","office_open","office_close",
        "benchmark","open_source_release","contract_award","other"
    ]
    title: str
    description: Optional[str] = None
    round_name: Optional[str] = None
    investors: Optional[List[str]] = None
    amount_usd: Optional[float] = None  # funding, contract, pricing deltas
    valuation_usd: Optional[float] = None
    actors: Optional[List[str]] = None  # investors, partners, customers, execs
    tags: Optional[List[str]] = None  # e.g., "Series B", "SOC2", "HIPAA"
    schema_version: str = "2.0.0"
    provenance: List[Provenance] = []

class Snapshot(BaseModel):
    company_id: str
    as_of: date
    headcount_total: Optional[int] = None
    headcount_growth_pct: Optional[float] = None
    job_openings_count: Optional[int] = None
    engineering_openings: Optional[int] = None
    sales_openings: Optional[int] = None
    hiring_focus: Optional[List[str]] = None  # e.g., "sales","ml","security"
    pricing_tiers: Optional[List[str]] = None
    active_products: Optional[List[str]] = None
    geo_presence: Optional[List[str]] = None
    confidence: Optional[float] = None
    schema_version: str = "2.0.0"
    provenance: List[Provenance] = []

class Product(BaseModel):
    product_id: str
    company_id: str
    name: str
    description: Optional[str] = None
    pricing_model: Optional[str] = None # "seat", "usage", "tiered"
    pricing_tiers_public: Optional[List[str]] = None
    ga_date: Optional[date] = None
    integration_partners: Optional[List[str]] = None
    github_repo: Optional[str] = None
    license_type: Optional[str] = None
    reference_customers: Optional[List[str]] = None
    schema_version: str = "2.0.0"
    provenance: List[Provenance] = []

class Leadership(BaseModel):
    person_id: str
    company_id: str
    name: str
    role: str  # CEO, CTO, CPO, etc.
    is_founder: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    previous_affiliation: Optional[str] = None
    education: Optional[str] = None
    linkedin: Optional[HttpUrl] = None
    schema_version: str = "2.0.0"
    provenance: List[Provenance] = []

class Visibility(BaseModel):
    company_id: str
    as_of: date
    news_mentions_30d: Optional[int] = None
    avg_sentiment: Optional[float] = None
    github_stars: Optional[int] = None
    glassdoor_rating: Optional[float] = None
    schema_version: str = "2.0.0"
    provenance: List[Provenance] = []

class Payload(BaseModel):
    company_record: Company
    events: List[Event] = []
    snapshots: List[Snapshot] = []
    products: List[Product] = []
    leadership: List[Leadership] = []
    visibility: List[Visibility] = []
    notes: Optional[str] = ""
    provenance_policy: Optional[str] = "Use only the sources you scraped. If a field is missing, write 'Not disclosed.' Do not infer valuation."
