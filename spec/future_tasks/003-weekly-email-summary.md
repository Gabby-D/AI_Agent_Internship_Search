# Future Task: Weekly Email Summary

## Goal

Send a weekly email summary of relevant new internship postings.

## Requirements

- Include only new or high-priority postings by default.
- Group roles by company and fit level.
- Include title, location, link, deadline if available, and fit explanation.
- Highlight roles at companies where the user has a connection.
- Include a short "recommended next actions" section.
- Keep email credentials in `.env` or another ignored local secret store.

## Output

- A weekly email sent to the configured recipient.
- A copy of the generated summary saved in `data/`.
