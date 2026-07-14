# Completed Task: Scheduler and Run Hardening

## Completed Outcome

Made recurring local runs easier to operate with clearer per-step summaries, partial-failure status, transient Gemini retries, and improved Windows Task Scheduler setup scripts.

## Implemented Files

- `src/internship_search/retry.py`
- `src/internship_search/scheduled_collection.py`
- `src/internship_search/ai_scoring.py`
- `src/internship_search/fit_scoring.py`
- `config/run_scheduled_collection.ps1`
- `config/windows_task_scheduler.example.ps1`
- `tests/test_retry.py`
- `tests/test_scheduled_collection.py`
- `tests/test_ai_scoring.py`

## Behavior

- `run-scheduled-collection` now records per-step results for registry, collect, detect, filter, report, score, and email.
- Run status is `success`, `partial`, or `failed`:
  - `partial` when source collection errors or AI scoring fallbacks occur
  - `failed` when a required step raises an exception
- Run logs in `data/scheduled_collection_runs.jsonl` keep existing count fields and add `steps`, `scoring_provider`, and `ai_fallback_count`.
- Gemini HTTP requests retry transient failures such as `503` with exponential backoff before falling back to local scoring.
- `config/run_scheduled_collection.ps1` wraps the workflow and writes console output to `data/scheduled_run_output/`.
- `config/windows_task_scheduler.example.ps1` registers the wrapper script with troubleshooting notes.

## CLI

Run manually with the richer summary:

```powershell
uv run internship-search run-scheduled-collection
```

Run with console logging through the wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File config/run_scheduled_collection.ps1
```

Register a recurring local Windows task:

```powershell
powershell -ExecutionPolicy Bypass -File config/windows_task_scheduler.example.ps1 -Frequency Weekly -At 09:00
```

## Troubleshooting

- Check the newest file in `data/scheduled_run_output/` for console output from scheduled runs.
- Inspect `data/scheduled_collection_runs.jsonl` for per-step status, source errors, and AI fallback counts.
- Run the wrapper script manually before registering Task Scheduler to confirm `uv` is on PATH.

## Verification

```powershell
uv run pytest
```

Result: `137 passed`.

## Next Step

No open tasks remain in the current future-task index.
