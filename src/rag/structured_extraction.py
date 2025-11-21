#!/usr/bin/env python3
"""RAG-based Structured Extraction: Extract and normalize company data from web scrapes using LLM.

This script:
1. Reads text extracted from company web pages (data/raw/{company_slug}/{page_type}/text.txt)
2. Queries Pinecone vector database to retrieve relevant context
3. Uses instructor + OpenAI to extract structured data into Pydantic models
4. Normalizes messy text data into clean, structured format
5. Saves results as data/structured/{company_id}.json

The extraction follows the schema defined in rag_models.py:
- Company (legal_name, website, headquarters, founding date, funding, etc.)
- Event (funding rounds, M&A, product releases, etc.)
- Snapshot (headcount, job openings, pricing, etc.)
- Product (description, pricing model, integrations, etc.)
- Leadership (founders, executives, roles, etc.)
- Visibility (news mentions, GitHub stars, ratings, etc.)

Usage:
  python src/rag/structured_extraction.py
  python src/rag/structured_extraction.py --company-slug world_labs --verbose
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4

import instructor
from openai import OpenAI
from pydantic import BaseModel, ValidationError, Field
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# Import Pydantic models
sys.path.insert(0, str(Path(__file__).parent))
from rag_models import (
    Company, Event, Snapshot, Product, Leadership, Visibility, 
    Payload, Provenance
)

# Load environment variables
load_dotenv()

print("✅ Running in LOCAL-ONLY mode (no Google Cloud Storage)")
print("✅ Data loading from: data/raw/{company_slug}/")
print("✅ Data saving to: data/structured/{company_id}.json")
print("✅ Enhanced with anti-hallucination validation")

# Global configuration
FALLBACK_STRATEGY = 'pinecone_first'  # Can be: 'pinecone_only', 'raw_only', 'pinecone_first'
USE_RAW_TEXT = True  # Set to True to skip Pinecone and use raw text directly

def setup_logging():
    """Setup logging for structured_extraction script."""
    log_dir = "data/logs"
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger('structured_extraction')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(f"{log_dir}/structured_extraction.log")
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# ============================================================================
# VALIDATION HELPERS - Anti-Hallucination
# ============================================================================

def is_website_section(name: str) -> bool:
    """
    Check if 'product' name is actually a website section.
    
    Filters out common false positives like:
    - Website pages: "Blog", "Press Kit", "Newsroom"
    - Legal docs: "Terms and Privacy", "Updates to Policy"
    - Initiatives: "Advisory Council", "Economic Program"
    - Partnerships: "MOU with Government"
    """
    if not name:
        return True
    
    website_sections = {
        'blog', 'videos', 'press kit', 'company', 'newsroom', 'press',
        'careers', 'about', 'contact', 'team', 'investors', 'customers',
        'partners', 'pricing', 'news', 'resources', 'insights', 'events',
        'webinars', 'documentation', 'docs', 'support', 'help center',
        'terms', 'privacy', 'policy', 'legal', 'security', 'compliance',
        'customer info', 'case studies', 'success stories'
    }
    
    name_lower = name.lower().strip()
    
    if name_lower in website_sections:
        return True
    
    # Pattern-based exclusions
    non_product_patterns = [
        r'^updates?\s+to\s+',  # "Updates to Terms"
        r'^signs?\s+',  # "Signs MOU"
        r'^mou\s+with\s+',  # "MOU with UK Government"
        r'^expanding\s+',  # "Expanding Google Cloud TPUs"
        r'^announces?\s+',  # "Announces Partnership"
        r'advisory\s+council',  # "Economic Advisory Council"
        r'futures?\s+program',  # "Economic Futures Program"
        r'program$',  # Ends with "Program" (usually initiatives)
    ]
    
    import re
    for pattern in non_product_patterns:
        if re.search(pattern, name_lower):
            return True
    
    return False


def extract_founded_year_aggressive(pages_text: Dict[str, str]) -> Optional[int]:
    """
    Aggressively search ALL text content for founding year.
    
    Searches through all pages looking for patterns:
    - "founded in", "established in", "since", etc.
    """
    import re
    all_text = ""
    
    # Combine ALL page texts
    for page_type, text in pages_text.items():
        all_text += text + "\n\n"
    
    # Search for founding mentions
    founding_patterns = [
        r'founded\s+in\s+(\d{4})',
        r'established\s+in\s+(\d{4})',
        r'started\s+in\s+(\d{4})',
        r'since\s+(\d{4})',
        r'began\s+in\s+(\d{4})',
        r'launched\s+in\s+(\d{4})',
        r'inception\s+in\s+(\d{4})',
        r'created\s+in\s+(\d{4})'
    ]
    
    for pattern in founding_patterns:
        match = re.search(pattern, all_text.lower())
        if match:
            try:
                year = int(match.group(1))
                if 1900 <= year <= 2024:  # Sanity check
                    return year
            except (ValueError, IndexError):
                continue
    
    return None


def get_llm_client():
    """Initialize OpenAI client with instructor patch."""
    logger = logging.getLogger('structured_extraction')
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not set in environment")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    # Create base OpenAI client
    base_client = OpenAI(api_key=api_key)
    
    # Patch with instructor - this modifies the client in place and returns it
    try:
        client = instructor.patch(
            base_client,
            mode=instructor.Mode.TOOLS,  # Use TOOLS mode for better compatibility
        )
        logger.info("Initialized OpenAI client with instructor (TOOLS mode)")
    except Exception as e:
        logger.warning(f"Failed to patch with TOOLS mode, trying MD_JSON: {e}")
        try:
            client = instructor.patch(
                base_client,
                mode=instructor.Mode.MD_JSON,
            )
            logger.info("Initialized OpenAI client with instructor (MD_JSON mode)")
        except Exception as e2:
            logger.warning(f"Failed to patch with MD_JSON mode, using standard: {e2}")
            client = instructor.patch(base_client)
            logger.info("Initialized OpenAI client with instructor (standard mode)")
    
    return client


def get_pinecone_client():
    """Initialize Pinecone client for vector search."""
    logger = logging.getLogger('structured_extraction')
    
    # Get Pinecone configuration from environment
    api_key = os.getenv('PINECONE_API_KEY')
    if not api_key:
        logger.error("PINECONE_API_KEY not set in environment")
        raise ValueError("PINECONE_API_KEY environment variable is required")
    
    index_name = os.getenv('PINECONE_INDEX_NAME', 'bigdata-assignment-04')
    logger.info(f"Attempting to connect to Pinecone index: {index_name}")
    
    try:
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Get index reference
        index = pc.Index(index_name)
        
        # Test connection by getting index stats
        try:
            logger.info("Testing Pinecone connection...")
            stats = index.describe_index_stats()
            logger.info(f"✅ Successfully connected to Pinecone index '{index_name}'")
            logger.info(f"   Namespaces: {list(stats.namespaces.keys()) if stats.namespaces else 'default'}")
            logger.info(f"   Total vectors: {stats.total_vector_count}")
            return index
        except Exception as test_error:
            logger.error(f"❌ Failed to verify Pinecone connection: {test_error}")
            raise
    except Exception as e:
        logger.warning(f"Failed to connect to Pinecone: {e}")
        logger.info("Will proceed without vector search (using raw text instead)")
        return None


def get_embeddings_model():
    """Get OpenAI embeddings model."""
    logger = logging.getLogger('structured_extraction')
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY not set for embeddings")
        raise ValueError("OPENAI_API_KEY required for embeddings")
    
    try:
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=api_key
        )
        logger.debug("Initialized OpenAI embeddings model")
        return embeddings
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        raise


def index_company_pages_to_pinecone(
    company_slug: str, 
    pages_text: Dict[str, str],
    pinecone_index,
    embeddings: Optional[OpenAIEmbeddings]
) -> Optional[str]:
    """Index company pages to Pinecone vector database."""
    logger = logging.getLogger('structured_extraction')
    
    if not pinecone_index or not embeddings:
        logger.debug("Pinecone index or embeddings not available, skipping indexing")
        return None
    
    try:
        namespace = os.getenv('PINECONE_NAMESPACE', 'default')
        logger.info(f"Using Pinecone namespace: '{namespace}'")
        
        # Split and embed text from all pages using same chunking strategy
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
        )
        
        vectors_to_upsert = []
        chunks_per_source = {}  # Track chunks per source file
        
        logger.info(f"\nIndexing source files for {company_slug}:")
        logger.info(f"{'─' * 60}")
        
        for page_type, text in pages_text.items():
            if not text:
                continue
            
            # Log source file information
            source_file = f"data/raw/{company_slug}/{page_type}/text.txt"
            logger.info(f"  📄 Source: {source_file}")
            logger.info(f"     Content size: {len(text)} characters")
            
            # Split text into chunks
            chunks = text_splitter.split_text(text)
            chunks_per_source[page_type] = len(chunks)
            logger.info(f"     Chunks created: {len(chunks)} (500 chars, 100 char overlap)")
            
            for chunk_idx, chunk in enumerate(chunks, 1):
                try:
                    # Generate embedding
                    embedding = embeddings.embed_query(chunk)
                    
                    # Create unique ID for the vector
                    vector_id = f"{company_slug}_{page_type}_{chunk_idx}_{str(uuid4())[:8]}"
                    
                    # Create vector tuple (id, embedding, metadata)
                    vector = (
                        vector_id,
                        embedding,
                        {
                            "text": chunk,
                            "page_type": page_type,
                            "company_slug": company_slug,
                            "source_file": source_file,
                            "chunk_index": chunk_idx,
                            "indexed_at": datetime.now().isoformat()
                        }
                    )
                    vectors_to_upsert.append(vector)
                except Exception as e:
                    logger.warning(f"Failed to embed chunk {chunk_idx} from {page_type}: {e}")
                    continue
            
            logger.info(f"     ✓ Processed {page_type}\n")
        
        if vectors_to_upsert:
            # Upsert vectors to Pinecone
            logger.info(f"Upserting {len(vectors_to_upsert)} vectors to Pinecone...")
            upsert_response = pinecone_index.upsert(
                vectors=vectors_to_upsert,
                namespace=namespace
            )
            logger.info(f"✅ Upserted {len(vectors_to_upsert)} vectors")
            
            # Summary logging
            logger.info(f"{'─' * 60}")
            logger.info(f"✓ Indexed {len(vectors_to_upsert)} total chunks to Pinecone (namespace: '{namespace}')")
            logger.info(f"\nBreakdown by source:")
            for source, count in sorted(chunks_per_source.items()):
                logger.info(f"  • {source:15} → {count:3} chunks")
            logger.info(f"{'─' * 60}\n")
        
        return namespace
        
    except Exception as e:
        logger.warning(f"Error indexing to Pinecone: {e}")
        return None




def build_semantic_search_queries(query_type: str) -> List[str]:
    """Build semantic search queries for different extraction types.
    
    Maps field names to semantic questions for better vector matching.
    """
    semantic_queries = {
        'company_info': [
            "company legal name brand headquarters location",
            "when was company founded established started",
            "company website URL domain",
            "what industries categories sectors does company operate in",
            "company funding raised capital investment valuation"
        ],
        'funding': [
            "funding rounds Series A B C seed investment capital raised",
            "investors venture capital backed by led by",
            "funding amounts rounds valuation investment history",
        ],
        'products': [
            "products services offerings what does company build make",
            "product description features capabilities",
            "pricing model pricing tiers cost pricing plans",
            "integrations partnerships APIs",
            "GitHub repository open source code",
        ],
        'leadership': [
            "founder co-founder CEO founder",
            "executive team leadership management",
            "LinkedIn profile background education university",
            "previous employment history former company",
        ],
        'snapshot': [
            "headcount employees team size number of people",
            "job openings hiring positions vacancies career",
            "office locations geographic presence countries regions",
            "product offerings current products services",
        ],
        'events': [
            "news announcements press releases",
            "M&A acquisition merger",
            "partnerships collaborations integrations",
            "milestones achievements awards recognition",
        ]
    }
    
    return semantic_queries.get(query_type, [f"{query_type} information"])


def search_pinecone_for_context(
    query: str,
    company_slug: str,
    pinecone_index,
    embeddings: Optional[OpenAIEmbeddings],
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Search Pinecone for relevant context using semantic search."""
    logger = logging.getLogger('structured_extraction')
    
    if not pinecone_index or not embeddings:
        logger.debug("Cannot search Pinecone - index/embeddings missing")
        return []
    
    namespace = os.getenv('PINECONE_NAMESPACE', 'default')
    
    try:
        # Generate embedding for query
        query_embedding = embeddings.embed_query(query)
        
        # Search Pinecone with company-specific filter
        logger.debug(f"🔍 Searching Pinecone (namespace '{namespace}'): '{query}' for company {company_slug}")
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=limit,
            namespace=namespace,
            filter={
                "company_slug": {"$eq": company_slug}
            } if company_slug else None,
            include_metadata=True
        )
        
        # Extract context from results with full source tracking
        context_docs = []
        for idx, match in enumerate(results.matches, 1):
            doc = {
                "text": match.metadata.get("text", ""),
                "page_type": match.metadata.get("page_type", ""),
                "score": match.score,
                "source_file": match.metadata.get("source_file", ""),
                "chunk_index": match.metadata.get("chunk_index", ""),
                "vector_id": match.id,
            }
            context_docs.append(doc)
            logger.debug(f"  🎯 Rank {idx}: {doc['source_file']} (chunk {doc['chunk_index']}, similarity: {match.score:.3f})")
        
        logger.debug(f"✅ Pinecone search returned {len(context_docs)} documents")
        return context_docs
        
    except Exception as e:
        logger.warning(f"❌ Error searching Pinecone: {e}")
        return []


