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
- A reusable Oracle collector requests up to 100 records at a time, advances offsets
  until the API's total is reached, and filters internship/co-op titles
  locally.
- Live validation paged all 219 keyword matches, identified 17 internship or
  co-op records for downstream filtering, and reported no source error.

### Everstream Analytics

- Everstream's official careers page identifies its public Greenhouse board.
- Source configuration now uses that board directly with the existing
  complete Greenhouse collector.
- Live validation found one current internship record and no source error.

### Goldman Sachs

- Source configuration now uses Goldman Sachs' official Higher campus-role
  service instead of the informational programs index.
- A reusable GraphQL collector requests every `CAMPUS` result page, retains
  exact role IDs and locations, and filters internship and summer-analyst
  titles locally.
- Live validation paged 153 current campus roles, identified 29 internship
  records for downstream preference filtering, and reported no source error.

### JPMorgan Chase

- Source configuration now uses the official Oracle Recruiting career site
  (`CX_1001`) linked from JPMorgan Chase's student careers experience.
- The Oracle collector can derive the public API host and site number directly
  from an Oracle career URL, pages the full result count in batches of up to
  100, and builds stable official role links.
- Live validation identified 91 internship or summer-analyst records for
  downstream preference filtering and reported no source error.

### Lemonade

- The former general corporate URL was replaced with Lemonade's current
  official Makers careers site.
- A reusable Next.js collector reads the site's complete structured
  `allRecipes` role list rather than relying on visible first-page links.
- Live validation found no current internship titles and no source error.

### Pixar

- Pixar recruiting is handled through Disney Careers. The configured source
  now uses Disney's working Pixar keyword route instead of an ignored query
  parameter.
- A reusable collector follows the site's explicit total-page count, keeps
  only rows branded `Pixar Animation Studios`, and then filters internship
  titles locally.
- Live validation searched every current Pixar result page, found no current
  Pixar internship titles, and reported no source error.

### Classification Regression Fixed

- `Research Intern` was incorrectly matching the generic navigation fragment
  `search intern`. Generic search-page detection now requires that phrase to
  begin the title, preserving legitimate research internship listings.

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

## Requested Company Batch (2026-07-27)

Fourteen unambiguous companies were added to the ignored private company list:
Rafael, Wix, Cloudflare, Elbit Systems, Dell, HP, IBM, Intel, Oracle, Osem,
The Coca-Cola Company, SodaStream, CyberArk, and Toyota. The requested name
`Lbit` was not added because it could not be distinguished safely from the
separately requested Elbit Systems without a website or full legal name.

### Live Collection Result

The focused scan collected 72 unique current internship/student candidates
after company attribution and duplicate cleanup:

| Company | Candidates | Collection status |
| --- | ---: | --- |
| Cloudflare | 9 | Complete Greenhouse board |
| Dell | 5 | Complete Oracle Recruiting board |
| HP | 20 | Complete Eightfold searches |
| Intel | 19 | Complete Workday board |
| Oracle | 14 | Complete Oracle Recruiting board |
| Osem | 4 | Complete Israel SuccessFactors search |
| SodaStream | 1 | Complete PepsiCo Jibe search, restricted to SodaStream-labelled roles |
| CyberArk | 0 | Complete parent Workday board; no CyberArk-labelled internships |
| Toyota | 0 | Complete Phenom search returned no internship-title matches |
| Rafael | 0 | Source issue: official portal returned HTTP 491 |
| Wix | 0 | Source issue: JavaScript-only layout is not yet supported |
| Elbit Systems | 0 | Source issue: current layout is not yet supported |
| IBM | 0 | Source issue: current dynamic careers layout is not yet supported |
| The Coca-Cola Company | 0 | Source issue: official careers request timed out |

Downstream private filters retained two target-location candidates: an Intel
non-technical student project-management role in Haifa and an Oracle
data-strategy internship in Redwood City. Both scored below the dashboard's
recommendation threshold, so they remain recorded but are not promoted as
recommendations. Cloudflare's San Francisco social-media internship and HP's
San Francisco software-engineering internship were correctly excluded by
explicit private role dislikes.

### Reusable Implementation

- Greenhouse collection now prefers explicit `Job Posting Location` metadata
  over generic labels such as `In-Office`.
