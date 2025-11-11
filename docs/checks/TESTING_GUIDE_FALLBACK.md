# Quick Testing Guide - Fallback Strategy

## Test the Implementation Quickly

### Prerequisites
```bash
# Ensure Qdrant is running
docker ps | grep qdrant

# Ensure the world_labs data exists
ls -la data/raw/world_labs/
```

---

## Test 1: Default Mode (qdrant_first)

**Purpose:** Verify default behavior with Qdrant preferred but fallback available

```bash
python src/rag/structured_extraction.py --company-slug world_labs --verbose
```

**Expected Log Outputs:**
- ✅ `Fallback strategy: qdrant_first`
- 🔍 `Searching Qdrant for context: "company overview mission vision"`
- 🎯 `Found [N] relevant chunks`
- 📊 `Using Qdrant context for company info extraction` (if Qdrant works)
- ⚠️ `Fallback: Qdrant returned no results...` (if Qdrant fails)
- ✓ `Successfully extracted company: ...`

---

## Test 2: Strict Mode (qdrant_only)

**Purpose:** Verify that extraction fails if Qdrant unavailable

```bash
python src/rag/structured_extraction.py --company-slug world_labs --fallback-strategy qdrant_only --verbose
```

**Expected Behavior (if Qdrant works):**
- ✅ Extracts successfully with Qdrant context

**Expected Behavior (if Qdrant fails/returns no results):**
- ❌ `Strategy 'qdrant_only': No Qdrant results for company info - ABORTING`
- 🔴 Script exits with `ValueError`

---

## Test 3: Baseline Mode (raw_only)

**Purpose:** Verify extraction works without Qdrant

```bash
python src/rag/structured_extraction.py --company-slug world_labs --fallback-strategy raw_only --verbose
```

**Expected Log Outputs:**
- ⚙️ `Strategy 'raw_only' selected - skipping Qdrant search for company info`
- ⚙️ `Strategy 'raw_only' selected - skipping Qdrant search for events`
- ⚙️ `Strategy 'raw_only' selected - skipping Qdrant search for snapshots`
- ⚙️ `Strategy 'raw_only' selected - skipping Qdrant search for products`
- ⚙️ `Strategy 'raw_only' selected - skipping Qdrant search for leadership`
- ⚙️ `Strategy 'raw_only' selected - skipping Qdrant search for visibility`
- 🔍 NO Qdrant search logs (all skipped)
- ✓ `Successfully extracted company: ...`
- ✓ `Saved structured data to: data/structured/world-labs.json`

---

## Test 4: Compare Outputs

Compare quality/completeness across strategies:

```bash
# Run with each strategy and compare output files
for strategy in qdrant_first raw_only; do
  echo "Testing with strategy: $strategy"
  python src/rag/structured_extraction.py \
    --company-slug test_company_$strategy \
    --fallback-strategy $strategy > logs/extraction_$strategy.log 2>&1
done

# Compare the structured outputs
diff <(jq '.company_record' data/structured/test_company_qdrant_first.json) \
     <(jq '.company_record' data/structured/test_company_raw_only.json)
```

---

## Test 5: Monitor Strategy in Logs

**Find all strategy references in logs:**
```bash
grep -E "Strategy|🔍|📊|⚠️|❌" extraction.log
```

**Example output:**
```
Fallback strategy: qdrant_first
🔍 Searching Qdrant for context: "company overview mission vision"
🎯 Found 3 relevant chunks with scores: 0.923, 0.891, 0.876
📊 Using Qdrant context for company info extraction
🔍 Searching Qdrant for context: "funding rounds Series A B C seed investment capital raised"
🎯 Found 2 relevant chunks with scores: 0.812, 0.798
📊 Using Qdrant context for events extraction
```

---

## Test 6: Error Handling

**Test qdrant_only mode failure:**

```bash
# 1. Stop Qdrant to simulate unavailability (optional)
# docker stop <qdrant_container>

# 2. Run with qdrant_only (should fail)
python src/rag/structured_extraction.py \
  --company-slug world_labs \
  --fallback-strategy qdrant_only 2>&1 | grep -E "❌|Error|ABORT"

# 3. Restart Qdrant if you stopped it
# docker start <qdrant_container>
```