def log_extraction_sources(
    extraction_type: str,
    company_id: str,
    search_queries: List[str],
    context_docs: List[Dict[str, Any]]
) -> None:
    """Log detailed source information for validation."""
    logger = logging.getLogger('structured_extraction')
    
    if not context_docs:
        logger.warning(f"  ⚠️  No Pinecone sources found for {extraction_type}")
        return
    
    logger.info(f"\n  📊 {extraction_type.upper()} - Source Validation:")
    logger.info(f"  {'─' * 70}")
    
    # Group by source file
    sources_by_file = {}
    for doc in context_docs:
        source_file = doc.get('source_file', 'unknown')
        if source_file not in sources_by_file:
            sources_by_file[source_file] = []
        sources_by_file[source_file].append(doc)
    
    # Log each source
    for source_file in sorted(sources_by_file.keys()):
        docs = sources_by_file[source_file]
        logger.info(f"  Source: {source_file}")
        logger.info(f"    Chunks used: {len(docs)}")
        for doc in docs:
            logger.info(f"      • Vector ID {doc['vector_id']}: chunk {doc['chunk_index']} (similarity: {doc['score']:.3f})")
        logger.info(f"    Content preview: {docs[0]['text'][:100]}...")
    
    logger.info(f"  {'─' * 70}\n")


