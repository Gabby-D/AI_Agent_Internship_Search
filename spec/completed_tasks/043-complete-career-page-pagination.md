# Completed Task: Complete Career-Page Pagination

Reworked direct company collection so internship postings are not limited to the first visible careers page.

## Behavior

- Follows same-site next-page, numbered-page, offset, job-index, and supported load-more links.
- Follows recognized external ATS boards linked from company careers pages.
- Scans BlackRock's unfiltered public jobs search across every result page, then
  identifies internship opportunities locally instead of relying on one keyword;
  repairs the site's JavaScript-dependent `&p=` pagination links before fetching.
- Uses McKinsey's public jobs API to retrieve every internship search result even
  when the JavaScript HTML shell times out.
- Reads complete public Greenhouse and Ashby boards.
- Pages through Lever, Workday, and Consider results until exhausted and
  recognizes complete public Teamtailor indexes.
- Opens named internship detail pages, skips programs that explicitly report
  closed applications, and merges all listed locations into the posting.
- Applies private location matching to every listed office, so a role is not
  excluded merely because its primary display location differs.
- Retains public qualification text and excludes graduate- or advanced-degree-only
  internships while keeping roles explicitly open to undergraduate applicants.
- Avoids crawling duplicate translated navigation trees on global career sites.
- Deduplicates pages and postings and caches shared pages during each run.
- Stops cyclic or unexpectedly large crawls at a 100-page safety limit and records a visible diagnostic.
- Falls back to HTML and structured-data extraction if an ATS API is unavailable.
- Keeps company inputs and all generated collection results in ignored local files.

## Verification

- Tests cover ordinary pagination, load-more attributes, cycles, trusted
  external boards, API result parsing, API pagination, semantic program details,
  open/closed status, multi-location roles, locale avoidance, shared-page
  caching, fallbacks, and safety-limit warnings.
- The full automated suite passed locally without committing or pushing the change.
