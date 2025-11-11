# Validation Guide: Tracing Data from Raw Files → Qdrant → Extracted Output

## How to Verify Data Actually Comes from Qdrant & Raw Sources

This guide explains how to validate the extraction pipeline and ensure all extracted values are traceable to their original sources.

---

## **Method 1: Enhanced Logging (Automatic)**

### What Changed
Updated extraction functions now log the full provenance chain:

```bash
python src/rag/structured_extraction.py --company-slug world_labs
```

**Output Example:**
```
2025-11-05 12:15:30 - structured_extraction - INFO - 
Indexing source files for world_labs:
────────────────────────────────────────────────────────────
  📄 Source: data/raw/world_labs/about/text.txt
     Content size: 5147 characters
     Chunks created: 11 (500 chars, 100 char overlap)
     ✓ Processed about

  📄 Source: data/raw/world_labs/linkedin/text.txt
     Content size: 17875 characters
     Chunks created: 36 (500 chars, 100 char overlap)
     ✓ Processed linkedin

────────────────────────────────────────────────────────────
✓ Indexed 52 total chunks to Qdrant

Breakdown by source:
  • about              →  11 chunks
  • blog               →   2 chunks
  • careers            →   3 chunks
  • linkedin           →  36 chunks
────────────────────────────────────────────────────────────
```

### Source Validation During Extraction

Each extraction logs which Qdrant documents were used:

```
  📊 COMPANY INFO - Source Validation:
  ──────────────────────────────────────────────────────────────────────
  Source: data/raw/world_labs/linkedin/text.txt
    Chunks used: 3
      • Point ID 15: chunk 2 (similarity: 0.823)
      • Point ID 22: chunk 5 (similarity: 0.781)
      • Point ID 8: chunk 1 (similarity: 0.756)
    Content preview: World Labs | LinkedIn World Labs Research Services...
  ──────────────────────────────────────────────────────────────────────
```

---

## **Method 2: Validation Script (Comprehensive)**

Run the dedicated validation script to audit all sources:

```bash
python src/rag/validate_extraction_sources.py
```

### What It Validates

#### ✓ **Qdrant Sources**
- Verifies Qdrant collection contains all raw files
- Checks each point's `source_file` path exists
- Validates content in Qdrant matches raw files
- Tracks chunk IDs and indices

**Example Output:**
```
======================================================================
QDRANT VALIDATION: world-labs
======================================================================
✓ Collection exists: company_world_labs
  Total points: 52

📊 Sources in Qdrant:
──────────────────────────────────────────────────────────────────────
✓ data/raw/world_labs/about/text.txt
    Chunks: 11
    Content matches: 3/3
✓ data/raw/world_labs/linkedin/text.txt
    Chunks: 36
    Content matches: 3/3
✓ All Qdrant sources verified against raw files
```

#### ✓ **Extraction Provenance**
- Checks each extracted field has provenance data
- Traces back to source URLs
- Validates provenance snippets match raw content

**Example Output:**
```
📋 Provenance Analysis for world-labs:
──────────────────────────────────────────────────────────────────────

✓ Company Record (provenance: 2 sources)
    Source: https://linkedin.com/
    Date: 2023-10-10
    Snippet: World Labs | LinkedIn...

✓ Events (2 total)
  Event: Series Unknown Funding Round
    Sources: 1
      - https://www.crunchbase.com/

✓ Leadership (4 total)
  Person: Fei-Fei Li (Co-founder)
    Sources: 1
      - https://linkedin.com/
```

#### ✓ **Raw vs Qdrant Comparison**
- Shows which raw files are indexed
- Verifies chunk-to-raw-file traceability
- Confirms similarity scoring

**Example Output:**
```
📄 Raw file: data/raw/world_labs/about/text.txt
   Size: 5147 chars
   Preview: World Labs is a spatial intelligence company...

📊 Qdrant Collection: company_world_labs
   Total chunks: 52

Verification: Chunks traceable to raw files?
──────────────────────────────────────────────────────────────────────
✓ Point 1: Found in about.txt
✓ Point 2: Found in linkedin.txt
✓ Point 3: Found in linkedin.txt
Verified: 10/10 chunks
```

---

## **Method 3: Manual Inspection**

### 1. **Check Extracted JSON Provenance**

```bash
jq '.company_record.provenance' data/structured/world-labs.json
```

**Output:**
```json
[
  {
    "source_url": "https://linkedin.com/",
    "crawled_at": "2023-10-10",
    "snippet": "World Labs | LinkedIn..."
  }
]
```