def should_use_fallback(context_docs: List[Dict[str, Any]], extraction_type: str) -> bool:
    """Determine if fallback should be used based on strategy and context availability."""
    logger = logging.getLogger('structured_extraction')
    
    global FALLBACK_STRATEGY
    
    if context_docs:
        # We have context, no fallback needed
        return False
    
    # No context available, check strategy
    if FALLBACK_STRATEGY == 'pinecone_only':
        logger.error(f"❌ Strategy 'pinecone_only': No Pinecone results for {extraction_type}, FAILING")
        return False
    elif FALLBACK_STRATEGY == 'raw_only':
        logger.warning(f"⚠️  Strategy 'raw_only': Ignoring Pinecone, using raw text for {extraction_type}")
        return True
    elif FALLBACK_STRATEGY == 'pinecone_first':
        logger.warning(f"⚠️  Strategy 'pinecone_first': Fallback to raw text for {extraction_type}")
        return True
    
    return False


def load_company_page_text(company_slug: str, page_type: str) -> Optional[str]:
    """Load extracted text from a company page."""
    logger = logging.getLogger('structured_extraction')
    
    text_file = f"data/raw/{company_slug}/{page_type}/text.txt"
    
    if not Path(text_file).exists():
        logger.debug(f"Text file not found: {text_file}")
        return None
    
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        logger.debug(f"Loaded text from {text_file}: {len(text)} chars")
        return text
    except Exception as e:
        logger.error(f"Failed to load text from {text_file}: {e}")
        return None


