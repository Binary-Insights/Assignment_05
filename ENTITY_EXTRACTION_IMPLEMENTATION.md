# Entity Extraction from Tavily Responses - Implementation Summary

## Overview

Enhanced the LangGraph workflow in `src/tavily_agent/graph.py` to automatically extract structured entities (events, leadership, products, snapshots, visibility) from Tavily search results and insert them into payload lists.

## What Changed

### 1. Import Pydantic Models (Line 29)

```python
from rag.rag_models import Event, Leadership, Visibility, Product, Snapshot, Provenance
```

Added imports for Pydantic models that define the structure of entities to extract.

### 2. Enhanced `analyze_payload()` Function (Lines 129-167)

**Before**: Only checked top-level scalar fields for null values  
**After**: Also queues entity lists for extraction from Tavily responses

**Key Changes**:
- Added check for 5 entity list types: `events`, `leadership`, `products`, `snapshots`, `visibility`
- Always queues these lists for potential extraction (even if they have existing items)
- Uses `entity_index = -1` as a special flag to indicate list extraction mode
- Logs current entity count for tracking

**Example Log Output**:
```
📋 events: currently has 3 items
   ✅ QUEUED for potential entity extraction
```

### 3. Modified `extract_and_update_payload()` Function (Lines 466-492)

**Before**: Only handled scalar field extraction  
**After**: Detects entity extraction mode and routes to specialized function

**Key Changes**:
- Added check for `entity_index == -1` (indicates entity list extraction)
- Routes entity extraction requests to new `extract_and_insert_entities()` function
- Maintains existing scalar field extraction logic

**Routing Logic**:
```python
if entity_index == -1:
    logger.info(f"🔍 [ENTITY EXTRACTION] Detected entity list extraction request for '{field_name}'")
    return await extract_and_insert_entities(state)
```

### 4. New Function: `extract_and_insert_entities()` (Lines 432-592)

**Purpose**: Extract structured entities from Tavily search results using instructor + GPT-4o

**Architecture**:
1. **Model Mapping**: Maps entity type to Pydantic model (events → Event, leadership → Leadership, etc.)
2. **Context Preparation**: Combines top 10 Tavily search results into LLM context
3. **Instructor Setup**: Patches OpenAI client with instructor for structured extraction
4. **Wrapper Model**: Creates `EntityExtractionResult` to hold list of extracted entities
5. **Extraction Prompt**: Instructs LLM to extract entities according to Pydantic schema
6. **LLM Call**: Uses GPT-4o with temperature=0.2 for factual extraction
7. **Insertion**: Converts Pydantic objects to dicts and appends to payload lists
8. **Tracking**: Records extraction count and reasoning in state

**Entity Model Mapping**:
```python
entity_model_map = {
    "events": Event,
    "leadership": Leadership,
    "products": Product,
    "snapshots": Snapshot,
    "visibility": Visibility
}
```

**Extraction Prompt Template**:
```
You are analyzing Tavily search results for **{company_name}**.

Your task: Extract structured **{field_name}** entities from the search results below.

**Entity Type**: {entity_model.__name__}
**Expected Fields**: Review the Pydantic model schema carefully

**Instructions**:
1. Read through all search results carefully
2. Identify information related to {field_name}
3. Structure according to the {entity_model.__name__} schema
4. Include provenance (source_url, snippet)
5. Extract all relevant entities found
6. Only extract for {company_name}, not competitors

[Search Results Content]
```

**Example Extraction Flow**:
```
🔍 [ENTITY EXTRACTION] Starting entity extraction for 'events'
   Company: Abridge (ID: abridge)
   Tavily search results available: 8
   Using Pydantic model: Event
   Combined context length: 15234 characters
🤖 [LLM] Calling GPT-4o with instructor for structured extraction...
✅ [LLM] Extraction complete!
   Entities extracted: 5
   Reasoning: Found 5 funding and partnership events from 2021-2024
   📝 Inserted 5 new events into payload
   📊 Total events in payload: 8
```

## How It Works

### Workflow Integration

1. **Analysis Phase** (`analyze_payload()`):
   - Checks entity lists (events, leadership, products, snapshots, visibility)
   - Queues each with `entity_index = -1` for extraction
   - Proceeds to generate search queries

2. **Search Phase** (`execute_searches()`):
   - Executes Tavily searches for entity-related queries
   - Saves responses to `data/raw/{company}/tavily/`
   - Ingests to Pinecone for future retrieval

3. **Extraction Phase** (`extract_and_insert_entities()`):
   - Detects `entity_index == -1` in `extract_and_update_payload()`
   - Routes to entity extraction function
   - Uses instructor + GPT-4o to structure Tavily data
   - Inserts extracted entities into payload lists

4. **Completion Phase** (`check_completion()`):
   - Verifies all queued extractions completed
   - Saves updated payload with new entities

### Entity Extraction Details

**Input**: Tavily search results (JSON documents with url, title, content)

**Processing**:
1. Combine search results into context string
2. Send to GPT-4o with Pydantic model schema
3. LLM structures data according to model fields
4. Validates using Pydantic model validation

**Output**: List of structured entities conforming to Pydantic models

