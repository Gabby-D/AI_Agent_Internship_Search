# Completed Task: Adzuna Job Board Configuration

## Status

**Superseded.** Adzuna support was removed after implementation. Job-board search now uses DuckDuckGo only.

## Original Goal

Make structured Adzuna job-board search easy to enable for better internship coverage.

## What Was Built (later removed)

- Adzuna API provider, `auto` composite mode, and related env vars/docs
- Fallback behavior when Adzuna failed

## Current Behavior

- `get_job_board_provider()` always returns `DuckDuckGoJobBoardProvider`
- No `ADZUNA_*` or `JOB_BOARD_PROVIDER` variables in `.env.example`
- `search-job-boards` and `collect --include-job-boards` use DuckDuckGo `site:` queries only

## Verification

```powershell
uv run pytest tests/test_job_board_search.py -q
uv run internship-search search-job-boards
```