### 2. **Verify Snippet Content in Raw Files**

```bash
grep -r "World Labs | LinkedIn" data/raw/world_labs/
```

**Output:**
```
data/raw/world_labs/linkedin/text.txt: World Labs | LinkedIn
```

✓ Content exists in raw file!

### 3. **Check Qdrant Collection Directly**

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
collection = client.get_collection("company_world_labs")

print(f"Total points: {collection.points_count}")

# Get a point
point = client.retrieve(collection_name="company_world_labs", ids=[1])
print(point[0].payload)
```

**Output:**
```python
{
    'text': 'World Labs is a spatial intelligence company...',
    'page_type': 'about',
    'company_slug': 'world_labs',
    'source_file': 'data/raw/world_labs/about/text.txt',
    'chunk_index': 1
}
```

✓ Shows exact source file and chunk!

---

## **Data Flow Traceability**

```
┌─────────────────────────────────────────────────────────────┐
│ RAW SOURCE FILES                                            │
│ ├─ data/raw/world_labs/about/text.txt         (5147 chars)  │
│ ├─ data/raw/world_labs/linkedin/text.txt      (17875 chars) │
│ ├─ data/raw/world_labs/careers/text.txt       (1458 chars)  │
│ └─ data/raw/world_labs/blog/text.txt          (687 chars)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─ Split into 500-char chunks
                       ├─ Generate embeddings (text-embedding-3-small)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ QDRANT VECTOR DATABASE                                      │
│ Collection: company_world_labs                              │
│ ├─ Point 1: chunk 1 of about [vector: 1536-dim]             │
│ ├─ Point 2: chunk 2 of about [vector: 1536-dim]             │
│ ├─ Point 15: chunk 1 of linkedin [vector: 1536-dim]         │
│ │   payload: {                                              │
│ │     source_file: "data/raw/world_labs/linkedin/text.txt"  │
│ │     chunk_index: 1                                        │
│ │     text: "World Labs | LinkedIn..."                      │
│ │   }                                                       │
│ └─ ...52 total points                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─ Semantic search with targeted queries
                       ├─ Retrieve top-K relevant chunks
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ LLM EXTRACTION (gpt-4o)                                     │
│ Input: Targeted context from Qdrant                         │
│ Output: Structured Pydantic models with provenance          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─ Validate against schema
                       ├─ Add provenance metadata
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ STRUCTURED OUTPUT                                           │
│ data/structured/world-labs.json                             │
│ {                                                           │
│   "company_record": {                                       │
│     "legal_name": "World Labs Technologies",                │
│     "provenance": [                                         │
│       {                                                     │
│         "source_url": "https://linkedin.com/",              │
│         "crawled_at": "2023-10-10",                         │
│         "snippet": "Traced from Qdrant point 15"            │
│       }                                                     │
│     ]                                                       │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## **Quick Validation Checklist**

- [ ] Raw files exist: `ls -la data/raw/{company_slug}/*/text.txt`
- [ ] Qdrant running: `curl http://localhost:6333/health`
- [ ] Collection created: Check Qdrant logs
- [ ] Chunks indexed: Validate count matches expectations
- [ ] Extraction runs: Check for no errors
- [ ] JSON has provenance: `jq .company_record.provenance data/structured/*.json`
- [ ] Validation passes: `python src/rag/validate_extraction_sources.py`

---

## **Key Fields for Tracing**

| Field | Purpose | Example |
|-------|---------|---------|
| `point.payload.source_file` | Raw file path | `data/raw/world_labs/linkedin/text.txt` |
| `point.payload.chunk_index` | Position in file | `15` (15th chunk) |
| `point.payload.page_type` | Page category | `linkedin`, `about`, `careers` |
| `point.id` | Unique ID in Qdrant | `42` |
| `provenance.source_url` | URL cited | `https://linkedin.com/` |
| `provenance.crawled_at` | Extraction date | `2023-10-10` |
| `provenance.snippet` | Content preview | `"World Labs is a..."` |

---

## **Troubleshooting**

**Q: Chunks not found in raw files?**
- A: Check if raw files were modified after indexing. Re-run indexing.

**Q: Qdrant collection empty?**
- A: Verify Qdrant is running: `docker ps | grep qdrant`
- Check for indexing errors in logs

**Q: Provenance missing?**
- A: Ensure LLM response includes sources. Check LLM prompts.

**Q: Similarity scores too low?**
- A: Queries may not match content. Adjust search query terms.

