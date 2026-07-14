# Completed Task: Create Local Results Review

## Completed Outcome

Implemented a modular Markdown report generator that reads filtered posting outputs and source registry metadata, then writes a readable local review report.

## Implemented Files

- `src/internship_search/review_report.py`
- `src/internship_search/cli.py`
- `tests/test_review_report.py`

## Generated Local Output

- `data/latest_report.md`

This file is generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Groups included postings by company.
- Shows title, location, posting URL, collected date, and relevance reasons.
- Highlights whether a company has a known connection from the source registry.
- Summarizes excluded posting counts by company.
- Includes questions and missing information for future improvements.
- Avoids resume text, credentials, and private personal notes.

## CLI

Use this command to generate the local review report:

```powershell
uv run internship-search report
```

## Latest Local Run

- Included postings: 4
- Excluded postings: 19
- Companies with included postings: 3

## Notes

The first local collection, filtering, and review flow is now complete. The next useful work should be planned from the future task list, such as new posting detection, AI fit scoring, internet search provider work, or better source-specific collectors.

## Verification

```powershell
uv run pytest
```

Result: `19 passed`.
