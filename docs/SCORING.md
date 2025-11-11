# Scoring rules for discover_links.py

This document explains exactly how candidate link `score` values are computed in `src/discover/discover_links.py`.

## High-level

The scoring logic is implemented in the function `score_candidate(url, link_text, page_type, homepage_url)`. The function returns a numeric score built from multiple heuristics:

- Domain match bonus/penalty (same company domain vs external)
- Page-type-specific bonuses and penalties based on path keywords and link text
- Special-case penalties (e.g., industry vertical product pages)
- Query-length and path-depth heuristics
- Immediate rejects (skip patterns)
- Manual overrides (assign a very large score)

Note: There are top-level constants (e.g., `SCORE_HOMEPAGE`, `SCORE_ABOUT`, ...) that are declared but not used directly in the scoring function.

## Detailed scoring rules

1. Skip patterns
   - If any substring from `SKIP_PATTERNS` appears in the URL path or hostname, the candidate is rejected immediately with a score of `-1000`.

2. Domain match
   - Extract `base_domain` from the `homepage_url` (last two labels of the netloc).
   - If `base_domain` appears in the candidate link's hostname: +40 points.
   - Otherwise (external site): -50 points.

3. Page-type specific scoring
   - about:
     - Each `ABOUT_KEYWORDS` match in the path: +80 per match.
     - Each `ABOUT_TEXT` match in link text: +60 per match.

   - product:
     - Any `PRODUCT_PENALTY_PATTERNS` match in path: -100 per match (strong penalty).
     - Each `PRODUCT_KEYWORDS` match in path: +70 per match.
     - Each `PRODUCT_TEXT` match in link text: +50 per match.
     - If path is exactly one of `"/product"`, `"/platform"`, `"/products"`, or empty string: +150 bonus.

   - careers:
     - If `"/team"` in path: -80 (penalize team pages for careers search).
     - If path equals one of `"/careers"`, `"/jobs"`, `"/join-us"`: +150.
     - Each `CAREERS_KEYWORDS` match in path: +60 per match.
     - Each `CAREERS_TEXT` match in link text: +40 per match.
     - Recruiting platforms (hostnames containing `ashby`, `lever`, or `greenhouse`):
       - If hosted on a different base domain than the company: -30 penalty.
       - Also add a +50 bonus (so external recruiting links typically net +20, internal-hosted recruiting paths get +50).

   - blog:
     - Each `BLOG_KEYWORDS` match in path: +50 per match.
     - Each `BLOG_TEXT` match in link text: +30 per match.

4. Query string length penalty
   - If the URL query string length (`parsed.query`) is greater than 100 characters: -30.

5. Path depth preference
   - If `path.count('/') <= 2`: +20 (prefer short paths).
   - Else if `path.count('/') <= 4`: +5 (small preference).

6. Candidate filtering
   - `discover_candidates_from_page()` only keeps candidates with `score > -100` (very negative candidates are dropped early).
   - `probe_common_paths()` will still record probed URLs with their scores.

7. Selection logic in `discover_page_links()`
   - Candidates are sorted by score (descending), then by URL as tiebreaker.
   - If the top candidate's score > 0 => it is selected.
   - If top score is between -50 and 0 inclusive => it may still be used but with a warning.
   - If top score < -50 => treated as unacceptable and `None` is returned (with a short candidate list for inspection).

8. Manual overrides
   - If a manual override exists in `src/discover/manual_overrides.json` for a company + page type, that override URL is used and stored with `score: 1000`.

## Example breakdown

Candidate:
- URL: `https://example.com/careers`
- Company homepage: `https://example-company.com`
- Link text: `Careers`

Scoring contributions (approx):
- Domain mismatch (external): -50
- Path exactly `/careers`: +150
- Path keyword match: +60
- Link text match: +40
- Short path bonus (depth <= 2): +20

Total ≈ -50 + 150 + 60 + 40 + 20 = 220

If that careers page were on `example-company.com`, the domain contribution would be +40 instead of -50 and the total would be ≈ 310.

## Where to find the code

- Main scoring: `src/discover/discover_links.py` -> function `score_candidate(...)`.
- Candidate extraction and filtering: `discover_candidates_from_page(...)`.
- Probing common paths: `probe_common_paths(...)`.
- Selection and acceptance thresholds: `discover_page_links(...)`.

## Notes and small improvements to consider

- The `SCORE_*` constants at the top of the file are unused and could be removed or wired into the scoring logic to centralize weights.
- The `normalize_url()` function removes tracking params listed in `TRACKING_PARAMS` (useful for deduplication).
- The script applies a hard reject (`-1000`) for `SKIP_PATTERNS` — if you want to surface more candidates for inspection, consider lowering that to a large negative value but not an absolute reject.

---

If you'd like, I can:
- Add a per-candidate scoring trace (which rule added/subtracted which points) and store it alongside the `discovered_pages` output for debugging.
- Move this markdown to another location (for example the repo `README.md`) or append it to an existing docs file.

Tell me which option you prefer and I will apply it.