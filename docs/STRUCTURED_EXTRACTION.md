# Structured Extraction RAG Pipeline

Extract and normalize company data from web scrapes into structured Pydantic models using LLM-powered RAG.

## Overview

`structured_extraction.py` is an advanced RAG (Retrieval-Augmented Generation) script that:

1. **Reads** extracted text from scraped company web pages
2. **Normalizes** messy text data using LLM intelligence
3. **Extracts** structured information into Pydantic models
4. **Saves** results as JSON following the schema in `rag_models.py`

## Features

### Structured Output Models

The script extracts data into the following Pydantic models:

- **Company**: Legal name, brand, website, headquarters, founding year, funding history, categories
- **Event**: Funding rounds, M&A, product launches, partnerships, hires, layoffs, milestones
- **Snapshot**: Headcount, job openings, products, pricing, geographic presence
- **Product**: Name, description, pricing model, integrations, GitHub repos, customers
- **Leadership**: Founders and executives with roles, backgrounds, LinkedIn profiles
- **Visibility**: News mentions, sentiment, GitHub stars, ratings

### Data Quality

- **Conservative extraction**: Only includes information explicitly mentioned in web content
- **No inference**: Missing fields are left as null, not guessed
- **Standardized formats**: Dates as YYYY-MM-DD, URLs normalized, IDs generated consistently
- **Full provenance**: Tracks source URLs for all extracted data

## Usage

### Basic Usage

Process all companies:
```bash
python src/rag/structured_extraction.py
```

### Process Specific Company

```bash
python src/rag/structured_extraction.py --company-slug world_labs
```

### Verbose Mode

Enable detailed logging:
```bash
python src/rag/structured_extraction.py --verbose
```

## Architecture

### Input

Reads extracted text files from the RAG pipeline:
```
data/raw/{company_slug}/
├── about/text.txt
├── product/text.txt
├── careers/text.txt
├── blog/text.txt
├── linkedin/text.txt
└── ...
```

### Processing

1. **Load** all page texts for a company
2. **Initialize** OpenAI client with instructor patching for structured outputs
3. **Extract** each data model type with dedicated prompts:
   - Company info extraction
   - Event/funding detection
   - Business snapshot metrics
   - Product information
   - Leadership team details
   - Visibility and metrics
4. **Combine** results into unified Payload
5. **Save** as JSON

### Output

Saves to `data/structured/{company_id}.json`:
```json
{
  "company_record": {
    "company_id": "world-labs",
    "legal_name": "World Labs",
    "website": "https://worldlabs.ai",
    ...
  },
  "events": [...],
  "snapshots": [...],
  "products": [...],
  "leadership": [...],
  "visibility": [...],
  "notes": "Extracted from web scrapes on 2025-11-05T..."
}
```

## LLM Configuration

### Model

Uses **GPT-4 Turbo Preview** for reliable structured extraction:
- Temperature: 0.3 (low for consistency)
- Response model: Pydantic schema validation
- Streaming: Disabled for deterministic results

### Instructor Integration

