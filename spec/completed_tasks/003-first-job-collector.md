# Completed Task: Implement First Job Collector

## Completed Outcome

Implemented a modular first-pass job collector that fetches company career source pages, extracts likely posting links, deduplicates by posting URL, and writes local JSONL output.

## Implemented Files

- `src/internship_search/job_collector.py`
- `src/internship_search/cli.py`
- `tests/test_job_collector.py`

## Generated Local Output

- `data/postings.jsonl`

This file is generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Reads company sources from `data/source_registry.json`.
- Fetches each source URL with a standard-library HTTP client.
- Extracts likely posting candidates from job-like links.
- Writes structured records with title, company, location, posting URL, collection date, and source URL.
- Deduplicates output by posting URL.
- Continues collecting from other companies if one source fails.

## CLI

Use this command to collect posting candidates:

```powershell
uv run internship-search collect
```

## Latest Local Run

- Posting candidates collected: 23
- Source errors: 1
- Timed out source: McKinsey & Co

## Notes

This is a first-pass collector. Some records are still broad posting candidates rather than confirmed target-cycle internships. The next task should filter and explain relevance.

## Verification

```powershell
uv run pytest
```

Result: `13 passed`.
