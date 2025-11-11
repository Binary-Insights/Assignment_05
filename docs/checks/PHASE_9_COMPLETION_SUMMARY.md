# Phase 9 Completion Summary - Fallback Strategy Enforcement

## 🎯 Objectives Completed

✅ **Implemented fallback strategy enforcement** across all 6 extraction functions
✅ **Added CLI argument** (`--fallback-strategy`) for runtime control  
✅ **Enhanced logging** with strategy-specific indicators (⚙️, 📊, ⚠️, ❌)
✅ **Created helper functions** for strategy decision logic
✅ **Comprehensive documentation** with testing guides

---

## 📋 What Was Changed

### File: `src/rag/structured_extraction.py`

#### 1. Global Configuration Variable (NEW)
```python
# Line ~51 (after imports)
FALLBACK_STRATEGY = 'qdrant_first'  # Can be: 'qdrant_only', 'raw_only', 'qdrant_first'
```

#### 2. Helper Functions (NEW)
- **`should_use_fallback(context_docs, extraction_type)`** - Determines fallback behavior based on strategy
- **`log_extraction_sources(extraction_type, company_id, search_queries, context_docs)`** - Enhanced source logging

#### 3. Updated Extraction Functions (6 total)
Each function now implements the strategy enforcement pattern:

| Function | Lines | Status |
|----------|-------|--------|
| `extract_company_info()` | 480-502 | ✅ Updated |
| `extract_events()` | 555-583 | ✅ Updated |
| `extract_snapshots()` | 657-685 | ✅ Updated |
| `extract_products()` | 748-776 | ✅ Updated |
| `extract_leadership()` | 835-863 | ✅ Updated |
| `extract_visibility()` | 927-955 | ✅ Updated |

#### 4. CLI Argument (NEW)
```python
# Lines 1160-1167
parser.add_argument(
    '--fallback-strategy',
    type=str,
    choices=['qdrant_only', 'raw_only', 'qdrant_first'],
    default='qdrant_first',
    help='Strategy for handling Qdrant failures...'
)
```

#### 5. Strategy Application (NEW)
```python
# Lines 1172-1174
global FALLBACK_STRATEGY
FALLBACK_STRATEGY = args.fallback_strategy
logger.info(f"Fallback strategy: {args.fallback_strategy}")
```

---

## 🔄 Strategy Behavior

### Strategy 1: `qdrant_first` (DEFAULT)
**Use when:** Production deployments needing best-effort extraction

**Behavior:**
```
TRY Qdrant search
├─ IF results found → Use Qdrant context (📊 log)
└─ IF no results → Fallback to raw text (⚠️ log)
ALWAYS complete extraction ✓
```

**Logs:**
```
🔍 Searching Qdrant: "query"
🎯 Found 3 results: [scores]
📊 Using Qdrant context for [TYPE] extraction
```
OR
```
🔍 Searching Qdrant: "query"
❌ No results found
⚠️ Fallback: Qdrant returned no results, using raw text instead
```

### Strategy 2: `qdrant_only` (STRICT)
**Use when:** Validating vector search quality or testing

**Behavior:**
```
TRY Qdrant search
├─ IF results found → Use Qdrant context (📊 log)
└─ IF no results → ABORT with error (❌ log)
FAIL extraction if Qdrant unavailable ✗
```

**Logs:**
```
🔍 Searching Qdrant: "query"
🎯 Found 3 results: [scores]
📊 Using Qdrant context for [TYPE] extraction
```
OR
```
🔍 Searching Qdrant: "query"
❌ No results found
❌ Strategy 'qdrant_only': No Qdrant results for [TYPE] - ABORTING
Error: No Qdrant context available and 'qdrant_only' strategy selected
```

### Strategy 3: `raw_only` (BASELINE)
**Use when:** Debugging, comparing without semantic search, or rapid iteration

**Behavior:**
```
SKIP Qdrant search entirely (⚙️ log)
Use raw text directly
ALWAYS complete extraction ✓
```

**Logs:**
```
⚙️  Strategy 'raw_only' selected - skipping Qdrant search for [TYPE]
✓ Successfully extracted company: [name]
```

---

## 💻 Usage Examples

### Run with Default Strategy (qdrant_first)
```bash
python src/rag/structured_extraction.py --company-slug world_labs
```

### Run with Strict Strategy (qdrant_only)
```bash
python src/rag/structured_extraction.py \
  --company-slug world_labs \
  --fallback-strategy qdrant_only
```

### Run with Baseline Strategy (raw_only)
```bash
python src/rag/structured_extraction.py \
  --company-slug world_labs \
  --fallback-strategy raw_only
```

### Run with Verbose Logging
```bash
python src/rag/structured_extraction.py \
  --company-slug world_labs \
  --fallback-strategy qdrant_first \
  --verbose
```

---

## 📊 Implementation Architecture

