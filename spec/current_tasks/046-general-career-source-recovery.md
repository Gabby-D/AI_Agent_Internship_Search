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