- A bounded Jibe API collector pages official parent-company search results
  and retains only roles explicitly labelled for the requested company.
- Standard SuccessFactors HTML pagination is reusable outside Bayer, and
  Hebrew student titles are recognized as internship-equivalent listings.
- Parent-company Workday collection can retain only CyberArk-labelled roles,
  avoiding the false attribution of all Palo Alto Networks internships.
- Configured company-source names remain authoritative when a title contains
  wording such as `Internship at ...`.
- The location filter no longer mistakes San Jose, Costa Rica for the Bay Area.

### Continuation Point

Resolve the four dynamic/blocked sources one at a time using the Decision Order
above, beginning with Wix or Elbit Systems. Rafael needs a user-confirmed
working official URL or confirmation that the official portal opens normally
on the same laptop/network. Do not treat these source issues as verified zero
openings. No email was sent and no Git push was performed in this batch.

### Dashboard Visibility Follow-up

The review dashboard no longer discards otherwise valid matches solely because
their fit score is below 60. Unreviewed lower-scoring roles appear in a
separate **Other Matching Internships** section. Review status takes priority:
an applied lower-scoring role remains in **Applied**, and dismissed or archived
roles remain in their respective sections. Hard location, undergraduate, and
explicit-dislike exclusions still apply before any role reaches the dashboard.

### Dashboard Logon Startup Follow-up (2026-07-30)

The local dashboard now has a dedicated Windows logon task, separate from the
daily search and weekly email tasks. `config/run_dashboard.ps1` starts the
windowless executable without opening a browser, remains attached to the
process, restarts it after ten seconds when it exits, and monitors an already
healthy instance instead of starting a duplicate. The registration script also
configures unlimited execution time, `IgnoreNew` multiple-instance behavior,
battery operation, and three one-minute Task Scheduler restart attempts as a
fallback. Automation verification now reports both the task state and the
local HTTP health check.

## Handoff Update (2026-07-27)

The next source-recovery batch is implemented locally but has not been pushed
to Git. It covers Clif Bar and Company, Deloitte, Goldman Sachs, JPMorgan
Chase, Lemonade, and Pixar.

### Verified Results

| Company | Official complete source | Internship candidates | Pass current private filters | Source issue |
| --- | --- | ---: | ---: | --- |
| Clif Bar and Company | Parent-company Workday search | 0 | 0 | No |
| Deloitte | Avature filtered RSS plus details | 2 | 2 | No |
| Goldman Sachs | Higher campus GraphQL API | 29 | 0 | No |
| JPMorgan Chase | Oracle Recruiting `CX_1001` API | 91 | 0 | No |
| Lemonade | Makers Next.js structured role list | 0 | 0 | No |
| Pixar | Paginated Disney Careers Pixar results | 0 | 0 | No |

The candidate counts are current-source results before private location,
undergraduate, and preference filtering. The full unattended workflow
registered 116 sources, collected 378 candidates, retained 18, and recorded 23
remaining source-error entries after removing Clif Bar's obsolete fallback
page. Email generation and sending were explicitly skipped.

### Verification State

- Full package suite: `279 passed`.
- Rebuilt executable:
  `app/Internship Search.exe`.
- The rebuilt executable is running at `http://127.0.0.1:8765/`.
- The local dashboard API returns HTTP 200, 18 filtered postings, successful
  scan results for all six companies, and no source issue for any of them.
- Generated output and private inputs remain local and Git-ignored.

### Implementation Added in This Batch

- `goldman_higher`: complete Goldman Sachs campus-role GraphQL pagination.
- Oracle Recruiting URL-derived host/site support and batches of up to 100,
  used by JPMorgan Chase as well as existing Oracle sources.
- `lemonade_jobs`: complete structured `allRecipes` extraction.
- `pixar_jobs`: explicit Disney page-count pagination plus exact Pixar brand
  filtering.
- A specific-listing regression fix for legitimate `Research Intern` titles.
- Clif Bar's obsolete informational alternate URL was removed because the
  complete Workday source succeeds and the fallback generated a false 403
  warning.

### Continuation Point