def load_all_company_pages(company_slug: str) -> Dict[str, str]:
    """Load all extracted text pages for a company."""
    logger = logging.getLogger('structured_extraction')
    
    company_raw_dir = Path(f"data/raw/{company_slug}")
    if not company_raw_dir.exists():
        logger.warning(f"Company directory not found: {company_raw_dir}")
        return {}
    
    pages_text = {}
    page_types = [d.name for d in company_raw_dir.iterdir() if d.is_dir()]
    
    for page_type in sorted(page_types):
        text = load_company_page_text(company_slug, page_type)
        if text:
            pages_text[page_type] = text
            logger.info(f"Loaded {page_type} page: {len(text)} chars")
    
    logger.info(f"Loaded {len(pages_text)} pages for {company_slug}")
    return pages_text


def create_extraction_prompt(company_name: str, pages_text: Dict[str, str]) -> str:
    """Create a comprehensive prompt for LLM-based extraction."""
    
    # Combine all page texts
    combined_text = ""
    for page_type, text in pages_text.items():
        combined_text += f"\n\n## {page_type.upper()} PAGE:\n{text[:2000]}\n"
    
    prompt = f"""You are an expert data analyst extracting structured information about the company "{company_name}" from web pages.

EXTRACTED WEB CONTENT:
{combined_text}

Extract and normalize the following information from the web content:

1. **Company Information**: Legal name, brand name, website, headquarters location, founding year, categories
2. **Financial Information**: Total funding raised, last valuation, last funding round details
3. **Events**: Any funding rounds, M&A activities, product launches, partnerships, major hires, layoffs mentioned
4. **Products**: Product names, descriptions, pricing models, integrations, GitHub repos
5. **Leadership**: Founders and executives mentioned - name, role, start dates, backgrounds
6. **Visibility**: News mentions, GitHub stars, ratings (if available)

Guidelines:
- Use ONLY information explicitly mentioned in the web content
- For missing fields, leave them as null/empty - DO NOT infer or guess
- Standardize date formats to YYYY-MM-DD
- Extract company_id from website domain (e.g., world-labs from worldlabs.ai)
- Extract all person IDs from names (e.g., john-doe from John Doe)
- Include source URLs in provenance fields
- Be conservative with data - if uncertain, leave blank

Return structured data matching the Pydantic schemas."""
    
    return prompt


