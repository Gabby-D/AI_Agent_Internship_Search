# Completed Task: Improved Career Page Collectors

## Completed Outcome

Added modular source-specific career page collectors, registry enrichment from internet-search results, and clearer per-source collection warnings for difficult sites such as BlackRock, Bakar Bio Labs, and McKinsey.

## Implemented Files

- `src/internship_search/career_collectors.py`
- `src/internship_search/registry_enrichment.py`
- `src/internship_search/job_collector.py`
- `src/internship_search/source_registry.py`
- `src/internship_search/cli.py`
- `tests/test_career_collectors.py`
- `tests/test_registry_enrichment.py`
- `tests/test_job_collector.py`
- `tests/test_source_registry.py`

## Behavior

- Routes collection through source-aware strategies instead of only generic anchor parsing.
- Adds a BlackRock collector that extracts `/job/` links from search-result HTML and builds titles from job slugs.
- Adds JSON-LD and embedded JSON collectors for structured job data when present.
- Adds a Consider job-board collector path for Bakar Bio Labs with a clear JavaScript-rendered warning when static HTML has no postings.
- Tries alternate careers URLs per source before giving up.
- Treats direct `/job/` careers URLs as posting candidates without fetching the page again.
- Enriches registry careers URLs from saved `internet-search` results via `--enrich-from-search`.
- Records per-source warnings and fetch failures without stopping the full collection run.
- Uses longer fetch timeouts for slow McKinsey pages.

## Updated Seed Metadata

- BlackRock now uses `search-jobs?keywords=2027%20intern` as the primary careers URL.
- McKinsey now uses `search-jobs?keywords=intern` with the undergraduate page as an alternate URL.
- Bakar Bio Labs uses the `consider_board` collector strategy.

## CLI

Rebuild the registry with search enrichment:

```powershell
uv run internship-search build-source-registry --enrich-from-search data/internet_search_results.jsonl
```

Collect with search enrichment:

```powershell
uv run internship-search collect --enrich-from-search data/internet_search_results.jsonl
```

## Verification

```powershell
uv run pytest
```

Result: `97 passed`.

## Latest Local Run

- BlackRock: no false-positive blog links; alternate direct job URLs can be collected without fetching HTML.
- Bakar Bio Labs: clear warning that the React job board has no static postings.
- McKinsey & Co: clearer timeout errors for both primary and alternate careers URLs.

## Notes

Browser automation was intentionally deferred. Bakar Bio Labs still needs a future API or Playwright-based collector if static extraction remains insufficient.

## Next Step

Continue with `017-specific-job-listing-filter.md` refinements and `021-scheduler-and-run-hardening.md` for recurring run improvements.
