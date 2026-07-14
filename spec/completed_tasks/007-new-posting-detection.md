# Completed Task: New Posting Detection

## Completed Outcome

Implemented a modular posting history tracker that detects whether collected postings are new, seen before, changed, or no longer available.

## Implemented Files

- `src/internship_search/posting_history.py`
- `src/internship_search/cli.py`
- `tests/test_posting_history.py`

## Generated Local Outputs

- `data/posting_history.json`
- `data/posting_changes.jsonl`
- `data/new_postings.jsonl`

These files are generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Uses canonical posting URLs as stable posting identifiers.
- Removes URL fragments and sorts query parameters for stable IDs.
- Tracks `first_seen`, `last_seen`, and active status.
- Marks postings as `new`, `seen`, `changed`, or `missing`.
- Deduplicates repeated current postings by canonical URL.
- Writes newly discovered postings separately for future reports or emails.

## CLI

Use this command after collection:

```powershell
uv run internship-search detect-new-postings
```

## Latest Local Runs

- First history run: 22 new postings.
- Second history run with the same current data: 22 seen postings, 0 new postings.

## Verification

```powershell
uv run pytest
```

Result: `28 passed`.
