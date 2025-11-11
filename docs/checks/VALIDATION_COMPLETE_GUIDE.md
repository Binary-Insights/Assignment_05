# How to Run validate_extraction_sources.py - Complete Guide

## 🚀 Quick Start (30 seconds)

```bash
# 1. Start Qdrant
docker-compose -f docker/docker-compose.yml up -d

# 2. Extract data (if needed)
python src/rag/structured_extraction.py --company-slug world_labs

# 3. Run validation
python src/rag/validate_extraction_sources.py
```

That's it! The script will validate all extracted files.

---

## 📋 Prerequisites

Before running, ensure you have:

### 1. Qdrant Running ✅
```bash
# Check if running
docker ps | grep qdrant

# If not, start it
docker-compose -f docker/docker-compose.yml up -d

# Verify it's healthy
curl -s http://localhost:6333/health | jq .
```

### 2. Structured Data Extracted ✅
```bash
# Check if extracted files exist
ls -la data/structured/

# If empty, extract first
python src/rag/structured_extraction.py --company-slug world_labs
```

### 3. Environment Variables Set ✅
```bash
# Check if set
echo $OPENAI_API_KEY
echo $QDRANT_URL

# If not set, add to .env file
cat > .env << EOF
OPENAI_API_KEY=sk-...your-key...
QDRANT_URL=http://localhost:6333
EOF
```

### 4. Raw Data Available ✅
```bash
# Verify raw source files exist
ls -la data/raw/world_labs/about/text.txt
ls -la data/raw/world_labs/blog/text.txt
```

---

## ▶️ Running the Script

### Standard Run (Validates All Files)
```bash
python src/rag/validate_extraction_sources.py
```

**What happens:**
1. Finds all `.json` files in `data/structured/`
2. For each file:
   - Connects to Qdrant collection
   - Verifies all chunks are from real raw files
   - Checks provenance data
   - Compares with raw files on disk
3. Prints validation report for each company
4. Shows final pass/fail status

**Expected output:**
```
QDRANT VALIDATION: world-labs
✓ Collection exists: company_world_labs
  Total points: 45

📊 Sources in Qdrant:
✓ data/raw/world_labs/about/text.txt
    Chunks: 12
    Content matches: 3/3

✓ All Qdrant sources verified

VALIDATION SUMMARY
Qdrant Sources: ✓ PASS
Provenance Chain: ✓ PASS
```

---

## 🔍 What the Script Checks

### Check 1: Qdrant Collections
- Does collection exist for this company?
- How many chunks are indexed?
- Do source files exist for each chunk?

**Example:**
```
✓ Collection exists: company_world_labs
  Total points: 45
✓ data/raw/world_labs/about/text.txt
    Chunks: 12
```

### Check 2: Provenance Chain
- Does extracted data have source attribution?
- Are timestamps present?
- Are source URLs recorded?

**Example:**
```
✓ Company Record (provenance: 5 sources)
✓ Events (3 total) - all have provenance
✓ Products (2 total) - all have provenance
✓ Leadership (8 total) - all have provenance
```

### Check 3: Raw File Traceability
- Can we find extracted content in raw files?
- Are chunks properly mapped?
- Is content consistent?

**Example:**
```
RAW FILES vs QDRANT COMPARISON: world_labs
✓ Point 1: Found in about/text.txt
✓ Point 2: Found in blog/text.txt
✓ Point 3: Found in careers/text.txt
Verified: 10/10 chunks
```

---

## 📊 Understanding the Output

### ✅ Success = PASS
```
VALIDATION SUMMARY
Qdrant Sources: ✓ PASS
Provenance Chain: ✓ PASS
```

**Means:**
- All extracted data is traceable to raw sources
- Qdrant is properly indexed
- Provenance metadata is complete

### ❌ Failure = Issue to Fix
```
✗ data/raw/world_labs/product/text.txt
⚠️  Event 'Series B Funding' has NO provenance!

VALIDATION SUMMARY
Qdrant Sources: ✗ FAIL
Provenance Chain: ✗ FAIL
```

**Means:**
- Raw file may be missing
- Provenance metadata not recorded
- Need to re-extract or investigate

---

## 🛠️ Troubleshooting

### Problem: "Collection not found"

**Error:**
```
Error validating Qdrant: QdrantException: Not found
```

**Cause:** Collection doesn't exist in Qdrant

**Solution:**
```bash
# 1. Verify Qdrant is running
docker ps | grep qdrant

# 2. Create collection by extracting
python src/rag/structured_extraction.py --company-slug world_labs

# 3. Try validation again
python src/rag/validate_extraction_sources.py
```

---

### Problem: "No structured files found"

**Error:**
```
No structured files found
```

**Cause:** `data/structured/` is empty

**Solution:**
```bash
# 1. Create the directory
mkdir -p data/structured

# 2. Extract data
python src/rag/structured_extraction.py --company-slug world_labs

# 3. Verify file created
ls -la data/structured/

# 4. Try validation again
python src/rag/validate_extraction_sources.py
```

---

### Problem: "Connection refused"

**Error:**
```
Error connecting to Qdrant: Connection refused
```

**Cause:** Qdrant is not running

**Solution:**
```bash
# 1. Start Qdrant
docker-compose -f docker/docker-compose.yml up -d

# 2. Wait for it to be ready
sleep 5

# 3. Verify it's running
curl -s http://localhost:6333/health | jq .

# 4. Try validation again
python src/rag/validate_extraction_sources.py
```

---

### Problem: "Source file missing"

**Error:**
```
✗ data/raw/world_labs/product/text.txt
```

**Cause:** Raw file doesn't exist

