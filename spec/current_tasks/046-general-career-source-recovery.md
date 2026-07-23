# Current Task 046: General Career-Source Recovery

Develop a clean, reusable recovery path for company career sources that return
403 responses, stale URLs, JavaScript-only shells, or unsupported layouts.
Use RTX as the first case study, then apply the proven platform-level approach
to other affected companies one at a time.

## Goals

- Determine the actual cause of each source failure before changing collectors.
- Prefer public recruiting-platform APIs and structured endpoints over browser
  automation.
- Keep platform behavior reusable and company-specific details in configuration.
- Preserve complete pagination, undergraduate filtering, private location
  preferences, source diagnostics, and email reporting.
- Never bypass authentication, CAPTCHAs, or anti-bot controls.

## Decision Order

1. Verify the official careers URL and reproduce the failure.
2. Classify it as an incorrect URL, access restriction, dynamic rendering,
   unsupported layout, or upstream outage.
3. Identify the recruiting platform from public page configuration, DNS,
   scripts, sitemaps, or job-detail pages.
4. Use a documented or publicly exposed structured endpoint when available.
5. Otherwise use structured HTML, an official sitemap, or another official URL.
6. Consider optional browser-assisted discovery only when no stable public
   interface exists; do not make browser automation part of unattended runs.
7. If collection remains incomplete, retain an actionable source diagnostic
   rather than silently treating the company as searched.

## Phase One: RTX

1. Record the response and relevant public headers from RTX's configured search
   URL.
2. Identify the recruiting platform and a stable public data interface.
3. Prove complete pagination using an internship-focused query.
4. Reuse the existing platform collector where possible, with RTX-specific
   values confined to the source registry.
5. Run an RTX-only live collection and confirm that all result pages are read.
6. Confirm graduate-only roles remain excluded by the normal eligibility
   filters.
7. Re-evaluate this plan if the public interface is unavailable, incomplete, or
   materially less stable than the alternatives.

## RTX Findings

- The official search and internship-result pages return HTTP 403 from
  Cloudflare to unattended requests.
- Public RTX job-detail and campus pages remain accessible.
- RTX uses Phenom, and the campus page exposes the same public widget
  configuration required by the existing reusable `phenom_api` collector.
- A live API pagination check on 2026-07-23 returned 10 internship/co-op
  records. No browser automation or anti-bot bypass was required.
- The implementation direction therefore changed from adding a new RTX
  collector to a source-configuration repair that reuses the existing Phenom
  adapter.
- The blocked search page is not retained as an alternate collection URL,
  because doing so would create a false source warning after a successful scan.

## Follow-up Source Findings

### Ayar Labs

- The company careers page embeds a Paycor Recruiting board.
- A reusable `paycor_html` collector reads the complete public `CareerHome`
  listing and treats an empty internship result as a successful scan.
- Live validation found no current internship or co-op titles and no source
  errors.

### Form Energy

- The company open-jobs wrapper embeds the public Form Energy Ashby board and
  can intermittently return HTTP 403.
- Source configuration now points directly to the Ashby board so the existing
  reusable `ashby_api` collector can scan the complete result set.
- Live validation found no current internship or co-op titles and no source
  errors.

### SpaceX

- The existing public Greenhouse source successfully enumerates all current
  internship and co-op records.
- Flexible multi-site records keep their location list in the job description,
  so location filtering now consults description text when the structured
  location is generic.
- Explicit graduate-program requirements take precedence over incidental
  bachelor's-degree text.
- Live validation collected four internship/co-op records, included the one
  matching undergraduate and private location requirements, excluded the
  graduate-engineer role, and reported no source errors.

### CrowdStrike

- CrowdStrike's official careers board uses Workday.
- The earlier HTTP 400 was caused by requesting 100 records per page; this
  Workday tenant accepts at most 20. The reusable Workday collector now uses
  the supported page size and continues until the reported total is reached.
- Live validation collected one current internship record and reported no
  source errors.

### Bank of America

- The official student job-search page exposes a structured public campus-jobs
  feed with a total count, program type, description, location, and stable job
  URL.
- A reusable collector pages that feed to completion and identifies
  internships from both the title and structured program type.
- Live validation read all 71 campus records, identified 65 internship or
  summer-analyst records for downstream location and undergraduate filtering,
  and reported no source errors.

### Bayer

- Bayer's official jobs portal is a server-rendered SAP SuccessFactors board.
- A reusable bounded paginator reads each 10-record result page, uses the
  portal's reported total as its stopping condition, and extracts structured
  job rows without following unrelated pagination links.
- Live validation read all 678 current jobs across 68 pages, identified five
  internship titles for downstream filtering, and reported no source errors.

### Berkeley Research Group

- BRG's official careers page links to its public Workday board.
- The repaired reusable Workday pagination applies without a company-specific
  scraper.
- Live validation collected three current internship records and reported no
  source errors.

### Bolt Threads

- The current official site states that the company is no longer operating.
- A reusable closure-page collector verifies that statement before treating
  the source as a successful scan with zero openings. If the notice changes or
  disappears, the scan reports an issue rather than assuming the company is
  still closed.

### Clif Bar and Company

- Clif Bar's official careers page routes recruiting to parent company
  Mondelēz and its public Workday site.
- The Workday collector now supports the `myworkdaysite.com/recruiting`
  URL shape and optional company search text, then pages the complete Clif
  result set.
- Live validation found no current Clif internship titles and no source error.

### Deloitte

- Deloitte's official US internship search is hosted on Avature and exposes a
  complete filtered RSS feed.
- A reusable Avature feed collector reads every item and retrieves each job
  detail page for its full location list and eligibility text.
