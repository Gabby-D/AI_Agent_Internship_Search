# Completed Task 045: All-Company Search and Manual Run

Extended collection across the complete monitored-company registry and added an
on-demand search action to the local dashboard.

## Behavior

- Every run attempts all locally monitored company sources.
- Supported Greenhouse, Lever, Ashby, Workday, Phenom, Teamtailor, Breezy,
  Consider, McKinsey, BlackRock, and other structured public boards are paged
  until their published results are exhausted.
- Company-specific source metadata replaces stale public career URLs with
  current official pages where verified.
- Other career sites use bounded same-site pagination and record a source
  diagnostic when access is blocked or the layout cannot be read completely.
- Internship candidates are filtered locally for the user's private location,
  education-level, and other preferences.
- Graduate-only roles are excluded; roles that explicitly accept
  undergraduates remain eligible.
- The dashboard header includes **Run search now**. It starts the complete
  workflow in a background thread, prevents duplicate runs, reports progress
  and source issues, and refreshes results when finished.
- A manual dashboard run does not generate or send an email. Scheduled email
  behavior remains separate and unchanged.
- Private inputs and generated results remain in ignored local paths.

## Verification

- Unit and integration tests cover exhaustive public-board pagination,
  source-aware fallbacks, stale URL replacements, direct-job sources,
  undergraduate filtering, and the manual search controller and UI.
- A live all-company run was performed without sending email or pushing Git.