**Solution:**
```bash
# 1. Verify raw files exist
ls -la data/raw/world_labs/*/text.txt

# 2. If missing, run scraper first
python src/scraper.py --company-slug world_labs

# 3. Re-extract structured data
python src/rag/structured_extraction.py --company-slug world_labs

# 4. Try validation again
python src/rag/validate_extraction_sources.py
```

---

## 📝 Full Workflow Example

### Step-by-Step: Extract and Validate a Company

```bash
# 1. Ensure Qdrant is running
echo "Starting Qdrant..."
docker-compose -f docker/docker-compose.yml up -d
sleep 5

# 2. Verify Qdrant is healthy
echo "Checking Qdrant health..."
curl -s http://localhost:6333/health | jq .

# 3. Download and scrape web pages (if needed)
echo "Scraping pages..."
python src/scraper.py --company-slug world_labs

# 4. Extract structured data
echo "Extracting structured data..."
python src/rag/structured_extraction.py --company-slug world_labs

# 5. Verify extracted file created
echo "Checking output..."
ls -la data/structured/world-labs.json

# 6. Run validation
echo "Running validation..."
python src/rag/validate_extraction_sources.py

# 7. Check result
if [ $? -eq 0 ]; then
    echo "✓ Validation PASSED"
else
    echo "✗ Validation FAILED"
fi
```

---

## 🔄 Validating Multiple Companies

```bash
# Create extracted data for multiple companies
echo "Extracting multiple companies..."
for company in world_labs anthropic openai; do
    echo "Processing: $company"
    python src/rag/structured_extraction.py --company-slug $company
done

# Verify all files created
echo "Checking extracted files..."
ls -lh data/structured/

# Run single validation for all
echo "Running validation..."
python src/rag/validate_extraction_sources.py
```

---

## 📍 Key Files & Directories

| Item | Path | Purpose |
|------|------|---------|
| Validation script | `src/rag/validate_extraction_sources.py` | Runs validation checks |
| Raw data | `data/raw/{company}/*/text.txt` | Source web page text |
| Extracted data | `data/structured/*.json` | Validated structured output |
| Qdrant | `http://localhost:6333` | Vector database |
| .env file | `.env` | Environment configuration |
| This guide | `HOW_TO_RUN_VALIDATION.md` | Complete documentation |

---

## ✅ Validation Checklist

Before running, verify:

- [ ] Qdrant is running: `docker ps | grep qdrant`
- [ ] Structured data exists: `ls data/structured/`
- [ ] Raw data exists: `ls data/raw/COMPANY/*/text.txt`
- [ ] Environment variables set: `echo $OPENAI_API_KEY`
- [ ] Python script exists: `ls src/rag/validate_extraction_sources.py`

---

## 🚀 One-Liner Commands

### Complete: Start, Extract, Validate
```bash
docker-compose -f docker/docker-compose.yml up -d && sleep 5 && python src/rag/structured_extraction.py --company-slug world_labs && python src/rag/validate_extraction_sources.py
```

### Just Validate (assumes everything is ready)
```bash
python src/rag/validate_extraction_sources.py
```

### Check Qdrant Ready
```bash
curl -s http://localhost:6333/health && echo "✓ Qdrant is ready"
```

### List What Will Be Validated
```bash
ls -lh data/structured/
```

---

## 📈 Expected Results

### ✅ Perfect Validation
```
VALIDATION SUMMARY
═════════════════════════════════════════════════════════════
Qdrant Sources: ✓ PASS
Provenance Chain: ✓ PASS
═════════════════════════════════════════════════════════════
```

### 📊 Typical Output
- For each company: 100-1000+ chunks indexed
- 2-8 page types per company (about, blog, careers, products, etc.)
- Complete provenance for all extracted fields
- 100% chunk traceability to raw files

---

## 🎯 After Validation Passes

Once validation succeeds, you can:

1. **Deploy the data** - Use `data/structured/` JSON files in production
2. **Analyze the results** - Query the extracted structured data
3. **Run batch processing** - Process multiple companies
4. **Compare strategies** - Try different `--fallback-strategy` options
5. **Generate reports** - Use the validated provenance data

---

## 📚 Related Documentation

- **Full Validation Guide:** `HOW_TO_RUN_VALIDATION.md`
- **Quick Commands:** `VALIDATION_QUICK_COMMANDS.md`
- **Extraction Script:** `src/rag/structured_extraction.py`
- **Fallback Strategy:** `QUICK_REFERENCE_FALLBACK.md`
- **Testing Guide:** `TESTING_GUIDE_FALLBACK.md`

---

## 💡 Tips & Best Practices

1. **Always run Qdrant first** - It's needed for all validations
2. **Extract before validating** - Need structured files to validate
3. **Check Qdrant health** - Use `/health` endpoint
4. **Monitor raw files** - Validation depends on raw source files
5. **Review error messages** - They tell you exactly what's wrong
6. **Validate after changes** - Run validation after any extraction

---

## 📞 Common Questions

**Q: Can I validate specific companies only?**
A: Yes, move other files temporarily or modify the script (see guide section on customization)

**Q: How long does validation take?**
A: Usually 1-2 minutes for 1-2 companies depending on chunk count

**Q: What if Qdrant is on a different machine?**
A: Set `QDRANT_URL` environment variable or modify `.env` file

**Q: Can I validate without OpenAI API?**
A: Yes, validation doesn't call OpenAI - just needs embeddings already in Qdrant

**Q: What's the success rate?**
A: Should be 100% - all chunks should be traceable to raw files

---

**Complete Guide v1.0** | **Status: ✅ Ready to Use** | **Phase 9**
