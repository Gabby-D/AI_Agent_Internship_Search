# Completed Task: Scheduled Collection

## Completed Outcome

Implemented a repeatable local workflow command that can be run manually or attached to Windows Task Scheduler for daily or weekly collection.

## Implemented Files

- `src/internship_search/scheduled_collection.py`
- `src/internship_search/cli.py`
- `tests/test_scheduled_collection.py`
- `config/windows_task_scheduler.example.ps1`

## Generated Local Outputs

- `data/scheduled_collection_runs.jsonl`
- Existing pipeline outputs under `data/`, including postings, history, filtered postings, report, scores, and weekly email draft.

These files are generated locally and ignored by git through the existing `data/` ignore rule.

## Behavior

- Rebuilds the source registry from private seed companies.
- Collects posting candidates from registered career sources.
- Updates posting history and new-posting outputs.
- Filters included and excluded postings.
- Regenerates the local Markdown review report.
- Scores included postings.
- Generates the weekly email draft only after the previous workflow steps complete.
- Appends a local run log with status, counts, source errors, and warnings.
- Leaves scheduling optional: the workflow can be run manually or registered with Windows Task Scheduler.

## CLI

Run the workflow manually:

```powershell
uv run internship-search run-scheduled-collection
```

Run without generating the weekly email draft:

```powershell
uv run internship-search run-scheduled-collection --skip-email
```

## Windows Task Scheduler

Use `config/windows_task_scheduler.example.ps1` as a starting point for local automation.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File config/windows_task_scheduler.example.ps1 -Frequency Weekly -At 09:00
```

```powershell
powershell -ExecutionPolicy Bypass -File config/windows_task_scheduler.example.ps1 -Frequency Daily -At 09:00
```

## Latest Local Run

- Status: success.
- Posting candidates collected: 23.
- Source errors: 1.
- New postings: 0.
- Included postings: 4.
- Excluded postings: 19.
- Scored postings: 4.
- Email draft postings: 0.
- Warning: McKinsey & Co timed out during collection.

## Verification

```powershell
uv run pytest
```

Result: `34 passed`.
