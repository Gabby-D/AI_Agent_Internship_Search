# Future Task 044: Company List Search

Add a search field to the Companies page so users can quickly confirm whether a
company is already in their monitored-company list.

## Scope

- Place the search field next to the **Add Company** button.
- Filter the displayed company list as the user types.
- Match company names case-insensitively and allow partial-name matches.
- Show all companies again when the search field is cleared.
- Display a clear empty-state message when no company matches.
- Keep searching read-only; it must not add, remove, or edit company data.

## Acceptance Criteria

1. A search field is visible beside **Add Company** on the Companies page.
2. Entering all or part of a company name immediately shows matching companies.
3. Matching does not depend on capitalization.
4. Clearing the field restores the complete company list.
5. A user can clearly distinguish "no match" from an empty company registry.
6. Existing add, edit, save, and delete behavior continues to work.
7. UI tests cover matching, no-match, clearing, and interaction with the existing
   company controls.

## Timing

Implement only after the current career-page collection work is finished.
