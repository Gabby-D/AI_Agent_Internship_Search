# Review UI Redesign

## Completed outcome

The local review dashboard now uses a modern, minimal tabbed interface while retaining its local-only Python server and all editing workflows.

## Delivered behavior

- Client-side tabs for Postings, Companies, Preferences, Reference Files, and Activity Log.
- Card-based layout, connection badges, normalized external posting links, and the visible location-policy banner.
- Editable company list, industries, preferences, and supported private reference files.
- Review statuses: To review, Applied, Not interested, and Archived.
- Dated activity entries presented newest first.
- Existing 30-second refresh behavior, paused while text input is active.

## Verification

- The existing UI tests cover tab structure, all status labels, editable endpoints, company connection indicators, and activity-log behavior.
- The full test suite passes with `uv run pytest`.