If continuing source recovery, choose the next company still marked
`Source issue` in the Companies page. Do not redo the six companies in this
batch unless their official source changes or a future scan records a new
failure. Before pushing, review the diff, run the full tests, and confirm no
private or generated files are staged.

### Farallon, General Dynamics, Meyer Sound, and Morgan Stanley (2026-07-27)

This recovery batch is implemented and live-validated locally. It has not been
pushed to Git.

| Company | Official complete source | Internship candidates | Source issue |
| --- | --- | ---: | --- |
| Farallon Capital Management | Greenhouse public board API | 0 | No |
| General Dynamics | Aggregate GD careers API | 10 | No |
| Meyer Sound | ADP Workforce Now public API | 0 | No |
| Morgan Stanley | Eightfold PCSX public search/detail APIs | 5 | No |

These are current-source candidate counts before the existing private
location, undergraduate, and preference filters. General Dynamics currently
returns one graduate internship among its ten candidates; the existing
graduate-only eligibility stage excludes that role from user-facing results.

Implementation details:

- Farallon now uses the official Greenhouse board linked from its corporate
  site.
- Meyer Sound now pages the official ADP Workforce Now requisitions endpoint.
  Its two current jobs are non-internships, so zero is a verified healthy
  result.
- Morgan Stanley searches and merges every page for `intern`, `summer analyst`,
  `summer associate`, and `co-op`, then loads job details for retained records.
- General Dynamics uses the official aggregate API. The required short-lived
  token and cookies must come from the same public careers-page session. The
  standard `curl` executable is used to preserve that session because the site
  rejects Python's direct HTTP fingerprint with 403 even when all headers and
  cookies are otherwise correct. No browser automation or stored token is
  required for scheduled scans.

Verification:

- Focused collector and registry tests pass.
- Full package suite: `283 passed`.
- All four live collectors completed without a source warning.
- No email was sent and no Git push was performed during this batch.

### Recommendation Relevance Repair (2026-07-27)

Recommendation relevance is now enforced at two deterministic boundaries:

- A specific role whose title clearly matches an explicit private dislike is
  excluded during posting filtering. Common singular, plural, and occupational
  word forms are normalized, and multiword dislikes require at least two
  meaningful matching terms.
- The webpage and weekly email show only scored roles at or above the minimum
  recommendation score (`60`) and never show a role whose scorer labels it
  weak.

The scoring stage repeats the explicit-dislike guard so a stale filtered file
cannot send a conflicting role to the AI scorer or weekly email. The dashboard
also applies the guard dynamically so edits to the private preference file take
effect before the next complete scheduled run.

Private preference contents remain only in ignored local files. Tracked tests
use synthetic examples and cover single-word variants, multiword conflicts,
unrelated-role preservation, stale-score protection, email selection, and
dashboard hiding. No email is sent and no Git push is performed as part of
this repair.

### Scheduler Reliability Repair (2026-07-27)

- Windows power events show that the laptop was asleep at the Monday 10:00 AM
  email time and resumed at 10:27 AM.
- The missed discovery, collection, and email tasks then started together and
  were externally interrupted with status `0xC000013A`; the email wrapper did
  not start far enough to create its normal log.
- All three tasks are now registered with wake, catch-up, battery-safe
  execution, three retries at five-minute intervals, and `IgnoreNew` instance
  handling.
- All three wrapper scripts use one named local mutex, preventing simultaneous
  automation from racing over generated files after a wake-up.
- The weekly email wrapper now runs a fresh full collection with job boards
  and sends the email only after that workflow completes.
- Windows accepted and reports the intended settings for all three registered
  tasks.
- A current weekly email was sent successfully after the repair. Its local
  summary reported 13 new internships and 23 job-site problems; sent history
  was updated only after SMTP success.

### Scheduler Interruption Follow-up (2026-08-03)

- The laptop slept through the Monday 10:00 AM target and resumed at 11:43 AM.
  Windows started catch-up automation, then terminated all four internship
  tasks with `0xC000013A` before the weekly wrapper reached SMTP delivery.
- The weekly task now has a daily 10:00 AM recovery trigger. The wrapper sends
  at most once per Monday-based week and records success in the ignored local
  `data/weekly_email_task_state.json` file only after the send command exits
  successfully.