def extract_company_info(
    client, 
    company_name: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> Optional[Company]:
    """Extract company information using LLM with instructor and Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"Extracting company info for {company_name}...")
    
    # Build search queries for company information
    search_queries = [
        f"company {company_name} legal name brand headquarters location founded",
        f"{company_name} website URL domain",
        f"{company_name} categories industry vertical",
        f"{company_name} funding raised valuation investment round",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for company info")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_name, pinecone_index, embeddings, limit=3)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info("📊 Using Pinecone context for company extraction")
            context_text = "\n\n".join([
                f"[{doc['page_type']}] {doc['text'][:300]}"
                for doc in context_docs[:10]  # Limit to top 10 results
            ])
        else:
            logger.error("❌ No Pinecone results for company info - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    # Log extraction sources for validation
    log_extraction_sources("Company Info", company_name, search_queries, context_docs)
    
    prompt = f"""Extract company information for "{company_name}" from the following web content and context:

{context_text}

Return a structured Company record with all available information.
- Use ONLY explicitly stated information
- Generate company_id from the website domain (e.g., "world-labs" from "worldlabs.ai")
- Use null for missing fields
- Do NOT infer or guess
- Standardize dates to YYYY-MM-DD format"""
    
    try:
        # Use instructor's patched client with response_model
        company = client.chat.completions.create(
            model="gpt-4o",
            response_model=Company,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for consistency
        )
        logger.info(f"✓ Successfully extracted company: {company.legal_name if hasattr(company, 'legal_name') else 'Unknown'}")
        return company
    except ValidationError as e:
        logger.error(f"Validation error extracting company: {e}")
        return None
    except Exception as e:
        logger.error(f"Error extracting company info: {e}", exc_info=True)
        return None


def extract_events(
    client, 
    company_id: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Event]:
    """Extract events (funding, M&A, partnerships, etc.) using LLM and Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"Extracting events for {company_id}...")
    
    # Build search queries for events
    search_queries = [
        f"funding rounds Series A B C seed investment capital raised",
        f"M&A acquisition merger merger company",
        f"product launch release announcement",
        f"partnership partnership collaboration integration",
        f"hiring jobs positions team expansion layoffs",
        f"milestones achievements awards recognition",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for events")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_id, pinecone_index, embeddings, limit=2)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info("📊 Using Pinecone context for events extraction")
            context_text = "\n\n".join([
                f"[{doc['page_type']}] {doc['text'][:250]}"
                for doc in context_docs[:15]  # Limit to top 15 results
            ])
        else:
            logger.error("❌ No Pinecone results for events - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    prompt = f"""Extract all significant events for company ID "{company_id}" from the web content:

{context_text}

Include:
- Funding rounds (Series A/B/C, seed, etc.) with amounts and dates
- M&A activities (acquisitions, mergers)
- Product launches and releases
- Partnerships and integrations
- Key hires and leadership changes
- Layoffs and restructuring
- Major milestones and achievements

For each event:
- Provide: event_type, occurred_on date (YYYY-MM-DD), title, description
- If it's a funding event, include amount_usd and valuation_usd
- Use only explicitly stated information
- Use null for missing fields

Return a list of Event objects."""
    
    try:
        # Define a wrapper model to handle list return
        class EventList(BaseModel):
            events: List[Event] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=EventList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"✓ Extracted {len(result.events)} events")
        return result.events
    except Exception as e:
        logger.warning(f"Error extracting events: {e}")
        return []


def extract_snapshots(
    client, 
    company_id: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Snapshot]:
    """Extract business snapshots (headcount, products, pricing, etc.) using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"Extracting snapshots for {company_id}...")
    
    # Search queries for snapshot data
    search_queries = [
        f"headcount employees team size headcount growth hiring",
        f"pricing tiers pricing model pricing plans subscription",
        f"products features product offerings services",
        f"geographic presence countries regions locations",
        f"job openings hiring positions vacancies",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for snapshots")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_id, pinecone_index, embeddings, limit=3)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info("📊 Using Pinecone context for snapshots extraction")
            context_text = "\n\n".join([
                f"[{doc['page_type']}] {doc['text'][:250]}"
                for doc in context_docs[:15]
            ])
        else:
            logger.error("❌ No Pinecone results for snapshots - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    prompt = f"""Extract business snapshot information for company ID "{company_id}" from web content:

{context_text}

Extract current/recent:
- Headcount total and growth percentage
- Job openings count by department (engineering, sales, etc.)
- Hiring focus areas
- Pricing tiers and pricing model
- Active products
- Geographic presence (countries/regions)

Return a list of Snapshot objects with as_of date set to today.
Use only explicitly stated information. Use null for missing fields."""
    
    try:
        class SnapshotList(BaseModel):
            snapshots: List[Snapshot] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=SnapshotList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"✓ Extracted {len(result.snapshots)} snapshots")
        return result.snapshots
    except Exception as e:
        logger.warning(f"Error extracting snapshots: {e}")
        return []


def extract_products(
    client, 
    company_id: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Product]:
    """Extract product information using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"Extracting products for {company_id}...")
    
    # Search queries for product data
    search_queries = [
        f"product name product description features",
        f"pricing model pricing tiers pricing plans cost",
        f"integrations partners integrations APIs",
        f"GitHub repository source code open source",
        f"customers clients reference accounts",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for products")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_id, pinecone_index, embeddings, limit=3)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info("📊 Using Pinecone context for products extraction")
            context_text = "\n\n".join([
                f"[{doc['page_type']}] {doc['text'][:250]}"
                for doc in context_docs[:12]
            ])
        else:
            logger.error("❌ No Pinecone results for products - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    prompt = f"""Extract product information for company ID "{company_id}" from web content:

{context_text}

🚨 STRICT PRODUCT FILTERING - ZERO HALLUCINATION 🚨

A PRODUCT is something customers can USE, BUY, or DEPLOY.

✅ INCLUDE (Real Products):
- Software products: apps, APIs, platforms, tools, models, SDKs
- Hardware products: robots, devices, equipment
- SaaS offerings, enterprise software
- Developer tools, libraries, frameworks

❌ EXCLUDE (NOT Products - Website Sections/Pages):
- Website pages: "Blog", "Videos", "Press Kit", "Company", "Newsroom", "Press", "Careers"
- Content sections: "Resources", "Insights", "Documentation", "Support", "News"
- Legal documents: "Terms", "Privacy Policy", "Updates to Terms and Privacy"
- Initiatives/Programs: "Advisory Council", "Economic Program", "Futures Program"
- Partnerships/MOUs: "Partnership with X", "MOU with Government", "Signs Agreement"
- Announcements: "Expanding X", "Announces Y", "Updates to Z"
- Generic pages: "About", "Contact", "Team", "Investors", "Customers", "Partners"

For each product extract:
- product_id: Generate from name (e.g., "claude-api" from "Claude API")
- company_id: "{company_id}"
- name: Product name - REQUIRED
- description: What it does (or null)
- pricing_model: "seat"/"usage"/"tiered" (or null)
- pricing_tiers_public: Tier names (or empty list)
- ga_date: Launch date (YYYY-MM-DD format) (or null)
- integration_partners: Partners (or empty list)
- github_repo: GitHub URL (or null)
- license_type: License (MIT, Apache, GPL, BSD, proprietary) (or null)
- reference_customers: Customers (or empty list)

VALIDATION: Ask yourself - Is this a REAL product customers use?
If it's a webpage, section, or initiative → SKIP IT

Return a list of Product objects. Use ONLY explicitly stated information.
DO NOT infer or hallucinate product names."""
    
    try:
        class ProductList(BaseModel):
            products: List[Product] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=ProductList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"✓ Extracted {len(result.products)} products")
        return result.products
    except Exception as e:
        logger.warning(f"Error extracting products: {e}")
        return []


def extract_leadership(
    client, 
    company_id: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> List[Leadership]:
    """Extract leadership and team information using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"Extracting leadership for {company_id}...")
    
    # Search queries for leadership data
    search_queries = [
        f"founder co-founder CEO CTO CPO founder",
        f"executive team leadership management",
        f"CEO founder name role",
        f"LinkedIn profile background education",
        f"previous company employment history",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for leadership")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_id, pinecone_index, embeddings, limit=3)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info("📊 Using Pinecone context for leadership extraction")
            context_text = "\n\n".join([
                f"[{doc['page_type']}] {doc['text'][:250]}"
                for doc in context_docs[:15]
            ])
        else:
            logger.error("❌ No Pinecone results for leadership - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    prompt = f"""Extract leadership and key team members for company ID "{company_id}" from web content:

{context_text}

For each person, extract:
- Full name
- Current role (CEO, CTO, CPO, Founder, Executive, etc.)
- Whether they are a founder
- Start date at company
- Education background and university
- LinkedIn profile URL
- Previous companies/roles and employment history

Generate person_id from full name (e.g., john-doe from John Doe).
Return a list of Leadership objects. Use only explicitly stated information."""
    
    try:
        class LeadershipList(BaseModel):
            leadership: List[Leadership] = Field(default_factory=list)
        
        result = client.chat.completions.create(
            model="gpt-4o",
            response_model=LeadershipList,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"✓ Extracted {len(result.leadership)} leadership members")
        return result.leadership
    except Exception as e:
        logger.warning(f"Error extracting leadership: {e}")
        return []


def extract_visibility(
    client, 
    company_id: str, 
    pages_text: Dict[str, str],
    pinecone_index = None,
    embeddings: Optional[OpenAIEmbeddings] = None,
    namespace: Optional[str] = None
) -> Optional[Visibility]:
    """Extract visibility and public metrics using Pinecone search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"Extracting visibility for {company_id}...")
    
    # Search queries for visibility data
    search_queries = [
        f"news mentions press coverage media articles",
        f"GitHub stars repository rating metrics",
        f"Glassdoor rating employee reviews",
        f"awards recognition industry recognition",
        f"social media followers engagement",
    ]
    
    # Determine search strategy
    context_docs = []
    context_text = ""
    
    global USE_RAW_TEXT
    
    if USE_RAW_TEXT:
        logger.info(f"⚙️  Using raw text mode for visibility")
        context_text = json.dumps(pages_text, indent=2)[:3000]
    else:
        # Try Pinecone search
        for query in search_queries:
            docs = search_pinecone_for_context(query, company_id, pinecone_index, embeddings, limit=3)
            context_docs.extend(docs)
        
        if context_docs:
            logger.info("📊 Using Pinecone context for visibility extraction")
            context_text = "\n\n".join([
                f"[{doc['page_type']}] {doc['text'][:250]}"
                for doc in context_docs[:10]
            ])
        else:
            logger.error("❌ No Pinecone results for visibility - ABORTING")
            raise ValueError("No Pinecone context available and raw text mode is disabled")
    
    prompt = f"""Extract visibility and public metrics for company ID "{company_id}" from web content:

{context_text}

Extract:
- News mentions or press coverage indicators (count and sentiment)
- Sentiment indicators (positive/negative/neutral)
- GitHub repository stars or popularity metrics
- Glassdoor rating if available
- Awards or industry recognition
- Social media followers if mentioned

Return a Visibility object with as_of set to today. Use only explicitly stated metrics."""
    
    try:
        visibility = client.chat.completions.create(
            model="gpt-4o",
            response_model=Visibility,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        
        logger.info(f"✓ Extracted visibility metrics")
        return visibility
    except Exception as e:
        logger.warning(f"Error extracting visibility: {e}")
        return None


def process_company(company_slug: str, company_name: str, verbose: bool = False):
    """Process a single company: extract structured data using Pinecone vector search."""
    logger = logging.getLogger('structured_extraction')
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Company: {company_name} ({company_slug})")
    logger.info(f"{'='*60}")
    
    pinecone_index = None
    embeddings = None
    namespace = None
    
    try:
        # Load all page texts
        pages_text = load_all_company_pages(company_slug)
        if not pages_text:
            logger.warning(f"No page texts found for {company_slug}")
            return None
        
        # Initialize LLM client
        client = get_llm_client()
        
        # Initialize Pinecone and embeddings
        logger.info("Initializing Pinecone vector database...")
        pinecone_index = get_pinecone_client()
        embeddings = get_embeddings_model()
        
        # Index company pages to Pinecone
        if pinecone_index and embeddings:
            namespace = index_company_pages_to_pinecone(
                company_slug, 
                pages_text,
                pinecone_index,
                embeddings
            )
            if namespace:
                logger.info(f"✓ Indexed to Pinecone namespace: {namespace}")
        
        # Extract structured data
        logger.info("Starting structured extraction with semantic search...")
        
        # 1. Extract company info
        company = extract_company_info(
            client, 
            company_name, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        if not company:
            logger.error(f"Failed to extract company info for {company_name}")
            return None
        
        company_id = company.company_id
        logger.info(f"Company ID: {company_id}")
        
        # 2. Extract events
        events = extract_events(
            client, 
            company_id, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 3. Extract snapshots
        snapshots = extract_snapshots(
            client, 
            company_id, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 4. Extract products
        products = extract_products(
            client, 
            company_id, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 5. Extract leadership
        leadership = extract_leadership(
            client, 
            company_id, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        
        # 6. Extract visibility
        visibility_list = []
        visibility = extract_visibility(
            client, 
            company_id, 
            pages_text,
            pinecone_index,
            embeddings,
            namespace
        )
        if visibility:
            visibility_list = [visibility]
        
        # Create payload
        payload = Payload(
            company_record=company,
            events=events,
            snapshots=snapshots,
            products=products,
            leadership=leadership,
            visibility=visibility_list,
            notes=f"Extracted with semantic search via Pinecone on {datetime.now().isoformat()}"
        )
        
        # Save results to data/structured/
        structured_dir = Path("data/structured")
        structured_dir.mkdir(parents=True, exist_ok=True)
        
        structured_file = structured_dir / f"{company_id}.json"
        with open(structured_file, 'w', encoding='utf-8') as f:
            json.dump(payload.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"\n✓ Saved structured data to: {structured_file}")
        
        # Also save to data/payloads/ for payload access
        payloads_dir = Path("data/payloads")
        payloads_dir.mkdir(parents=True, exist_ok=True)
        
        payload_file = payloads_dir / f"{company_id}.json"
        with open(payload_file, 'w', encoding='utf-8') as f:
            json.dump(payload.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"✓ Saved payload data to: {payload_file}")
        
        logger.info(f"  Company: {company.legal_name}")
        logger.info(f"  Events: {len(events)}")
        logger.info(f"  Snapshots: {len(snapshots)}")
        logger.info(f"  Products: {len(products)}")
        logger.info(f"  Leadership: {len(leadership)}")
        logger.info(f"  Visibility: {len(visibility_list)}")
        
        return payload
        
    except Exception as e:
        logger.error(f"Error processing company {company_name}: {e}", exc_info=True)
        return None


def discover_companies_from_raw_data() -> List[tuple]:
    """Discover companies from raw data directory structure."""
    logger = logging.getLogger('structured_extraction')
    
    raw_dir = Path("data/raw")
    companies = []
    
    if not raw_dir.exists():
        logger.warning(f"Raw data directory not found: {raw_dir}")
        return companies
    
    for company_dir in raw_dir.iterdir():
        if company_dir.is_dir():
            company_slug = company_dir.name
            # Convert slug back to title case as company name
            company_name = company_slug.replace('_', ' ').title()
            companies.append((company_slug, company_name))
    
    logger.info(f"Discovered {len(companies)} companies from raw data")
    return companies


def main():
    logger = setup_logging()
    logger.info("=== Starting Structured Extraction (RAG with Pinecone) ===")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Extract structured data from web scrapes")
    parser.add_argument(
        '--company-slug',
        type=str,
        default=None,
        help='Extract a specific company by slug (e.g., abridge, world_labs). If not provided, all companies in data/raw/ will be processed.'
    )
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument(
        '--fallback-strategy',
        type=str,
        choices=['pinecone_only', 'raw_only', 'pinecone_first'],
        default='pinecone_first',
        help='Strategy for handling Pinecone failures: pinecone_only (fail if no Pinecone), raw_only (always use raw text), pinecone_first (prefer Pinecone, fallback to raw)'
    )
    
    args = parser.parse_args()
    
    # Store fallback strategy globally for use in extraction functions
    global FALLBACK_STRATEGY
    FALLBACK_STRATEGY = args.fallback_strategy
    logger.info(f"Fallback strategy: {args.fallback_strategy}")
    
    try:
        # If specific company provided, process only that one
        if args.company_slug:
            companies = [(args.company_slug, args.company_slug.replace('_', ' ').title())]
            logger.info(f"Processing specific company: {args.company_slug}")
        else:
            # Discover all companies to process
            companies = discover_companies_from_raw_data()
        
        if not companies:
            logger.warning("No companies found in data/raw directory")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {len(companies)} companies")
        logger.info(f"{'='*60}\n")
        
        results = []
        for idx, (company_slug, company_name) in enumerate(companies, 1):
            logger.info(f"[{idx}/{len(companies)}] {company_name}")
            result = process_company(company_slug, company_name, args.verbose)
            if result:
                results.append({
                    'company_slug': company_slug,
                    'company_name': company_name,
                    'success': True,
                    'company_id': result.company_record.company_id
                })
            else:
                results.append({
                    'company_slug': company_slug,
                    'company_name': company_name,
                    'success': False
                })
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("=== EXTRACTION COMPLETE ===")
        logger.info(f"{'='*60}")
        
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Successfully processed: {successful}/{len(results)}")
        
        if successful > 0:
            logger.info("\nSuccessful companies:")
            for r in results:
                if r['success']:
                    logger.info(f"  ✓ {r['company_name']} → {r['company_id']}")
        
        failed = [r for r in results if not r['success']]
        if failed:
            logger.info("\nFailed companies:")
            for r in failed:
                logger.info(f"  ✗ {r['company_name']}")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
