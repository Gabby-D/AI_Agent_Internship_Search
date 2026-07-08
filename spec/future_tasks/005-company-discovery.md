# Future Task: Similar Company Discovery

## Goal

Use AI or structured research to discover companies similar to the user's target companies and industries of interest.

The user-provided company list is a seed list only. This task should intentionally broaden the search beyond those companies.

## Inputs

- Existing company list.
- Industries of interest, including finance, aerospace and defense, operations, and geopolitics.
- Preferences for Bay Area and Israel roles.

## Requirements

- Use the modular internet search provider when it is available.
- Suggest similar companies with a short reason for each.
- Find official websites and careers pages.
- Mark whether each company should be added to the source registry.
- Label discovered companies separately from original seed companies.
- Include companies related to the user's industries of interest, even when they are not direct competitors of the seed companies.
- Avoid adding companies that mainly match disliked work areas.

## Output

- A reviewable list of suggested companies before they are added to active collection.
- Approved discovered companies should be added to the source registry for future collection runs.

## Depends On

- `007-internet-search-provider.md` for searching the web from the Python app.
