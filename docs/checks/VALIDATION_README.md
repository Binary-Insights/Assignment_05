# How to Run validate_extraction_sources.py - Documentation Index

## 🎯 Choose Your Guide

### 🏃 I'm in a Hurry (5 minutes)
**Read:** `VALIDATION_QUICK_COMMANDS.md`
- One-liners
- Quick checklist
- TL;DR commands
- Common errors & fixes

### 📖 I Want the Full Picture (15 minutes)
**Read:** `VALIDATION_COMPLETE_GUIDE.md`
- Step-by-step instructions
- All prerequisites
- What the script checks
- Troubleshooting section
- Full workflow example

### 🔧 I Need Technical Details (30+ minutes)
**Read:** `HOW_TO_RUN_VALIDATION.md` (In current editor)
- Deep technical documentation
- Validation phases explained
- Advanced customization
- CI/CD integration
- Code analysis

---

## 🚀 Ultra-Quick Start

**3 commands, 2 minutes:**

```bash
# 1. Start Qdrant
docker-compose -f docker/docker-compose.yml up -d

# 2. Extract data
python src/rag/structured_extraction.py --company-slug world_labs

# 3. Validate
python src/rag/validate_extraction_sources.py
```

---

## ❓ Common Questions → Right Guide

| Question | Read This | Time |
|----------|-----------|------|
| How do I run it? | `VALIDATION_QUICK_COMMANDS.md` | 2 min |
| What does it check? | `VALIDATION_COMPLETE_GUIDE.md` | 5 min |
| Why did it fail? | `VALIDATION_COMPLETE_GUIDE.md` § Troubleshooting | 5 min |
| How do I customize it? | `HOW_TO_RUN_VALIDATION.md` § Customization | 10 min |
| How do I use in CI/CD? | `HOW_TO_RUN_VALIDATION.md` § CI/CD Integration | 10 min |
| What happens during validation? | `HOW_TO_RUN_VALIDATION.md` § What Happens | 10 min |

---

## 📋 Prerequisites Checklist

Before running ANY guide, verify:

- [ ] **Qdrant Running:** `docker ps | grep qdrant`
- [ ] **Structured Data:** `ls data/structured/ | wc -l` (at least 1 file)
- [ ] **Raw Data:** `ls data/raw/*/*/text.txt | wc -l` (has files)
- [ ] **Environment:** `echo $OPENAI_API_KEY` (not empty)
- [ ] **Script Exists:** `ls src/rag/validate_extraction_sources.py`

**Fix Missing Prerequisites:**
```bash
# Start Qdrant
docker-compose -f docker/docker-compose.yml up -d

# Extract data (creates structured files)
python src/rag/structured_extraction.py --company-slug world_labs

# Check environment
cat .env | grep -E "OPENAI_API_KEY|QDRANT_URL"
```

---

## 🎓 Learning Path

### Beginner: "Just run it"
1. Read: `VALIDATION_QUICK_COMMANDS.md`
2. Run: `python src/rag/validate_extraction_sources.py`
3. Check: Output shows ✓ PASS or ✗ FAIL

### Intermediate: "Understand what it does"
1. Read: `VALIDATION_COMPLETE_GUIDE.md`
2. Follow: Full workflow example
3. Troubleshoot: Any issues with guide's section

### Advanced: "Customize for my needs"
1. Read: `HOW_TO_RUN_VALIDATION.md`
2. Modify: Script or add custom checks
3. Integrate: Into CI/CD pipeline

---

## 📚 Documentation Files

| File | Purpose | Length | Audience |
|------|---------|--------|----------|
| `VALIDATION_QUICK_COMMANDS.md` | One-liners & quick ref | 1 page | Everyone |
| `VALIDATION_COMPLETE_GUIDE.md` | Full instructions | 5 pages | Users |
| `HOW_TO_RUN_VALIDATION.md` | Technical deep dive | 10+ pages | Developers |

---

## ✅ What Gets Validated

