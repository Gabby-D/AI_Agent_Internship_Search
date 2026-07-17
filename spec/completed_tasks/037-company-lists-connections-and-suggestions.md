# Company Lists, Connections, and Suggestions

## Goal

Make the Companies tab easier to manage while clearly separating user-entered companies from recommendations.

## Requirements

- Move **Industries of interest** above the company lists and make it collapsible.
- Move the **Add company** control to the top of the user-entered company list.
- Present two distinct lists:
  - **My companies**: companies entered by the user in `private/list_of_companies.md`.
  - **Suggested companies**: recommendations derived from the user’s industries and saved companies, sourced from the existing discovery workflow where available.
- Make suggestion provenance clear and provide controls to add a suggestion to **My companies** or dismiss it without altering private inputs unintentionally.
- When **Know someone** is enabled for a user-entered company, provide a private field to record the person or people known there.
- Preserve existing `yes`/`no` connection compatibility and migrate the private company-input format without losing current entries.
- Add an expandable company overview in the Postings tab for internships from suggested companies. The overview should identify the company and explain why it was suggested without obscuring the internship details.

## Data and privacy

- Keep user-entered company and connection-person data in Git-ignored private files.
- Keep generated recommendations and dismissals in Git-ignored `data/` files.
- Do not send personal connection names to external services.

## Acceptance checks

- User-entered and suggested companies are visibly separate.
- Industries and Add company controls appear at the top of the Companies tab.
- Connection names persist locally and are editable.
- A suggested-company posting exposes a concise company overview.
- Existing company input files continue to load correctly.
