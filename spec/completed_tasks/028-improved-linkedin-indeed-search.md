# Completed Task: Improved LinkedIn and Indeed Search

## Goal

Increase useful internship coverage from LinkedIn and Indeed beyond the current DuckDuckGo site-query fallback.

## Implemented

- Added `job_board_listings.py` for LinkedIn and Indeed URL normalization, listing detection, and platform counting.
- Expanded DuckDuckGo default queries with additional LinkedIn and Indeed `site:` variants for the target internship cycle.
- DuckDuckGo provider now runs all default query templates instead of stopping early when ATS results fill the quota.
- Canonical posting URLs normalize LinkedIn job IDs and Indeed `jk` parameters for stable deduplication.
- `merge_posting_candidates` applies role-key deduplication so career-page URLs win over LinkedIn/Indeed duplicates.
- `select_preferred_posting` prefers company career sources and direct ATS URLs over aggregator listings.
- `JobBoardSearchResponse` records platform counts and provider limitations in search and collection summaries.

## Design Decision

Official LinkedIn and Indeed APIs are not used. The no-credentials DuckDuckGo fallback remains the supported path for local scheduled collection. Logged-in-only listings are documented as out of scope.

## Verification

```powershell
uv run pytest tests/test_job_board_listings.py tests/test_job_board_search.py -q
```

## Notes

- Provider limitations appear in `search-job-boards` output and scheduled collection logs when LinkedIn or Indeed return zero listings.
- Cross-source dedup uses existing `role_key` matching from `posting_history.py`.
