# Validation Script - Quick Command Reference

## TL;DR - Just Run It

```bash
# 1. Make sure Qdrant is running
docker-compose -f docker/docker-compose.yml up -d

# 2. Extract structured data (if not already done)
python src/rag/structured_extraction.py --company-slug world_labs

# 3. Run validation
python src/rag/validate_extraction_sources.py
```

---

## One-Liners

### Everything: Start Qdrant, Extract, Validate
```bash
docker-compose -f docker/docker-compose.yml up -d && sleep 5 && python src/rag/structured_extraction.py --company-slug world_labs && python src/rag/validate_extraction_sources.py
```

### Just Validation (assumes Qdrant running and data extracted)
```bash
python src/rag/validate_extraction_sources.py
```

### Check if Qdrant is Ready
```bash
curl -s http://localhost:6333/health | jq .
```

### List All Collections
```bash
curl -s http://localhost:6333/collections | jq '.collections[] | .name'
```

### List All Structured Files (to validate)
```bash
ls -lh data/structured/
```

---

## Prerequisites Checklist

- [ ] Qdrant running: `docker ps | grep qdrant`
- [ ] Raw data exists: `ls data/raw/`
- [ ] Structured data exists: `ls data/structured/`
- [ ] Environment vars set: `echo $OPENAI_API_KEY`

---

## What It Validates

| Check | Status | Details |
|-------|--------|---------|
| Qdrant collections exist | ✅ | For each company in structured/ |
| All raw files indexed | ✅ | Chunks map to data/raw files |
| Chunk content matches | ✅ | Verify text.txt content |
| Provenance data present | ✅ | Events, snapshots, products have sources |
| Source file traceability | ✅ | Can trace from extraction back to raw file |

---

## Output Format

### Success ✅
```
Qdrant Sources: ✓ PASS
Provenance Chain: ✓ PASS
```

### Failure ❌
```
✗ data/raw/world_labs/product/text.txt
⚠️  Event 'Series B' has NO provenance!
Qdrant Sources: ✗ FAIL
Provenance Chain: ✗ FAIL
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Collection not found" | Run extraction: `python src/rag/structured_extraction.py --company-slug COMPANY` |
| "No structured files found" | Create one: `python src/rag/structured_extraction.py --company-slug world_labs` |
| "Connection refused" | Start Qdrant: `docker-compose -f docker/docker-compose.yml up -d` |
| "Source file missing" | Verify raw files: `ls -la data/raw/COMPANY/*/text.txt` |

---

## File Locations

| What | Where |
|------|-------|
| Validation script | `src/rag/validate_extraction_sources.py` |
| Structured data | `data/structured/*.json` |
| Raw source data | `data/raw/COMPANY/PAGE_TYPE/text.txt` |
| Qdrant | `http://localhost:6333` |
| Detailed guide | `HOW_TO_RUN_VALIDATION.md` |

---

## Flow Diagram

```
                    Validation Process
                          │
                          ▼
                ┌─────────────────────┐
                │  Load .json files   │
                │  from data/         │
                │  structured/        │
                └──────────┬──────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │ Qdrant  │      │Provenance│     │Raw Files│
    │Validation       │Validation│     │Validation
    │                 │          │     │
    │ ✓ Exists        │ ✓ Sources      │ ✓ Exist
    │ ✓ Has chunks    │ ✓ Timestamps   │ ✓ Content
    │ ✓ Mapped        │ ✓ URLs         │ ✓ Matches
    └────────┬────────┴────────┬──────┴────────┘
             │                 │
             └─────────┬───────┘
                       ▼
              ┌──────────────────┐
              │ VALIDATION       │
              │ SUMMARY          │
              │                  │
              │ ✓ PASS or ✗ FAIL │
              └──────────────────┘
```

---

## Next: What to Do With Results

### ✅ If Validation Passes
- Extraction is working correctly
- Qdrant is properly indexed
- Data is traceable to sources
- Ready for analysis or deployment

### ❌ If Validation Fails
1. Check the error message
2. Re-run extraction
3. Verify raw files exist
4. Check Qdrant is running
5. Review full logs in `HOW_TO_RUN_VALIDATION.md`

---

## See Also

- **Full Guide:** `HOW_TO_RUN_VALIDATION.md`
- **Extraction Script:** `src/rag/structured_extraction.py`
- **Fallback Strategy:** `QUICK_REFERENCE_FALLBACK.md`
- **Testing:** `TESTING_GUIDE_FALLBACK.md`

---

**Quick Reference v1.0** | **Updated: Phase 9** | ✅ Ready to Use
