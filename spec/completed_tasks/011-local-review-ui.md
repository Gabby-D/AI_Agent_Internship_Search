# Completed Task: Local Review UI

## Completed Outcome

Implemented a simple local browser dashboard for reviewing internship postings, marking review status, and editing preferences without manually editing Markdown files.

## Implemented Files

- `src/internship_search/review_state.py`
- `src/internship_search/review_ui.py`
- `src/internship_search/cli.py`
- `tests/test_review_ui.py`

## Generated Local Outputs

- `data/posting_reviews.json`
- `data/ui_preferences.json`

These files are generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Shows included and excluded postings from local generated data files.
- Shows score, fit level, connection status, and posting links when available.
- Lets the user mark postings as `interested`, `applied`, `ignored`, or `needs_follow_up`.
- Loads default preferences from `private/preferences.md`.
- Saves edited preferences to `data/ui_preferences.json`.
- Uses Python's standard library HTTP server only, with no extra UI dependencies.

## CLI

Start the local review UI:

```powershell
uv run internship-search review-ui
```

Then open:

`http://127.0.0.1:8765`

Optional custom host or port:

```powershell
uv run internship-search review-ui --host 127.0.0.1 --port 8765
```

## Verification

```powershell
uv run pytest
```

Result: `43 passed`.