- The specific-listing classifier now recognizes Avature `/JobDetail/` URLs.
- Live validation found one current US internship record, including San
  Francisco among its listed locations, and no source error.

### Earth Mine / Nokia

- Nokia's official jobs portal uses Oracle Recruiting Cloud and exposes the
  API host and career-site number in its public page.
- A reusable Oracle collector requests 25 records at a time, advances offsets
  until the API's total is reached, and filters internship/co-op titles
  locally.
- Live validation paged all 219 keyword matches, identified 17 internship or
  co-op records for downstream filtering, and reported no source error.

### Everstream Analytics

- Everstream's official careers page identifies its public Greenhouse board.
- Source configuration now uses that board directly with the existing
  complete Greenhouse collector.
- Live validation found one current internship record and no source error.

## Handoff Snapshot (2026-07-23)

This section is the continuation point for another AI agent. The work described
above is implemented on `main`; use the commit containing this spec as the safe
Git checkpoint.

### Verified Current State

- The standard package test suite passes: `274 passed`.
- The one-click Windows executable was rebuilt from the current source and
  started successfully at `http://127.0.0.1:8765/`.
- The Companies page includes a `Latest scan` column. It distinguishes a
  working source (including a valid zero-opening result) from a source issue.
- The latest full local workflow registered 116 companies, collected 241
  internship candidates, retained 18 after preference filtering, and recorded
  28 source-error entries. Generated results remain local and Git-ignored.
- No email was sent during the verification run.
- No private input, generated output, credential, resume, email address,
  personal location, or detailed internship preference belongs in this spec or
  any tracked file.

### Latest Results for the Five Most Recent Sources

| Company | Complete source | Collected | Relevant after private filters | Source issue |
| --- | --- | ---: | ---: | --- |
| Bolt Threads | Verified official closure page | 0 | 0 | No |
| Clif Bar and Company | Mondelēz Workday search for Clif | 0 | 0 | No |
| Deloitte | Filtered Avature RSS plus job details | 1 | 1 | No |
| Earth Mine / Nokia | Oracle Recruiting API with complete offsets | 16 unique | 0 | No |
| Everstream Analytics | Greenhouse public board API | 1 | 0 | No |

The Deloitte record is relevant because its detail page includes a target
location. Nokia's records did not match the user's private location
preferences. Everstream's record is broadly US-remote and is intentionally not
treated as a target-location match by the current rules.

### Implementation Map

- `src/internship_search/career_collectors.py`: reusable Workday, Phenom,
  Greenhouse, Avature RSS, Oracle Recruiting, Paycor, Bank of America, Bayer,
  and closure-page collection behavior.
- `src/internship_search/source_registry.py`: official recruiting source URLs
  and collector selection for recovered companies.
- `src/internship_search/internship_listing.py`: specific internship URL
  classification, including Avature `/JobDetail/` paths.
- `src/internship_search/location_filter.py`: private target-location matching
  and flexible/multi-location handling.
- `src/internship_search/review_state.py` and `review_ui.py`: source status and
  internship counts shown on the Companies page.
- `tests/test_career_collectors.py`, `test_source_registry.py`,
  `test_internship_listing.py`, `test_location_filter.py`, and
  `test_review_ui.py`: regression coverage for the above.

### First Recommended Follow-up

Revisit RTX first. Its focused Phenom validation succeeded with 10 records, but
the latest full unattended workflow later recorded:

`RTX: phenom_api failed: HTTP Error 403: Forbidden`

Treat this as an intermittent upstream-access problem until reproduced. Check
whether the public campus bootstrap page or widget endpoint changed, and keep
the solution at the Phenom/platform level if possible. Do not add CAPTCHA
bypasses or require browser automation for scheduled runs.

After RTX, continue resolving the remaining companies marked `Source issue` in
the Companies page one at a time using the Decision Order above. The latest run
included issues for Zipline, Wellfound startup, Symbio, Profusa, Pottery Barn,
Novi Connect, Upside Foods, PowerBar, Meyer Sound, DYMO / Newell Brands,
Annie's Homegrown / General Mills, Acme Bread Company, Stellarus, PayPal,
Lemonade, Pixar, Levi's, Ripple, Farallon Capital Management, Goldman Sachs,
JPMorgan Chase, Morgan Stanley, Wiz, Northrop Grumman, RTX, and General
Dynamics. Re-run the source before assuming a recorded network error is still
current.

### Verification and Local App Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -c "from internship_search.cli import main; raise SystemExit(main(['run-scheduled-collection', '--skip-email']))"
powershell -ExecutionPolicy Bypass -File config\build_windows_app.ps1 -Clean
```

The executable is `app/Internship Search.exe`. It reads ignored local data from
`private/` and `data/`; rebuilding it must not embed or replace those files.
Before a clean rebuild, stop any running `Internship Search.exe` processes that
still lock the existing executable.

### Known Non-blocking Issue

Some older generated location summaries can display a mojibake ellipsis
(`â€¦`) rather than `…`. This was observed in existing rows during visual
verification and was not part of the source-recovery changes. Diagnose the
generated-data encoding path separately without changing private preferences.

## Acceptance Criteria

- RTX collection does not depend on the Cloudflare-blocked search-result HTML.
- The public Phenom result set is paged to completion.
- Records retain stable title, URL, location, and available eligibility text.
- Graduate-only opportunities are excluded by the existing eligibility stage.
- Failures remain visible in collection diagnostics and weekly email reporting.
- Unit tests and an RTX-only live validation pass.
- No private data, generated output, credentials, or local configuration is
  added to Git.

## Direction-Change Rule

When evidence invalidates the current approach, document the evidence, compare
the simplest compliant alternatives, update this task, and then continue. Do
not preserve an approach merely because implementation has already started.
