# Completed Task: Specific Job Listing Filter

## Completed Outcome

Strengthened deterministic listing classification so generic program pages, search pages, and blog stories are excluded with explicit reasons while specific internship postings remain included.

## Implemented Files

- `src/internship_search/internship_listing.py`
- `src/internship_search/posting_filter.py`
- `src/internship_search/review_report.py`
- `tests/test_internship_listing.py`
- `tests/test_posting_filter.py`
- `tests/test_review_report.py`

## Behavior

- Adds `classify_internship_listing()` with explicit categories:
  - `specific_listing`
  - `generic_program_page`
  - `generic_search_page`
  - `blog_or_story`
  - `not_internship`
- Uses word-boundary internship matching so words like `internal` no longer count as internships.
- Excludes generic URLs such as `/search-jobs`, `/students/`, `/work-with-us/`, and `/blog`.
- Excludes long narrative titles that look like page copy rather than job titles.
- Keeps specific `/job/` and role-based internship titles included.
- Writes clearer inclusion and exclusion reasons into filtered JSONL output.
- Adds an `Excluded By Listing Type` section to the review report.

## CLI

No new commands. Existing workflow:

```powershell
uv run internship-search filter-postings
uv run internship-search report
```

## Verification

```powershell
uv run pytest
```

Result: `104 passed`.

## Sample Outcomes

- Included: `2027 Summer Internship Program Amers` with a BlackRock `/job/` URL.
- Excluded: Bain `Internships & Programs`, PwC search pages, Bakar resource pages.
- Excluded: BlackRock employee story/blog pages that mention `internal mobility`.

## Notes

Generic program pages remain excluded from included results, but monitored companies still track seed employers with no specific openings.

## Next Step

Continue with `021-scheduler-and-run-hardening.md` or `022-review-ui-enhancements.md`.
