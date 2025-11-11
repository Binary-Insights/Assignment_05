# Structured Extraction Quick Start

Get structured company data extracted in 5 minutes.

## Prerequisites

✅ Web scraping completed: `data/raw/{company_slug}/*.txt` files exist
✅ OpenAI API key configured: `OPENAI_API_KEY=sk-...` in `.env`
✅ All dependencies installed: `pip install -r requirements.txt`

## Quick Start

### Step 1: Verify Your Data

Check that text files were extracted from web scrapes:

```bash
ls -la data/raw/world_labs/*/text.txt
```

Expected output:
```
data/raw/world_labs/about/text.txt
data/raw/world_labs/blog/text.txt
data/raw/world_labs/linkedin/text.txt
...
```

### Step 2: Verify API Key

```bash
echo $OPENAI_API_KEY
```

Should output: `sk-...` (your OpenAI key)

### Step 3: Run Tests First (Optional)

Validate that all models work correctly:

```bash
python src/rag/test_structured_extraction.py
```

Expected output:
```
✓ Company: valid
✓ Events: 2 items
✓ Snapshots: 1 items
✓ Products: 1 items
✓ Leadership: 2 items
✓ Visibility: valid
✓ All tests passed!
```

### Step 4: Extract Structured Data

**Option A: Extract specific company**
```bash
python src/rag/structured_extraction.py --company-slug world_labs
```

**Option B: Extract all companies**
```bash
python src/rag/structured_extraction.py
```

### Step 5: Check Results

```bash
ls -la data/structured/
cat data/structured/world-labs.json | jq '.'
```

View the logs:
```bash
tail -f data/logs/structured_extraction.log
```

## Example Output

File: `data/structured/world-labs.json`

```json
{
  "company_record": {
    "company_id": "world-labs",
    "legal_name": "World Labs",
    "website": "https://worldlabs.ai",
    "hq_city": "San Francisco",
    "founded_year": 2023,
    "categories": ["AI", "Computer Vision"],
    "total_raised_usd": 5000000
  },
  "events": [
    {
      "event_id": "worldlabs-funding-1",
      "event_type": "funding",
      "title": "Seed Funding",
      "amount_usd": 500000,
      "occurred_on": "2023-09-15"
    },
    {
      "event_id": "worldlabs-funding-2",
      "event_type": "funding",
      "title": "Series A",
      "amount_usd": 5000000,
      "occurred_on": "2024-06-15"
    }
  ],
  "products": [
    {
      "product_id": "worldlabs-openworld",
      "name": "OpenWorld",
      "description": "AI-powered 3D world generation",
      "pricing_model": "seat"
    }
  ],
  "leadership": [
    {
      "person_id": "alex-johnson",
      "name": "Alex Johnson",
      "role": "CEO",
      "is_founder": true
    }
  ]
}
```

## Troubleshooting

### "Company directory not found"

```
ERROR - Company directory not found: data/raw/world_labs
```

**Fix**: Run web scraping first
```bash
python src/discover/process_discovered_pages.py
```

### "OPENAI_API_KEY not set"

```
ERROR - OPENAI_API_KEY not set in environment
```

**Fix**: Add to `.env` or export:
```bash
export OPENAI_API_KEY="sk-..."
```

### "No page texts found"

```
WARNING - No page texts found for world_labs
```

**Fix**: Check that text extraction completed:
```bash
find data/raw/world_labs -name "text.txt" -type f
```

If empty, run:
```bash
python src/discover/process_discovered_pages.py
```

### Slow or timing out

The script calls OpenAI's API multiple times. This may take 1-2 minutes.

Monitor progress in logs:
```bash
tail -f data/logs/structured_extraction.log
```

### Invalid or missing fields

Check the raw text data:
```bash
cat data/raw/world_labs/about/text.txt | head -100
```

The LLM can only extract what's explicitly mentioned. For missing fields, they're set to `null`.

## Common Commands

### Extract one company
```bash
python src/rag/structured_extraction.py --company-slug world_labs
```

### Extract all companies with verbose logging
```bash
python src/rag/structured_extraction.py --verbose
```

### Run validation tests
```bash
python src/rag/test_structured_extraction.py
```

### View latest results
```bash
ls -ltr data/structured/ | tail -5
```

### Pretty-print JSON output
```bash
cat data/structured/world-labs.json | python -m json.tool
```

### Check extraction logs
```bash
tail -100 data/logs/structured_extraction.log
```

## What Gets Extracted

For each company, the script extracts:

| Category | Examples |
|----------|----------|
| **Company** | Legal name, website, HQ location, founding year, funding amounts |
| **Events** | Funding rounds, M&A, product launches, partnerships, hires |
| **Products** | Product names, descriptions, pricing, integrations |
| **Leadership** | Founders, executives, roles, backgrounds |
| **Snapshots** | Headcount, job openings, geographic presence |
| **Visibility** | News mentions, GitHub stars, ratings |

## Performance

Typical extraction for one company:

- **Time**: 30-60 seconds
- **API calls**: 6 (one per category)
- **Tokens used**: 3,000-5,000
- **Cost**: ~$0.10-0.20 per company

## Next Steps

1. ✅ Extract your first company
2. Review the JSON output structure
3. Validate extracted data quality
4. Process all companies in batch
5. [Optional] Build downstream applications using the structured data

## Getting Help

### Full Documentation
```bash
cat docs/STRUCTURED_EXTRACTION.md
```

### View Script
```bash
cat src/rag/structured_extraction.py
```

### View Models
```bash
cat src/rag/rag_models.py
```

### Check Logs
```bash
tail -f data/logs/structured_extraction.log
```

## Notes

- **Conservative extraction**: Only explicitly mentioned data is included
- **No inference**: Missing fields are `null`, not guessed
- **Provenance**: Source URLs tracked for all extracted data
- **Repeatable**: Running twice extracts the same data (no caching)
- **Cost**: Each run costs ~$0.10-0.20 per company with GPT-4

---

Ready? Start with: `python src/rag/structured_extraction.py --company-slug world_labs`
