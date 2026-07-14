# Completed Task: Filter Summer 2027 Internship Postings

## Completed Outcome

Implemented a modular deterministic filter that reads first-pass posting candidates, evaluates them against Summer 2027 internship relevance rules, and writes both included and excluded results with reasons.

## Implemented Files

- `src/internship_search/posting_filter.py`
- `src/internship_search/cli.py`
- `tests/test_posting_filter.py`

## Generated Local Outputs

- `data/filtered_postings.jsonl`
- `data/excluded_postings.jsonl`

These files are generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Includes postings that clearly mention internship-related terms.
- Prefers Summer 2027 and early-career terms when available.
- Excludes postings that match disliked terms, including marketing and social media.
- Records reasons for both included and excluded postings.
- Keeps filtering rules in one module so they are easy to update.

## CLI

Use this command to filter collected posting candidates:

```powershell
uv run internship-search filter-postings
```

## Latest Local Run

- Included postings: 4
- Excluded postings: 19

## Notes

This is a deterministic first-pass filter. It does not yet use AI, and it does not verify full posting page details. The next task should generate a review report that makes included and excluded results easier to inspect.

## Verification

```powershell
uv run pytest
```

Result: `17 passed`.