```
main()
├── Parse CLI args (including --fallback-strategy)
├── Set global FALLBACK_STRATEGY
│
├── extract_company_info()
│   ├── IF FALLBACK_STRATEGY == 'raw_only'
│   │   └── Use raw text only (⚙️)
│   └── ELSE
│       ├── TRY Qdrant search (🔍)
│       ├── IF results → Use context (📊)
│       ├── ELSE IF 'qdrant_only' → Abort (❌)
│       └── ELSE → Fallback to raw (⚠️)
│
├── extract_events()
│   └── [Same pattern as above]
│
├── extract_snapshots()
│   └── [Same pattern as above]
│
├── extract_products()
│   └── [Same pattern as above]
│
├── extract_leadership()
│   └── [Same pattern as above]
│
└── extract_visibility()
    └── [Same pattern as above]
```

---

## 🔍 Logging Icons System

| Icon | Meaning | Context |
|------|---------|---------|
| 🔍 | Search initiated | Searching Qdrant for context |
| 🎯 | Results ranked | Top matches with similarity scores |
| ✅ | Success | Operation completed successfully |
| ❌ | Error/Failure | Operation failed or strategy aborted |
| 📊 | Using Qdrant | Proceeding with vector search results |
| ⚠️ | Fallback warning | Falling back to raw text |
| ⚙️ | Strategy action | Action taken due to strategy choice |

---

## 📝 Code Pattern Applied to All 6 Functions

```python
# Determine search strategy
context_docs = []
context_text = ""

global FALLBACK_STRATEGY

if FALLBACK_STRATEGY == 'raw_only':
    logger.info(f"⚙️  Strategy 'raw_only' selected - skipping Qdrant search for [TYPE]")
    context_text = json.dumps(pages_text, indent=2)[:3000]
else:
    # Try Qdrant search
    for query in search_queries:
        docs = search_qdrant_for_context(query, collection_name, qdrant_client, embeddings, limit=N)
        context_docs.extend(docs)
    
    if context_docs:
        logger.info("📊 Using Qdrant context for [TYPE] extraction")
        context_text = "\n\n".join([
            f"[{doc['page_type']}] {doc['text'][:250]}"
            for doc in context_docs[:limit]
        ])
    elif FALLBACK_STRATEGY == 'qdrant_only':
        logger.error("❌ Strategy 'qdrant_only': No Qdrant results for [TYPE] - ABORTING")
        raise ValueError("No Qdrant context available and 'qdrant_only' strategy selected")
    else:  # qdrant_first
        logger.warning("⚠️  Fallback: Qdrant returned no results for [TYPE], using raw text instead")
        context_text = json.dumps(pages_text, indent=2)[:3000]

# Log extraction sources for validation
log_extraction_sources("[TYPE]", company_id, search_queries, context_docs)

# Continue with LLM extraction using context_text...
```

---

## ✅ Testing Checklist

- [ ] Test 1: Run with `qdrant_first` (default) - should show 📊 or ⚠️ icons
- [ ] Test 2: Run with `qdrant_only` - should fail with ❌ if no Qdrant results
- [ ] Test 3: Run with `raw_only` - should show only ⚙️ icons, no 🔍 icons
- [ ] Test 4: Verify output JSON is created in `data/structured/`
- [ ] Test 5: Compare outputs between strategies
- [ ] Test 6: Check logs for clear strategy selection message
- [ ] Test 7: Verify error handling with `qdrant_only` when Qdrant unavailable
- [ ] Test 8: Run batch processing with consistent strategy

**Testing Guides:**
- See: `TESTING_GUIDE_FALLBACK.md`
- See: `FALLBACK_STRATEGY_IMPLEMENTATION.md`

---

## 📚 Documentation Created

### 1. `FALLBACK_STRATEGY_IMPLEMENTATION.md`
Comprehensive technical documentation covering:
- Strategy overview and behavior
- Use cases for each strategy
- Updated extraction functions
- Error handling
- Performance implications
- Troubleshooting guide

### 2. `TESTING_GUIDE_FALLBACK.md`
Quick reference with:
- 8 practical test scenarios
- Expected outputs for each strategy
- Performance comparison
- Debugging tips
- Quick checklist

---

## 🚀 Deployment Guide

### Production Deployment (Recommended)
```bash
python src/rag/structured_extraction.py \
  --company-slug COMPANY_NAME \
  --fallback-strategy qdrant_first  # Default
```

### Batch Processing
```bash
for company in $(ls data/raw/); do
  python src/rag/structured_extraction.py \
    --company-slug "$company" \
    --fallback-strategy qdrant_first
done
```

### Strict Validation Mode
```bash
# Ensure Qdrant is working for all companies
for company in $(ls data/raw/); do
  python src/rag/structured_extraction.py \
    --company-slug "$company" \
    --fallback-strategy qdrant_only || echo "Failed: $company"
done
```

### Baseline Comparison
```bash
# Generate baseline without semantic search
python src/rag/structured_extraction.py \
  --company-slug COMPANY_NAME \
  --fallback-strategy raw_only
```

---

## 📊 Expected Log Output Examples

