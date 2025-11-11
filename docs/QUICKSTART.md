# Quick Start: LLM Page Finder

## 30-Second Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key (choose one)
export OPENAI_API_KEY="sk-..."           # For OpenAI/GPT-4o-mini
# OR
export ANTHROPIC_API_KEY="sk-ant-..."    # For Anthropic/Claude

# 3. Run a test
python src/discover/llm_page_finder.py \
  --website "https://www.anthropic.com/" \
  --page-type "careers"
```

## Common Examples

### Find Product Page
```bash
python src/discover/llm_page_finder.py \
  --website "https://worldlabs.ai/" \
  --page-type "product"
```

### Find Careers Page & Save Output
```bash
python src/discover/llm_page_finder.py \
  --website "https://www.abridge.com/" \
  --page-type "careers" \
  --output output/abridge_careers.json
```

### Test Batch Discovery (3 companies)
```bash
python src/discover/test_llm_finder.py --sample-count 3
```

### Test Single Company (All Page Types)
```bash
python src/discover/test_llm_finder.py \
  --website "https://www.anthropic.com/" \
  --batch \
  --page-types product careers about blog
```

## What You Get

Each request returns:
```json
{
  "page_type": "product",
  "discovered_url": "https://example.com/products",
  "confidence": 0.85,
  "reasoning": "...",
  "alternative_urls": [...]
}
```

- **confidence**: 0.0 (not found) to 1.0 (very confident)
- **discovered_url**: The page URL found (or null if not found)
- **reasoning**: Why this URL was chosen
- **alternative_urls**: Other candidates

## Files Created

- `src/discover/llm_page_finder.py` — Main discovery script
- `src/discover/test_llm_finder.py` — Test harness
- `src/discover/LLM_PAGE_FINDER.md` — Full documentation
- Updated `requirements.txt` — New dependencies

## How It Works

1. **Fetch**: Gets HTML from company website homepage
2. **Parse**: Extracts text, removes src/styles, limits to 4000 chars
3. **LLM**: Sends page type + content to LLM via LangChain
4. **Structured Output**: Uses Instructor to validate and parse JSON response
5. **Return**: Structured `DiscoveredPage` with URL, confidence, reasoning

## Key Features

- ✅ **Structured I/O**: Pydantic models + Instructor validation
- ✅ **LLM Choice**: Supports OpenAI GPT and Anthropic Claude
- ✅ **Error Handling**: Graceful fallback if structured output fails
- ✅ **Web Fetching**: Handles timeouts, parsing, content limits
- ✅ **CLI + Testing**: Full argparse interface + batch test harness
- ✅ **Logging**: Detailed logs for debugging

## Troubleshooting

**Missing API key?**
```bash
echo $OPENAI_API_KEY  # Check if set
export OPENAI_API_KEY="sk-..."  # Set if not
```

**Dependencies not installed?**
```bash
pip install langchain langchain-openai instructor beautifulsoup4 anthropic
```

**Slow website fetch?**
- Increase timeout: edit `fetch_page_content(timeout=20)` in llm_page_finder.py
- Or skip using `--no-structured` for faster fallback parsing

**Low confidence results?**
- Website structure is non-standard → consider manual override
- Try GPT-4 Turbo instead of GPT-4o-mini for better reasoning

## Next Steps

1. Run `test_llm_finder.py` with a few sample companies
2. Compare results with heuristic `discover_links.py` output
3. For uncertain cases in heuristic discovery, use LLM as refinement
4. Integrate into pipeline or use for manual validation

## Full Documentation

See `src/discover/LLM_PAGE_FINDER.md` for:
- Complete API reference
- Advanced configuration
- Integration with heuristic discovery
- Performance benchmarks
- Troubleshooting guide
