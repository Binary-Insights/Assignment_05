# EVALUATION SCORING THRESHOLDS - QUICK REFERENCE

## Overview

Each evaluation metric has specific thresholds that determine the score. When you run an evaluation with the enhanced logging, these thresholds will be clearly shown in the logs.

---

## 1. Factual Accuracy (0-3 points)

**What it measures**: How well the generated text covers the key facts from ground truth data.

**Scoring thresholds:**

```
Coverage Percentage    Score   Quality Rating
───────────────────────────────────────────
< 40%                   0      Poor (Major gaps)
40% - 70%               1      Fair (Some gaps)
70% - 90%               2      Good (Minor gaps)
≥ 90%                   3      Excellent (Complete)
```

**Log example:**
```
Coverage = 85% → Score = 2 (falls in 70-90% range)
```

**How to improve:**
- Mention more key facts from the source data
- Cover all important aspects of the company
- Ensure facts are verified and present

---

## 2. Schema Compliance (0-2 points)

**What it measures**: Whether the generated content has proper structure (headers, sections, lists).

**Scoring thresholds:**

```
Sections Found    Structure Present    Score   Quality
─────────────────────────────────────────────────────
< 50%             No                   0       Poor
50% - 80%         Maybe                1       Acceptable
≥ 80%             Yes                  2       Excellent
```

**Detailed logic:**
- Score 0: Less than 50% required sections AND no markdown structure
- Score 1: 50-80% sections found OR basic markdown structure (headers or lists)
- Score 2: 80% or more sections found AND proper structure (headers + lists)

**Log example:**
```
Sections matched: 75% AND Structure: Present → Score = 1
```

