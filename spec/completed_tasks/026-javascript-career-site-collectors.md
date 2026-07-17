# Completed Task: JavaScript Career Site Collectors

## Goal

Collect internships from JavaScript-heavy seed company sites that previously returned zero postings.

## Implemented Collectors

- **Consider / Bakar board** — POSTs to `jobs.bakarlabs.org/api-boards/search-jobs`, caches board results per host, and filters jobs by tenant company name.
- **PwC jobs portal** — Parses `/job/` links from `jobs-us.pwc.com` search results.
- **BlackRock search results** — Parses structured `section3__search-results-a` HTML in addition to `/job/` paths and full job URLs.

## Other Improvements

- Clearer Consider-board warnings distinguish empty boards, companies without jobs, and companies with jobs but no internship matches.
- PwC seed metadata now points at the live search-results URL with `pwc_jobs` collector.
- Bain alternate URL added for the `careers.bain.com` recruits portal.
- McKinsey fetch timeout increased to 60s with retry on source fetch.
- Added tests with mocked Consider API responses and saved HTML fixtures.

## Verification

```powershell
uv run pytest tests/test_career_collectors.py -q
```

Live checks during implementation:

- Example source: multiple target-cycle intern postings from a public careers site
- Bakar tenant (Glyphic Biotechnologies): Consider API returned company jobs with a clear no-internship warning
- BlackRock, Bain, McKinsey: still partially JavaScript-rendered; BlackRock direct `/job/` URLs and registry alternates continue to work

## Notes

- Bakar tenants share one Consider board; collection is cached so all tenant sources reuse one API call per run.
- Bain and McKinsey still need future browser automation or ATS-specific collectors for full coverage.
- Browser automation remains optional and was not introduced in this task.
