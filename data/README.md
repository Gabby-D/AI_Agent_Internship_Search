# Generated Data

Use this directory for generated search results, cached job postings, scoring outputs, and weekly summaries.

Generated files in this directory are ignored by git by default. Some contain personal notes, search history, application state, or email metadata; do not force-add them to git.

Current generated files:

- `source_registry.json` contains local company career-source metadata built from seed companies.
- `discovered_companies.json` contains reviewable similar-company suggestions.
- `company_dismissals.json` contains dismissed company recommendations to prevent them from reappearing in UI suggestions.
- `discovered_companies.md` contains a readable review report for suggested companies.
- `internet_search_results.jsonl` contains structured careers-page search results.
- `job_board_postings.jsonl` contains posting candidates found through public job-board search results.
- `postings.jsonl` contains first-pass posting candidates collected from the source registry.
- `collection_errors.jsonl` contains source collection failures from the latest collection run.
- `posting_history.json` contains stable posting history with first-seen and last-seen dates.
- `posting_changes.jsonl` contains the latest run's new, seen, changed, and missing status records.
- `new_postings.jsonl` contains postings discovered for the first time in the latest run.
- `filtered_postings.jsonl` contains included posting candidates with inclusion reasons.
- `excluded_postings.jsonl` contains excluded posting candidates with exclusion reasons.
- `monitored_no_openings.jsonl` contains seed companies that have no specific matching opening or could not be checked.
- `latest_report.md` contains the readable local review report.
- `scored_postings.jsonl` contains fit scores, fit levels, explanations, and gaps for filtered postings.
- `weekly_email_summary.md` contains the local email-ready weekly summary draft.
- `email_sent_history.json` contains posting URLs included in successfully sent email summaries.
- `scheduled_collection_runs.jsonl` contains append-only run logs for manual or scheduled workflow runs.
- `scheduled_run_output/` contains console logs from the scheduled-collection and weekly-email wrapper scripts.
- `posting_reviews.json` contains posting review status: to review, applied, not interested, or archived.
- `posting_notes.json` contains local personal notes keyed by posting URL.
- `activity_log.jsonl` contains dated, append-only local UI activity records.
- `ui_preferences.json` is a legacy local preferences cache; the review UI edits `private/preferences.md`.

Most JSONL files contain one JSON object per line. Files described as “latest run” are replaced on the next run; history, sent-history, review-state, note, dismissal, activity-log, and scheduler-log files persist across runs.
