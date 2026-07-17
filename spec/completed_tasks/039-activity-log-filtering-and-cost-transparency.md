# Activity Log Filtering and Cost Transparency

## Goal

Make the activity log useful for reviewing actions, dates, API use, and any associated cost.

## Requirements

- Show a clear activity type for every activity-log entry, using readable labels such as posting status, note edit, company edit, file upload, collection, scoring, or email.
- Add client-side filters for date or date range and activity type without requiring a full page reload.
- Extend activity metadata to record whether the activity invoked an external API or paid service.
- When a cost is known, display the currency, amount, and basis (for example, an API request or email provider charge).
- When cost is unavailable or not applicable, say so explicitly rather than estimating.
- Preserve existing dated entries and handle legacy entries that lack new metadata.

## Privacy and accuracy

- Do not expose API keys, request payloads, personal notes, or resume contents in the log.
- Record only attributable costs from provider responses or configured rates; do not invent cost estimates.

## Acceptance checks

- Users can filter activity by date and type.
- Entries consistently state API usage and known cost status.
- Legacy entries remain readable.
- Tests cover filtering, metadata normalization, and cost-display behavior.
