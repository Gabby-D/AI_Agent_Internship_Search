# Review UI Redesign

## Goal

Redesign the local review dashboard so it looks and feels like a modern, minimal web app organized by top-level tabs, while keeping all current editing capabilities (postings, companies, preferences, reference files, activity log) and fixing the plain, sparse layout in the current version.

## Why this matters

The dashboard is functionally complete today (editable inputs, opportunity statuses, a live company list, verified career links, and a dated activity log), but its single scrolling page of stacked collapsed sections and plain HTML tables looks dated and is hard to scan. A modern layout will make daily review faster and more pleasant to use.

## Confirmed requirements

### Navigation

- Replace the single scrolling page with top-level tabs: **Postings**, **Companies**, **Preferences**, **Reference Files**, **Activity Log**.
- Switching tabs should not require a full page reload beyond the initial load (client-side tab switching against the already-loaded dashboard data is acceptable).

### Visual style

- Modern, minimal aesthetic: generous whitespace, a restrained color palette, and clean card-based groupings instead of plain HTML tables with default browser borders.
- Keep the app self-describing: the location policy banner ("Showing Bay Area, Israel, and fully remote internships only...") must remain visible from the Postings tab.

### Postings tab

- Keep the existing grouping by review status: **To review**, **Applied**, **Not interested**, **Archived**.
- Row/card fields: job title, company, location, "Open posting" link, review-status control, and a clear visual indicator for whether I know someone at the company (yes/no).
- Do not add score, fit level, explanations, or gaps to the main view (keep it minimal). These may remain available as optional expandable detail if convenient, but are not required.
- Keep the existing 30-second auto-refresh behavior (already paused while a text field is focused).

### Companies tab

- Editable table of all monitored companies: name, career/jobs page URL, and "I know someone" toggle.
- Support adding new companies, removing companies, and editing the industries-of-interest list.
- Saving must update `private/list_of_companies.md` and rebuild the local source registry, exactly as today.

### Preferences tab

- Editable "Things I like" / "Things I don't like" lists, saved to `private/preferences.md`.

### Reference Files tab

- Editable raw text for `mcgill_class_list.md`, `connections.md`, and `resume_summary.md`, with the same validation rules as today (course-list content must still parse before saving).

### Activity Log tab

- Read-only, reverse-chronological view of `data/activity_log.jsonl` (dated entries), replacing the current collapsed `<details>` element with a clearer list/table appropriate to the new visual style.

### Technical approach

- Must remain a Python project. Mainstream Python packages/frameworks are allowed (not limited to the stdlib-only `http.server` approach used today) if they meaningfully improve the result.
- No required Node.js/npm build step; if a CSS framework is used, prefer a CDN-hosted stylesheet or a small vendored CSS file over a JS build pipeline.
- All existing local-only behavior must be preserved: runs on `127.0.0.1`, no external services, no telemetry.

## Open decisions for implementation planning

- Final choice of Python web stack (e.g., staying with `http.server` plus a CSS framework via CDN, or moving to a mainstream framework such as FastAPI, Flask, NiceGUI, or Streamlit). Choose during implementation planning based on how well each supports tabs, inline editing, and the modern-minimal look without a build step.
- Whether "Open posting" links and company career links get a lightweight visual distinction (e.g., an icon) beyond plain link styling.

## Acceptance checks

- All five tabs are reachable and functionally equivalent to today's sections.
- Opportunity statuses remain: To review, Applied, Not interested, Archived.
- Company list, preference, and reference-file edits persist to the same private files as before.
- `data/activity_log.jsonl` continues to receive dated entries for edits and status changes.
- "Open posting" links continue to resolve to real, normalized career-page URLs.
- Full test suite passes (`uv run pytest`).

## Notes

- Follow the existing private-data conventions in `.gitignore`; no new tracked files should contain personal data.
- Start implementation in Plan mode since this involves a UI/framework decision, per the guidance in `spec/future_tasks/README.md`.
