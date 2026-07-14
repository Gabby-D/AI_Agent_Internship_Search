# Completed Task: Posting Metadata Enrichment

## Goal

Improve posting quality in reports, scoring, and the review UI by filling in company names and locations more reliably.

## Implemented

- Added `posting_metadata.py` for deterministic title, company, and location enrichment.
- Parses Greenhouse `Job Application for ... at ...` titles into separate role titles and company names.
- Infers company names from Greenhouse and Lever board slugs in posting URLs.
- Fetches location/title/company from public Greenhouse and Lever APIs when writing `postings.jsonl`.
- Extracts locations from job-board snippets (for example `Location: Boston, MA`).
- Merges richer metadata when deduplicating postings by canonical URL.
- Updated PwC/Adzuna/LinkedIn/Indeed company inference to use the shared metadata helpers.

## Pipeline Integration

- `job_board_search.py` — normalizes titles and companies at search-result conversion time.
- `job_collector.py` — local enrichment during merge; API enrichment when writing JSONL output.
- Metadata flows through existing filter, scoring, report, and review UI paths unchanged.

## Verification

```powershell
uv run pytest tests/test_posting_metadata.py -q
```

Live check during implementation: Greenhouse API returned `Virtu Financial` / `New York` for a sample Virtu posting URL.

## Notes

- API enrichment runs on write, not during in-memory merge, to keep collection fast and tests offline-friendly.
- Canonical URL deduplication and posting history behavior are unchanged.
