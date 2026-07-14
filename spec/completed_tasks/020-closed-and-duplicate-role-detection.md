# Completed Task: Closed and Duplicate Role Detection

## Completed Outcome

Strengthened posting history to recognize the same internship role across alternate URLs, record clearer closed or expired reasons, and keep weekly email drafts free of inactive roles.

## Implemented Files

- `src/internship_search/posting_history.py`
- `src/internship_search/email_summary.py`
- `tests/test_posting_history.py`

## Behavior

- Adds a normalized `role_key` (company, title, location) to posting history entries with backward-compatible loading for older history files.
- `deduplicate_current_postings()` merges same-role postings within a run and records `duplicate` changes in `data/posting_changes.jsonl`.
- `detect-new-postings` matches alternate URLs for the same role as `seen` or `changed` instead of `new`.
- Missing postings get explicit reasons such as "likely closed or expired" in change logs.
- Reopened roles after a missing run are recorded as `changed` with a reopen reason.
- `inactive_posting_urls()` filters inactive history entries out of weekly email candidate selection.

## CLI

No new commands. Existing workflow commands pick up the improved detection automatically:

```powershell
uv run internship-search detect-new-postings
uv run internship-search weekly-email-summary
uv run internship-search run-scheduled-collection
```

## Verification

```powershell
uv run pytest
```

Result: `128 passed`.

## Notes

URL canonicalization reuses `canonical_posting_url()` from `job_collector.py` so tracking parameters do not create false new postings. Role matching is deterministic and avoids hiding genuinely updated postings when title or location changes.

## Next Step

Continue with `022-review-ui-enhancements.md`.
