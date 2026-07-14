# Completed Task: Job Board Search

## Completed Outcome

Added a modular job-board search layer that returns posting candidates compatible with the existing collection, filter, scoring, and detection pipeline.

## Implemented Files

- `src/internship_search/job_board_search.py`
- `src/internship_search/job_collector.py`
- `src/internship_search/cli.py`
- `src/internship_search/scheduled_collection.py`
- `.env.example`
- `tests/test_job_board_search.py`
- `tests/test_scheduled_collection.py`

## Behavior

- Adds a dedicated `search-job-boards` CLI command separate from `internet-search` and company discovery.
- Supports two providers:
  - `adzuna` when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set
  - `duckduckgo_job_board` fallback using site-focused internship queries
- Writes intermediate results to `data/job_board_postings.jsonl`.
- `collect --include-job-boards` and `run-scheduled-collection --include-job-boards` merge job-board postings into `data/postings.jsonl`.
- Merges deduplicate by canonical posting URL so tracking parameters do not create duplicates.
- Converts job-board hits into the existing `JobPosting` schema for downstream filter, score, and detect steps.

## CLI

Search job boards only:

```powershell
uv run internship-search search-job-boards
```

Merge job-board results during collection:

```powershell
uv run internship-search collect --include-job-boards
uv run internship-search run-scheduled-collection --include-job-boards
```

## Environment Variables

- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`
- `ADZUNA_COUNTRY` - defaults to `us`
- `JOB_BOARD_PROVIDER` - `auto`, `adzuna`, or `duckduckgo_job_board`

## Verification

```powershell
uv run pytest
```

Result: `124 passed`.

## Notes

Adzuna is the structured first provider. DuckDuckGo job-board queries provide a no-key fallback focused on ATS domains such as Greenhouse, Lever, and Workday.

## Next Step

Continue with `021-scheduler-and-run-hardening.md` or `022-review-ui-enhancements.md`.