The script uses [instructor](https://github.com/jxnl/instructor) to:
- Patch OpenAI client for structured JSON output
- Validate responses against Pydantic models
- Retry on validation failures
- Handle complex nested models

## Key Functions

### Core Extraction Functions

```python
extract_company_info(client, company_name, pages_text)
    → Company

extract_events(client, company_id, pages_text)
    → List[Event]

extract_snapshots(client, company_id, pages_text)
    → List[Snapshot]

extract_products(client, company_id, pages_text)
    → List[Product]

extract_leadership(client, company_id, pages_text)
    → List[Leadership]

extract_visibility(client, company_id, pages_text)
    → Optional[Visibility]
```

### Utility Functions

```python
load_all_company_pages(company_slug: str)
    → Dict[str, str]
    # Loads all page texts for a company

discover_companies_from_raw_data()
    → List[tuple]
    # Auto-discovers companies from data/raw structure

process_company(company_slug: str, company_name: str)
    → Payload
    # End-to-end processing for one company
```

## Logging

Logs written to `data/logs/structured_extraction.log`:
- Started at: timestamp
- Company processing: step-by-step extraction
- Extraction results: counts and file paths
- Errors and warnings with context

Example log output:
```
2025-11-05 12:00:00 - structured_extraction - INFO - === Processing Company: World Labs ===
2025-11-05 12:00:00 - structured_extraction - INFO - Loaded 5 pages for world_labs
2025-11-05 12:00:02 - structured_extraction - INFO - ✓ Successfully extracted company: World Labs
2025-11-05 12:00:03 - structured_extraction - INFO - ✓ Extracted 3 events
2025-11-05 12:00:04 - structured_extraction - INFO - ✓ Extracted 1 snapshots
2025-11-05 12:00:05 - structured_extraction - INFO - ✓ Extracted 2 products
2025-11-05 12:00:06 - structured_extraction - INFO - ✓ Extracted 4 leadership members
2025-11-05 12:00:07 - structured_extraction - INFO - ✓ Saved structured data to: data/structured/world-labs.json
```

## Error Handling

- **Missing pages**: Logs warning, skips that company
- **LLM validation failure**: Logs error, returns empty list or null
- **File I/O errors**: Logs error, continues with next company
- **Missing OPENAI_API_KEY**: Raises error immediately

## Dependencies

All dependencies are in `requirements.txt`:
- `openai>=1.0.0` - OpenAI API client v1.0+ with structured outputs
- `instructor>=1.0.0` - Pydantic-based response validation
- `pydantic>=2.0` - Data validation and serialization
- `python-dotenv` - Environment variable loading
- `langchain` - LLM framework (optional, for future enhancements)

## Configuration

### Environment Variables

```bash
# .env
OPENAI_API_KEY=sk-...
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_NAME=rag_chunks
```

### Customization

Modify extraction prompts in functions:
- `create_extraction_prompt()` - Overall extraction guidance
- Individual `extract_*()` functions - Specific extraction logic

## Data Model Examples

### Company Record

```json
{
  "company_id": "world-labs",
  "legal_name": "World Labs",
  "brand_name": null,
  "website": "https://worldlabs.ai",
  "hq_city": "San Francisco",
  "hq_state": "CA",
  "hq_country": "USA",
  "founded_year": 2023,
  "categories": ["AI", "Computer Vision"],
  "total_raised_usd": 5000000,
  "last_round_name": "Series A",
  "last_round_date": "2024-06-15"
}
```

### Event Record

```json
{
  "event_id": "worldlabs-seed-2023",
  "company_id": "world-labs",
  "occurred_on": "2023-09-15",
  "event_type": "funding",
  "title": "Seed Round Funding",
  "amount_usd": 5000000,
  "investors": ["OpenAI Ventures", "Khosla Ventures"],
  "tags": ["Seed"]
}
```

### Product Record

```json
{
  "product_id": "worldlabs-openworld",
  "company_id": "world-labs",
  "name": "OpenWorld",
  "description": "3D world generation platform",
  "pricing_model": "seat",
  "ga_date": "2024-03-01",
  "integration_partners": ["Unity", "Unreal Engine"]
}
```

## Performance Considerations

- **LLM calls**: ~1 call per extraction type per company
- **Token usage**: ~2000-5000 tokens per company (content + extraction)
- **Processing time**: ~30-60 seconds per company
- **Cost**: ~$0.10-0.20 per company with GPT-4 Turbo

## Future Enhancements

- [ ] Add Qdrant similarity search for context-aware extraction
- [ ] Implement multi-turn extraction for complex companies
- [ ] Add confidence scores and extraction uncertainty
- [ ] Support for multiple LLM providers (Claude, Gemini, etc.)
- [ ] Incremental extraction (update fields without re-processing)
- [ ] Parallel processing for multiple companies
- [ ] Extraction result caching and deduplication

## Troubleshooting

### "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY="sk-..."
```

### "Company directory not found"
Ensure web scraping has completed and data exists:
```bash
python src/discover/process_discovered_pages.py
```

### "Validation error extracting company"
Check logs for validation details. Often due to:
- Unusual date formats (should be YYYY-MM-DD)
- Missing required fields
- Invalid enum values for event_type

### Low extraction quality
Try these steps:
1. Increase prompt verbosity
2. Lower LLM temperature (more conservative)
3. Provide more context pages
4. Manually review and enhance prompts

## Related Scripts

- `process_discovered_pages.py` - Web scraping and text extraction
- `experimental_framework.py` - Chunk creation and keyword extraction
- `ingest_to_qdrant.py` - Vector database population
- `rag_search_api.py` - Semantic search endpoint

## License

Part of Assignment_04 - Big Data & Intelligence Analytics

