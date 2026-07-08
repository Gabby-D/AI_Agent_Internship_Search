# Task: Filter Summer 2027 Internship Postings

## Goal

Filter collected postings to find roles that are likely relevant for Summer 2027 internships.

## Requirements

- Include postings that mention internship, intern, co-op, analyst intern, summer analyst, or similar early-career terms.
- Prefer postings that mention Summer 2027 or 2027 explicitly.
- Keep potentially relevant postings when the season is unclear but the role is an internship.
- Exclude roles that clearly match dislikes, especially social media management and marketing.
- Prefer Bay Area, Israel, remote, finance-related, aerospace and defense, operations, analytics, and geopolitics-related roles.
- Preserve the reason a posting was included or excluded.

## Output

- A filtered results file in `data/`, such as `data/filtered_postings.jsonl`.

## Acceptance Criteria

- Each filtered posting has an inclusion reason.
- Excluded postings can be reviewed later with an exclusion reason.
- Filtering rules are easy to update as preferences change.