### 1. Qdrant Collections
```
✓ Collections exist
✓ Chunks are indexed
✓ Metadata is present
✓ Source files are mapped
```

### 2. Raw File Traceability
```
✓ Raw files exist on disk
✓ Chunks map to raw files
✓ Content matches exactly
✓ All sources are accounted for
```

### 3. Provenance Chain
```
✓ Extracted data has sources
✓ Timestamps are recorded
✓ URLs are preserved
✓ Snippets are included
```

---

## 🔍 Expected Output

### ✅ Success
```
VALIDATION SUMMARY
Qdrant Sources: ✓ PASS
Provenance Chain: ✓ PASS
```

### ❌ Failure
```
✗ data/raw/world_labs/product/text.txt
⚠️  Event 'Series B' has NO provenance!
VALIDATION SUMMARY
Qdrant Sources: ✗ FAIL
Provenance Chain: ✗ FAIL
```

---

## 🚀 Start Here Based on Your Needs

### "Just tell me the commands"
👉 Go to: `VALIDATION_QUICK_COMMANDS.md`

### "Walk me through step-by-step"
👉 Go to: `VALIDATION_COMPLETE_GUIDE.md`

### "I need every technical detail"
👉 Go to: `HOW_TO_RUN_VALIDATION.md`

### "Something failed, help!"
👉 Go to: `VALIDATION_COMPLETE_GUIDE.md` → Troubleshooting

---

## 🔄 Full Workflow

```
1. Prerequisites
   └─ Qdrant running
   └─ Raw data available
   └─ Environment set

2. Prepare Data
   └─ Extract structured data
   └─ Verify files created
   └─ Check formats

3. Run Validation
   └─ python src/rag/validate_extraction_sources.py
   └─ Wait for completion
   └─ Review output

4. Interpret Results
   └─ ✓ PASS → Data is valid
   └─ ✗ FAIL → Fix issues (see troubleshooting)

5. Next Steps
   └─ Deploy data
   └─ Analyze results
   └─ Process more companies
```

---

## 📞 Quick Help Matrix

| Issue | Solution | Guide |
|-------|----------|-------|
| "How do I run it?" | `python src/rag/validate_extraction_sources.py` | Quick Cmds |
| "Qdrant not found" | Start Docker: `docker-compose up -d` | Complete |
| "No structured files" | Extract first: `python structured_extraction.py` | Complete |
| "Collection not found" | Re-extract company | Complete |
| "Validation failed" | Check troubleshooting section | Complete |
| "Customize validation" | Modify script (see guide) | Technical |
| "Use in CI/CD" | See CI/CD section | Technical |

---

## ⚡ 60-Second Overview

**What:** Script that verifies extraction data comes from real sources

**Where:** `src/rag/validate_extraction_sources.py`

**When:** After extracting structured data

**How:** `python src/rag/validate_extraction_sources.py`

**Why:** Ensures data quality & traceability

**Result:** ✓ PASS (data is valid) or ✗ FAIL (issues found)

---

## 🎯 Success Criteria

Your validation is complete when:

- ✅ Script runs without errors
- ✅ All Qdrant collections found
- ✅ All raw files verified
- ✅ Provenance data present
- ✅ Final status shows: `✓ PASS`

---

## 📖 Navigation

**You are here:** Documentation Index

**Quick reference:** `VALIDATION_QUICK_COMMANDS.md` (← Start here)

**Full guide:** `VALIDATION_COMPLETE_GUIDE.md`

**Technical:** `HOW_TO_RUN_VALIDATION.md` (currently open)

**Main validation script:** `src/rag/validate_extraction_sources.py`

---

## 🚀 One-Click Start

```bash
# Copy and paste this entire block:

# Start Qdrant
docker-compose -f docker/docker-compose.yml up -d && sleep 5

# Extract data
python src/rag/structured_extraction.py --company-slug world_labs

# Validate
python src/rag/validate_extraction_sources.py

# That's it!
```

---

**Documentation Index v1.0** | **Status: ✅ Ready** | **Choose your guide above →**