**Expected error:**
```
❌ Strategy 'qdrant_only': No Qdrant results for company info - ABORTING
Error: No Qdrant context available and 'qdrant_only' strategy selected
```

---

## Test 7: Performance Comparison

Track latency for each strategy:

```bash
echo "Testing performance with different strategies..."

for strategy in raw_only qdrant_first; do
  echo "Strategy: $strategy"
  time python src/rag/structured_extraction.py \
    --company-slug world_labs \
    --fallback-strategy $strategy > /dev/null 2>&1
done
```

**Expected latency (roughly):**
- `raw_only`: 🚀 Fastest (no Qdrant overhead, but more LLM tokens)
- `qdrant_first`: 🔄 Variable (depending on Qdrant availability and response time)
- `qdrant_only`: ⏸️ Similar to qdrant_first (but fails if no results)

---

## Test 8: Batch Processing with Strategy

```bash
# Process multiple companies with the same strategy
STRATEGY="qdrant_first"

for company_dir in data/raw/*/; do
  company_name=$(basename "$company_dir")
  echo "Processing $company_name with strategy: $STRATEGY"
  python src/rag/structured_extraction.py \
    --company-slug "$company_name" \
    --fallback-strategy "$STRATEGY" \
    --verbose 2>&1 | head -20
done
```

---

## Quick Checklist

Use this to verify everything is working:

```
✓ Test 1: qdrant_first mode runs successfully
✓ Test 2: qdrant_only mode fails gracefully when no results
✓ Test 3: raw_only mode produces output with ⚙️ icons (no 🔍)
✓ Test 4: Outputs differ between strategies (Qdrant results more targeted)
✓ Test 5: Logs show clear strategy selection and fallback indicators
✓ Test 6: Error handling works (❌ logs when using qdrant_only)
✓ Test 7: raw_only is fastest, qdrant_first has semantic quality
✓ Test 8: Batch processing works with consistent strategy
```

---

## Debugging Tips

### Log Format
```
🔍 = Qdrant search initiated
🎯 = Results ranked by similarity
📊 = Using Qdrant results in extraction
⚠️ = Falling back to raw text
❌ = Error/failure
⚙️ = Strategy-driven action (skip Qdrant)
✓ = Success
```

### If All Strategies Fail
```bash
# 1. Check Qdrant is running
curl -s http://localhost:6333/health | jq .

# 2. Check collection exists
curl -s http://localhost:6333/collections | jq '.collections[] | {name, points_count}'

# 3. Check data exists
ls -la data/raw/world_labs/*/text.txt

# 4. Check API keys
echo $OPENAI_API_KEY | head -c 10

# 5. Try verbose mode
python src/rag/structured_extraction.py --company-slug world_labs --verbose 2>&1 | grep -i error
```

### If Qdrant Returns No Results
```bash
# 1. Check if collection is empty
curl -s http://localhost:6333/collections/company_world_labs | jq '.result.points_count'

# 2. Re-index the collection (if needed)
python src/rag/structured_extraction.py --company-slug world_labs --fallback-strategy qdrant_first

# 3. Check search query
# (Look at search_queries in extract_company_info function)
```

---

## Expected Output Summary

### qdrant_first (DEFAULT)
```
✅ Runs with Qdrant context when available
✅ Falls back to raw text if Qdrant fails
✅ Always completes extraction
✅ Best for production
```

### qdrant_only (STRICT)
```
✅ Runs with Qdrant context when available
❌ Fails if Qdrant unavailable
✅ Best for validation/testing
```

### raw_only (BASELINE)
```
⚙️ Skips Qdrant entirely
✅ Uses raw text only
✅ Fastest execution
✅ Best for debugging/comparison
```

---

## Next Steps

After testing passes:

1. ✅ Run all tests above
2. ✅ Compare outputs with baseline
3. ✅ Review logs for clear strategy indicators
4. ✅ Check error handling works
5. ✅ Monitor performance
6. ✅ Deploy to production with `--fallback-strategy qdrant_first`

---

**Created:** Phase 9 - Fallback Strategy Implementation
**Last Updated:** Post-Implementation
**Status:** Ready for Testing ✅