**Example Event Extraction**:
```python
# Input: Tavily search result
{
    "url": "https://techcrunch.com/2024/01/15/abridge-series-c",
    "title": "Abridge raises $150M Series C",
    "content": "Healthcare AI startup Abridge announced today..."
}

# Output: Structured Event object
{
    "event_id": "abridge_event_2024_01_15_001",
    "company_id": "abridge",
    "occurred_on": "2024-01-15",
    "event_type": "funding",
    "title": "Abridge raises $150M Series C",
    "description": "Healthcare AI startup raised $150M in Series C funding",
    "round_name": "Series C",
    "amount_usd": 150000000,
    "investors": ["Lightspeed Venture Partners", "NVIDIA"],
    "provenance": [{
        "source_url": "https://techcrunch.com/2024/01/15/abridge-series-c",
        "snippet": "Abridge announced today...",
        "crawled_at": "2024-01-15T10:30:00Z"
    }]
}
```

## Configuration Requirements

### Environment Variables
- `OPENAI_API_KEY`: Required for instructor + GPT-4o
- `LLM_MODEL`: Set to "gpt-4o" (default now set in config.py)
- `LLM_TEMPERATURE`: Optional, extraction uses 0.2 for factual accuracy

### Pydantic Models (src/rag/rag_models.py)
Must have these models defined:
- `Event`: Funding, acquisitions, partnerships, product launches
- `Leadership`: Executives, founders, board members, advisors
- `Product`: Software, services, APIs, integrations
- `Snapshot`: Headcount, hiring, growth metrics at specific dates
- `Visibility`: News mentions, sentiment, github stars, glassdoor ratings
- `Provenance`: Source tracking (url, snippet, crawled_at, chunk_id)

## Benefits

1. **Automated Enrichment**: Automatically populates structured entity lists from web searches
2. **Pydantic Validation**: Ensures extracted data conforms to schema
3. **Provenance Tracking**: Every entity includes source URLs for verification
4. **Incremental Updates**: Can add entities to existing lists (doesn't replace)
5. **LLM-Powered**: Uses GPT-4o to intelligently structure unstructured web content
6. **Comprehensive Coverage**: Extracts 5 entity types covering company profile, events, team, products, metrics

## Testing Recommendations

### 1. Test Entity Extraction
```bash
# Run enrichment DAG for a company
# Check that entity lists are populated from Tavily search results
```

### 2. Verify Pydantic Validation
- Check that extracted entities have all required fields
- Verify date formats (ISO 8601)
- Confirm provenance includes source URLs

### 3. Review Extraction Quality
- Check logs for extraction reasoning
- Verify entity count matches search result relevance
- Ensure entities are for correct company (not competitors)

### 4. Check Incremental Updates
- Run enrichment multiple times
- Verify new entities are added, not replacing existing ones
- Confirm no duplicate entities

## Example Log Output

```
📦 Checking entity lists for enrichment opportunities...
📋 events: currently has 3 items
   ✅ QUEUED for potential entity extraction
📋 leadership: currently has 8 items
   ✅ QUEUED for potential entity extraction
...

🔍 [ENTITY EXTRACTION] Starting entity extraction for 'events'
   Company: Abridge (ID: abridge)
   Tavily search results available: 8
   Using Pydantic model: Event
   Combined context length: 15234 characters

🤖 [LLM] Calling GPT-4o with instructor for structured extraction...

✅ [LLM] Extraction complete!
   Entities extracted: 5
   Reasoning: Found 5 funding and partnership events from 2021-2024
   📝 Inserted 5 new events into payload
   📊 Total events in payload: 8

✅ [ENTITY EXTRACTION] Completed for 'events'
```

## Potential Improvements

1. **Deduplication**: Add logic to prevent duplicate entities (compare event_id, person_id, etc.)
2. **Batch Processing**: Extract multiple entity types in single LLM call
3. **Confidence Scoring**: Add confidence field to track extraction quality
4. **Entity Merging**: Merge overlapping entities from different sources
5. **Selective Querying**: Only search for entities that have low counts
6. **Custom Prompts**: Entity-type-specific extraction prompts for better accuracy

## Files Modified

- `src/tavily_agent/graph.py`: Added entity extraction logic (170 lines added)
- `src/tavily_agent/config.py`: Fixed LLM_MODEL default (earlier fix)
- `src/rag/structured_extraction_search.py`: Enhanced OpenAIEmbeddings (earlier fix)

## Status

✅ **Implementation Complete**
- Pydantic models imported
- `analyze_payload()` enhanced to queue entity lists
- `extract_and_update_payload()` routes to entity extraction
- `extract_and_insert_entities()` function implemented with instructor + GPT-4o

🔄 **Next Steps**
1. Rebuild Docker containers with updated code
2. Test entity extraction with abridge company
3. Verify extracted entities match Pydantic schema
4. Review logs for extraction quality

## Related Documentation

- `docs/EVALUATION_FRAMEWORK_README.md`: Evaluation metrics for extraction quality
- `src/rag/rag_models.py`: Pydantic model definitions
- `TAVILY_INGESTION_FIX.md`: Earlier fix for Tavily response saving
- `LLM_MODEL_FIX.md`: Earlier fix for OpenAI model parameter

---

**Implementation Date**: 2024-01-XX  
**Author**: GitHub Copilot  
**Status**: Ready for Testing
