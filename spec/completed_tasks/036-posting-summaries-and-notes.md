# Posting Summaries and Notes

## Completed outcome

Added an expandable **Summary & notes** area to every internship row in the Postings tab.

## Delivered behavior

- Concise summary from the role title, company, and location.
- Highlights sourced from fit-scoring explanations or collection reasons when scoring is unavailable.
- Editable notes saved locally by posting URL in `data/posting_notes.json`.
- Note additions, changes, and clears are recorded in the dated activity log.

## Verification

- Added coverage for notes persistence, clearing notes, dashboard summary payloads, and the new UI controls.
- `uv run pytest tests/test_review_ui.py` passes.
