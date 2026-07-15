# Live Workflow Validation

## Completed outcome

Ran the full live workflow with job-board search on July 15, 2026. The workflow completed with a partial status because several external career sources are JavaScript-rendered, unavailable, or timed out; all required pipeline stages completed and local run details were recorded.

## Live validation result

- Registered 70 monitored career sources.
- Collected 12 posting candidates.
- Included 1 location-safe role and excluded 11 roles outside the location policy.
- Scored the included role with Gemini and generated a local email draft without sending email.
- Dashboard API returned the included role and correctly retained the Bay Area/Israel/fully-remote policy message.

### Included role

- **Relling — Business Operations Intern**
  - Location: San Francisco, CA, US
  - Source: official Y Combinator jobs page
  - URL: `https://www.ycombinator.com/companies/relling/jobs/ZFJwHfg-business-operations-intern`

## Fix applied during validation

The Relling collector initially extracted the role with an `Unknown` location, causing the deterministic location filter to exclude it. Added a Y Combinator collector that reads the page's embedded job data and preserves the official listing location. The retry then included the San Francisco role without weakening the location policy.

## External-source diagnostics

- 73 source warnings were recorded in `data/collection_errors.jsonl`.
- Most Bakar tenant warnings accurately report no current jobs or no internship-specific jobs on the shared Consider board.
- Several company sites are JavaScript-rendered or have unsupported layouts (for example, Bain, Bluevine, Robinhood, Patreon, Shield AI, and CrowdStrike); their diagnostics identify the source and failure mode for future collector work.
- McKinsey requests timed out or closed the remote connection; Levi's had a DNS lookup failure; Ripple returned an HTTP 308 redirect.
- LinkedIn and Indeed search remains best-effort through public DuckDuckGo indexing and did not return direct listing URLs in this run.

## Acceptance checks

- [x] Workflow completed and recorded its run details in `data/scheduled_collection_runs.jsonl`.
- [x] Included roles satisfy the Bay Area, Israel, or fully remote location policy.
- [x] Dashboard contains no disallowed-location role; its empty-state policy message is served when no qualifying roles exist.
- [x] Failed sources have a specific diagnostic in `data/collection_errors.jsonl` or a documented no-openings status in `data/monitored_no_openings.jsonl`.

## Verification

```powershell
uv run pytest tests/test_career_collectors.py tests/test_source_registry.py tests/test_location_filter.py
```

Result: 22 passed.
