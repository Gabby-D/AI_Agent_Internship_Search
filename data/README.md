# Generated Data

Use this directory for generated search results, cached job postings, scoring outputs, and weekly summaries.

Generated files in this directory are ignored by git by default.

Current generated files:

- `source_registry.json` contains local company career-source metadata built from seed companies.
- `discovered_companies.json` contains reviewable similar-company suggestions.
- `discovered_companies.md` contains a readable review report for suggested companies.
- `postings.jsonl` contains first-pass posting candidates collected from the source registry.
- `posting_history.json` contains stable posting history with first-seen and last-seen dates.
- `posting_changes.jsonl` contains the latest run's new, seen, changed, and missing status records.
- `new_postings.jsonl` contains postings discovered for the first time in the latest run.
- `filtered_postings.jsonl` contains included posting candidates with inclusion reasons.
- `excluded_postings.jsonl` contains excluded posting candidates with exclusion reasons.
- `latest_report.md` contains the readable local review report.
- `scored_postings.jsonl` contains fit scores, fit levels, explanations, and gaps for filtered postings.
- `weekly_email_summary.md` contains the local email-ready weekly summary draft.
- `email_sent_history.json` contains posting URLs already included in weekly email summaries.
- `scheduled_collection_runs.jsonl` contains append-only run logs for manual or scheduled workflow runs.
- `scheduled_run_output/` contains console logs from `config/run_scheduled_collection.ps1`.
- `posting_reviews.json` contains posting review status such as interested, applied, ignored, or needs follow-up.
- `ui_preferences.json` contains likes and dislikes edited through the local review UI.