- If Monday is missed or interrupted, the next available daily trigger retries
  automatically. A successful week is skipped on later days, preventing normal
  duplicate summaries.
- A requested SMTP send that does not produce `email_sent=True` now returns a
  non-zero command result, allowing Task Scheduler retries instead of falsely
  recording success.
- All automation PowerShell actions are hidden and use `-NoProfile`, so these
  recovery checks do not open terminal windows or depend on profile scripts.

### Weekly Email Readability Repair (2026-08-03)

- Gemini quota failures previously placed the full HTTP 429 response payload
  inside a fallback score explanation, which exposed JSON and retry metadata in
  the plain-text weekly email.
- Fallback scoring now stores only a short human status message; provider error
  details are not treated as recommendation rationale.
- Email rendering independently filters legacy provider diagnostics, collapses
  whitespace, and limits each fit explanation to two sentences and 280
  characters. This protects emails generated from older scored records too.
- Recommendation labels now read `Why it may fit` and `Apply`, and multi-office
  postings use the existing allowed-location summary instead of listing every
  office.

### Northrop Grumman, Novi, PayPal, PowerBar, and Profusa (2026-07-27)

| Company | Complete source | Current internship candidates | Source issue |
|---|---|---:|---|
| Northrop Grumman | Eightfold PCSX public search/detail APIs | 1 | No |
| Novi Connect | Public Notion page API | 0 | No |
| PayPal | Eightfold PCSX public search/detail APIs | 0 | No |
| PowerBar | Premier Nutrition Paycor board | 0 | No |
| Profusa | Current official static careers page | 0 | No |

These counts precede the existing location, undergraduate, and explicit
preference filters. Northrop Grumman's current candidate is a software
engineering internship in Melbourne, Florida, so it is collected for source
completeness but excluded from recommendations by the user's local filters.

Implementation details:

- The reusable Eightfold collector now reads the tenant domain from source
  configuration rather than assuming one company. Northrop Grumman, PayPal,
  and Morgan Stanley therefore share the same paginated implementation.
- Novi's corporate careers page links to a public Notion page. The reusable
  Notion collector pages the anonymous public page API and inspects every
  direct child role page; Novi's current roles are not internships.
- PowerBar is monitored through the complete Paycor board linked by Premier
  Nutrition. Its current openings are not internships.
- Profusa's obsolete careers URL was replaced with its current official page.
  A successful semantic page check with no role links is a verified healthy
  zero-opening result.

Verification:

- Focused collector and registry suite: `55 passed`.
- Live scans completed for all five companies without a source warning.
- Dashboard data was refreshed after the live scans.
- No email was sent and no Git push was performed during this batch.

### Stellarus, Symbio, Wiz, and Zipline (2026-07-27)

| Company | Complete source | Current internship candidates | Source issue |
|---|---|---:|---|
| Stellarus | Oracle Recruiting public API | 0 | No |
| Symbio | Verified former-domain parking redirect | 0 | No |
| Wiz | Greenhouse public board API | 0 | No |
| Zipline | Greenhouse public board API | 21 | No |

These are source-complete counts before local preference filtering. Zipline's
21 current Fall 2026 internships include nine Bay Area titles that pass the
deterministic location and explicit-title-dislike filters. Local scoring gives
all nine a score below the webpage and email recommendation threshold, so none
is currently presented as a recommendation.

Implementation details:

- Stellarus's stale Google share link was resolved to the intended healthcare
  company. Its official careers page links to an Oracle Recruiting board, which
  is now paged through the existing reusable Oracle collector.
- The former Symbio Robotics domain currently redirects to a parking page. A
  dedicated collector verifies that exact state and treats it as a complete
  zero-opening result; any future change causes a visible source diagnostic
  instead of silently assuming the company remains inactive.
- Wiz's official careers page embeds the `wizinc` Greenhouse board. The complete
  public board currently has no specific internship listing.
- Zipline now uses its `flyzipline` Greenhouse board directly, returning the
  full public result set rather than relying on the first rendered careers page.

Verification:

- Focused collector and registry suite: `56 passed`.
- Live scans completed for all four companies without a source warning.
- Dashboard data was refreshed after applying private local filters.
- No email was sent and no Git push was performed during this batch.

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