**How to improve:**
- Add headers (# ## ###) for sections
- Include bullet lists for key points
- Create tables for comparison data
- Organize content hierarchically

---

## 3. Provenance Quality (0-2 points)

**What it measures**: How many citations and sources are referenced in the content.

**Scoring thresholds:**

```
Citation Count    Unique Sources    Score   Quality
────────────────────────────────────────────────────
< 2               < 1               0       Poor
≥ 2               ≥ 1               1       Fair
≥ 5               ≥ 2               2       Excellent
```

**Detailed logic:**
- Score 0: Fewer than 2 citations AND fewer than 1 unique source
- Score 1: 2 or more citations OR at least 1 unique source
- Score 2: 5+ citations AND 2+ unique sources

**Citation patterns detected:**
1. Direct URLs: `https://example.com`
2. Source tags: `[Source: URL]`
3. Numeric references: `[1]`, `[2]`, etc.
4. Source links: `Source links here`
5. Citation format: `(Author, Year)` style
6. Reference format: Traditional academic

**Log example:**
```
Citations: 8, Unique sources: 3 → Score = 2 (Excellent)
```

**How to improve:**
- Include hyperlinks to sources
- Use citation format: `[Source: https://example.com]`
- Reference multiple websites
- Include publication dates
- Cite official company pages

---

## 4. Hallucination Detection (0-2 points)

**What it measures**: Whether the content contains false information or contradictions.

**Scoring thresholds:**

```
Problem Indicators    Score   Quality
──────────────────────────────────────
0                     2       Excellent (No problems)
1-2                   1       Acceptable (Minor issues)
> 2                   0       Poor (Multiple issues)
```

**Hallucination markers detected:**
1. "I don't have access to" / "I cannot provide"
2. Vague uncertainty: "unknown", "not specified"
3. Unrealistic values: "approximately infinite", "unlimited"
4. Vague intensifiers: "very large", "extremely small"
5. Contradictions between stated facts

**Log example:**
```
Markers found: 2, Contradictions: 1 → Total: 3 → Score = 0 (Poor)
```

**How to improve:**
- Verify all facts against ground truth
- Avoid vague quantifications
- Don't include speculative information
- Check for internal contradictions
- Only state facts you can verify

---

## 5. Readability (0-1 points)

**What it measures**: Whether the content is well-formatted and easy to read.

**Scoring thresholds:**

```
Structure Present?    Avg Line Length    Score   Quality
────────────────────────────────────────────────────────
Headers + Lists       30-120 chars       1       Excellent
Otherwise             Any                0       Poor
```

**Detailed logic:**
- Score 0: Missing headers OR missing lists OR line length outside 30-120 chars
- Score 1: Has headers AND has lists AND line length between 30-120 chars

**Formatting elements counted:**
- Headers: # ## ### etc.
- Bold: **text**
- Italic: *text*
- Lists: - * • bullets
- Code: ``` or `inline`

**Log example:**
```
Headers: 3, Lists: 4, Avg line: 68 chars → Score = 1 (Excellent)
```

**Ideal line length ranges:**
- < 30 chars: Too short, choppy reading
- 30-120 chars: Optimal for scannability
- > 120 chars: Too long, hard to scan

**How to improve:**
- Add section headers to organize content
- Use bullet lists for key points
- Break long paragraphs into shorter lines
- Use bold for emphasis
- Include code examples when relevant

---

## Total Score Calculation

```
Maximum possible: 14 points

Factual Accuracy:       0-3 points
Schema Compliance:      0-2 points
Provenance Quality:     0-2 points
Hallucination Detection: 0-2 points
Readability:           0-1 point
MRR (Metric):          0-2 points
─────────────────────────────────
Total:                 0-14 points
```

**Score interpretation:**
- 12-14 points: Excellent
- 10-12 points: Good
- 8-10 points: Acceptable
- 6-8 points: Needs Improvement
- < 6 points: Poor

---

## Log Reading Guide

When you see log output like:

```
================================================================================
CALCULATING: Factual Accuracy (0-3)
================================================================================
INPUT VALIDATION: Ground truth has 5 key facts
STEP 1: Analyzing coverage of key facts
------------------------------------------------------------
  Fact 1/5: "Founded in 2015" - FOUND in text
  Fact 2/5: "AI company" - FOUND in text
  Coverage = 2/5 = 40%

STEP 2: Scoring decision tree
------------------------------------------------------------
  Coverage: 40%
  Checking thresholds: < 40% (0) | 40-70% (1) | 70-90% (2) | >= 90% (3)
  
THRESHOLD RESULT: 40% falls in 40-70% range
SCORE = 1 (Fair: Basic coverage with major gaps)
================================================================================
```

**Reading this:**
1. The function calculated coverage = 40%
2. Threshold ranges are shown explicitly
3. The 40% value falls in the "40-70%" bucket
4. Therefore, score = 1 (the value assigned to that bucket)
5. The "Fair" label explains the quality level

---

## Quick Decision Trees

### Factual Accuracy Quick Decision

```
   Ask: What % of key facts are present?
        │
        ├─ < 40% → Score 0 (Poor)
        ├─ 40-70% → Score 1 (Fair)
        ├─ 70-90% → Score 2 (Good)
        └─ ≥ 90% → Score 3 (Excellent)
```

### Schema Compliance Quick Decision

```
   Ask: Does it have headers AND lists?
        │
        ├─ NO  → Score 0 (Poor)
        │
        └─ YES → Ask: Are ≥80% required sections present?
                 │
                 ├─ NO → Score 1 (Acceptable)
                 └─ YES → Score 2 (Excellent)
```

### Provenance Quality Quick Decision

```
   Ask: How many citations and sources?
        │
        ├─ < 2 citations AND < 1 source → Score 0 (Poor)
        │
        ├─ 2-4 citations OR 1 source → Score 1 (Fair)
        │
        └─ ≥ 5 citations AND ≥ 2 sources → Score 2 (Excellent)
```

### Hallucination Detection Quick Decision

```
   Ask: How many problems found?
        │
        ├─ 0 problems → Score 2 (Excellent)
        │
        ├─ 1-2 problems → Score 1 (Acceptable)
        │
        └─ > 2 problems → Score 0 (Poor)
```

### Readability Quick Decision

```
   Ask: Has headers AND lists AND 30-120 char avg lines?
        │
        ├─ YES → Score 1 (Excellent)
        │
        └─ NO → Score 0 (Poor)
```

---

## Threshold Interpretation Examples

### Example 1: Good Factual Accuracy

```
Coverage = 82% → Falls in 70-90% range → Score = 2

Why? 
- The generated text covers 82% of the key facts
- The threshold for score 2 is "70% to 90%"
- 82% is within this range
- Therefore: Score = 2 (Good, with 18% gaps)
```

### Example 2: Acceptable Schema

```
Sections: 75%, Structure: Yes → Score = 1

Why?
- 75% of required sections are present
- The text has proper headers and lists
- But score requires ≥80% sections for score 2
- Since we have 75% (not quite 80%), score = 1 (Acceptable)
```

### Example 3: Excellent Provenance

```
Citations: 7, Unique sources: 3 → Score = 2

Why?
- 7 citations ≥ 5 minimum ✓
- 3 unique sources ≥ 2 minimum ✓
- Both conditions met
- Therefore: Score = 2 (Excellent)
```

---

## FAQ: Understanding Thresholds

**Q: Why is the line length 30-120 characters?**
A: This range is optimal for reading speed and comprehension. Lines shorter than 30 chars feel choppy, and lines longer than 120 chars require more eye movement.

**Q: Can I score 1 on Readability without all formatting?**
A: No, readability requires BOTH headers AND lists. Just having headers (without lists) scores 0.

**Q: Does a typo cause hallucination score to drop to 0?**
A: Only if it represents a factual error or contradiction. A simple spelling mistake isn't a hallucination.

**Q: How are unique sources counted?**
A: By extracting URLs from the text. "https://example.com" counts as 1 unique source. If the same URL appears 3 times, it still counts as 1.

**Q: What if the text has 7 required sections but only 5 present?**
A: That's 5/7 = 71% sections. This falls in 50-80% range, so if structure is present, score = 1.

---

## Testing the Thresholds

To verify the thresholds work as expected, the logging will show:

```
Coverage = 73%
Checking thresholds: < 40% (0) | 40-70% (1) | 70-90% (2) | >= 90% (3)
73% falls in 70-90% range
SCORE = 2
```

This makes it clear exactly which bucket the value falls into and why that score was assigned.

---

## Summary

The enhanced logging makes the scoring algorithm **transparent and debuggable**:

- ✅ You see exactly what was analyzed
- ✅ You see the exact threshold ranges
- ✅ You see which bucket your value falls into
- ✅ You see the calculated score with reasoning
- ✅ You can understand how to improve each score

This enables confidence in the evaluation results and clear guidance on improvements.