### qdrant_first with Successful Qdrant Search
```
INFO:structured_extraction:Fallback strategy: qdrant_first
INFO:structured_extraction:Extracting company info for World Labs...
DEBUG:structured_extraction:🔍 Searching Qdrant for context: "company overview mission vision"
DEBUG:structured_extraction:🎯 Rank 1: world_labs/about.html (chunk 0, similarity: 0.923)
DEBUG:structured_extraction:🎯 Rank 2: world_labs/blog.html (chunk 5, similarity: 0.891)
DEBUG:structured_extraction:✅ Qdrant search returned 2 documents
INFO:structured_extraction:📊 Using Qdrant context for company extraction
```

### qdrant_first with Fallback to Raw Text
```
INFO:structured_extraction:Fallback strategy: qdrant_first
INFO:structured_extraction:Extracting company info for Test Corp...
DEBUG:structured_extraction:🔍 Searching Qdrant for context: "company overview mission vision"
DEBUG:structured_extraction:❌ Error searching Qdrant: Collection not found
WARNING:structured_extraction:⚠️  Fallback: Qdrant returned no results for company info, using raw text instead
```

### raw_only Mode
```
INFO:structured_extraction:Fallback strategy: raw_only
INFO:structured_extraction:Extracting company info for World Labs...
INFO:structured_extraction:⚙️  Strategy 'raw_only' selected - skipping Qdrant search for company info
DEBUG:structured_extraction:Building context from raw text (3000 chars)
```

### qdrant_only with Failure
```
INFO:structured_extraction:Fallback strategy: qdrant_only
INFO:structured_extraction:Extracting company info for World Labs...
DEBUG:structured_extraction:🔍 Searching Qdrant for context: "company overview mission vision"
DEBUG:structured_extraction:❌ No results found
ERROR:structured_extraction:❌ Strategy 'qdrant_only': No Qdrant results for company info - ABORTING
ERROR:structured_extraction:Error processing company World Labs: No Qdrant context available and 'qdrant_only' strategy selected
```

---

## 🔧 Troubleshooting

### All Strategies Fail
```bash
# 1. Check Qdrant health
curl http://localhost:6333/health

# 2. Verify collections exist
curl http://localhost:6333/collections

# 3. Check data files
ls -la data/raw/COMPANY_NAME/

# 4. Try raw_only (should always work if data exists)
python src/rag/structured_extraction.py --company-slug COMPANY --fallback-strategy raw_only
```

### qdrant_only Fails but qdrant_first Works
- Qdrant is available but returns no results for that company
- Try re-indexing the Qdrant collection
- Check if embeddings are properly generated

### raw_only is Slow
- Expected: raw_only uses full text context (more LLM tokens)
- Solution: Use `qdrant_first` for better performance

### Inconsistent Results Between Strategies
- Normal: `qdrant_first` uses semantic search, `raw_only` uses full text
- `qdrant_first` should be more targeted but `raw_only` provides complete context
- Compare with `VALIDATION_GUIDE.md` for expected quality

---

## 📈 Performance Comparison

| Strategy | Speed | Quality | Qdrant Dependency | Use Case |
|----------|-------|---------|-------------------|----------|
| `qdrant_only` | Fast | High (semantic) | Required | Validation |
| `raw_only` | Medium | Medium | None | Baseline/Debug |
| `qdrant_first` | Variable | High (when possible) | Optional | Production |

---

## 🎓 Key Takeaways

1. **Three strategies cover all use cases**: strict validation, baseline testing, and production deployment
2. **Clear logging with emoji indicators**: Easy to track which code path executed
3. **Runtime configuration**: Choose strategy at execution time, not compile time
4. **Graceful degradation**: Production mode falls back to raw text if Qdrant unavailable
5. **Error handling**: Strict mode fails fast for validation, production mode completes extraction

---

## 📞 Next Steps

1. **Run tests** from `TESTING_GUIDE_FALLBACK.md`
2. **Compare outputs** between strategies
3. **Deploy** with `--fallback-strategy qdrant_first` for production
4. **Monitor logs** for strategy selection and fallback events
5. **Adjust** based on performance and quality metrics

---

## 📄 Related Files

- `src/rag/structured_extraction.py` - Main extraction script (MODIFIED)
- `src/rag/rag_models.py` - Pydantic models (unchanged, already fixed)
- `src/rag/validate_extraction_sources.py` - Validation script (reference)
- `VALIDATION_GUIDE.md` - Comprehensive validation documentation
- `FALLBACK_STRATEGY_IMPLEMENTATION.md` - Detailed technical documentation
- `TESTING_GUIDE_FALLBACK.md` - Quick testing reference

---

**Status:** ✅ Implementation Complete - Ready for Testing
**Date:** Phase 9
**Total Functions Updated:** 6 extraction functions + 2 helper functions
**CLI Arguments Added:** 1 (`--fallback-strategy`)
**Documentation Files Created:** 2 (Implementation guide + Testing guide)
